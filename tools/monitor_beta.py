#!/usr/bin/env python3
"""Run a credential-safe health check for an ORIGIN interactive beta."""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import stat
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit


MAX_RESPONSE = 1_000_000
LEASE_ERROR = re.compile(
    r"Traceback \(most recent call last\)|"
    r"worker lease[^\n]*(?:error|failed|unavailable)|"
    r"worker health check failed", re.IGNORECASE)


class MonitorError(RuntimeError):
    pass


def _origin(value: str, *, allow_http_local: bool = False) -> str:
    value = value.strip().rstrip("/")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise MonitorError("invalid API origin") from exc
    local = parsed.hostname in ("127.0.0.1", "localhost", "::1")
    schemes = {"https", "http"} if allow_http_local else {"https"}
    if (not parsed.hostname or parsed.username or parsed.password or parsed.path or
            parsed.query or parsed.fragment or parsed.scheme not in schemes or
            (parsed.scheme == "http" and not local) or
            (port is not None and not 1 <= port <= 65_535)):
        raise MonitorError("API origin must use HTTPS (HTTP is test-loopback only)")
    return value


def _token(path: Path) -> str:
    path = Path(path)
    token = path.read_text(encoding="utf-8").strip()
    if len(token) < 24:
        raise MonitorError("administrator credential file is missing or too short")
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise MonitorError("administrator credential file must not be group/world accessible")
    return token


