"""Performance-reproducibility tests (v1.2).

Covers the three tiers a replay is allowed to claim:
  exact reproducibility  (asserted always)
  statistical reproducibility (reported; asserted only with --strict)
  non-transferable absolute timings (never asserted)

plus result-schema v2 metadata, the conservative significance rule, and
backward compatibility with schema-1 results written by ORIGIN <= v1.1.
"""
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import stats                                       # noqa: E402
from origin.cli import main as cli_main                        # noqa: E402
from origin.controller import ResearchController               # noqa: E402
from origin.domains.base import get_domain                     # noqa: E402
from origin.replay import (ReplayPolicy, compare_results,       # noqa: E402
                           RESULT_SCHEMA_VERSION)
from origin.state import ResearchState                         # noqa: E402

REPO = Path(__file__).resolve().parents[1]


def _mission(root: Path, profile: str = "fast") -> ResearchState:
    cli_main(["init", "perf", "--dir", str(root), "--profile", profile,
              "--brain", "none"])
    st = ResearchState.load(root)
    ResearchController(st, get_domain(st.meta["domain"])).run()
    return st


def _completed(st: ResearchState):
    rec = next(r for r in st.experiments.values() if r.status == "completed")
    path = rec.path(st.root) / "result.json"
    return rec, path, json.loads(path.read_text())


def _cell(mean, trials=7, spread=0.0, correct=True, alg="a", regime="random",
          n=100, inp="i0", out="o0"):
    samples = [mean + (i - (trials - 1) / 2) * spread for i in range(trials)]
    row = {"algorithm": alg, "regime": regime, "n": n, "correct": correct,
           "trials": trials, "samples": samples, "mean_s": mean,
           "median_s": mean, "stdev_s": spread, "min_s": min(samples),
           "input_digest": inp, "output_digest": out}
    return row


def _payload(rows, env=None, code="c0"):
    return {"schema_version": 2, "code_digest": code,
            "reference_workload_s": 0.01,
            "environment": env or {"python_version": "3.12.3",
                                   "python_implementation": "CPython",
                                   "system": "Linux", "machine": "x86_64",
                                   "cpu_count": 8},
            "rows": rows}


# ---------------------------------------------------------------- statistics
class TestConservativeStatistics(unittest.TestCase):
    def test_small_margin_is_never_decisive(self):
        a = stats.row_stats(_cell(0.0100, spread=1e-6))
        b = stats.row_stats(_cell(0.0104, spread=1e-6))   # 4% apart, tight
        v = stats.compare(a, b)
        self.assertFalse(v["decisive"])
        self.assertIn("margin_below_floor", v["reason"])

    def test_overlapping_uncertainty_is_never_decisive(self):
        a = stats.row_stats(_cell(0.010, spread=0.004))   # huge spread
        b = stats.row_stats(_cell(0.013, spread=0.004))
        v = stats.compare(a, b)
        self.assertFalse(v["decisive"])
        self.assertIn("uncertainty_overlap", v["reason"])

    def test_too_few_trials_is_never_decisive(self):
        a = stats.row_stats(_cell(0.010, trials=3, spread=1e-7))
        b = stats.row_stats(_cell(0.100, trials=3, spread=1e-7))  # 10x apart
        v = stats.compare(a, b)
        self.assertFalse(v["decisive"])
        self.assertIn("insufficient_trials", v["reason"])

    def test_large_clean_separation_is_decisive(self):
        a = stats.row_stats(_cell(0.010, spread=1e-5))
        b = stats.row_stats(_cell(0.050, spread=1e-5))
        v = stats.compare(a, b)
        self.assertTrue(v["decisive"])
        self.assertEqual(v["relation"], stats.FASTER)

    def test_indistinguishable_set_reports_ties(self):
        cells = {"c8": stats.row_stats(_cell(0.0100, spread=1e-6)),
                 "c16": stats.row_stats(_cell(0.0102, spread=1e-6)),
                 "c64": stats.row_stats(_cell(0.0500, spread=1e-6))}
        tied = stats.indistinguishable_set(cells)
        self.assertIn("c8", tied)
        self.assertIn("c16", tied)
        self.assertNotIn("c64", tied)

    def test_legacy_rows_without_samples_still_summarize(self):
        legacy = {"algorithm": "a", "regime": "random", "n": 100,
                  "correct": True, "trials": 7, "mean_s": 0.01,
                  "stdev_s": 0.0001}
        s = stats.row_stats(legacy)
        self.assertTrue(s["legacy"])
        self.assertEqual(s["trials"], 7)
        self.assertGreater(s["sem_s"], 0)


