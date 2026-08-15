"""ORIGIN experiment engine.

Experiments are self-contained generated scripts, executed in a separate
sandboxed process with a hard timeout. The generated code, the design spec,
stdout, and the raw results are all kept on disk forever — experiments are
part of the permanent research history and are individually re-runnable:

    python experiments/exp_xxxx/run.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from . import sandbox
from .models import ExperimentRecord, new_id


class ExperimentEngine:
    def __init__(self, state, domain) -> None:
        self.state = state
        self.domain = domain

    def run(self, design: dict, title: str) -> ExperimentRecord:
        rec = ExperimentRecord(id=new_id("exp"), title=title,
                               hypothesis_ids=list(design.get("hypothesis_ids", [])),
                               design=design)
        # Policy gate: unsafe designs are rejected BEFORE any process exists.
        violations = sandbox.validate_design(design)
        if violations:
            rec.status = "rejected"
            rec.error = "unsafe design: " + "; ".join(violations)
            self.state.add(rec)
            self.state.failures.append({
                "experiment": rec.id, "hypothesis": ",".join(rec.hypothesis_ids),
                "kind": "unsafe_design", "prediction": "(policy)",
                "expected": "design within sandbox policy",
                "observed": rec.error,
                "action": "rejected without execution; no budget charged",
                "ts": time.time()})
            self.state.log_event("experiment_rejected",
                                 f"{rec.id}: {rec.error}", experiment=rec.id)
            return rec
        root = Path(self.state.root)
        exp_dir = (root / "experiments" / rec.id).resolve()
        exp_dir.mkdir(parents=True, exist_ok=True)
        # Stored root-relative: the project must stay valid when copied,
        # archived, or unpacked on another machine.
        rec.dir = (Path("experiments") / rec.id).as_posix()
        (exp_dir / "spec.json").write_text(json.dumps(design, indent=2))
        runner = self.domain.write_runner(design, exp_dir)

        self.state.add(rec)
        rec.status = "running"
        self.state.log_event("experiment_started", f"{rec.id}: {title}", experiment=rec.id)

        timeout_s = design.get("timeout_s", 600)
        confinement = sandbox.confinement_profile(timeout_s)
        rec.summary["confinement"] = confinement
        confinement_path = exp_dir / "confinement.json"
        confinement_path.write_text(json.dumps(confinement, indent=2))

        t0 = time.perf_counter()
        try:
            proc = sandbox.run_confined(
                [sys.executable, "-I", runner.name],
                cwd=str(exp_dir), timeout_s=timeout_s,
                env=sandbox.scrubbed_env(str(exp_dir)),
            )
            rec.duration_s = time.perf_counter() - t0
            confinement["observed_peak_rss_bytes"] = proc.peak_rss_bytes
            confinement["termination_reason"] = proc.termination_reason
            confinement_path.write_text(json.dumps(confinement, indent=2))
            (exp_dir / "stdout.log").write_text(
                sandbox.truncate_output(proc.stdout) +
                "\n--- stderr ---\n" + sandbox.truncate_output(proc.stderr))
            result_path = exp_dir / "result.json"
            if proc.returncode != 0 or not result_path.exists():
                rec.status = "failed"
                rec.error = (proc.stderr or proc.stdout or "no output").strip()[-500:]
            else:
                result = json.loads(result_path.read_text())
                if "error" in result:
                    rec.status = "failed"
                    rec.error = result["error"]
                else:
                    rec.status = "completed"
                    rec.summary["measurements"] = len(result.get("rows", []))
        except subprocess.TimeoutExpired:
            rec.duration_s = time.perf_counter() - t0
            rec.status = "failed"
            rec.error = f"timeout after {design.get('timeout_s', 600)}s"
            confinement["termination_reason"] = "wall_timeout"
            confinement_path.write_text(json.dumps(confinement, indent=2))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            # A confinement primitive that cannot be installed is a failed
            # experiment, never permission to run the child without it.
            rec.duration_s = time.perf_counter() - t0
            rec.status = "failed"
            rec.error = ("confinement setup failed closed: "
                         f"{type(exc).__name__}: {exc}")
            confinement["termination_reason"] = "confinement_setup_failed"
            confinement_path.write_text(json.dumps(confinement, indent=2))

        rec.finished_at = time.time()
        self.state.budget.charge_experiment(rec.duration_s)

        if rec.status == "failed":
            self.state.failures.append({
                "experiment": rec.id, "hypothesis": ",".join(rec.hypothesis_ids),
                "prediction": "(execution)", "expected": "successful run",
                "observed": rec.error, "action": "experiment marked failed; budget charged",
                "ts": time.time()})
            self.state.log_event("experiment_failed", f"{rec.id}: {rec.error}", experiment=rec.id)
        else:
            self.state.log_event(
                "experiment_completed",
                f"{rec.id} completed in {rec.duration_s:.1f}s "
                f"({rec.summary.get('measurements', 0)} measurements)",
                experiment=rec.id)
        return rec

    def load_result(self, rec: ExperimentRecord) -> dict | None:
        path = rec.path(self.state.root) / "result.json"
        if rec.status == "completed" and path.exists():
            return json.loads(path.read_text())
        return None
