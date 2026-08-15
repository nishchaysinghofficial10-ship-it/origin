# Historical ORIGIN 2.0.0 — Release Notes

> This is the preserved 2.0.0 release record. It is not release evidence for
> the current 2.1.1rc1 candidate. See
> [`V2_1_1_RELEASE_NOTES.md`](V2_1_1_RELEASE_NOTES.md) and
> [`V2_1_1_FINAL_STATUS.md`](V2_1_1_FINAL_STATUS.md) for current status.

## What ORIGIN is

A persistent computational research engine. Give it a question in a supported
domain and a budget; it maintains competing hypotheses, turns them into
machine-checkable predictions, runs reproducible experiments in a confined
subprocess, attacks its own conclusions with independent replication and
falsification probes, records every decision, and stops with an explicit
reason. Zero third-party runtime dependencies.

## Why it might be worth your attention

A pre-registered evaluation ran one question through three workflows
(`docs/reports/FLAGSHIP_EVALUATION.md`). The "just benchmark it" workflow
produced four headline conclusions in 2.7 seconds — **three of them named a
candidate that returns wrong answers**. It was genuinely the fastest; it was
also incorrect, and a benchmark cannot notice that.

ORIGIN spent six experiments instead of one and produced *fewer* conclusions.
Zero were wrong that way. It also rejected two of its own textbook-plausible
hypotheses on its own evidence, and raised nine cautions — four of them saying a
topology's apparent winner was not statistically separable, so **no winner is
claimed**.

That trade — more cost, fewer conclusions, no fast wrong answers — is the
product.

## Highlights

- **Two research domains.** Sorting benchmarks and graph shortest paths. The
  second exists to test whether the core is really domain-agnostic; eleven core
  modules are asserted never to name a domain.
- **Bounded autonomy.** Continue a mission across sessions and restarts inside
  explicit limits. Every run is finite, every choice is recorded with what it
  beat, every stop reason is truthful. No daemon.
- **Evidence with provenance.** Retrieved sources carry canonical URL, status,
  content hash, cached text and an *explained* reliability score. Claims keep
  the exact passage they came from. Nothing retrieved becomes a finding.
- **An LLM that proposes, never concludes.** Four validated proposal types, an
  append-only audit of accepted *and* rejected proposals with reasons.
- **Reproducibility that distinguishes tiers.** Correctness, inputs, outputs and
  code are exact and asserted. Rankings are judged under a conservative
  significance rule. Absolute timings are reported, never asserted.

## Honest limitations

The live Anthropic call has never executed (no credential was available in the
build environment) — it is labelled UNVERIFIED, not demonstrated. General-web
retrieval is proven only against allow-listed hosts. Confinement is user-space
rlimits and a scrubbed environment; it is **not** kernel-grade isolation, and a
test fails the build if the docs ever claim otherwise. There is no exactly-once
guarantee for external actions: a crash mid-action is recorded as `interrupted`
for a human to resolve, never guessed. No novelty is claimed — ORIGIN
rediscovered textbook results from measurement, correctly scoped, having also
rejected plausible claims that were wrong.

## Getting started

```bash
python -m unittest discover -s tests             # 261 tests, ~2 min
python -m origin init "Which sorting strategy wins where?" --dir runs/demo --profile fast
python -m origin run    --dir runs/demo
python -m origin report --dir runs/demo
```

Supported: Python 3.10–3.14 on Linux (tested). macOS untested; Windows
unsupported — POSIX rlimits are required and failure is explicit.