# ------------------------------------------------------- replay comparison
class TestReplayTiers(unittest.TestCase):
    def setUp(self):
        self.stored = _payload([
            _cell(0.010, alg="fast_alg", spread=1e-5, inp="i1", out="o1"),
            _cell(0.050, alg="slow_alg", spread=1e-5, inp="i1", out="o2"),
        ])

    def test_identical_replay_passes(self):
        rep = compare_results(self.stored, copy.deepcopy(self.stored))
        self.assertEqual(rep.hard_failures, [])
        self.assertFalse(rep.failed(ReplayPolicy()))
        self.assertEqual(rep.integrity["output_digests"], 2)
        self.assertEqual(rep.integrity["code_digest"], "verified")

    def test_ordinary_timing_noise_does_not_fail(self):
        fresh = copy.deepcopy(self.stored)
        for row in fresh["rows"]:                     # everything 3x slower
            row["samples"] = [s * 3 for s in row["samples"]]
            row["mean_s"] *= 3
        rep = compare_results(self.stored, fresh)
        self.assertEqual(rep.hard_failures, [])
        self.assertFalse(rep.failed(ReplayPolicy()))
        self.assertTrue(rep.timing, "deviation should still be reported")
        self.assertEqual(rep.inversions, [])
        # ...and --strict on a matching environment does fail on it
        self.assertTrue(rep.failed(ReplayPolicy(strict=True)))

    def test_correctness_mismatch_always_fails(self):
        fresh = copy.deepcopy(self.stored)
        fresh["rows"][0]["correct"] = False
        rep = compare_results(self.stored, fresh)
        self.assertTrue(any("correctness" in f for f in rep.hard_failures))
        self.assertTrue(rep.failed(ReplayPolicy()))
        # no tolerance setting can suppress a correctness failure
        self.assertTrue(rep.failed(ReplayPolicy(tolerance=1e9,
                                                noise_floor_ms=1e9)))

    def test_changed_output_digest_fails(self):
        fresh = copy.deepcopy(self.stored)
        fresh["rows"][0]["output_digest"] = "deadbeefdeadbeef"
        rep = compare_results(self.stored, fresh)
        self.assertTrue(any("output changed" in f for f in rep.hard_failures))

    def test_changed_input_digest_fails(self):
        fresh = copy.deepcopy(self.stored)
        fresh["rows"][0]["input_digest"] = "0000000000000000"
        rep = compare_results(self.stored, fresh)
        self.assertTrue(any("input data changed" in f for f in rep.hard_failures))

    def test_changed_experiment_code_fails(self):
        fresh = copy.deepcopy(self.stored)
        fresh["code_digest"] = "1111111111111111"
        rep = compare_results(self.stored, fresh)
        self.assertTrue(any("code changed" in f for f in rep.hard_failures))

    def test_missing_and_extra_cells_fail(self):
        fresh = copy.deepcopy(self.stored)
        fresh["rows"] = fresh["rows"][:1]
        rep = compare_results(self.stored, fresh)
        self.assertTrue(any("missing in replay" in f for f in rep.hard_failures))

        fresh2 = copy.deepcopy(self.stored)
        fresh2["rows"].append(_cell(0.02, alg="surprise_alg"))
        rep2 = compare_results(self.stored, fresh2)
        self.assertTrue(any("not stored" in f for f in rep2.hard_failures))

    def test_decisive_ranking_inversion_is_surfaced(self):
        fresh = copy.deepcopy(self.stored)
        for row in fresh["rows"]:                     # swap the two timings
            factor = 5.0 if row["algorithm"] == "fast_alg" else 0.2
            row["samples"] = [s * factor for s in row["samples"]]
            row["mean_s"] *= factor
        rep = compare_results(self.stored, fresh)
        self.assertEqual(len(rep.inversions), 1, rep.inversions)
        self.assertIn("decisively slower on replay", rep.inversions[0])
        self.assertTrue(rep.failed(ReplayPolicy(strict=True)))
        # default mode reports it without inventing a correctness failure
        self.assertEqual(rep.hard_failures, [])

    def test_reordering_below_significance_is_not_an_inversion(self):
        stored = _payload([_cell(0.0100, alg="a", spread=1e-6),
                           _cell(0.0104, alg="b", spread=1e-6)])
        fresh = _payload([_cell(0.0104, alg="a", spread=1e-6),
                          _cell(0.0100, alg="b", spread=1e-6)])
        rep = compare_results(stored, fresh)
        self.assertEqual(rep.inversions, [])
        self.assertFalse(rep.failed(ReplayPolicy(strict=True)))

    def test_low_trial_counts_cannot_produce_an_inversion(self):
        stored = _payload([_cell(0.010, alg="a", trials=3, spread=1e-6),
                           _cell(0.100, alg="b", trials=3, spread=1e-6)])
        fresh = _payload([_cell(0.100, alg="a", trials=3, spread=1e-6),
                          _cell(0.010, alg="b", trials=3, spread=1e-6)])
        rep = compare_results(stored, fresh)
        self.assertEqual(rep.inversions, [])

    def test_environment_mismatch_downgrades_strict_assertions(self):
        fresh = copy.deepcopy(self.stored)
        fresh["environment"]["python_version"] = "3.10.20"
        for row in fresh["rows"]:                     # big timing drift too
            row["samples"] = [s * 4 for s in row["samples"]]
            row["mean_s"] *= 4
        rep = compare_results(self.stored, fresh)
        self.assertTrue(rep.env_mismatches)
        self.assertTrue(rep.timing)
        self.assertFalse(rep.failed(ReplayPolicy(strict=True)),
                         "cross-environment timings must not be asserted")

    def test_legacy_schema1_payload_still_compares(self):
        legacy_rows = [{"algorithm": "a", "regime": "random", "n": 100,
                        "correct": True, "trials": 3, "mean_s": 0.01,
                        "stdev_s": 0.0005},
                       {"algorithm": "b", "regime": "random", "n": 100,
                        "correct": True, "trials": 3, "mean_s": 0.02,
                        "stdev_s": 0.0005}]
        stored = {"rows": legacy_rows}
        fresh = {"rows": copy.deepcopy(legacy_rows)}
        rep = compare_results(stored, fresh)
        self.assertEqual(rep.hard_failures, [])
        self.assertTrue(any("schema v1" in n for n in rep.notes))
        self.assertEqual(rep.integrity["output_digests"], 0)


