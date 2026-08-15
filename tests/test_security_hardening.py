"""Security hardening regression tests (v1.7 pass).

Red-teams the surfaces added since the v1.0 review — the second domain, the
autonomy layer, and report claims — against the same standard as the rest:
attempt the attack, assert the refusal, and keep the evidence.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import autonomy as A                              # noqa: E402
from origin import sandbox                                    # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES, main as cli_main             # noqa: E402
from origin.controller import ResearchController              # noqa: E402
from origin.domains.base import get_domain                    # noqa: E402
from origin.experiments import ExperimentEngine               # noqa: E402
from origin.models import HypothesisStatus                    # noqa: E402
from origin.scheduler import Scheduler                        # noqa: E402
from origin.state import ResearchState                        # noqa: E402

FAKE_KEY = "sk-ant-redteam-not-a-real-key-0123456789"


def mission(tmp, name="m", domain="graphbench", profile="graph_fast"):
    st = ResearchState.create(tmp / name, "security probe", domain,
                              PROFILES[profile],
                              Budget(experiments_total=6,
                                     compute_seconds_total=300),
                              profile=profile)
    st.meta["brain"] = "none"
    st.save()
    return st


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()
        os.environ.pop("ANTHROPIC_API_KEY", None)


class TestSecondDomainExecutionSafety(Base):
    """A new domain must not become a new way to run arbitrary code."""

    def test_graph_designs_still_face_the_sandbox_gate(self):
        st = mission(self.tmp)
        engine = ExperimentEngine(st, get_domain("graphbench"))
        unsafe = {"kind": "benchmark", "round": 1,
                  "algorithms": ["dijkstra_heap"], "regimes": ["sparse_random"],
                  "sizes": [10 ** 7], "trials": 99, "seed": 1,
                  "timeout_s": 99_999, "hypothesis_ids": []}
        rec = engine.run(unsafe, title="unsafe graph design")
        self.assertEqual(rec.status, "rejected")
        self.assertIn("unsafe design", rec.error)
        self.assertEqual(st.budget.experiments_used, 0)
        self.assertFalse((Path(st.root) / "experiments" / rec.id).exists())

    def test_generated_graph_runner_has_no_dangerous_capability(self):
        st = mission(self.tmp, "m2")
        ResearchController(st, get_domain("graphbench")).run()
        rec = next(r for r in st.experiments.values() if r.status == "completed")
        code = (rec.path(st.root) / "run.py").read_text()
        for banned in ("subprocess", "os.system", "socket", "urllib",
                       "eval(", "exec(", "__import__(", "open('/", 'open("/'):
            self.assertNotIn(banned, code, f"runner contains {banned!r}")
        self.assertNotIn("ANTHROPIC", code)

    def test_graph_runner_environment_is_scrubbed(self):
        os.environ["ANTHROPIC_API_KEY"] = FAKE_KEY
        st = mission(self.tmp, "m3")
        ResearchController(st, get_domain("graphbench")).run()
        rec = next(r for r in st.experiments.values() if r.status == "completed")
        for name in ("stdout.log", "result.json", "run.py", "spec.json"):
            path = rec.path(st.root) / name
            if path.exists():
                self.assertNotIn(FAKE_KEY, path.read_text(errors="replace"))

    def test_domain_config_cannot_widen_sandbox_limits(self):
        """A mission spec is semi-trusted input: it may request, not decide."""
        st = mission(self.tmp, "m4")
        st.meta["domain_config"]["timeout_s"] = 99_999
        st.meta["domain_config"]["sizes"] = [10 ** 7]
        st.save()
        ResearchController(st, get_domain("graphbench")).run()
        for rec in st.experiments.values():
            if rec.status == "completed":
                self.fail("an over-cap design must never complete")
        # Two independent gates can refuse it, and either is a correct outcome:
        # the cost estimator refuses to afford it, or the sandbox refuses to
        # run it. What must never happen is that it executes.
        refused_by_sandbox = any(f.get("kind") == "unsafe_design"
                                 for f in st.failures)
        refused_by_budget = "budget" in (st.meta.get("stop_reason") or "")
        self.assertTrue(refused_by_sandbox or refused_by_budget,
                        f"neither gate refused it: {st.meta.get('stop_reason')}")
        self.assertEqual(st.budget.experiments_used, 0)
        self.assertEqual(ResearchState.load(st.root).verify(), [])

    def test_a_mission_config_does_not_leak_into_other_missions(self):
        """v1.7 finding: `create()` stored a REFERENCE to the shared PROFILES
        dict, so one mission raising its own timeout silently rewrote the
        default for every later mission in the same process."""
        import copy as _copy
        from origin.cli import PROFILES as _PROFILES
        pristine = _copy.deepcopy(_PROFILES["graph_fast"])
        first = mission(self.tmp, "leak1")
        first.meta["domain_config"]["timeout_s"] = 99_999
        first.meta["domain_config"]["sizes"] = [10 ** 7]
        first.save()
        self.assertEqual(_PROFILES["graph_fast"], pristine,
                         "a mission mutated the shared profile table")
        second = mission(self.tmp, "leak2")
        self.assertEqual(second.meta["domain_config"]["timeout_s"],
                         pristine["timeout_s"])
        self.assertEqual(second.meta["domain_config"]["sizes"],
                         pristine["sizes"])


class TestAutonomyResourceSafety(Base):
    def test_autonomy_cannot_exceed_the_mission_experiment_budget(self):
        st = mission(self.tmp, "b1")
        st.budget.experiments_total = 2
        st.save()
        Scheduler(st.root, A.RunLimits(max_steps=25, max_wall_s=120)).run()
        reloaded = ResearchState.load(st.root)
        self.assertLessEqual(reloaded.budget.experiments_used, 2)

    def test_autonomy_state_cannot_grant_itself_authority(self):
        """Hand-editing the durable queue must not enable network or provider
        access, which are per-run operator grants, not item properties."""
        st = mission(self.tmp, "b2")
        s = Scheduler(st.root, A.RunLimits(max_steps=4, max_wall_s=60))
        item, _ = s.store.add(A.new_item(
            A.RETRIEVE_SOURCE, "self-granted", priority=0.99,
            params={"url": "https://fixtures.invalid/x"}))
        item.requires_network = False          # the tamper
        item.approved_by = "self"
        s.store.save()
        reloaded = A.AutonomyStore(st.root)
        decision = A.AutonomyPolicy(A.RunLimits(), allow_network=False).evaluate(
            reloaded, st)
        chosen = decision["chosen"]
        if chosen == item.id:
            # If the flag tamper let it be selected, execution must still refuse.
            out = Scheduler(st.root, A.RunLimits(max_steps=1, max_wall_s=30)
                            ).tick(state=st)
            self.assertFalse(out.get("acted") and out.get("status") == A.DONE)
        self.assertEqual(st.flags.get("retrievals_used", 0), 0)

    def test_lease_file_is_not_world_writable(self):
        st = mission(self.tmp, "b3")
        lease = A.MissionLease(st.root)
        lease.acquire()
        try:
            mode = oct(lease.path.stat().st_mode)[-3:]
            self.assertEqual(mode, "600", f"lease mode is {mode}")
        finally:
            lease.release(lease.owner)

    def test_autonomy_artifacts_contain_no_secrets(self):
        os.environ["ANTHROPIC_API_KEY"] = FAKE_KEY
        st = mission(self.tmp, "b4")
        Scheduler(st.root, A.RunLimits(max_steps=6, max_wall_s=90)).run()
        for name in ("state.json", "decisions.jsonl"):
            path = st.root / "autonomy" / name
            if path.exists():
                text = path.read_text()
                self.assertNotIn(FAKE_KEY, text)
                self.assertNotIn("sk-ant-", text)


class TestReportClaimsMatchStoredTruth(Base):
    """A report that overstates is a security defect, not a cosmetic one."""

    def test_dossier_never_calls_an_incorrect_candidate_a_winner(self):
        st = mission(self.tmp, "r1")
        ResearchController(st, get_domain("graphbench")).run()
        dossier = (st.root / "reports" / "dossier.md").read_text()
        wrong = {f["observed"].split()[0] for f in st.failures
                 if f.get("kind") == "incorrect_output"}
        self.assertTrue(wrong)
        for candidate in wrong:
            for line in dossier.splitlines():
                if candidate in line and "fastest" in line.lower():
                    self.assertIn("INCORRECT", line.upper(),
                                  f"dossier calls {candidate} fastest without "
                                  f"noting it was wrong: {line}")

    def test_accepted_conclusions_in_the_dossier_are_backed_by_state(self):
        st = mission(self.tmp, "r2")
        ResearchController(st, get_domain("graphbench")).run()
        dossier = (st.root / "reports" / "dossier.md").read_text()
        accepted = [h for h in st.hypotheses.values()
                    if h.status == HypothesisStatus.ACCEPTED_WITH_SCOPE]
        for h in accepted:
            self.assertIn(h.statement, dossier)
            self.assertTrue(h.scope)
            self.assertIn("replicated", h.tags)
        if "Accepted with scope" in dossier:
            self.assertTrue(accepted)

    def test_dossier_states_scope_and_does_not_universalise(self):
        st = mission(self.tmp, "r3")
        ResearchController(st, get_domain("graphbench")).run()
        text = (st.root / "reports" / "dossier.md").read_text().lower()
        for overclaim in ("universally faster", "always faster",
                          "the best algorithm", "proven optimal"):
            self.assertNotIn(overclaim, text)
        self.assertIn("scoped to", text)


class TestTamperedArtifacts(Base):
    def test_tampered_experiment_result_is_detected_by_replay(self):
        st = mission(self.tmp, "t1")
        ResearchController(st, get_domain("graphbench")).run()
        rec = next(r for r in st.experiments.values() if r.status == "completed")
        path = rec.path(st.root) / "result.json"
        data = json.loads(path.read_text())
        for row in data["rows"]:
            row["correct"] = True              # claim the wrong ones were right
        path.write_text(json.dumps(data))
        self.assertEqual(cli_main(["replay", "--dir", str(st.root),
                                   "--exp", rec.id]), 1)

    def test_tampered_runner_is_detected_by_replay(self):
        st = mission(self.tmp, "t2")
        ResearchController(st, get_domain("graphbench")).run()
        rec = next(r for r in st.experiments.values() if r.status == "completed")
        runner = rec.path(st.root) / "run.py"
        runner.write_text(runner.read_text() + "\n# silently edited\n")
        self.assertEqual(cli_main(["replay", "--dir", str(st.root),
                                   "--exp", rec.id]), 1)

    def test_deleted_artifact_fails_verify_rather_than_passing_quietly(self):
        st = mission(self.tmp, "t3")
        ResearchController(st, get_domain("graphbench")).run()
        rec = next(r for r in st.experiments.values() if r.status == "completed")
        (rec.path(st.root) / "result.json").unlink()
        problems = ResearchState.load(st.root).verify()
        self.assertTrue(any("result.json missing" in p for p in problems))
        self.assertEqual(cli_main(["verify", "--dir", str(st.root)]), 1)


class TestSandboxClaimsMatchControls(Base):
    """Documentation must not describe controls the code does not implement."""

    def test_sandbox_policy_enforces_every_documented_limit(self):
        policy = sandbox.DEFAULT_POLICY
        for key in ("max_timeout_s", "mem_mb", "fsize_mb", "nproc",
                    "output_cap_bytes", "max_input_size", "max_trials"):
            self.assertIn(key, policy)
        violations = sandbox.validate_design(
            {"timeout_s": policy["max_timeout_s"] + 1,
             "sizes": [policy["max_input_size"] + 1],
             "trials": policy["max_trials"] + 1})
        self.assertEqual(len(violations), 3, violations)

    def test_documentation_does_not_claim_kernel_grade_isolation(self):
        root = Path(__file__).resolve().parents[1]
        for doc in ("docs/SECURITY.md", "docs/security/THREAT_MODEL.md",
                    "docs/security/SECURITY_REVIEW.md", "README.md"):
            path = root / doc
            if not path.exists():
                continue
            text = path.read_text().lower()
            for overclaim in ("kernel-grade sandbox", "kernel-level isolation",
                              "fully isolated sandbox", "complete isolation"):
                # The phrase may appear only as an explicit disclaimer.
                for line in text.splitlines():
                    if overclaim in line:
                        self.assertTrue(
                            any(w in line for w in
                                ("not ", "no ", "never", "cannot", "unavailable",
                                 "without")),
                            f"{doc} claims {overclaim!r}: {line}")


class TestPublicArtifactClaims(Base):
    """Defects found by the clean-room onboarding test."""

    def test_dossier_reports_the_real_version(self):
        """The dossier header was hardcoded to "ORIGIN v1.0" for five releases —
        a stale claim printed on every public artifact."""
        import origin
        st = mission(self.tmp, "v1")
        ResearchController(st, get_domain("graphbench")).run()
        header = (st.root / "reports" / "dossier.md").read_text().splitlines()[2]
        self.assertIn(f"v{origin.__version__}", header)
        self.assertNotIn("v1.0 ", header)

    def test_cli_survives_a_closed_pipe(self):
        """`origin report | head` printed a BrokenPipeError traceback."""
        import subprocess
        st = mission(self.tmp, "v2")
        ResearchController(st, get_domain("graphbench")).run()
        repo = Path(__file__).resolve().parents[1]
        proc = subprocess.run(
            f'python3 -m origin report --dir "{st.root}" | head -3',
            shell=True, cwd=str(repo), capture_output=True, text=True,
            timeout=120)
        self.assertNotIn("BrokenPipeError", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)

    def test_shipped_examples_all_verify(self):
        repo = Path(__file__).resolve().parents[1]
        found = 0
        for example in sorted((repo / "examples").iterdir()):
            if not (example / "state.json").exists():
                continue
            found += 1
            self.assertEqual(ResearchState.load(example).verify(), [],
                             f"{example.name} does not verify")
        self.assertGreater(found, 0)


if __name__ == "__main__":
    unittest.main()
