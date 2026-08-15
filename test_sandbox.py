"""Sandbox/confinement tests: unsafe designs rejected with logged reasons and
no execution; resource limits actually kill offenders; output caps hold; the
child environment carries no secrets."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import sandbox                                    # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES                               # noqa: E402
from origin.domains.base import get_domain                    # noqa: E402
from origin.experiments import ExperimentEngine               # noqa: E402
from origin.state import ResearchState                        # noqa: E402


class TestSandboxPolicy(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.st = ResearchState.create(self.tmp / "p", "q", "algobench",
                                       PROFILES["fast"], Budget(), "fast")
        self.eng = ExperimentEngine(self.st, get_domain("algobench"))

    def tearDown(self):
        self._td.cleanup()

    def test_validate_design_flags_violations(self):
        bad = {"timeout_s": 99999, "sizes": [10**8, -3], "trials": 400}
        probs = sandbox.validate_design(bad)
        joined = " ".join(probs)
        self.assertIn("timeout_s", joined)
        self.assertIn("exceeds policy max", joined)
        self.assertIn("trials", joined)
        self.assertEqual(sandbox.validate_design(
            {"timeout_s": 60, "sizes": [100], "trials": 3}), [])

    def test_unsafe_design_rejected_without_execution(self):
        exp_before = self.st.budget.experiments_used
        design = {"kind": "benchmark", "round": 1,
                  "algorithms": ["insertion_sort"], "regimes": ["random"],
                  "sizes": [64], "trials": 3, "seed": 1,
                  "timeout_s": 10_000,             # over policy cap
                  "hypothesis_ids": []}
        rec = self.eng.run(design, title="unsafe")
        self.assertEqual(rec.status, "rejected")
        self.assertIn("unsafe design", rec.error)
        self.assertEqual(self.st.budget.experiments_used, exp_before)  # no charge
        self.assertFalse((Path(self.st.root) / "experiments" / rec.id).exists())
        kinds = [e["kind"] for e in self.st.read_events()]
        self.assertIn("experiment_rejected", kinds)
        self.assertNotIn("experiment_started", kinds)
        self.assertTrue(any(f.get("kind") == "unsafe_design"
                            for f in self.st.failures))

    def test_memory_limit_kills_allocation_bomb(self):
        script = self.tmp / "bomb.py"
        script.write_text("x = bytearray(2_000_000_000)\nprint('survived')\n")
        proc = subprocess.run(
            [sys.executable, "-I", str(script)], cwd=str(self.tmp),
            capture_output=True, text=True, timeout=30,
            env=sandbox.scrubbed_env(str(self.tmp)),
            preexec_fn=sandbox.make_preexec(10, {"mem_mb": 128}))
        self.assertNotEqual(proc.returncode, 0)
        self.assertNotIn("survived", proc.stdout)

    def test_output_flood_is_truncated(self):
        flood = "A" * 5_000_000
        capped = sandbox.truncate_output(flood)
        self.assertLess(len(capped.encode()), 300_000)
        self.assertIn("truncated", capped)

    def test_child_env_is_scrubbed_of_secrets(self):
        script = self.tmp / "env.py"
        script.write_text("import os, json; print(json.dumps(dict(os.environ)))")
        proc = subprocess.run(
            [sys.executable, "-I", str(script)], capture_output=True, text=True,
            timeout=30, cwd=str(self.tmp),
            env={**sandbox.scrubbed_env(str(self.tmp))},
        )
        child_env = json.loads(proc.stdout)
        for banned in ("ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY",
                       "HTTP_PROXY", "HTTPS_PROXY"):
            self.assertNotIn(banned, child_env)
        self.assertEqual(child_env.get("PYTHONDONTWRITEBYTECODE"), "1")

    def test_failed_experiment_leaves_state_consistent(self):
        # Even a genuinely crashing run must not corrupt mission state.
        class CrashDomain:
            name = "crash"
            def write_runner(self, design, exp_dir):
                p = exp_dir / "run.py"
                p.write_text("raise RuntimeError('boom')\n")
                return p
        design = {"kind": "benchmark", "round": 1, "algorithms": [],
                  "regimes": [], "sizes": [8], "trials": 1, "seed": 1,
                  "timeout_s": 30, "hypothesis_ids": []}
        eng = ExperimentEngine(self.st, CrashDomain())
        rec = eng.run(design, title="crash test")
        self.assertEqual(rec.status, "failed")
        self.assertIn("boom", rec.error)
        self.st.save()
        st2 = ResearchState.load(self.st.root)
        self.assertEqual(st2.verify(), [])
        self.assertEqual(st2.experiments[rec.id].status, "failed")


if __name__ == "__main__":
    unittest.main()
