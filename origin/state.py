"""ORIGIN persistent research state.

Everything ORIGIN learns or decides is persisted after every controller step.
If the machine shuts down mid-research, `ResearchState.load()` resumes from
the last checkpoint. The append-only event log doubles as a replayable
research timeline.

On-disk layout (per project):

    project.json            immutable project metadata
    state.json              full atomic snapshot (checkpoint)
    research_state/         per-type JSON views for browsing
    experiments/exp_.../    generated code + raw results, versioned forever
    logs/events.jsonl       append-only research timeline
    reports/                dossier.md, timeline.md
"""
from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path

from .budget import Budget
from .graph import KnowledgeGraph
from .models import (Claim, Evidence, ExperimentRecord, FalsificationAttempt,
                     Hypothesis, Invalidity, Source, new_id, to_jsonable)

SCHEMA_VERSION = 3


class CheckpointCorrupted(Exception):
    """state.json (and its backup, if any) could not be loaded safely."""


def _relative_dir(value: str, rec_id: str, root: Path) -> str:
    """Normalize an experiment directory reference to a root-relative path."""
    if not value:
        return (Path("experiments") / rec_id).as_posix()
    p = Path(value)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        # Absolute path from another machine/checkout: fall back to the
        # canonical layout rather than reading a foreign directory.
        return (Path("experiments") / rec_id).as_posix()


