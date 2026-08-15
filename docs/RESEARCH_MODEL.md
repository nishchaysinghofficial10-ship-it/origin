# ORIGIN v1.0 — Research Model

## Entities
| Entity | Durable fields (beyond id/timestamps) |
|---|---|
| `Source` | kind, title, locator (`file:… sha256:…`), reliability |
| `Claim` | text, epistemic status, confidence, source_ids |
| `Evidence` | target_id, direction (supports/contradicts), strength, kind, summary, experiment_id, payload |
| `Hypothesis` | statement, rationale, status, predictions, supporting/contradicting evidence, importance, cost, tags, tested_in, **scope**, **revisions** |
| `Prediction` | text, machine-checkable `check` dict, outcome, detail |
| `ExperimentRecord` | title, hypothesis_ids, full design spec, dir, status, duration, error, summary |
| `FalsificationAttempt` | hypothesis_id, experiment_id, probe, outcome, detail |
| `Decision` | step, context, all scored options, chosen, reason |
| `Budget` | experiments, compute seconds, wall time, provider calls, retries (total/used) |
| Failure record | experiment, hypothesis, prediction, expected, observed, action |
| Confidence change | kind, id, old, new, reason (append-only) |

## Epistemic ladder
```
SPECULATION            ingested/untrusted claims (confidence ≤ 0.4)
HYPOTHESIS             proposed, untested
EXPERIMENTAL_RESULT    produced by ORIGIN's own measurements
FACT                   seeded prior knowledge only
CONTRADICTED           significant evidence against
```
LLM output can enter at HYPOTHESIS or SPECULATION. Nothing else.

## Hypothesis lifecycle
```
PROPOSED → UNDER_TEST → {PROVISIONALLY_SUPPORTED | WEAKENED | REJECTED}
PROVISIONALLY_SUPPORTED → (independent replication)
                        → (falsification probe)
                        → ACCEPTED_WITH_SCOPE  (survived, scope recorded)
                        → WEAKENED             (probe broke it)
```
Every arrow appends a `revision` with the reason and a `confidence_history`
entry. Promotion to `ACCEPTED_WITH_SCOPE` requires **all three**: confirmed
predictions, an independent replication, and a survived falsification probe.
Hypotheses whose prediction types cannot be probed stay provisionally supported
and receive a caution — they are never promoted by default.

## Predictions are machine-checkable
Supported checks (algobench): `fastest_on`, `slowest_on`, `within_pct_of_best`,
`beats` (with `min_pct`), `lowest_mean_rel_stdev`, `never_fastest`,
`sweep_optimum_in`, `sweep_optimum_ge`. Each returns
(verdict, human-readable detail, margin); margin drives evidence strength, which
is discounted when winner timing noise (stdev/mean) exceeds 0.30.

## Experiment plan fields
kind, round, algorithms, regimes (input distributions), sizes, trials, seed,
timeout, covered hypothesis ids, and — for falsification — the explicit probe
list with roles (`boundary` vs `scope`). Plans are persisted as `spec.json`
next to the exact generated `run.py` that consumed them.

## Independence of replication
A replication uses a different seed (base + 1000), regenerates all inputs, runs
as a separately spawned process with its own experiment directory, and evaluates
the same predictions. A confirmed prediction that fails replication becomes
`unstable`, the hypothesis is downgraded, and a failure record is written.

## Falsification (v1.0)
The critic designs probes rather than re-running the same test:
- **boundary role** — the original prediction at 2× the largest tested size;
- **scope role** — the same prediction on input regimes never used in the main
  rounds (`sawtooth`, `organ_pipe`).
A refuted boundary probe fails the hypothesis. A survived probe yields an
explicit scope string recording which unseen regimes it extends to, which it
does not, and which remained untested.

## Novelty policy
ORIGIN may synthesize candidates (the hybrid sorter, the cutoff-sweep
hypothesis). Novelty is claimed only as "candidate that outperformed the tested
baselines under these conditions", never as an unqualified discovery.
