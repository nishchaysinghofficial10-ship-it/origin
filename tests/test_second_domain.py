"""Second research domain (graphbench) and domain-neutrality tests.

The point of a second domain is not "more features" — it is a check on whether
ORIGIN's core is genuinely domain-agnostic. These tests assert both: that
graphbench does real research end to end, and that it does so *through the same
core* as algobench with no domain-specific branching in the controller, state,
budget, critic, reporting or autonomy layers.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import autonomy as A                              # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES, main as cli_main             # noqa: E402
from origin.controller import ResearchController              # noqa: E402
from origin.domains import graphbench as G                    # noqa: E402
from origin.domains.base import get_domain                    # noqa: E402
from origin.models import EpistemicStatus                     # noqa: E402
from origin.replay import ReplayPolicy, compare_results       # noqa: E402
from origin.scheduler import Scheduler                        # noqa: E402
from origin.state import ResearchState                        # noqa: E402


def graph_mission(tmp, name="g", profile="graph_fast", experiments=12):
    st = ResearchState.create(tmp / name,
                              "Which shortest-path method wins on which graph "
                              "topology, and where is BFS correct?",
                              "graphbench", PROFILES[profile],
                              Budget(experiments_total=experiments,
                                     compute_seconds_total=900),
                              profile=profile)
    st.meta["brain"] = "none"
    st.save()
    return st


class TestGraphAlgorithms(unittest.TestCase):
    """The candidates themselves must be right before any research about them
    means anything."""

    def test_all_weighted_candidates_agree_with_the_reference(self):
        for regime, gen in G.GENERATORS.items():
            adj = gen(64, 7)
            n = len(adj)
            reference, _ = G.dijkstra_heap(n, adj, 0)
            for name in G.BASE_ROSTER:
                fn = G.ALGORITHMS[name][-1]
                dist, relax = fn(n, adj, 0)
                self.assertEqual(list(dist), reference,
                                 f"{name} disagrees on {regime}")
                self.assertGreater(relax, 0, f"{name} counted no relaxations")

    def test_bfs_is_correct_only_on_unit_weights(self):
        unit = G.gen_unit_weight(64, 3)
        ref_unit, _ = G.dijkstra_heap(len(unit), unit, 0)
        bfs_unit_dist, _ = G.bfs_unit(len(unit), unit, 0)
        self.assertEqual(list(bfs_unit_dist), ref_unit)

        weighted = G.gen_sparse_random(64, 3)
        ref_w, _ = G.dijkstra_heap(len(weighted), weighted, 0)
        bfs_w, _ = G.bfs_unit(len(weighted), weighted, 0)
        self.assertNotEqual(list(bfs_w), ref_w,
                            "the correctness boundary must be real")

    def test_generators_are_deterministic_and_connected(self):
        for regime, gen in G.GENERATORS.items():
            a1, a2 = gen(48, 11), gen(48, 11)
            self.assertEqual([sorted(e) for e in a1], [sorted(e) for e in a2],
                             f"{regime} is not deterministic")
            dist, _ = G.dijkstra_heap(len(a1), a1, 0)
            self.assertTrue(all(d != float("inf") for d in dist),
                            f"{regime} produced an unreachable vertex")

    def test_relaxation_counts_are_machine_independent(self):
        adj = G.gen_sparse_random(96, 5)
        n = len(adj)
        counts = [G.spfa(n, adj, 0)[1] for _ in range(3)]
        self.assertEqual(len(set(counts)), 1,
                         "a relaxation count must not vary run to run")


class TestGraphMissionEndToEnd(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_full_mission_produces_scoped_conclusions(self):
        st = graph_mission(self.tmp)
        ResearchController(st, get_domain("graphbench")).run()
        self.assertEqual(st.meta["phase"], "COMPLETED")
        self.assertTrue(st.meta.get("stop_reason"))
        self.assertGreaterEqual(len(st.hypotheses), 5)
        self.assertGreater(len(st.evidence), 0)
        self.assertEqual(st.verify(), [])
        # Every Evidence item still comes from an experiment.
        for e in st.evidence.values():
            self.assertTrue(e.experiment_id)
        # Accepted conclusions carry an explicit scope.
        for h in st.hypotheses.values():
            if h.status.value == "accepted_with_scope":
                self.assertTrue(h.scope)
                self.assertIn("replicated", h.tags)

    def test_incorrect_candidate_is_recorded_and_excluded(self):
        st = graph_mission(self.tmp, "g2")
        ResearchController(st, get_domain("graphbench")).run()
        wrong = [f for f in st.failures if f.get("kind") == "incorrect_output"]
        self.assertTrue(wrong, "the BFS correctness boundary must be detected")
        self.assertTrue(all("bfs_unit" in f["observed"] for f in wrong))
        # ...and a wrong candidate is never named the fastest on that topology.
        for e in st.evidence.values():
            if "fastest on" in e.summary and "bfs_unit" in e.summary:
                self.assertIn("INCORRECT", e.summary + " ")

    def test_machine_independent_claim_is_recorded(self):
        st = graph_mission(self.tmp, "g3")
        ResearchController(st, get_domain("graphbench")).run()
        claims = [c for c in st.claims.values()
                  if c.status == EpistemicStatus.EXPERIMENTAL_RESULT]
        self.assertTrue(any("relaxations" in c.text for c in claims))
        self.assertTrue(any("machine-independent" in c.text for c in claims))

    def test_results_use_schema_v2_with_relaxations(self):
        st = graph_mission(self.tmp, "g4")
        ResearchController(st, get_domain("graphbench")).run()
        rec = next(r for r in st.experiments.values() if r.status == "completed")
        res = json.loads((rec.path(st.root) / "result.json").read_text())
        self.assertEqual(res["schema_version"], 2)
        self.assertIn("environment", res)
        for row in res["rows"]:
            self.assertIn("relaxations", row)
            self.assertIn("input_digest", row)
            self.assertEqual(len(row["samples"]), row["trials"])

    def test_graph_experiment_replays(self):
        st = graph_mission(self.tmp, "g5")
        ResearchController(st, get_domain("graphbench")).run()
        exp = next(r.id for r in st.experiments.values()
                   if r.status == "completed")
        self.assertEqual(cli_main(["replay", "--dir", str(st.root),
                                   "--exp", exp]), 0)

    def test_replay_detects_a_tampered_graph_result(self):
        st = graph_mission(self.tmp, "g6")
        ResearchController(st, get_domain("graphbench")).run()
        rec = next(r for r in st.experiments.values() if r.status == "completed")
        path = rec.path(st.root) / "result.json"
        data = json.loads(path.read_text())
        data["rows"][0]["output_digest"] = "tampered00000000"
        path.write_text(json.dumps(data))
        self.assertEqual(cli_main(["replay", "--dir", str(st.root),
                                   "--exp", rec.id]), 1)


class TestDomainNeutrality(unittest.TestCase):
    """The core must not know which domain it is running."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_core_modules_do_not_mention_a_specific_domain(self):
        root = Path(__file__).resolve().parents[1] / "origin"
        for name in ("controller.py", "state.py", "budget.py", "critic.py",
                     "report.py", "scheduler.py", "autonomy.py", "replay.py",
                     "stats.py", "graph.py", "lifecycle.py"):
            text = (root / name).read_text()
            for domain in ("algobench", "graphbench", "merge_sort",
                           "dijkstra"):
                self.assertNotIn(domain, text,
                                 f"{name} references the domain-specific name "
                                 f"{domain!r}; the core must stay agnostic")

    def test_both_domains_run_through_the_same_controller(self):
        algo = ResearchState.create(self.tmp / "a", "sorting?", "algobench",
                                    PROFILES["fast"], Budget(), "fast")
        algo.meta["brain"] = "none"
        ResearchController(algo, get_domain("algobench")).run()
        graph = graph_mission(self.tmp, "b")
        ResearchController(graph, get_domain("graphbench")).run()
        for st in (algo, graph):
            self.assertEqual(st.meta["phase"], "COMPLETED")
            self.assertEqual(st.verify(), [])
            self.assertTrue(st.decisions)
            self.assertTrue((st.root / "reports" / "dossier.md").exists())
        # Same report machinery, same sections, different content.
        a_doss = (algo.root / "reports" / "dossier.md").read_text()
        g_doss = (graph.root / "reports" / "dossier.md").read_text()
        for section in ("Prediction ledger", "Falsification attempts",
                        "Budget ledger", "Threats to validity",
                        "Measurement environment and scope"):
            self.assertIn(section, a_doss)
            self.assertIn(section, g_doss)
        self.assertIn("dijkstra", g_doss)
        self.assertNotIn("dijkstra", a_doss)

    def test_autonomy_schedules_the_new_domain_unchanged(self):
        st = graph_mission(self.tmp, "auto")
        s = Scheduler(st.root, A.RunLimits(max_steps=12, max_wall_s=180))
        out = s.run()
        self.assertIn(out["stop"], (A.COMPLETED, A.NO_WORK, A.STEP_LIMIT))
        self.assertGreater(out["steps"], 0)
        reloaded = ResearchState.load(st.root)
        self.assertEqual(reloaded.verify(), [])
        self.assertGreater(reloaded.budget.experiments_used, 0)
        # The queue used only the generic action vocabulary.
        for item in s.store.items.values():
            self.assertIn(item.action, A.ACTION_TYPES)

    def test_domain_registry_reports_both(self):
        for name in ("algobench", "graphbench"):
            self.assertEqual(get_domain(name).name, name)
        with self.assertRaises(KeyError):
            get_domain("no_such_domain")

    def test_replay_engine_is_shared_and_domain_blind(self):
        st = graph_mission(self.tmp, "shared")
        ResearchController(st, get_domain("graphbench")).run()
        rec = next(r for r in st.experiments.values() if r.status == "completed")
        stored = json.loads((rec.path(st.root) / "result.json").read_text())
        rep = compare_results(stored, json.loads(json.dumps(stored)),
                              ReplayPolicy())
        self.assertEqual(rep.hard_failures, [])
        self.assertGreater(rep.integrity["output_digests"], 0)