# ------------------------------------------------------- end-to-end mission
class TestResultSchemaAndFlagship(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def test_environment_metadata_is_stored_for_every_experiment(self):
        st = _mission(self.tmp / "m")
        checked = 0
        for rec in st.experiments.values():
            if rec.status != "completed":
                continue
            res = json.loads((rec.path(st.root) / "result.json").read_text())
            self.assertEqual(res["schema_version"], RESULT_SCHEMA_VERSION)
            env = res["environment"]
            for key in ("python_version", "python_implementation", "system",
                        "machine", "cpu_count", "origin_version",
                        "timestamp_utc", "timer_resolution_s"):
                self.assertIn(key, env)
            self.assertEqual(res["config"]["seed"], rec.design["seed"])
            self.assertTrue(res["code_digest"])
            self.assertGreater(res["reference_workload_s"], 0)
            for row in res["rows"]:
                self.assertEqual(len(row["samples"]), row["trials"])
                self.assertTrue(row["input_digest"] and row["output_digest"])
            checked += 1
        self.assertGreater(checked, 0)

    def test_environment_carries_no_host_identity(self):
        st = _mission(self.tmp / "m")
        _, _, res = _completed(st)
        blob = json.dumps(res["environment"])
        self.assertNotIn("node", blob)
        import socket
        self.assertNotIn(socket.gethostname(), blob)

    def test_replay_after_relocation_passes(self):
        st = _mission(self.tmp / "m")
        moved = self.tmp / "somewhere" / "else"
        moved.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(st.root, moved)
        rec, _, _ = _completed(ResearchState.load(moved))
        self.assertEqual(cli_main(["replay", "--dir", str(moved),
                                   "--exp", rec.id]), 0)

    def test_missing_artifact_fails_replay_honestly(self):
        st = _mission(self.tmp / "m")
        rec, path, _ = _completed(st)
        path.unlink()
        self.assertEqual(cli_main(["replay", "--dir", str(st.root),
                                   "--exp", rec.id]), 1)
        # a missing runner is equally fatal
        st2 = _mission(self.tmp / "m2")
        rec2, _, _ = _completed(st2)
        (rec2.path(st2.root) / "run.py").unlink()
        self.assertEqual(cli_main(["replay", "--dir", str(st2.root),
                                   "--exp", rec2.id]), 1)

    def test_altered_stored_result_fails_replay(self):
        st = _mission(self.tmp / "m")
        rec, path, res = _completed(st)
        res["rows"][0]["output_digest"] = "tampered00000000"
        path.write_text(json.dumps(res))
        self.assertEqual(cli_main(["replay", "--dir", str(st.root),
                                   "--exp", rec.id]), 1)

    def test_dossier_distinguishes_correctness_from_timing(self):
        st = _mission(self.tmp / "m")
        cli_main(["report", "--dir", str(st.root)])
        dossier = (st.root / "reports" / "dossier.md").read_text()
        self.assertIn("Measurement environment and scope", dossier)
        self.assertIn("Every performance statement in this dossier is scoped to",
                      dossier)
        self.assertIn("INCONCLUSIVE", dossier)
        self.assertIn("Prediction ledger", dossier)
        self.assertIn("no p-values", dossier.lower().replace("p-values", "p-values"))

    def test_shipped_flagship_dossier_is_scoped(self):
        dossier = REPO / "examples" / "flagship_run" / "reports" / "dossier.md"
        if not dossier.exists():
            self.skipTest("flagship example not present")
        text = dossier.read_text()
        self.assertIn("Measurement environment and scope", text)
        self.assertIn("Nothing here is a claim about these algorithms in general",
                      text)
        for banned in ("universally faster", "the best sorting algorithm",
                       "always faster"):
            self.assertNotIn(banned, text.lower())


if __name__ == "__main__":
    unittest.main()
