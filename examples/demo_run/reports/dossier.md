# ORIGIN Research Dossier

Generated: 2026-08-13 19:42:28  |  ORIGIN v2.0.0  |  domain: `algobench`

## 1. Research question

> Which comparison-sort strategy is most efficient across input regimes (random, nearly-sorted, reversed, few-unique) in pure Python at n<=1600, and can a hybrid synthesized from the evidence beat the base algorithms?

## 2. Initial assumptions

- Wall-clock time on a single machine/interpreter is an acceptable proxy for algorithmic cost at these sizes.
- Pure-Python implementations are compared against each other only; C-accelerated builtins are out of scope for fairness.
- The four tested input regimes are representative of the distributions of interest.
- All timings come from a single machine and interpreter; absolute numbers will not transfer, only rankings might.
- Conclusions hold only for the tested input regimes and sizes; extrapolation beyond them is speculation, not inference.

## 3. Existing knowledge (seeded claims)

- **[FACT]** Any comparison sort requires Omega(n log n) comparisons in the worst case. (confidence 0.97)
- **[FACT]** Insertion sort runs in O(n + inversions); it is linear on nearly-sorted input. (confidence 0.97)
- **[FACT]** Quicksort's worst case is O(n^2), but median-of-three pivoting avoids it on sorted/reversed inputs. (confidence 0.97)

## 4. Evidence map (knowledge graph)

- quick_sort —fastest_on→ random (confidence 0.90, evidence: 9)
- insertion_sort —fastest_on→ nearly_sorted (confidence 0.90, evidence: 13)
- quick_sort —fastest_on→ reversed (confidence 0.90, evidence: 13)
- quick_sort —fastest_on→ few_unique (confidence 0.90, evidence: 9)
- hybrid_sort —derived_from→ merge_sort (confidence 0.99, evidence: 0)
- hybrid_sort —derived_from→ insertion_sort (confidence 0.99, evidence: 0)
- hybrid_sort —fastest_on→ random (confidence 0.51, evidence: 4)
- hybrid_sort —fastest_on→ few_unique (confidence 0.59, evidence: 4)

## 5. Contradictions

- 'quick_sort' and 'hybrid_sort' both claimed as fastest_on 'random'
- 'quick_sort' and 'hybrid_sort' both claimed as fastest_on 'few_unique'

## 6. Knowledge gaps

- Scaling behavior beyond n=1600 is untested (asymptotic crossovers may differ).
- Memory usage and comparison/move counts were not measured (wall time only).
- Adversarial input patterns (sawtooth, organ-pipe, quicksort-killer) are untested.
- Only one machine/interpreter was used; hardware sensitivity is unknown.
- Stability of the sorts (equal-key ordering) was not evaluated.

## 7. Hypotheses (competing pool, with evidence ledgers)

### hyp_d4e20c8a29 — PROVISIONALLY_SUPPORTED

**Statement.** Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes.

**Rationale.** Adaptive O(n + inversions) behavior dominates on low-inversion input; O(n^2) dominates on random input.

Supporting evidence: 4 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 2 | refuted: 0

- [CONFIRMED] insertion_sort is fastest on nearly_sorted — fastest_on 'nearly_sorted' at n=1600 is insertion_sort (0.1 ms, margin 688%)
- [CONFIRMED] insertion_sort is slowest on random — slowest_on 'random' at n=1600 is insertion_sort (38.5 ms, margin 94%)

### hyp_e8add5b17c — REJECTED

**Statement.** Merge sort is the fastest pure-Python candidate on random input.

**Rationale.** Guaranteed n log n with sequential memory access; no pathological cases.

Supporting evidence: 0 | Contradicting: 1 | Experiments: 1 | Predictions confirmed: 0 | refuted: 1

- [REFUTED] merge_sort is fastest on random — fastest_on 'random' at n=1600 is quick_sort (1.4 ms, margin 60%)

### hyp_c8cb718328 — PROVISIONALLY_SUPPORTED

**Statement.** Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input.

**Rationale.** MO3 pivoting neutralizes ordered-input pathologies; constant factors are low.

Supporting evidence: 4 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 2 | refuted: 0

- [CONFIRMED] quick_sort within 25% of best on random — quick_sort is 0% off best on 'random' (limit 25%)
- [CONFIRMED] quick_sort within 200% of best on reversed — quick_sort is 0% off best on 'reversed' (limit 200%)

