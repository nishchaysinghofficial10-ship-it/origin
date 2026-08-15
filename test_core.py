"""ORIGIN v0.1 test suite (stdlib unittest — no dependencies).

Run:  python -m unittest discover -s tests -v
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin.budget import Budget                       # noqa: E402
from origin.cli import PROFILES                        # noqa: E402
from origin.controller import ResearchController      # noqa: E402
from origin.domains.base import get_domain             # noqa: E402
from origin.graph import KnowledgeGraph                # noqa: E402
from origin.models import (EpistemicStatus, Claim, Hypothesis,  # noqa: E402
                           HypothesisStatus, new_id)
from origin.state import ResearchState                 # noqa: E402


class TestBudget(unittest.TestCase):
    def test_accounting_and_exhaustion(self):
        b = Budget(experiments_total=2, compute_seconds_total=10)
        self.assertTrue(b.can_run_experiment(1))
        b.charge_experiment(4.0)
        b.charge_experiment(4.0)
        self.assertFalse(b.can_run_experiment(1))       # experiment count exhausted
        b2 = Budget(experiments_total=10, compute_seconds_total=5)
        self.assertFalse(b2.can_run_experiment(6.0))    # compute exhausted


class TestGraph(unittest.TestCase):
    def test_contradiction_detection(self):
        g = KnowledgeGraph()
        a = g.entity("alg_a", "algorithm")
        b = g.entity("alg_b", "algorithm")
        r = g.entity("random", "input_regime")
        g.add_relation(a, "fastest_on", r, 0.8)
        self.assertEqual(len(g.contradictions), 0)
        g.add_relation(a, "fastest_on", r, 0.9)          # merge, not duplicate
        self.assertEqual(len(g.relations), 1)
        g.add_relation(b, "fastest_on", r, 0.7)          # conflicting subject
        self.assertEqual(len(g.contradictions), 1)

    def test_roundtrip(self):
        g = KnowledgeGraph()
        a = g.entity("x", "thing")
        g.add_relation(a, "related_to", g.entity("y", "thing"), 0.5, ["ev1"])
        g2 = KnowledgeGraph.from_dict(g.to_dict())
        self.assertEqual(len(g2.relations), 1)
        self.assertEqual(g2.entity("x", "thing"), a)     # dedupe survives reload


class TestStatePersistence(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_roundtrip_and_resume(self):
        st = ResearchState.create(self.tmp / "p", "test question", "algobench",
                                  PROFILES["fast"], Budget(), profile="fast")
        h = Hypothesis(id=new_id("hyp"), statement="s", rationale="r")
        st.add(h)
        st.add(Claim(id=new_id("clm"), text="c", status=EpistemicStatus.FACT, confidence=0.9))
        st.log_event("test", "hello")
        st.step = 3
        st.save()

        st2 = ResearchState.load(self.tmp / "p")
        self.assertEqual(st2.step, 3)
        self.assertEqual(len(st2.hypotheses), 1)
        self.assertIsInstance(next(iter(st2.hypotheses.values())).status, HypothesisStatus)
        self.assertIsInstance(next(iter(st2.claims.values())).status, EpistemicStatus)
        self.assertEqual(st2.read_events()[-1]["msg"], "hello")
        # browsable views exist
        self.assertTrue((self.tmp / "p" / "research_state" / "hypotheses.json").exists())


class TestEndToEnd(unittest.TestCase):
    """A full autonomous run on the fast profile: plan -> hypotheses ->
    experiments -> analysis -> critic replication -> synthesis."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_full_run(self):
        root = self.tmp / "proj"
        st = ResearchState.create(root, "Which sort wins per regime?", "algobench",
                                  PROFILES["fast"], Budget(experiments_total=8,
                                                           compute_seconds_total=600),
                                  profile="fast")
        domain = get_domain("algobench")
        ResearchController(st, domain).run()

        self.assertEqual(st.meta["phase"], "COMPLETED")
        self.assertGreaterEqual(len(st.hypotheses), 5)   # 4 base + 1 generated
        self.assertGreaterEqual(len(st.experiments), 2)  # round1 + round2 (+ replications)
        self.assertTrue(any("generated" in h.tags for h in st.hypotheses.values()))
        resolved = [h for h in st.hypotheses.values()
                    if h.status != HypothesisStatus.PROPOSED]
        self.assertEqual(len(resolved), len(st.hypotheses))
        self.assertTrue((root / "reports" / "dossier.md").exists())
        self.assertTrue((root / "reports" / "timeline.md").exists())
        self.assertGreater(len(st.read_events()), 10)
        self.assertGreater(len(st.decisions), 0)

        # resume after "shutdown": load and confirm nothing is lost
        st2 = ResearchState.load(root)
        self.assertEqual(st2.meta["phase"], "COMPLETED")
        self.assertEqual(len(st2.evidence), len(st.evidence))

        # every experiment's generated code is preserved and self-contained
        for rec in st2.experiments.values():
            # v1.1: artifact references are ROOT-RELATIVE, resolved via the
            # project root, so a copied/unpacked project stays valid.
            self.assertFalse(Path(rec.dir).is_absolute(), rec.dir)
            self.assertTrue((st.experiment_dir(rec) / "run.py").exists())
            self.assertTrue((st.experiment_dir(rec) / "spec.json").exists())

    def test_budget_stops_research(self):
        # An exhaustable-but-valid budget stops cleanly with a recorded reason.
        root = self.tmp / "proj2"
        st = ResearchState.create(root, "q", "algobench", PROFILES["fast"],
                                  Budget(experiments_total=1,
                                         compute_seconds_total=0.0001),
                                  profile="fast")
        domain = get_domain("algobench")
        ResearchController(st, domain).run()
        self.assertEqual(st.budget.experiments_used, 0)
        self.assertEqual(st.meta["phase"], "COMPLETED")   # synthesizes what it has
        self.assertIn("budget", st.meta.get("stop_reason", ""))
        events = json.dumps(st.read_events())
        self.assertIn("budget", events)

    def test_invalid_budget_fails_validation(self):
        # A zero-experiment budget is an invalid mission spec -> FAILED terminal.
        root = self.tmp / "proj3"
        st = ResearchState.create(root, "q", "algobench", PROFILES["fast"],
                                  Budget(experiments_total=0, compute_seconds_total=1),
                                  profile="fast")
        ResearchController(st, get_domain("algobench")).run()
        self.assertEqual(st.meta["phase"], "FAILED")
        self.assertIn("experiments_total", st.meta.get("stop_reason", ""))


if __name__ == "__main__":
    unittest.main()
