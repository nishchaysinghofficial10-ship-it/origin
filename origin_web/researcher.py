"""Networked, paid general-research worker for the interactive beta.

Only this process receives the Anthropic secret and outbound network access.
The computational worker remains ``network_mode: none`` and cannot read this
secret.  No provider response is executed locally.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import time
from pathlib import Path
from typing import Callable

from .config import WebConfig
from .general_research import (
    AnthropicResearchClient,
    GeneralResearchConfigError,
    ProviderResearchError,
    ResearchResult,
    TopicRejected,
    read_api_key,
)
from .store import QuotaExceeded, Store
from .worker import WorkerError, WorkerLease, worker_lease_healthy


ClientFactory = Callable[[WebConfig, str], AnthropicResearchClient]


def _client(config: WebConfig, key: str) -> AnthropicResearchClient:
    return AnthropicResearchClient(
        key,
        model=config.research_model,
        max_output_tokens=config.research_max_output_tokens,
        max_searches=config.web_searches_per_mission,
        timeout_s=config.research_timeout_s,
        max_continuations=config.provider_calls_per_mission - 1,
    )


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Researcher:
    def __init__(self, config: WebConfig, store: Store | None = None, *,
                 client_factory: ClientFactory = _client):
        self.config = config
        self.store = store or Store(config.db_path)
        self.client_factory = client_factory
        self.researcher_id = (
            f"researcher:{platform.node()}:{os.getpid()}:{int(time.time())}")

    def _mission_dir(self, mission_id: str) -> Path:
        if not (mission_id.startswith("msn_") and len(mission_id) == 20 and
                all(character in "0123456789abcdef" for character in mission_id[4:])):
            raise WorkerError("invalid mission identifier in durable queue")
        path = (self.config.runs_dir / mission_id).resolve()
        if self.config.runs_dir.resolve() not in path.parents:
            raise WorkerError("mission path escaped the configured run directory")
        return path

    def _control_after_provider(self, mission: dict) -> bool:
        control = self.store.worker_control(mission["id"])
        if control == "cancel_requested":
            self.store.finish(
                mission["id"], "cancelled",
                stop_reason="cancelled after the bounded provider request completed")
            self.store.audit(
                mission["owner_hash"], "researcher_cancel", "cancelled",
                mission["id"], "provider request could not be interrupted mid-flight")
            return True
        if control == "pause_requested":
            self.store.audit(
                mission["owner_hash"], "researcher_pause",
                "completed_before_pause", mission["id"],
                "the single bounded provider turn had already completed")
            return False
        return False

    def _save(self, mission: dict, result: ResearchResult) -> None:
        mission_dir = self._mission_dir(mission["id"])
        metadata = result.metadata()
        metadata.update({
            "mission_id": mission["id"],
            "generated_at": time.time(),
            "workflow": "general_public_web_research",
            "experimental_evidence": False,
        })
        _atomic_write(mission_dir / "reports" / "dossier.md", result.dossier)
        _atomic_write(
            mission_dir / "research-metadata.json",
            json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    def process(self, mission: dict, api_key: str) -> None:
        mission_id = mission["id"]
        result: ResearchResult | None = None
        try:
            if mission.get("domain") != "general" or mission.get("profile") != "web_research":
                raise WorkerError("general researcher received an unsupported mission")
            self.store.reserve_provider_mission(
                mission_id, self.config.research_model,
                self.config.provider_missions_per_day)
            self.store.update_general_progress(
                mission_id, step=1, phase="planning_and_web_research",
                stop_reason="Searching and synthesizing bounded public-web evidence")
            client = self.client_factory(self.config, api_key)
            if isinstance(client, AnthropicResearchClient):
                client.on_request = lambda: self.store.charge_provider_attempt(
                    mission_id, self.config.provider_calls_per_mission)
            result = client.research(mission["question"])
            self.store.finish_provider_usage(
                mission_id, status="completed",
                provider_calls=result.provider_calls,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                web_searches=result.web_searches)
            self.store.update_general_progress(
                mission_id, step=7, phase="finalizing_cited_dossier",
                stop_reason="Cited synthesis complete; not experimental proof",
                provider_calls=result.provider_calls,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                web_searches=result.web_searches)
            if self._control_after_provider(mission):
                return
            self._save(mission, result)
            self.store.finish(
                mission_id, "completed",
                stop_reason="cited public-web synthesis completed within paid limits")
            self.store.audit(
                mission["owner_hash"], "researcher_finish", "completed",
                mission_id,
                f"calls={result.provider_calls};searches={result.web_searches};"
                f"input_tokens={result.input_tokens};output_tokens={result.output_tokens}")
        except QuotaExceeded as exc:
            try:
                self.store.finish_provider_usage(mission_id, status="failed")
            except Exception:
                pass
            self.store.finish(
                mission_id, "failed", error=str(exc),
                stop_reason="operator paid-research budget protected")
            self.store.audit(
                mission["owner_hash"], "researcher_finish", "quota_rejected",
                mission_id, "global paid mission cap reached")
        except TopicRejected as exc:
            # The API applies the same policy before enqueueing.  Rechecking in
            # the secret-bearing process protects against database tampering.
            self.store.finish(
                mission_id, "failed", error=str(exc),
                stop_reason="topic rejected by the general research safety policy")
            self.store.audit(
                mission["owner_hash"], "researcher_finish", "topic_rejected",
                mission_id, f"category={exc.category}")
        except ProviderResearchError as exc:
            try:
                self.store.finish_provider_usage(
                    mission_id, status="failed",
                    provider_calls=(result.provider_calls if result else 0),
                    input_tokens=(result.input_tokens if result else 0),
                    output_tokens=(result.output_tokens if result else 0),
                    web_searches=(result.web_searches if result else 0))
            except Exception:
                pass
            public_errors = {
                "authentication": "research provider authentication failed; operator action required",
                "credit_or_rate_limit": "research provider credit or rate limit reached; try later",
                "provider_unavailable": "research provider is temporarily unavailable; try later",
                "ungrounded_response": "research provider returned no usable citations",
            }
            detail = public_errors.get(exc.category, "research provider returned an unusable response")
            self.store.finish(
                mission_id, "failed", error=detail,
                stop_reason="general research provider failure")
            self.store.audit(
                mission["owner_hash"], "researcher_finish", "provider_failed",
                mission_id, f"category={exc.category}")
        except Exception as exc:  # Never persist request objects or credential text.
            detail = f"{type(exc).__name__}: general researcher failed"[:500]
            self.store.finish(
                mission_id, "failed", error=detail,
                stop_reason="general research worker failure")
            self.store.audit(
                mission["owner_hash"], "researcher_finish", "failed",
                mission_id, detail)

    def run(self, api_key: str, *, once: bool = False) -> int:
        for mission in self.store.pending_control(
                "cancel_requested", domains=("general",)):
            self.store.finish(
                mission["id"], "cancelled",
                stop_reason="cancel request recovered before paid research started")
            self.store.audit(
                mission["owner_hash"], "researcher_cancel", "cancelled",
                mission["id"], "recovered before provider request")
        for mission in self.store.pending_control(
                "pause_requested", domains=("general",)):
            self.store.worker_pause(mission["id"])
            self.store.audit(
                mission["owner_hash"], "researcher_pause", "paused",
                mission["id"], "recovered before provider request")
        recovered = self.store.recover_running(
            "research service restarted", domains=("general",))
        if recovered:
            print(f"Recovered {recovered} interrupted mission(s) into the queue.")
        while True:
            mission = self.store.claim_next(
                self.researcher_id, domains=("general",))
            if mission is None:
                if once:
                    return 0
                time.sleep(self.config.worker_poll_s)
                continue
            print(f"Processing {mission['id']} (general/web_research)")
            self.process(mission, api_key)
            if once:
                return 0


def run_researcher(config: WebConfig | None = None, *, once: bool = False,
                   client_factory: ClientFactory = _client) -> int:
    config = config or WebConfig.from_env(require_tokens=False)
    if not config.general_research_enabled:
        raise GeneralResearchConfigError("general research is not enabled")
    if config.anthropic_key_file is None:
        raise GeneralResearchConfigError("ORIGIN_ANTHROPIC_KEY_FILE is not configured")
    api_key = read_api_key(config.anthropic_key_file)
    config.prepare()
    store = Store(config.db_path)
    researcher = Researcher(config, store, client_factory=client_factory)
    try:
        with WorkerLease(config.data_dir / "researcher.lock"):
            return researcher.run(api_key, once=once)
    finally:
        # Remove the last in-scope reference before the process exits.  Python
        # cannot guarantee memory zeroization, but the value is never persisted.
        api_key = ""
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--health-check", action="store_true")
    args = parser.parse_args(argv)
    if args.once and args.health_check:
        parser.error("--once and --health-check are mutually exclusive")
    try:
        config = WebConfig.from_env(require_tokens=False)
        if args.health_check:
            return (0 if worker_lease_healthy(
                config.data_dir / "researcher.lock") else 1)
        return run_researcher(config, once=args.once)
    except (GeneralResearchConfigError, WorkerError) as exc:
        print(f"RESEARCHER ERROR: {exc}", file=os.sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