### hyp_a2e585909f — WEAKENED

**Statement.** Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.

**Rationale.** Input-oblivious n log n behavior; poor cache locality keeps constants high.

Supporting evidence: 3 | Contradicting: 1 | Experiments: 2 | Predictions confirmed: 1 | refuted: 0

- [UNSTABLE] heap_sort has lowest mean relative stdev — failed replication: lowest mean relative stdev: merge_sort (0.029)
- [CONFIRMED] heap_sort is never fastest in any regime — regime winners: ['insertion_sort', 'quick_sort']

### hyp_7850a311fa — PROVISIONALLY_SUPPORTED

**Statement.** A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) beats plain merge sort on random AND nearly-sorted input at the tested sizes.

**Rationale.** Round-1 evidence: 'insertion_sort' won nearly_sorted and 'quick_sort' won random. Combining merge structure with insertion's strength on short/ordered runs should reduce recursion overhead without losing n log n guarantees. Derived from experiment exp_defeaebae2.

Supporting evidence: 4 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 2 | refuted: 0

- [CONFIRMED] hybrid_sort beats merge_sort on random by >= 5% — hybrid_sort vs merge_sort on 'random': +61% (needs >= 5%)
- [CONFIRMED] hybrid_sort beats merge_sort on nearly_sorted — hybrid_sort vs merge_sort on 'nearly_sorted': +190% (needs >= 0%)

## 8. Experiments

- `exp_defeaebae2` [completed] Benchmark round 1 covering 4 hypothesis(es) — 0.6s (design: 4 algorithms x 4 regimes x sizes [400, 1600])
- `exp_dfae537d8f` [completed] Benchmark round 2 covering 1 hypothesis(es) — 0.6s (design: 5 algorithms x 4 regimes x sizes [400, 1600])
- `exp_d6590ff7d6` [completed] Replication of hyp_d4e20c8a29 — 0.5s (design: 4 algorithms x 4 regimes x sizes [1600])
- `exp_21ee7d3058` [completed] Replication of hyp_c8cb718328 — 0.5s (design: 4 algorithms x 4 regimes x sizes [1600])
- `exp_89bfcf883b` [completed] Replication of hyp_a2e585909f — 0.5s (design: 4 algorithms x 4 regimes x sizes [1600])
- `exp_03c68e9b8c` [completed] Replication of hyp_7850a311fa — 0.5s (design: 5 algorithms x 4 regimes x sizes [1600])

## 9. Results