if __name__ == "__main__":
    unittest.main()


class TestCoreConceptsFromGapAnalysis(unittest.TestCase):
    """v2.1: the two gaps `graphbench` exposed, now closed in the core."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    # ---- gap 7: metrics declare what they are -------------------------
    def test_exact_metrics_skip_the_timing_noise_gate(self):
        from origin import stats
        # As timings, one trial each and a 1% margin would be indistinguishable.
        timing = stats.compare({"mean_s": 100.0, "trials": 1, "sem_s": 0.0},
                               {"mean_s": 101.0, "trials": 1, "sem_s": 0.0})
        self.assertFalse(timing["decisive"])
        # As exact counts, a difference of one is a real difference of one.
        exact = stats.compare({"mean_s": 100.0}, {"mean_s": 101.0},
                              metric_kind=stats.EXACT)
        self.assertTrue(exact["decisive"])
        self.assertEqual(exact["relation"], stats.FASTER)
        self.assertEqual(exact["metric_kind"], stats.EXACT)
        # ...and an exact tie is honestly a tie.
        tie = stats.compare({"mean_s": 7.0}, {"mean_s": 7.0},
                            metric_kind=stats.EXACT)
        self.assertFalse(tie["decisive"])
        self.assertIn("exact tie", tie["reason"])

    def test_domain_declares_its_metric_kinds(self):
        from origin import stats
        domain = get_domain("graphbench")
        self.assertEqual(domain.metric_kinds["relaxations"], stats.EXACT)
        self.assertEqual(domain.metric_kinds["mean_s"], stats.TIMING)
        # A domain that measures only time needs no declaration.
        self.assertEqual(get_domain("algobench").metric_kinds["mean_s"],
                         stats.TIMING)

    # ---- gap 8: invalidity is a core concept --------------------------
    def test_invalidity_is_recorded_and_enforced_by_the_core(self):
        st = graph_mission(self.tmp, "inv")
        st.record_invalidity("bfs_unit", "sparse_random", "wrong distances")
        self.assertFalse(st.is_valid("bfs_unit", "sparse_random"))
        self.assertTrue(st.is_valid("bfs_unit", "unit_weight"))
        self.assertEqual(
            st.valid_candidates(["dijkstra_heap", "bfs_unit"], "sparse_random"),
            ["dijkstra_heap"])
        # Idempotent, and it survives a reload.
        first = len(st.invalidities)
        st.record_invalidity("bfs_unit", "sparse_random", "again")
        self.assertEqual(len(st.invalidities), first)
        st.save()
        self.assertFalse(ResearchState.load(st.root)
                         .is_valid("bfs_unit", "sparse_random"))

    def test_a_wildcard_invalidity_excludes_everywhere(self):
        st = graph_mission(self.tmp, "inv2")
        st.record_invalidity("broken", "*", "wrong under every condition")
        for condition in ("sparse_random", "grid_2d", "anything"):
            self.assertFalse(st.is_valid("broken", condition))

    def test_a_real_mission_records_invalidities_through_the_core(self):
        st = graph_mission(self.tmp, "inv3")
        ResearchController(st, get_domain("graphbench")).run()
        self.assertTrue(st.invalidities, "the BFS boundary must be recorded")
        for inv in st.invalidities.values():
            self.assertEqual(inv.candidate, "bfs_unit")
            self.assertIn(inv.experiment_id, st.experiments)
        self.assertTrue(st.is_valid("bfs_unit", "unit_weight"))
        self.assertEqual(ResearchState.load(st.root).verify(), [])

    def test_dossier_publishes_validity_boundaries_and_metric_kinds(self):
        st = graph_mission(self.tmp, "inv4")
        ResearchController(st, get_domain("graphbench")).run()
        dossier = (st.root / "reports" / "dossier.md").read_text()
        self.assertIn("Candidate validity boundaries", dossier)
        self.assertIn("bfs_unit", dossier)
        self.assertIn("exact metric", dossier)
        self.assertIn("relaxations", dossier)

    def test_verify_catches_an_invalidity_citing_a_ghost_experiment(self):
        st = graph_mission(self.tmp, "inv5")
        st.record_invalidity("x", "y", "reason", experiment_id="exp_ghost")
        st.save()
        problems = ResearchState.load(st.root).verify()
        self.assertTrue(any("unknown experiment" in p for p in problems))
