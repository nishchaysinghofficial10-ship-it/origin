"""Lifecycle state-machine tests: legal transitions only, v0.1 migration,
pause/resume, cancel, and terminal stop reasons."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import lifecycle as lc                            # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES, main as cli_main             # noqa: E402
from origin.controller import ResearchController              # noqa: E402
from origin.domains.base import get_domain                    # noqa: E402
from origin.state import ResearchState                        # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def mk(tmp, name="p", profile="fast"):
    return ResearchState.create(tmp / name, "q", "algobench",
                                PROFILES[profile], Budget(), profile=profile)


class TestLifecycle(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_illegal_transitions_rejected_and_logged_legal_ones(self):
        st = mk(self.tmp)
        with self.assertRaises(lc.IllegalTransition):
            lc.advance(st, lc.EXECUTING)          # CREATED cannot jump to EXECUTING
        with self.assertRaises(lc.IllegalTransition):
            lc.advance(st, "NOT_A_STATE")
        lc.advance(st, lc.VALIDATING)
        lc.advance(st, lc.PLANNING)
        kinds = [e["kind"] for e in st.read_events()]
        self.assertGreaterEqual(kinds.count("transition"), 2)

    def test_terminal_states_are_final_and_carry_stop_reason(self):
        st = mk(self.tmp, "t")
        lc.advance(st, lc.CANCELLED, "cancelled by user")
        self.assertEqual(st.meta["phase"], lc.CANCELLED)
        self.assertEqual(st.meta["stop_reason"], "cancelled by user")
        self.assertIn("ended_at", st.meta)
        with self.assertRaises(lc.IllegalTransition):
            lc.advance(st, lc.PLANNING)

    def test_pause_resume_restores_prior_phase(self):
        st = mk(self.tmp, "pr")
        lc.advance(st, lc.VALIDATING)
        lc.advance(st, lc.PLANNING)
        lc.advance(st, lc.PAUSED, "paused by test")
        self.assertEqual(st.meta["phase"], lc.PAUSED)
        lc.resume(st)
        self.assertEqual(st.meta["phase"], lc.PLANNING)

    def test_steps_flag_pauses_then_resumes_to_completion(self):
        root = self.tmp / "steps"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        cli_main(["run", "--dir", str(root), "--steps", "2"])
        st = ResearchState.load(root)
        self.assertEqual(st.meta["phase"], lc.PAUSED)
        cli_main(["run", "--dir", str(root)])
        st = ResearchState.load(root)
        self.assertEqual(st.meta["phase"], lc.COMPLETED)
        self.assertIn("stop_reason", st.meta)

    def test_paused_mission_resumes_through_the_library_api(self):
        """R-5: only the CLI called lifecycle.resume(), so a PAUSED mission
        resumed programmatically crashed with IllegalTransition."""
        root = self.tmp / "libresume"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        st = ResearchState.load(root)
        ResearchController(st, get_domain("algobench")).run(max_steps=2)
        self.assertEqual(st.meta["phase"], lc.PAUSED)
        st2 = ResearchState.load(root)                 # fresh object, no CLI
        ResearchController(st2, get_domain("algobench")).run()
        self.assertEqual(st2.meta["phase"], lc.COMPLETED)
        self.assertEqual(ResearchState.load(root).verify(), [])

    def test_v01_phase_names_migrate_on_load(self):
        st = mk(self.tmp, "mig")
        st.meta["phase"] = "investigating"      # simulate a v0.1 checkpoint
        st.save()
        st2 = ResearchState.load(st.root)
        self.assertEqual(st2.meta["phase"], lc.SELECTING_NEXT_ACTION)
        self.assertEqual(st2.flags.get("migrated_from"), "investigating")
        # And the archived v0.1 demo (if present) loads read-only as COMPLETED.
        demo = REPO / "examples" / "demo_run"
        if demo.exists():
            d = ResearchState.load(demo)
            self.assertEqual(d.meta["phase"], lc.COMPLETED)

    def test_cancel_command(self):
        root = self.tmp / "can"
        cli_main(["init", "q", "--dir", str(root), "--profile", "fast",
                  "--brain", "none"])
        cli_main(["run", "--dir", str(root), "--steps", "1"])
        rc = cli_main(["cancel", "--dir", str(root)])
        self.assertEqual(rc, 0)
        st = ResearchState.load(root)
        self.assertEqual(st.meta["phase"], lc.CANCELLED)
        # run refuses to continue a terminal mission
        rc = cli_main(["run", "--dir", str(root)])
        self.assertEqual(rc, 0)
        self.assertEqual(ResearchState.load(root).meta["phase"], lc.CANCELLED)


if __name__ == "__main__":
    unittest.main()