**exp_defeaebae2** — Benchmark round 1 covering 4 hypothesis(es) (0.6s, n = 1600 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.45 | 0.02 | 3 |
| 2 | merge_sort | 2.31 | 0.06 | 3 |
| 3 | heap_sort | 2.44 | 0.04 | 3 |
| 4 | insertion_sort | 38.46 | 1.83 | 3 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.12 | 0.01 | 3 |
| 2 | quick_sort | 0.95 | 0.03 | 3 |
| 3 | merge_sort | 1.96 | 0.53 | 3 |
| 4 | heap_sort | 2.45 | 0.02 | 3 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 0.97 | 0.01 | 3 |
| 2 | merge_sort | 1.79 | 0.24 | 3 |
| 3 | heap_sort | 2.13 | 0.02 | 3 |
| 4 | insertion_sort | 74.20 | 8.82 | 3 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.23 | 0.01 | 3 |
| 2 | heap_sort | 2.08 | 0.05 | 3 |
| 3 | merge_sort | 2.19 | 0.13 | 3 |
| 4 | insertion_sort | 29.32 | 0.79 | 3 |

**exp_dfae537d8f** — Benchmark round 2 covering 1 hypothesis(es) (0.6s, n = 1600 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_sort | 1.39 | 0.02 | 3 |
| 2 | quick_sort | 1.40 | 0.02 | 3 |
| 3 | merge_sort | 2.25 | 0.04 | 3 |
| 4 | heap_sort | 2.41 | 0.06 | 3 |
| 5 | insertion_sort | 35.72 | 0.21 | 3 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.11 | 0.00 | 3 |
| 2 | hybrid_sort | 0.54 | 0.01 | 3 |
| 3 | quick_sort | 0.94 | 0.01 | 3 |
| 4 | merge_sort | 1.56 | 0.04 | 3 |
| 5 | heap_sort | 2.40 | 0.00 | 3 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 0.96 | 0.02 | 3 |
| 2 | hybrid_sort | 1.28 | 0.01 | 3 |
| 3 | merge_sort | 1.59 | 0.02 | 3 |
| 4 | heap_sort | 2.23 | 0.05 | 3 |
| 5 | insertion_sort | 65.20 | 0.60 | 3 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_sort | 1.15 | 0.01 | 3 |
| 2 | quick_sort | 1.27 | 0.04 | 3 |
| 3 | merge_sort | 2.05 | 0.01 | 3 |
| 4 | heap_sort | 2.08 | 0.02 | 3 |
| 5 | insertion_sort | 30.33 | 0.73 | 3 |

**exp_d6590ff7d6** — Replication of hyp_d4e20c8a29 (0.5s, n = 1600 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.44 | 0.02 | 3 |
| 2 | merge_sort | 2.29 | 0.06 | 3 |
| 3 | heap_sort | 2.41 | 0.02 | 3 |
| 4 | insertion_sort | 36.54 | 1.12 | 3 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.13 | 0.01 | 3 |
| 2 | quick_sort | 0.94 | 0.02 | 3 |
| 3 | merge_sort | 1.59 | 0.03 | 3 |
| 4 | heap_sort | 2.50 | 0.02 | 3 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 0.99 | 0.02 | 3 |
| 2 | merge_sort | 1.63 | 0.04 | 3 |
| 3 | heap_sort | 2.19 | 0.05 | 3 |
| 4 | insertion_sort | 68.24 | 2.45 | 3 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.27 | 0.01 | 3 |
| 2 | heap_sort | 2.07 | 0.03 | 3 |
| 3 | merge_sort | 2.12 | 0.12 | 3 |
| 4 | insertion_sort | 28.83 | 0.50 | 3 |

**exp_21ee7d3058** — Replication of hyp_c8cb718328 (0.5s, n = 1600 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.48 | 0.03 | 3 |
| 2 | merge_sort | 2.33 | 0.03 | 3 |
| 3 | heap_sort | 2.43 | 0.02 | 3 |
| 4 | insertion_sort | 35.79 | 0.31 | 3 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.12 | 0.00 | 3 |
| 2 | quick_sort | 1.00 | 0.02 | 3 |
| 3 | merge_sort | 1.54 | 0.02 | 3 |
| 4 | heap_sort | 2.45 | 0.05 | 3 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 0.99 | 0.02 | 3 |
| 2 | merge_sort | 1.62 | 0.03 | 3 |
| 3 | heap_sort | 2.17 | 0.01 | 3 |
| 4 | insertion_sort | 67.26 | 2.24 | 3 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.24 | 0.01 | 3 |
| 2 | merge_sort | 2.04 | 0.04 | 3 |
| 3 | heap_sort | 2.11 | 0.06 | 3 |
| 4 | insertion_sort | 28.84 | 0.29 | 3 |

**exp_89bfcf883b** — Replication of hyp_a2e585909f (0.5s, n = 1600 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.48 | 0.05 | 3 |
| 2 | heap_sort | 2.51 | 0.04 | 3 |
| 3 | merge_sort | 2.72 | 0.23 | 3 |
| 4 | insertion_sort | 35.83 | 0.44 | 3 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.13 | 0.01 | 3 |
| 2 | quick_sort | 0.98 | 0.02 | 3 |
| 3 | merge_sort | 1.55 | 0.01 | 3 |
| 4 | heap_sort | 2.46 | 0.04 | 3 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.16 | 0.16 | 3 |
| 2 | merge_sort | 1.60 | 0.02 | 3 |
| 3 | heap_sort | 2.38 | 0.17 | 3 |
| 4 | insertion_sort | 69.30 | 1.55 | 3 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.30 | 0.05 | 3 |
| 2 | merge_sort | 2.10 | 0.02 | 3 |
| 3 | heap_sort | 2.40 | 0.14 | 3 |
| 4 | insertion_sort | 29.32 | 0.64 | 3 |

**exp_03c68e9b8c** — Replication of hyp_7850a311fa (0.5s, n = 1600 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_sort | 1.44 | 0.04 | 3 |
| 2 | quick_sort | 1.45 | 0.05 | 3 |
| 3 | merge_sort | 2.38 | 0.07 | 3 |
| 4 | heap_sort | 2.42 | 0.05 | 3 |
| 5 | insertion_sort | 36.72 | 0.36 | 3 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.12 | 0.01 | 3 |
| 2 | hybrid_sort | 0.54 | 0.03 | 3 |
| 3 | quick_sort | 0.97 | 0.03 | 3 |
| 4 | merge_sort | 1.62 | 0.01 | 3 |
| 5 | heap_sort | 2.58 | 0.13 | 3 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 0.98 | 0.02 | 3 |
| 2 | hybrid_sort | 1.32 | 0.02 | 3 |
| 3 | merge_sort | 1.65 | 0.01 | 3 |
| 4 | heap_sort | 2.32 | 0.12 | 3 |
| 5 | insertion_sort | 70.26 | 0.84 | 3 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_sort | 1.21 | 0.04 | 3 |
| 2 | quick_sort | 1.33 | 0.03 | 3 |
| 3 | heap_sort | 2.07 | 0.01 | 3 |
| 4 | merge_sort | 2.21 | 0.07 | 3 |
| 5 | insertion_sort | 30.93 | 1.03 | 3 |

## 10. Failed approaches (failure log)

- **exp_defeaebae2** / hyp_e8add5b17c: predicted “merge_sort is fastest on random”; observed: fastest_on 'random' at n=1600 is quick_sort (1.4 ms, margin 60%). Action: hypothesis status re-evaluated from evidence.
- **exp_89bfcf883b** / hyp_a2e585909f: predicted “heap_sort has lowest mean relative stdev”; observed: lowest mean relative stdev: merge_sort (0.029). Action: hyp_a2e585909f downgraded to WEAKENED.

## 11. Decision history

- step 2 [select_investigation] → **hyp_d4e20c8a29** — highest expected information gain per unit cost; experiment co-tests 4 hypothesis(es)
- step 3 [select_investigation] → **hyp_7850a311fa** — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)
- step 4 [critic_replication] → **hyp_d4e20c8a29** — critic refuses single-experiment support; independent replication with new seeds
- step 5 [critic_replication] → **hyp_c8cb718328** — critic refuses single-experiment support; independent replication with new seeds
- step 6 [critic_replication] → **hyp_a2e585909f** — critic refuses single-experiment support; independent replication with new seeds
- step 7 [critic_replication] → **hyp_7850a311fa** — critic refuses single-experiment support; independent replication with new seeds

## 12. Current conclusions

Provisionally supported (survived testing and replication):

- Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes. *(independently replicated)*
- Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input. *(independently replicated)*
- A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) beats plain merge sort on random AND nearly-sorted input at the tested sizes. *(independently replicated)*

Weakened (mixed evidence — revision candidates):

- Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.

Rejected by experiment:

- Merge sort is the fastest pure-Python candidate on random input.

## 13. Confidence and cautions

- Unresolved contradiction in knowledge graph: 'quick_sort' and 'hybrid_sort' both claimed as fastest_on 'random'
- Unresolved contradiction in knowledge graph: 'quick_sort' and 'hybrid_sort' both claimed as fastest_on 'few_unique'

## 14. Novel findings

- ORIGIN synthesized a new candidate from round-1 evidence: **A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) beats plain merge sort on random AND nearly-sorted input at the tested sizes.** → outcome: **provisionally_supported**.

## 15. Remaining questions & recommended next investigations

- Investigate knowledge gap: Scaling behavior beyond n=1600 is untested (asymptotic crossovers may differ).
- Investigate knowledge gap: Memory usage and comparison/move counts were not measured (wall time only).
- Investigate knowledge gap: Adversarial input patterns (sawtooth, organ-pipe, quicksort-killer) are untested.
- Investigate knowledge gap: Only one machine/interpreter was used; hardware sensitivity is unknown.
- Investigate knowledge gap: Stability of the sorts (equal-key ordering) was not evaluated.
- Revise or split hyp_a2e585909f: mixed evidence (3 for / 1 against).

## 15b. Measurement environment and scope of performance claims

- Environment metadata was not recorded for these experiments (result schema v1); timings cannot be attributed to a specific interpreter or machine.

**Every performance statement in this dossier is scoped to:** the machine and interpreter above; the input regimes ['random', 'nearly_sorted', 'reversed', 'few_unique']; the input sizes [400, 1600]; 3 trials per measurement cell; and pure-Python implementations of the listed algorithms. Nothing here is a claim about these algorithms in general, in another language, at other input sizes, or on other hardware.

Comparisons are only called decisive when the separation exceeds 3x the combined standard error of the two means AND at least 10% of the faster mean, with at least 5 trials on both sides. Everything else is recorded as INCONCLUSIVE — not as a win, and not as a refutation.

## 16. Prediction ledger

| Hypothesis | Prediction | Check | Outcome | Basis |
|---|---|---|---|---|
| hyp_d4e20c8a29 | insertion_sort is fastest on nearly_sorted | `fastest_on` | **confirmed** | fastest_on 'nearly_sorted' at n=1600 is insertion_sort (0.1 ms, margin 688%) |
| hyp_d4e20c8a29 | insertion_sort is slowest on random | `slowest_on` | **confirmed** | slowest_on 'random' at n=1600 is insertion_sort (38.5 ms, margin 94%) |
| hyp_e8add5b17c | merge_sort is fastest on random | `fastest_on` | **refuted** | fastest_on 'random' at n=1600 is quick_sort (1.4 ms, margin 60%) |
| hyp_c8cb718328 | quick_sort within 25% of best on random | `within_pct_of_best` | **confirmed** | quick_sort is 0% off best on 'random' (limit 25%) |
| hyp_c8cb718328 | quick_sort within 200% of best on reversed | `within_pct_of_best` | **confirmed** | quick_sort is 0% off best on 'reversed' (limit 200%) |
| hyp_a2e585909f | heap_sort has lowest mean relative stdev | `lowest_mean_rel_stdev` | **unstable** | failed replication: lowest mean relative stdev: merge_sort (0.029) |
| hyp_a2e585909f | heap_sort is never fastest in any regime | `never_fastest` | **confirmed** | regime winners: ['insertion_sort', 'quick_sort'] |
| hyp_7850a311fa | hybrid_sort beats merge_sort on random by >= 5% | `beats` | **confirmed** | hybrid_sort vs merge_sort on 'random': +61% (needs >= 5%) |
| hyp_7850a311fa | hybrid_sort beats merge_sort on nearly_sorted | `beats` | **confirmed** | hybrid_sort vs merge_sort on 'nearly_sorted': +190% (needs >= 0%) |

`inconclusive` means the measurement could not resolve the question at this trial count — it is neither support nor refutation.

## 16b. LLM proposal ledger

- No LLM proposals were offered in this mission (brain: `none`).

## 17. Falsification attempts (critic attacks)

- No falsification attempts this run.

## 18. Budget ledger & stop reason

- Experiments: 6/10
- Compute: 3.2s / 1200s
- Active runtime (controller): 0.0s (no wall-time cap)
- Provider calls: 0 (uncapped)
- Retries: 0/8
- **Stop reason**: (mission still active)

## 19. Threats to validity

- Single machine, single CPython version: absolute timings will not transfer; only within-run rankings are meaningful, and only at the tested sizes.
- Wall-clock time only: no comparison counts, memory, or cache metrics. A ranking here is a ranking of *this implementation on this host*, not of the algorithms as such.
- Trial count (3 per cell) supports the conservative separation rule used here, not a formal hypothesis test; no p-values are computed or implied.
- Timing noise: evidence strength is capped when winner stdev/mean > 0.30, but low-margin rankings can still flip between seeds (observed as recorded contradictions).
- Scope: falsification probes cover boundary sizes (2x) and two unseen regimes; conclusions say nothing beyond that envelope.
- Knowledge-graph `fastest_on` relations are size-agnostic by design in v1.0; scale-dependent flips appear as contradictions rather than conditioned relations.

## Appendix — reproducibility

- Recreate this mission: `python -m origin init "<question>" --dir <new_dir> --profile <profile>` then `python -m origin run --dir <new_dir>`
- Replay any experiment from stored metadata: `python -m origin replay --dir <this_dir> --exp <exp_id>`
- Verify state consistency: `python -m origin verify --dir <this_dir>`
- Full machine-readable state: `state.json`, browsable views in `research_state/`
- Every experiment's generated code + raw results: `experiments/exp_*/` (each `run.py` is self-contained and re-runnable)
- Append-only event log: `logs/events.jsonl` — rendered as `reports/timeline.md`
- Budget consumed: 6/10 experiments, 3.2s compute
