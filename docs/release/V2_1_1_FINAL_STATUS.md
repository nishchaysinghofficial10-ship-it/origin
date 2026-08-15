# ORIGIN 2.1.1rc1 — Final Status

**Verdict: NOT READY FOR PUBLIC RELEASE.**

The candidate is internally coherent: its package version is consistent, the
source contains 268 test cases, a clean candidate archive imports as
`2.1.1rc1`, the portable-artifact scan is clean, and the three checked shipped
mission states verify correctly from that archive. The project also contains the
intended v2.1 features: bounded autonomy, two registered computational domains,
provenance-aware evidence handling, a constrained LLM proposal layer,
reproducibility checks, a flagship evaluation, and release scaffolding.

It is not ready to be called publicly released because fresh candidate-specific
execution evidence is incomplete. The prior 2.0.0 matrix and clean-room record
cannot prove the 2.1.1rc1 candidate.

## Remaining required actions

1. Run the full 268-test suite on Linux CPython 3.10–3.14 for this candidate.
2. Run the included hosted CI workflow and record its URL and outcome.
3. Make a clean candidate archive and repeat the artifact and portability
   checks from that archive.

## Deliberately unverified capabilities

- Live Anthropic provider use remains `UNVERIFIED` without an operator-run,
  redacted live-check summary.
- macOS remains `untested`; Windows remains unsupported.

No document in this candidate may replace these missing facts with claims of
completion. Once the required actions are evidenced, update this document, the
candidate checklist, release notes, and changelog together before publishing.
