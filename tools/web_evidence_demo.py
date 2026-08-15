#!/usr/bin/env python3
"""Bounded evidence-acquisition demonstration for the algorithms domain.

Question:
    What source-backed conditions are commonly associated with algorithmic
    performance tradeoffs, and which of those claims can ORIGIN test in its own
    controlled benchmark domain?

Two modes, same pipeline:

    python tools/web_evidence_demo.py --dir runs/evidence_demo --mode live
    python tools/web_evidence_demo.py --dir runs/evidence_demo --mode fixture

`live` retrieves a small set of approved https sources; `fixture` serves the
same shapes from local files with no network at all.

The demonstration deliberately produces **research directions, not findings**.
Nothing retrieved is treated as proof that one algorithm is better than
another — the last section prints which claims ORIGIN could actually test in
its own benchmark domain, and by which experiment.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import web_evidence as W                          # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES                               # noqa: E402
from origin.models import EpistemicStatus                     # noqa: E402
from origin.retrieval import (PolicyViolation, RetrievalPolicy,  # noqa: E402
                              FixtureProvider, HttpsProvider)
from origin.state import ResearchState                        # noqa: E402

QUESTION = ("What source-backed conditions are commonly associated with "
            "algorithmic performance tradeoffs, and which of those claims can "
            "ORIGIN test in its own controlled benchmark domain?")

# Approved sources: primary, public, plain-text, and directly about the
# tradeoffs the algorithms domain measures.
LIVE_SOURCES = [
    "https://raw.githubusercontent.com/python/cpython/main/Objects/listsort.txt",
    "https://raw.githubusercontent.com/python/cpython/main/Doc/howto/sorting.rst",
]
LIVE_HOSTS = ("raw.githubusercontent.com",)

FIXTURE_DOCS = {
    "https://fixtures.invalid/adaptive-sorting": (
        "Adaptive Sorting Notes\n\n"
        "Insertion sort is faster than merge sort on nearly-sorted input "
        "because the number of inversions is small and the work approaches "
        "linear.\n\n"
        "Merge sort is a stable comparison sort with guaranteed n log n "
        "behaviour on every input distribution.\n\n"
        "Quick sort has poor worst-case behaviour on adversarial inputs, so "
        "practical implementations add a fallback strategy.\n"),
    "https://fixtures.invalid/counter-commentary": (
        "Alternative Commentary\n\n"
        "In the measurements reported here merge sort is faster than insertion "
        "sort on every input distribution examined, including nearly-sorted "
        "arrays.\n"),
}

# Which claim shapes the algorithms domain can actually put to the test.
# Deliberately conservative keyword mapping: a claim that does not clearly
# name a measurable condition is reported as unmapped rather than stretched
# into an experiment it does not justify.
TESTABLE_HINTS = [
    ("insertion sort", "nearly", "TESTABLE: beats(insertion_sort, merge_sort, nearly_sorted)"),
    ("partially ordered", "", "TESTABLE: beats(hybrid_sort, merge_sort, nearly_sorted) — "
                              "adaptive advantage on presorted runs"),
    ("presorted", "", "TESTABLE: beats(hybrid_sort, merge_sort, nearly_sorted)"),
    ("merge sort", "random", "TESTABLE: beats(merge_sort, quick_sort, random)"),
    ("quick sort", "worst", "TESTABLE: fastest_on(quick_sort, reversed) + falsification probe"),
    ("cutoff", "", "TESTABLE: hybrid cutoff sweep (sweep_optimum_in)"),
    ("temp array", "", "NOT MEASURABLE here: memory use is not instrumented"),
    ("memory", "", "NOT MEASURABLE here: memory use is not instrumented"),
    ("stable", "", "NOT MEASURABLE here: stability (equal-key order) is unmeasured"),
    ("comparison", "count", "NOT MEASURABLE here: comparison counts are unmeasured"),
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--mode", default="fixture", choices=["live", "fixture"])
    ap.add_argument("--max-requests", type=int, default=4)
    args = ap.parse_args(argv)

    root = Path(args.dir)
    st = ResearchState.create(root, QUESTION, "algobench", PROFILES["fast"],
                              Budget(), profile="fast")
    st.meta["brain"] = "none"
    st.save()

    if args.mode == "live":
        provider = HttpsProvider()
        policy = RetrievalPolicy(max_requests=args.max_requests,
                                 allow_hosts=LIVE_HOSTS, min_interval_s=1.0)
        urls = LIVE_SOURCES
    else:
        provider = FixtureProvider({
            url: {"body": body, "content_type": "text/plain; charset=utf-8"}
            for url, body in FIXTURE_DOCS.items()})
        policy = RetrievalPolicy(max_requests=args.max_requests,
                                 min_interval_s=0.0)
        urls = list(FIXTURE_DOCS)

    results = []
    for url in urls:
        try:
            results.append(W.ingest_url(st, url, provider, None, policy))
        except PolicyViolation as e:
            results.append({"ok": False, "url": url, "refused": str(e)})
    st.save()

    web_sources = [s for s in st.sources.values() if s.kind == "web_document"]
    web_claims = [c for c in st.claims.values()
                  if any(s.id in c.source_ids for s in web_sources)]
    conflicts = [c for c in st.graph.contradictions
                 if c.get("kind") == "external_claim_conflict"]

    print(f"\n=== SOURCES ({len(web_sources)}) ===")
    for s in web_sources:
        print(f"  {s.id}  {s.title[:60]}")
        print(f"      {s.canonical_url}")
        print(f"      status {s.http_status} · {s.content_type.split(';')[0]} · "
              f"sha256 {s.content_hash[:16]} · provider {s.provider}")
        print(f"      reliability {s.reliability} because: "
              f"{', '.join(b['reason'] for b in s.reliability_basis if 'reason' in b)}")

    print(f"\n=== EXTRACTED CLAIMS ({len(web_claims)}) — all SPECULATION ===")
    for c in web_claims:
        print(f"  {c.id} [{c.claim_type}] conf {c.confidence} "
              f"(source {c.source_ids[0]} @ offset {c.passage_offset})")
        print(f"      {c.text[:110]}")

    print(f"\n=== VISIBLE CONFLICTS ({len(conflicts)}) ===")
    for c in conflicts:
        print(f"  {c['description'][:190]}")
    if not conflicts:
        print("  none detected among these sources")

    print("\n=== WHICH OF THIS CAN ORIGIN ACTUALLY TEST? ===")
    directions = []
    for c in web_claims:
        low = c.text.lower()
        for subject, condition, experiment in TESTABLE_HINTS:
            if subject in low and (not condition or condition in low):
                directions.append({"claim": c.id, "maps_to": experiment})
                print(f"  {c.id} → {experiment}")
                break
    unmapped = len(web_claims) - len(directions)
    if not directions:
        print("  no retrieved claim mapped onto a runnable benchmark shape")
    print(f"  ({len(directions)} of {len(web_claims)} claims mapped; {unmapped} "
          f"did not and are kept as context only)")

    summary = {
        "mode": args.mode, "question": QUESTION,
        "requests": st.flags.get("retrievals_used", 0),
        "sources": [s.id for s in web_sources],
        "claims": len(web_claims),
        "claim_statuses": sorted({c.status.value for c in web_claims}),
        "conflicts": len(conflicts),
        "testable_directions": directions,
        "results": results,
        "facts_created_from_web": sum(
            1 for c in web_claims if c.status == EpistemicStatus.FACT),
        "evidence_items_created_from_web": sum(
            1 for e in st.evidence.values() if not e.experiment_id),
    }
    out = root / "logs" / "evidence_demo_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSummary: {out}")
    print("Every claim above is SPECULATION with a stored passage. None of it "
          "is a finding: only an ORIGIN experiment can produce one.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