def _request_json(api_origin: str, path: str, *, token: str = "") -> dict[str, Any]:
    headers = {"User-Agent": "ORIGIN-beta-monitor/1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(api_origin + path, headers=headers)
    try:
        response = urllib.request.urlopen(
            request, timeout=15, context=ssl.create_default_context())
    except urllib.error.HTTPError as exc:
        raise MonitorError(f"{path} returned HTTP {exc.code}") from exc
    try:
        body = response.read(MAX_RESPONSE + 1)
        if len(body) > MAX_RESPONSE:
            raise MonitorError(f"{path} exceeded the response limit")
        if response.status != 200:
            raise MonitorError(f"{path} returned HTTP {response.status}")
        value = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MonitorError(f"{path} did not return valid JSON") from exc
    finally:
        response.close()
    if not isinstance(value, dict):
        raise MonitorError(f"{path} did not return a JSON object")
    return value


def assess_remote(public: dict[str, Any], admin: dict[str, Any], *,
                  max_queue_age: int, max_failed: int,
                  min_free_bytes: int, require_intake_open: bool,
                  max_provider_missions: int | None = None) -> dict[str, Any]:
    if public.get("status") != "ok":
        raise MonitorError("public health is not OK")
    if admin.get("database") != "ok":
        raise MonitorError("database health is not OK")
    queue = admin.get("queue")
    storage = admin.get("storage")
    if not isinstance(queue, dict) or not isinstance(storage, dict):
        raise MonitorError("administrator health lacks monitoring metrics")
    failed = admin.get("failed_missions")
    queue_age = admin.get("oldest_queued_seconds")
    free_bytes = storage.get("free_bytes")
    total_bytes = storage.get("total_bytes")
    if not all(isinstance(value, int) and value >= 0 for value in
               (failed, queue_age, free_bytes, total_bytes)):
        raise MonitorError("administrator monitoring metrics are invalid")
    if failed > max_failed:
        raise MonitorError(f"failed mission count {failed} exceeds {max_failed}")
    if queue_age > max_queue_age:
        raise MonitorError(f"oldest queued mission is {queue_age}s old")
    if free_bytes < min_free_bytes:
        raise MonitorError(f"data volume has only {free_bytes} free bytes")
    if require_intake_open and not (public.get("accepting_missions") and
                                    admin.get("accepting_jobs")):
        raise MonitorError("mission intake is not open")
    evidence = {
        "status": public["status"],
        "accepting_missions": bool(public.get("accepting_missions")),
        "database": admin["database"],
        "queue": queue,
        "failed_missions": failed,
        "oldest_queued_seconds": queue_age,
        "storage": {"free_bytes": free_bytes, "total_bytes": total_bytes},
    }
    if max_provider_missions is not None:
        usage = admin.get("provider_usage")
        if not isinstance(usage, dict):
            raise MonitorError("administrator health lacks paid-provider metrics")
        required = ("missions_reserved_24h", "provider_calls_24h",
                    "input_tokens_24h", "output_tokens_24h", "web_searches_24h")
        if not all(isinstance(usage.get(key), int) and usage[key] >= 0
                   for key in required):
            raise MonitorError("paid-provider metrics are invalid")
        if usage["missions_reserved_24h"] > max_provider_missions:
            raise MonitorError("paid-provider mission cap was exceeded")
        evidence["provider_usage"] = {key: usage[key] for key in required}
    return evidence


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _run_docker(args: list[str], runner: Runner) -> subprocess.CompletedProcess[str]:
    try:
        result = runner(args, capture_output=True, text=True,
                        timeout=20, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise MonitorError("Docker monitoring command failed to start") from exc
    if result.returncode:
        raise MonitorError("Docker monitoring command returned a failure")
    return result


def container_evidence(name: str, *, max_restarts: int,
                       runner: Runner = subprocess.run) -> dict[str, Any]:
    result = _run_docker(["docker", "inspect", name], runner)
    try:
        payload = json.loads(result.stdout)
        state = payload[0]["State"]
        status_value = state["Status"]
        health = state.get("Health", {}).get("Status", "missing")
        restarts = int(payload[0].get("RestartCount", 0))
    except (IndexError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MonitorError(f"Docker returned invalid inspection data for {name}") from exc
    if status_value != "running" or health != "healthy":
        raise MonitorError(f"container {name} is {status_value}/{health}")
    if restarts > max_restarts:
        raise MonitorError(f"container {name} restart count {restarts} exceeds {max_restarts}")
    return {"status": status_value, "health": health, "restart_count": restarts}


def worker_lease_errors(name: str, *, since: str,
                        runner: Runner = subprocess.run) -> int:
    result = _run_docker(["docker", "logs", "--since", since, name], runner)
    return len(LEASE_ERROR.findall(result.stdout + "\n" + result.stderr))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-origin", required=True)
    parser.add_argument("--admin-token-file", type=Path, required=True)
    parser.add_argument("--api-container", default="origin-beta-api-1")
    parser.add_argument("--worker-container", default="origin-beta-worker-1")
    parser.add_argument("--researcher-container", default="origin-beta-researcher-1")
    parser.add_argument("--max-queue-age", type=int, default=900)
    parser.add_argument("--max-failed", type=int, default=0)
    parser.add_argument("--min-free-bytes", type=int, default=536_870_912)
    parser.add_argument("--max-restarts", type=int, default=0)
    parser.add_argument("--max-provider-missions-24h", type=int, default=4)
    parser.add_argument("--log-since", default="15m")
    parser.add_argument("--require-intake-open", action="store_true")
    parser.add_argument("--skip-docker", action="store_true")
    parser.add_argument("--require-researcher", action="store_true")
    parser.add_argument("--allow-http-local", action="store_true",
                        help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if min(args.max_queue_age, args.max_failed, args.min_free_bytes,
               args.max_restarts, args.max_provider_missions_24h) < 0:
            raise MonitorError("monitor thresholds must be non-negative")
        api_origin = _origin(args.api_origin,
                             allow_http_local=args.allow_http_local)
        token = _token(args.admin_token_file)
        public = _request_json(api_origin, "/api/v1/health")
        admin = _request_json(api_origin, "/api/v1/admin/health", token=token)
        token = ""
        evidence: dict[str, Any] = {
            "api_origin": api_origin,
            "remote": assess_remote(
                public, admin, max_queue_age=args.max_queue_age,
                max_failed=args.max_failed, min_free_bytes=args.min_free_bytes,
                require_intake_open=args.require_intake_open,
                max_provider_missions=args.max_provider_missions_24h),
        }
        if not args.skip_docker:
            api = container_evidence(
                args.api_container, max_restarts=args.max_restarts)
            worker = container_evidence(
                args.worker_container, max_restarts=args.max_restarts)
            lease_errors = worker_lease_errors(
                args.worker_container, since=args.log_since)
            if lease_errors:
                raise MonitorError(
                    f"worker logged {lease_errors} lease/traceback error(s) since {args.log_since}")
            evidence["containers"] = {
                "api": api,
                "worker": worker,
                "worker_lease_errors": lease_errors,
            }
            if args.require_researcher:
                researcher = container_evidence(
                    args.researcher_container,
                    max_restarts=args.max_restarts)
                researcher_errors = worker_lease_errors(
                    args.researcher_container, since=args.log_since)
                if researcher_errors:
                    raise MonitorError(
                        f"researcher logged {researcher_errors} lease/traceback "
                        f"error(s) since {args.log_since}")
                evidence["containers"]["researcher"] = researcher
                evidence["containers"]["researcher_lease_errors"] = researcher_errors
    except (OSError, urllib.error.URLError, MonitorError) as exc:
        print(f"BETA MONITOR FAILED: {exc}")
        return 2
    print(json.dumps({"ok": True, "evidence": evidence},
                     indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
