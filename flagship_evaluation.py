#!/usr/bin/env python3
"""Flagship autonomous research evaluation.

Runs the SAME pre-registered research question through three workflows and
measures what each produces:

    baseline    run every benchmark once; report the raw winners. No
                hypotheses, no replication, no falsification, no significance
                gate — this is what "just benchmark it" produces.
    proposal    the LLM proposal layer generates hypotheses, and they are
                reported as-is. No experiments. This is what "ask a model"
                produces.
    origin      the full loop: competing hypotheses → machine-checkable
                predictions → budgeted experiment selection → analysis →
                criticism → falsification → independent replication → scoped
                conclusions.

The point is not to make ORIGIN look good. It is to measure what the extra
machinery actually buys, and to report it even when the answer is "not much"
or "it refused to conclude anything".

    python tools/flagship_evaluation.py --dir examples/final_flagship_mission
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import stats as st_                               # noqa: E402
from origin.brain import MockBrain                            # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES                               # noqa: E402
from origin.controller import ResearchController              # noqa: E402
from origin.domains.base import get_domain                    # noqa: E402
from origin.experiments import ExperimentEngine               # noqa: E402
from origin.models import HypothesisStatus                    # noqa: E402
from origin.state import ResearchState                        # noqa: E402

# ----------------------------------------------------------- pre-registration
PREREGISTRATION = {
    "question": ("Which single-source shortest-path method wins on which graph "
                 "topology at n<=512, does the machine-independent relaxation "
                 "count agree with the wall-clock ranking, and under what "
                 "precondition is the BFS candidate correct?"),
    "domain": "graphbench",
    "baselines": ["dijkstra_heap", "dijkstra_array", "bellman_ford", "spfa",
                  "bfs_unit"],
    "metrics": ["correctness vs a reference Dijkstra (exact)",
                "wall-clock mean per cell (host-specific)",
                "edge relaxations (machine-independent count)"],
    "input_generation": ("deterministic generators seeded from the mission "
                         "config: sparse_random, dense_random, grid_2d, "
                         "unit_weight for the main rounds"),
    "held_out_conditions": ["long_chain", "scale_free"],
    "sizes": [128, 512],
    "trials_per_cell": 5,
    "budget": {"experiments": 40, "compute_minutes": 30},
    "replication_rule": ("any provisionally supported hypothesis must be "
                         "re-tested with seed+1000 in a separately spawned "
                         "experiment before it can be accepted"),
    "falsification_rule": ("a replicated hypothesis must survive a probe at 2x "
                           "the largest tested size on its own topology plus "
                           "the two held-out topologies"),
    "significance_rule": ("timing comparisons need >=5 trials per side, "
                          "separation > 3x combined SEM, and >=10% relative "
                          "margin; relaxation counts are exact and need none"),
    "evaluation_criteria": [
        "correctness: does any workflow report a wrong candidate as a winner?",
        "efficiency: experiments spent per accepted conclusion",
        "self-correction: hypotheses rejected or weakened by own evidence",
        "replication agreement",
        "held-out behaviour: do conclusions survive unseen topologies?",
        "overclaiming: conclusions asserted without scope"],
    "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "note": ("Registered before any workflow was run. ORIGIN was not steered "
             "toward an answer: the hypotheses are the domain's standing "
             "templates plus whatever the proposal layer generated."),
}


def _mission(root: Path, name: str, brain: str = "none") -> ResearchState:
    st = ResearchState.create(
        root / name, PREREGISTRATION["question"], "graphbench",
        PROFILES["graph_standard"],
        Budget(experiments_total=PREREGISTRATION["budget"]["experiments"],
               compute_seconds_total=PREREGISTRATION["budget"]["compute_minutes"] * 60),
        profile="graph_standard")
    st.meta["brain"] = brain
    st.save()
    return st


# ------------------------------------------------------------- workflow A
def run_baseline(root: Path) -> dict:
    """Benchmark once, report the winners. No hypotheses, no checks."""
    st = _mission(root, "baseline")
    domain = get_domain("graphbench")
    cfg = st.meta["domain_config"]
    design = {"kind": "benchmark", "round": 1,
              "algorithms": PREREGISTRATION["baselines"],
              "regimes": cfg["regimes"], "sizes": cfg["sizes"],
              "trials": cfg["trials"], "seed": cfg["seed"],
              "timeout_s": cfg["timeout_s"], "hypothesis_ids": []}
    t0 = time.time()
    engine = ExperimentEngine(st, domain)
    rec = engine.run(design, title="baseline sweep")
    result = engine.load_result(rec)
    st.save()
    rows = result["rows"] if result else []
    n_top = max(cfg["sizes"])
    winners, unchecked_winners = {}, []
    for regime in cfg["regimes"]:
        cells = [r for r in rows if r["regime"] == regime and r["n"] == n_top]
        if not cells:
            continue
        best = min(cells, key=lambda r: r["mean_s"])
        winners[regime] = best["algorithm"]
        if not best["correct"]:
            unchecked_winners.append(f"{best['algorithm']} on {regime}")
    return {
        "workflow": "baseline", "experiments": st.budget.experiments_used,
        "wall_s": round(time.time() - t0, 1),
        "conclusions": [f"fastest on {k} is {v}" for k, v in winners.items()],
        "winners": winners,
        "incorrect_candidates_reported_as_winners": unchecked_winners,
        "hypotheses_tested": 0, "replications": 0, "falsifications": 0,
        "self_corrections": 0, "scoped_conclusions": 0,
        "significance_gated": False,
    }


# ------------------------------------------------------------- workflow B
def run_proposal_only(root: Path) -> dict:
    """The proposal layer speaks; nothing is tested."""
    st = _mission(root, "proposal_only", brain="mock")
    domain = get_domain("graphbench")
    brain = MockBrain()
    t0 = time.time()
    context = domain.proposal_context(st)
    context["existing_hypothesis_ids"] = []
    raw = brain.propose_research(context, k=5)
    from origin import proposals as P
    accepted, rejected = P.review(raw, domain, st, provider="mock")
    st.save()
    return {
        "workflow": "proposal_only", "experiments": 0,
        "wall_s": round(time.time() - t0, 1),
        "conclusions": [p.statement for p in accepted],
        "proposals_accepted": len(accepted),
        "proposals_rejected": [r.reason[:120] for r in rejected],
        "hypotheses_tested": 0, "replications": 0, "falsifications": 0,
        "self_corrections": 0, "scoped_conclusions": 0,
        "significance_gated": False,
        "note": ("These are proposals, not findings. Nothing here was measured; "
                 "any that survived validation would still have to earn their "
                 "status through experiments."),
    }


# ------------------------------------------------------------- workflow C
def run_origin(root: Path) -> dict:
    """The full research loop."""
    st = _mission(root, "origin_full", brain="mock")
    t0 = time.time()
    ResearchController(st, get_domain("graphbench"),
                       brain=MockBrain()).run()
    accepted = [h for h in st.hypotheses.values()
                if h.status == HypothesisStatus.ACCEPTED_WITH_SCOPE]
    rejected = [h for h in st.hypotheses.values()
                if h.status == HypothesisStatus.REJECTED]
    weakened = [h for h in st.hypotheses.values()
                if h.status == HypothesisStatus.WEAKENED]
    replications = sum(1 for r in st.experiments.values()
                       if r.design.get("round") == 2)
    falsifications = sum(1 for r in st.experiments.values()
                         if r.design.get("kind") == "falsification")
    incorrect = {f["observed"].split()[0] for f in st.failures
                 if f.get("kind") == "incorrect_output"}
    wrong_winners = [h.statement for h in accepted
                     if any(c in h.statement for c in incorrect)
                     and "incorrect" not in h.statement.lower()]
    inconclusive = sum(1 for h in st.hypotheses.values()
                       for p in h.predictions if p.outcome == "inconclusive")
    return {
        "workflow": "origin_full", "experiments": st.budget.experiments_used,
        "wall_s": round(time.time() - t0, 1),
        "conclusions": [f"{h.statement} [scope: {h.scope}]" for h in accepted],
        "hypotheses_total": len(st.hypotheses),
        "hypotheses_tested": sum(1 for h in st.hypotheses.values() if h.tested_in),
        "accepted_with_scope": len(accepted),
        "rejected_by_own_evidence": [h.statement[:90] for h in rejected],
        "weakened": len(weakened),
        "self_corrections": len(rejected) + len(weakened),
        "inconclusive_predictions": inconclusive,
        "replications": replications, "falsifications": falsifications,
        "scoped_conclusions": sum(1 for h in accepted if h.scope),
        "significance_gated": True,
        "incorrect_candidates_reported_as_winners": wrong_winners,
        "correctness_boundaries_found": sorted(incorrect),
        "cautions": len(st.cautions),
        "compute_s": round(st.budget.compute_seconds_used, 1),
        "mission_dir": str(Path(st.root).name),
        "stop_reason": st.meta.get("stop_reason"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args(argv)
    root = Path(args.dir)
    if root.exists() and not args.keep:
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "PREREGISTRATION.json").write_text(
        json.dumps(PREREGISTRATION, indent=2))
    print("Pre-registration written BEFORE any workflow ran:")
    print(f"  {root / 'PREREGISTRATION.json'}\n")

    results = {}
    for label, fn in (("baseline", run_baseline),
                      ("proposal_only", run_proposal_only),
                      ("origin_full", run_origin)):
        print(f"=== running workflow: {label} ===")
        results[label] = fn(root)
        r = results[label]
        print(f"    {r['experiments']} experiment(s), {r['wall_s']}s, "
              f"{len(r['conclusions'])} conclusion(s)")

    comparison = {
        "pre_registration": PREREGISTRATION,
        "workflows": results,
        "comparison": {
            "experiments_spent": {k: v["experiments"] for k, v in results.items()},
            "conclusions_produced": {k: len(v["conclusions"])
                                     for k, v in results.items()},
            "scoped_conclusions": {k: v["scoped_conclusions"]
                                   for k, v in results.items()},
            "replications": {k: v["replications"] for k, v in results.items()},
            "falsification_probes": {k: v["falsifications"]
                                     for k, v in results.items()},
            "self_corrections": {k: v["self_corrections"]
                                 for k, v in results.items()},
            "significance_gated": {k: v["significance_gated"]
                                   for k, v in results.items()},
            "incorrect_candidate_named_a_winner": {
                k: v.get("incorrect_candidates_reported_as_winners", [])
                for k, v in results.items()},
        },
    }
    out = root / "EVALUATION_RESULTS.json"
    out.write_text(json.dumps(comparison, indent=2, default=str))
    print(f"\nComparison written to {out}")
    print(json.dumps(comparison["comparison"], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
