# ORIGIN 2.1.1rc1 — Release Candidate Notes

This candidate reconciles the v2.1 implementation with truthful release
material. It does not add a new research capability and it is not yet approved
for public release.

## Included capabilities

- Two bounded computational research domains: sorting benchmarks and graph
  shortest paths.
- Persistent mission state, hypotheses, predictions, experiments, replication,
  falsification, provenance, and reports.
- Bounded autonomy with a durable queue, deterministic decisions, budgets,
  operator controls, and a single-writer lease.
- Restricted evidence retrieval and a schema-gated LLM proposal layer.
- Reproducibility checks that distinguish exact results from host-dependent
  timing claims.

## What changed in this candidate

- Version and archive instructions now consistently say `2.1.1rc1`.
- The README distinguishes the 268 test-case inventory from a fresh passing
  support-matrix result.
- Current release records document the outstanding verification work instead of
  reusing v2.0.0 evidence.

## Release blockers

The Linux CPython 3.10–3.14 matrix, hosted CI run, and clean-archive candidate
verification remain pending. See
[`V2_1_1_FINAL_STATUS.md`](V2_1_1_FINAL_STATUS.md) for the current verdict.

## Honest limitations

Live LLM use remains unverified without an operator-run check. macOS remains
untested, Windows remains unsupported, experiments use user-space rather than
kernel-grade isolation, and external actions cannot have exactly-once semantics
after a crash.
