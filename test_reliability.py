"""Phase 1 reliability proofs: interruption/restart, checkpoint corruption,
and replay-from-metadata. These are the handoff's required Phase-1 evidence."""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin.cli import main as cli_main                       # noqa: E402
from origin.controller import ResearchController              # noqa: E402
from origin.domains.base import get_domain                    # noqa: E402
from origin.state import CheckpointCorrupted, ResearchState   # noqa: E402

REPO = Path(__file__).resolve().parents[1]


class TestInterruptionRecovery(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_sigkill_midrun_then_resume_without_loss_or_duplication(self):
        root = self.tmp / "m"
        rc = cli_main(["init", "interrupt me", "--dir", str(root),
                       "--profile", "standard", "--max-experiments", "12",
                       "--brain", "none"])
        self.assertEqual(rc, 0)
        # Launch the mission as a real OS process and kill it mid-work.
        proc = subprocess.Popen([sys.executable, "-m", "origin", "run",
                                 "--dir", str(root)], cwd=str(REPO),
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        time.sleep(1.5)                       # standard profile takes several s
        interrupted_midway = proc.poll() is None
        if interrupted_midway:
            os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=30)
        self.assertTrue(interrupted_midway,
                        "process finished before the kill; increase work size")

        # The durable checkpoint must load cleanly after a hard kill.
        st = ResearchState.load(root)
        step_at_kill = st.step
        events_at_kill = len(st.read_events())
        exps_at_kill = set(st.experiments)
        self.assertNotEqual(st.meta["phase"], "COMPLETED")

        # Resume in-process to completion.
        ResearchController(st, get_domain(st.meta["domain"])).run()
        self.assertEqual(st.meta["phase"], "COMPLETED")
        self.assertGreater(st.step, step_at_kill)
        self.assertGreater(len(st.read_events()), events_at_kill)
        # No research history lost: every pre-kill experiment still present.
        self.assertTrue(exps_at_kill.issubset(set(st.experiments)))
        # No duplicated history: ids unique, event log has no duplicate starts.
        st2 = ResearchState.load(root)
        self.assertEqual(st2.verify(), [])
        started = [e["refs"]["experiment"] for e in st2.read_events()
                   if e["kind"] == "experiment_started"]
        self.assertEqual(len(started), len(set(started)))

    def test_corrupted_checkpoint_recovers_from_backup(self):
        root = self.tmp / "c"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        st = ResearchState.load(root)
        ResearchController(st, get_domain("algobench")).run(max_steps=3)
        (root / "state.json").write_text("{ this is not json !!!")
        st2 = ResearchState.load(root)         # falls back to state.json.bak
        self.assertTrue(st2.flags.get("recovered_from_backup"))
        self.assertGreaterEqual(st2.step, 1)

    def test_both_checkpoints_corrupted_fails_safely(self):
        root = self.tmp / "d"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        st = ResearchState.load(root)
        ResearchController(st, get_domain("algobench")).run(max_steps=2)
        (root / "state.json").write_text("garbage")
        (root / "state.json.bak").write_text("also garbage")
        with self.assertRaises(CheckpointCorrupted) as cm:
            ResearchState.load(root)
        self.assertIn("logs/", str(cm.exception))  # tells user history survives

    # ---- regression: checkpoint-recovery defects R-1, R-2, R-3 ------------
    def test_missing_primary_with_intact_backup_recovers(self):
        """R-1: `save()` rotates state.json -> .bak before writing the new
        snapshot. A crash inside that window left the project unloadable
        (FileNotFoundError) even though a valid backup existed."""
        root = self.tmp / "r1"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        st = ResearchState.load(root)
        ResearchController(st, get_domain("algobench")).run(max_steps=3)
        step_before = ResearchState.load(root).step
        (root / "state.json").unlink()                 # simulate the crash window
        st2 = ResearchState.load(root)
        self.assertTrue(st2.flags.get("recovered_from_backup"))
        self.assertGreaterEqual(st2.step, max(0, step_before - 1))
        # and the mission still finishes from the recovered checkpoint
        ResearchController(st2, get_domain("algobench")).run()
        self.assertEqual(st2.meta["phase"], "COMPLETED")

    def test_structurally_invalid_primary_falls_back_to_backup(self):
        """R-2: a syntactically valid but structurally broken snapshot raised a
        bare KeyError instead of falling back to the backup."""
        root = self.tmp / "r2"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        st = ResearchState.load(root)
        ResearchController(st, get_domain("algobench")).run(max_steps=3)
        (root / "state.json").write_text('{"schema_version": 3}')
        st2 = ResearchState.load(root)
        self.assertTrue(st2.flags.get("recovered_from_backup"))
        self.assertIn("phase", st2.meta)

    def test_corrupt_backup_alone_is_harmless(self):
        root = self.tmp / "r2b"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        st = ResearchState.load(root)
        ResearchController(st, get_domain("algobench")).run(max_steps=3)
        (root / "state.json.bak").write_text("}{ not json")
        st2 = ResearchState.load(root)
        self.assertFalse(st2.flags.get("recovered_from_backup"))
        self.assertGreaterEqual(st2.step, 1)

    def test_torn_event_log_line_is_survivable(self):
        """R-3: a partially written final line (crash mid-append) made the
        timeline/report crash and produced a misleading 'event log is empty'."""
        root = self.tmp / "r3"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        st = ResearchState.load(root)
        ResearchController(st, get_domain("algobench")).run()
        with open(root / "logs" / "events.jsonl", "a") as f:
            f.write('{"ts": 1786284860.0, "kind": "torn"')   # no newline, no close
        st2 = ResearchState.load(root)
        events = st2.read_events()
        self.assertGreater(len(events), 5)                   # history still readable
        self.assertEqual(st2.event_log_skipped, 1)
        problems = st2.verify()
        self.assertTrue(any("malformed line" in p for p in problems), problems)
        self.assertFalse(any("event log is empty" in p for p in problems), problems)
        self.assertEqual(cli_main(["timeline", "--dir", str(root)]), 0)
        self.assertEqual(cli_main(["report", "--dir", str(root)]), 0)

    def test_orphaned_experiment_artifacts_are_reconciled(self):
        """R-4: a hard kill between spawning an experiment and the next
        checkpoint left artifacts on disk that the ledger never knew about,
        and `verify()` called that state clean."""
        root = self.tmp / "orphan"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        st = ResearchState.load(root)
        ResearchController(st, get_domain("algobench")).run(max_steps=3)

        # Simulate the crash window: artifacts exist, no checkpoint record.
        ghost = root / "experiments" / "exp_ghost0001"
        ghost.mkdir(parents=True)
        (ghost / "spec.json").write_text(json.dumps(
            {"kind": "benchmark", "hypothesis_ids": [], "sizes": [8],
             "trials": 1, "seed": 1, "timeout_s": 30}))
        (ghost / "run.py").write_text("# interrupted before checkpoint\n")
        (ghost / "result.json").write_text(json.dumps({"rows": []}))

        st2 = ResearchState.load(root)
        problems = st2.verify()
        self.assertTrue(any("exp_ghost0001" in p for p in problems), problems)

        # Resuming reconciles it into the ledger, then the state is clean.
        ResearchController(st2, get_domain("algobench")).run()
        self.assertIn("exp_ghost0001", st2.experiments)
        self.assertEqual(st2.experiments["exp_ghost0001"].status, "interrupted")
        self.assertTrue(any(f.get("kind") == "interrupted"
                            for f in st2.failures))
        st3 = ResearchState.load(root)
        self.assertEqual(st3.verify(), [])
        # Idempotent: reconciling again adopts nothing new.
        self.assertEqual(st3.reconcile_orphans(), [])

    def test_missing_project_reports_cleanly(self):
        rc = cli_main(["verify", "--dir", str(self.tmp / "does_not_exist")])
        self.assertEqual(rc, 2)

    def test_replay_from_recorded_metadata_within_tolerance(self):
        root = self.tmp / "r"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        st = ResearchState.load(root)
        ResearchController(st, get_domain("algobench")).run()
        exp = next(r.id for r in st.experiments.values()
                   if r.status == "completed")
        rc = cli_main(["replay", "--dir", str(root), "--exp", exp,
                       "--tolerance", "0.8"])
        self.assertEqual(rc, 0)
        # Determinism of the science: correctness + rankings come from fixed
        # seeds; only wall-clock timing varies (hence the tolerance).
        stored = json.loads((st.experiment_dir(st.experiments[exp]) /
                             "result.json").read_text())
        self.assertTrue(all(r["correct"] for r in stored["rows"]))


if __name__ == "__main__":
    unittest.main()