class ResearchState:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.meta: dict = {}
        self.budget = Budget()
        self.plan: dict = {}
        self.sources: dict[str, Source] = {}
        self.claims: dict[str, Claim] = {}
        self.hypotheses: dict[str, Hypothesis] = {}
        self.evidence: dict[str, Evidence] = {}
        self.experiments: dict[str, ExperimentRecord] = {}
        self.decisions: list[dict] = []
        self.graph = KnowledgeGraph()
        self.assumptions: list[str] = []
        self.cautions: list[str] = []
        self.failures: list[dict] = []
        self.falsifications: dict[str, FalsificationAttempt] = {}
        self.invalidities: dict[str, Invalidity] = {}
        self.confidence_history: list[dict] = []
        self.recommendations: list[str] = []
        self.flags: dict = {}
        self.step: int = 0
        self.event_log_skipped: int = 0

    # ------------------------------------------------------------------ create
    @classmethod
    def create(cls, root: Path, question: str, domain: str,
               domain_config: dict, budget: Budget, profile: str = "standard") -> "ResearchState":
        root = Path(root)
        if (root / "state.json").exists():
            raise FileExistsError(f"A research project already exists at {root}")
        for sub in ("research_state", "experiments", "logs", "reports", "sources"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        st = cls(root)
        st.meta = {
            "question": question,
            "domain": domain,
            # Deep-copied: a mission must never hold a reference to a shared
            # profile dict. Without this, mutating one mission's config
            # silently rewrites the module-level PROFILES for every later
            # mission in the same process (found in the v1.7 security pass).
            "domain_config": copy.deepcopy(domain_config),
            "profile": profile,
            "phase": "CREATED",
            "created_at": time.time(),
            "origin_version": "1.0.0",
        }
        st.budget = budget
        (root / "project.json").write_text(json.dumps(st.meta, indent=2))
        st.log_event("init", f"Research project initialized: {question}")
        st.save()
        return st

    # -------------------------------------------------------------------- load
    @classmethod
    def load(cls, root: Path) -> "ResearchState":
        """Load the durable checkpoint.

        Tries `state.json`, then `state.json.bak`. A candidate is only accepted
        if it parses *and* reconstructs into a usable state, so a syntactically
        valid but structurally broken snapshot (e.g. truncated to `{}` or
        written by a crashed process) falls through to the backup instead of
        raising a bare KeyError. A missing primary with an intact backup is a
        normal crash-window outcome and is recovered, not an error.
        """
        root = Path(root)
        main, bak = root / "state.json", root / "state.json.bak"
        if not main.exists() and not bak.exists():
            raise FileNotFoundError(
                f"No ORIGIN project at {root} (no state.json or state.json.bak)")

        errors: list[str] = []
        for path, is_backup in ((main, False), (bak, True)):
            if not path.exists():
                errors.append(f"{path.name}: missing")
                continue
            try:
                d = json.loads(path.read_text())
                sv = d.get("schema_version", 1)
                if sv > SCHEMA_VERSION:
                    raise CheckpointCorrupted(
                        f"Checkpoint schema v{sv} is newer than this ORIGIN "
                        f"(v{SCHEMA_VERSION}); refusing to load to avoid data loss.")
                st = cls._from_snapshot(root, d, sv)
            except CheckpointCorrupted:
                raise
            except (json.JSONDecodeError, OSError, KeyError, TypeError,
                    ValueError, AttributeError) as e:
                errors.append(f"{path.name}: {type(e).__name__}: {e}")
                continue
            if is_backup:
                st.flags["recovered_from_backup"] = True
                st.log_event("recovered",
                             "state.json was unusable (" + errors[0] + "); "
                             "recovered from state.json.bak")
            return st

        raise CheckpointCorrupted(
            f"Checkpoint at {main} could not be loaded and no usable backup "
            f"exists ({'; '.join(errors)}). Research history in logs/ and "
            f"experiments/ is intact; state.json needs manual repair.")

    @classmethod
    def _from_snapshot(cls, root: Path, d: dict, sv: int) -> "ResearchState":
        if not isinstance(d.get("meta"), dict):
            raise KeyError("meta")
        st = cls(root)
        st.meta = d["meta"]
        st.budget = Budget.from_dict(d["budget"])
        st.plan = d.get("plan", {})
        st.sources = {k: Source.from_dict(v) for k, v in d.get("sources", {}).items()}
        st.claims = {k: Claim.from_dict(v) for k, v in d.get("claims", {}).items()}
        st.hypotheses = {k: Hypothesis.from_dict(v) for k, v in d.get("hypotheses", {}).items()}
        st.evidence = {k: Evidence.from_dict(v) for k, v in d.get("evidence", {}).items()}
        st.experiments = {k: ExperimentRecord.from_dict(v) for k, v in d.get("experiments", {}).items()}
        st.decisions = d.get("decisions", [])
        st.graph = KnowledgeGraph.from_dict(d.get("graph", {}))
        st.assumptions = d.get("assumptions", [])
        st.cautions = d.get("cautions", [])
        st.failures = d.get("failures", [])
        st.recommendations = d.get("recommendations", [])
        st.falsifications = {k: FalsificationAttempt.from_dict(v)
                             for k, v in d.get("falsifications", {}).items()}
        st.invalidities = {k: Invalidity.from_dict(v)
                           for k, v in d.get("invalidities", {}).items()}
        st.confidence_history = d.get("confidence_history", [])
        st.flags = d.get("flags", {})
        st.step = d.get("step", 0)
        from .lifecycle import migrate_phase
        old = st.meta.get("phase", "CREATED")
        st.meta["phase"] = migrate_phase(old)
        if st.meta["phase"] != old:
            # No event append here: loading an archived project must not mutate
            # it. The migration is recorded on the next save() via this flag.
            st.flags["migrated_from"] = old
        # Portability migration: ORIGIN <= v1.0 stored absolute artifact paths,
        # which silently pointed at the ORIGINAL machine after a project was
        # copied. Normalize to root-relative on read.
        migrated = 0
        for rec in st.experiments.values():
            norm = _relative_dir(rec.dir, rec.id, root)
            if norm != rec.dir:
                rec.dir = norm
                migrated += 1
        if migrated:
            st.flags["migrated_paths"] = migrated
        return st

    # -------------------------------------------------------------------- save
    def save(self) -> None:
        snapshot = {
            "schema_version": SCHEMA_VERSION,
            "meta": self.meta,
            "budget": self.budget.to_dict(),
            "plan": self.plan,
            "sources": {k: to_jsonable(v) for k, v in self.sources.items()},
            "claims": {k: to_jsonable(v) for k, v in self.claims.items()},
            "hypotheses": {k: to_jsonable(v) for k, v in self.hypotheses.items()},
            "evidence": {k: to_jsonable(v) for k, v in self.evidence.items()},
            "experiments": {k: to_jsonable(v) for k, v in self.experiments.items()},
            "decisions": self.decisions,
            "graph": self.graph.to_dict(),
            "assumptions": self.assumptions,
            "cautions": self.cautions,
            "failures": self.failures,
            "falsifications": {k: to_jsonable(v) for k, v in self.falsifications.items()},
            "invalidities": {k: to_jsonable(v) for k, v in self.invalidities.items()},
            "confidence_history": self.confidence_history,
            "recommendations": self.recommendations,
            "flags": self.flags,
            "step": self.step,
        }
        main = self.root / "state.json"
        tmp = self.root / "state.json.tmp"
        # Write and flush the new checkpoint BEFORE touching the current one,
        # so a crash can never leave the project without a loadable snapshot.
        with open(tmp, "w") as f:
            f.write(json.dumps(snapshot, indent=2, default=str))
            f.flush()
            os.fsync(f.fileno())
        if main.exists():                      # rotate last good checkpoint
            os.replace(main, self.root / "state.json.bak")
        os.replace(tmp, main)
        try:                                   # make the rename itself durable
            dfd = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass

        rs = self.root / "research_state"
        views = {
            "hypotheses.json": snapshot["hypotheses"],
            "claims.json": snapshot["claims"],
            "evidence.json": snapshot["evidence"],
            "experiments.json": snapshot["experiments"],
            "decisions.json": snapshot["decisions"],
            "failure_log.json": snapshot["failures"],
            "graph.json": snapshot["graph"],
        }
        for name, payload in views.items():
            (rs / name).write_text(json.dumps(payload, indent=2, default=str))

    # ------------------------------------------------------------------ events
    def log_event(self, kind: str, msg: str, **refs) -> None:
        (self.root / "logs").mkdir(parents=True, exist_ok=True)
        entry = {"ts": time.time(), "kind": kind, "msg": msg}
        if refs:
            entry["refs"] = refs
        with open(self.root / "logs" / "events.jsonl", "a") as f:
            f.write(json.dumps(entry, default=str) + "\n")

    def read_events(self) -> list[dict]:
        """Read the append-only event log, tolerating a torn final line.

        A crash during an append can leave a partial JSON line. That must not
        make the research history unreadable; malformed lines are skipped and
        counted in `event_log_skipped` (surfaced by `verify()`).
        """
        path = self.root / "logs" / "events.jsonl"
        self.event_log_skipped = 0
        if not path.exists():
            return []
        out = []
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                self.event_log_skipped += 1
        return out

    def day_of(self, ts: float) -> int:
        start = self.meta.get("created_at", ts)
        return int((ts - start) // 86400) + 1

    # -------------------------------------------------------------- convenience
    def add(self, obj) -> None:
        table = {
            Source: self.sources, Claim: self.claims, Hypothesis: self.hypotheses,
            Evidence: self.evidence, ExperimentRecord: self.experiments,
        }[type(obj)]
        table[obj.id] = obj

    def counts(self) -> dict:
        return {
            "sources": len(self.sources),
            "claims": len(self.claims),
            "hypotheses": len(self.hypotheses),
            "evidence": len(self.evidence),
            "experiments": len(self.experiments),
            "contradictions": len(self.graph.contradictions),
            "failures": len(self.failures),
        }

    # ------------------------------------------------------- v1.0 additions
    def record_invalidity(self, candidate: str, condition: str, reason: str,
                          experiment_id: str = "") -> "Invalidity":
        """Record that a candidate is not valid under a condition.

        Idempotent per (candidate, condition). Recording an invalidity is a
        research finding, not an error: it is logged, it appears in the
        dossier, and `valid_candidates()` keeps the candidate out of any
        ranking for that condition.
        """
        for inv in self.invalidities.values():
            if inv.candidate == candidate and inv.condition == condition:
                return inv
        inv = Invalidity(id=new_id("inv"), candidate=candidate,
                         condition=condition, reason=reason,
                         experiment_id=experiment_id)
        self.invalidities[inv.id] = inv
        self.log_event("invalidity",
                       f"{candidate} is NOT VALID under '{condition}': {reason}",
                       experiment=experiment_id or None)
        return inv

    def is_valid(self, candidate: str, condition: str) -> bool:
        return not any(i.candidate == candidate
                       and i.condition in (condition, "*")
                       for i in self.invalidities.values())

    def valid_candidates(self, candidates, condition: str) -> list:
        """Filter a candidate list down to those still valid for a condition."""
        return [c for c in candidates if self.is_valid(c, condition)]

    def record_confidence_change(self, kind: str, obj_id: str,
                                 old, new, reason: str) -> None:
        """Append-only confidence/status history — changes are never silently
        overwritten without trace."""
        self.confidence_history.append({
            "ts": time.time(), "kind": kind, "id": obj_id,
            "old": old, "new": new, "reason": reason})

    def verify(self) -> list[str]:
        """Consistency check of the durable state. Returns problems ([] = ok)."""
        probs: list[str] = []
        for e in self.evidence.values():
            tid = e.target_id
            if tid and tid not in self.hypotheses and tid not in self.claims:
                probs.append(f"evidence {e.id} targets unknown object {tid}")
            if e.experiment_id and e.experiment_id not in self.experiments:
                probs.append(f"evidence {e.id} cites unknown experiment {e.experiment_id}")
        for rec in self.experiments.values():
            if Path(rec.dir).is_absolute():
                probs.append(f"experiment {rec.id} stores an absolute artifact "
                             f"path ({rec.dir}); project is not portable")
            d = rec.path(self.root)
            if rec.status in ("completed", "failed") and not (d / "spec.json").exists():
                probs.append(f"experiment {rec.id} missing spec.json on disk")
            if rec.status == "completed" and not (d / "result.json").exists():
                probs.append(f"experiment {rec.id} completed but result.json missing")
        for h in self.hypotheses.values():
            for xid in h.tested_in:
                if xid not in self.experiments:
                    probs.append(f"hypothesis {h.id} references unknown experiment {xid}")
        try:
            events = self.read_events()
        except Exception as e:  # noqa: BLE001 - report, don't crash a verify
            probs.append(f"event log unreadable: {e}")
            events = []
        if getattr(self, "event_log_skipped", 0):
            probs.append(f"{self.event_log_skipped} malformed line(s) in the "
                         f"event log (torn write?); they were skipped")
        if not events:
            probs.append("event log is empty")
        # Autonomy state (v1.5): optional, but if present it must be loadable,
        # schema-valid and free of absolute paths.
        auto = self.root / "autonomy" / "state.json"
        if auto.exists():
            try:
                from . import autonomy as _autonomy
                store = _autonomy.AutonomyStore(self.root)
                for item in store.items.values():
                    if item.reason.startswith("quarantined:"):
                        # The loader neutralises malformed items so a mission
                        # still opens; verify() is where that gets surfaced.
                        probs.append(
                            f"autonomy work item {item.id} was quarantined on "
                            f"load: {item.last_error[:110]}")
                        continue
                    bad = _autonomy.validate_item(item.to_dict())
                    if bad:
                        probs.append(f"autonomy work item {item.id} is invalid: "
                                     f"{'; '.join(bad)[:120]}")
                blob = auto.read_text()
                for marker in ("/home/", "/Users/", "/root/"):
                    if marker in blob:
                        probs.append(f"autonomy state contains a machine-specific "
                                     f"absolute path ({marker}…)")
            except Exception as e:  # noqa: BLE001 - report, never crash a verify
                probs.append(f"autonomy state is unreadable: {e}")
        for inv in self.invalidities.values():
            if inv.experiment_id and inv.experiment_id not in self.experiments:
                probs.append(f"invalidity {inv.id} cites unknown experiment "
                             f"{inv.experiment_id}")
        for name in self.orphan_experiment_dirs():
            probs.append(f"experiment directory experiments/{name} has no "
                         f"record in the checkpoint (interrupted run?); "
                         f"resume the mission to reconcile it")
        ids = [ev.get("refs", {}).get("experiment") for ev in events
               if ev.get("kind") == "experiment_started"]
        for xid in {i for i in ids if i and i not in self.experiments}:
            probs.append(f"event log records {xid} as started but it is absent "
                         f"from the checkpoint")
        seen, dups = set(), set()
        for i in ids:
            if i in seen:
                dups.add(i)
            seen.add(i)
        for d_ in dups:
            probs.append(f"duplicate experiment_started event for {d_}")
        return probs

    def experiment_dir(self, rec) -> Path:
        """Absolute artifact directory for an experiment record."""
        return rec.path(self.root)

    # ------------------------------------------------- crash reconciliation
    def orphan_experiment_dirs(self) -> list[str]:
        """Experiment directories on disk with no record in the checkpoint.

        A hard kill between spawning an experiment and the next checkpoint
        leaves artifacts (sometimes a complete result.json) that the ledger
        knows nothing about: compute was spent but never accounted for.
        """
        base = self.root / "experiments"
        if not base.exists():
            return []
        return sorted(p.name for p in base.iterdir()
                      if p.is_dir() and p.name not in self.experiments)

    def reconcile_orphans(self) -> list[str]:
        """Adopt orphaned experiment directories into the ledger as
        `interrupted` records. Idempotent; never resurrects unanalysed results
        as findings — the artifacts are preserved and clearly marked."""
        from .models import ExperimentRecord
        adopted = []
        # Autonomy state (v1.5): optional, but if present it must be loadable,
        # schema-valid and free of absolute paths.
        auto = self.root / "autonomy" / "state.json"
        if auto.exists():
            try:
                from . import autonomy as _autonomy
                store = _autonomy.AutonomyStore(self.root)
                for item in store.items.values():
                    if item.reason.startswith("quarantined:"):
                        # The loader neutralises malformed items so a mission
                        # still opens; verify() is where that gets surfaced.
                        probs.append(
                            f"autonomy work item {item.id} was quarantined on "
                            f"load: {item.last_error[:110]}")
                        continue
                    bad = _autonomy.validate_item(item.to_dict())
                    if bad:
                        probs.append(f"autonomy work item {item.id} is invalid: "
                                     f"{'; '.join(bad)[:120]}")
                blob = auto.read_text()
                for marker in ("/home/", "/Users/", "/root/"):
                    if marker in blob:
                        probs.append(f"autonomy state contains a machine-specific "
                                     f"absolute path ({marker}…)")
            except Exception as e:  # noqa: BLE001 - report, never crash a verify
                probs.append(f"autonomy state is unreadable: {e}")
        for inv in self.invalidities.values():
            if inv.experiment_id and inv.experiment_id not in self.experiments:
                probs.append(f"invalidity {inv.id} cites unknown experiment "
                             f"{inv.experiment_id}")
        for name in self.orphan_experiment_dirs():
            d = self.root / "experiments" / name
            design = {}
            spec = d / "spec.json"
            if spec.exists():
                try:
                    design = json.loads(spec.read_text())
                except (json.JSONDecodeError, OSError):
                    design = {}
            rec = ExperimentRecord(
                id=name, title="Interrupted before checkpoint (recovered)",
                hypothesis_ids=list(design.get("hypothesis_ids", [])),
                design=design, status="interrupted",
                dir=(Path("experiments") / name).as_posix(),
                error="process terminated before this experiment was "
                      "checkpointed; artifacts preserved, results not analysed")
            self.experiments[name] = rec
            self.failures.append({
                "experiment": name, "hypothesis": ",".join(rec.hypothesis_ids),
                "kind": "interrupted", "prediction": "(execution)",
                "expected": "checkpointed experiment record",
                "observed": "artifacts on disk with no ledger entry "
                            "(interrupted run)",
                "action": "adopted as interrupted; compute spent but not "
                          "charged; experiment re-planned normally",
                "ts": time.time()})
            self.log_event("experiment_orphaned",
                           f"{name}: artifacts found on disk with no checkpoint "
                           f"record; adopted as interrupted", experiment=name)
            adopted.append(name)
        return adopted
