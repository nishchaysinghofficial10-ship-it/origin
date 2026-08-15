#!/usr/bin/env python3
"""Bounded live-provider verification for ORIGIN's LLM proposal layer.

This is the ONE command that exercises a real network call. It is deliberately
tiny: one mission, the fast profile, a hard provider-call budget, and the
algorithms domain only.

    export ANTHROPIC_API_KEY=...          # never passed as an argument
    python tools/live_llm_check.py --dir runs/live_check --provider-calls 2

It prints, and writes to <dir>/logs/live_check_summary.json:
    provider / model, number of calls, token usage if reported,
    validated proposals, rejected proposals with reasons,
    resulting experiments, and the final mission conclusion.

Nothing here bypasses ORIGIN: the mission runs through the normal controller,
so the conclusion is produced by experiments, the critic and replication — not
by the model's prose.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin.brain import BrainConfigError, make_brain          # noqa: E402
from origin.budget import Budget                               # noqa: E402
from origin.cli import PROFILES, _brain_logger                 # noqa: E402
from origin.controller import ResearchController               # noqa: E402
from origin.domains.base import get_domain                     # noqa: E402
from origin.proposals import ProposalAudit                     # noqa: E402
from origin.state import ResearchState                         # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--provider-calls", type=int, default=2)
    ap.add_argument("--max-experiments", type=int, default=8)
    ap.add_argument("--profile", default="fast", choices=sorted(PROFILES))
    ap.add_argument("--question",
                    default="Which sorting strategy wins under which input "
                            "regime at small sizes?")
    args = ap.parse_args(argv)

    root = Path(args.dir)
    budget = Budget(experiments_total=args.max_experiments,
                    compute_seconds_total=600,
                    provider_calls_total=args.provider_calls)
    st = ResearchState.create(root, args.question, "algobench",
                              PROFILES[args.profile], budget,
                              profile=args.profile)
    st.meta["brain"] = "anthropic"
    st.save()
    try:
        brain = make_brain("anthropic", logger=_brain_logger(root),
                           budget=st.budget, audit_dir=str(root))
    except BrainConfigError as e:
        print(f"NOT RUN — {e}", file=sys.stderr)
        return 2

    ResearchController(st, get_domain("algobench"), brain=brain).run()

    audit = ProposalAudit(root).read()
    calls = [json.loads(x) for x in
             (root / "logs" / "brain.jsonl").read_text().splitlines()] \
        if (root / "logs" / "brain.jsonl").exists() else []
    accepted = [a for a in audit if a["verdict"] == "accepted"]
    rejected = [a for a in audit if a["verdict"] == "rejected"]
    llm_hyps = {h.id: h for h in st.hypotheses.values() if "llm_proposed" in h.tags}
    summary = {
        "provider": brain.name, "model": getattr(brain, "model", ""),
        "provider_calls_attempted": len(calls),
        "provider_calls_charged": st.budget.provider_calls_used,
        "provider_calls_budget": st.budget.provider_calls_total,
        "input_tokens": sum(c.get("input_tokens") or 0 for c in calls),
        "output_tokens": sum(c.get("output_tokens") or 0 for c in calls),
        "failure_classes": sorted({c.get("failure_class") for c in calls
                                   if c.get("failure_class")}),
        "proposals_accepted": [{"id": a["proposal_id"],
                                "type": a["proposal_type"],
                                "outcome": a["outcome"]} for a in accepted],
        "proposals_rejected": [{"id": r["proposal_id"], "stage": r["stage"],
                                "reason": r["reason"][:200]} for r in rejected],
        "llm_hypotheses": {hid: {"status": h.status.value,
                                 "tested_in": h.tested_in,
                                 "scope": h.scope,
                                 "supporting_evidence": len(h.supporting_evidence),
                                 "contradicting_evidence": len(h.contradicting_evidence)}
                           for hid, h in llm_hyps.items()},
        "experiments_run": st.budget.experiments_used,
        "mission_phase": st.meta["phase"],
        "stop_reason": st.meta.get("stop_reason"),
    }
    out = root / "logs" / "live_check_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))
    print(f"\nSummary written to {out}")
    print(f"Dossier: {root / 'reports' / 'dossier.md'}")
    print("\nEvery conclusion above was produced by ORIGIN's experiment, critic "
          "and replication pipeline. The provider only proposed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
