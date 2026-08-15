# ORIGIN 2.1.1 — Release Notes

This patch release reconciles the v2.1 implementation with truthful release
material, restores the public repository hierarchy, and adds executed hosted CI
evidence. It does not claim a new research capability.

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

## What changed

- Version and archive instructions now consistently say `2.1.1`.
- The README links the fresh passing 268-case support-matrix result.
- Current release records document the outstanding verification work instead of
  reusing v2.0.0 evidence.
- The GitHub repository has its intended folder structure and an executable CI
  workflow rather than a flattened web upload.

## Verification

Hosted CI run #2 passed all seven jobs, including the full suite on Linux
CPython 3.10–3.14, portability, replay, archive round-trip, and a clean
end-to-end mission. See
[`V2_1_1_VERIFICATION.md`](V2_1_1_VERIFICATION.md) for the evidence.

## Honest limitations

Live LLM use remains unverified without an operator-run check. macOS remains
untested, Windows remains unsupported, experiments use user-space rather than
kernel-grade isolation, and external actions cannot have exactly-once semantics
after a crash.
