# ORIGIN Research Dossier

Generated: 2026-08-11 20:49:33  |  ORIGIN v1.0  |  domain: `algobench`

## 1. Research question

> Which sorting strategy wins under which input regime, and what does the published literature claim about those tradeoffs?

## 2. Initial assumptions

- Wall-clock time on a single machine/interpreter is an acceptable proxy for algorithmic cost at these sizes.
- Pure-Python implementations are compared against each other only; C-accelerated builtins are out of scope for fairness.
- The four tested input regimes are representative of the distributions of interest.
- All timings come from a single machine and interpreter; absolute numbers will not transfer, only rankings might.
- Conclusions hold only for the tested input regimes and sizes; extrapolation beyond them is speculation, not inference.

## 3. Existing knowledge (seeded claims)

- **[SPECULATION]** Insertion sort is faster than merge sort on nearly-sorted input because the number of inversions is small and the work approaches linear. (confidence 0.25)
- **[SPECULATION]** Merge sort is a stable comparison sort with guaranteed n log n behaviour on every input distribution. (confidence 0.25)
- **[FACT]** Any comparison sort requires Omega(n log n) comparisons in the worst case. (confidence 0.97)
- **[FACT]** Insertion sort runs in O(n + inversions); it is linear on nearly-sorted input. (confidence 0.97)
- **[FACT]** Quicksort's worst case is O(n^2), but median-of-three pivoting avoids it on sorted/reversed inputs. (confidence 0.97)

## 4. Evidence map (knowledge graph)

- quick_sort —fastest_on→ random (confidence 0.57, evidence: 5)
- insertion_sort —fastest_on→ nearly_sorted (confidence 0.90, evidence: 5)
- quick_sort —fastest_on→ reversed (confidence 0.62, evidence: 5)
- shell_sort —fastest_on→ few_unique (confidence 0.46, evidence: 5)
- hybrid_sort —derived_from→ merge_sort (confidence 0.99, evidence: 0)
- hybrid_sort —derived_from→ insertion_sort (confidence 0.99, evidence: 0)

## 5. Contradictions

- None detected across experiments in this run.

## 6. Knowledge gaps

- Scaling behavior beyond n=128 is untested (asymptotic crossovers may differ).
- Memory usage and comparison/move counts were not measured (wall time only).
- Adversarial input patterns (sawtooth, organ-pipe, quicksort-killer) are untested.
- Only one machine/interpreter was used; hardware sensitivity is unknown.
- Stability of the sorts (equal-key ordering) was not evaluated.

## 7. Hypotheses (competing pool, with evidence ledgers)

### hyp_48de48fcea — WEAKENED

**Statement.** Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes.

**Rationale.** Adaptive O(n + inversions) behavior dominates on low-inversion input; O(n^2) dominates on random input.

Supporting evidence: 1 | Contradicting: 0 | Experiments: 1 | Predictions confirmed: 1 | refuted: 0

- [CONFIRMED] insertion_sort is fastest on nearly_sorted — fastest_on on 'nearly_sorted' is insertion_sort (0.0 ms, margin 407% over shell_sort, separation 0.02 ms > required 0.00 ms) [n=128, 5 trials]
- [INCONCLUSIVE] insertion_sort is slowest on random — insertion_sort has the lowest mean on 'random' (0.1 ms) but is not decisively slower than merge_sort: uncertainty_overlap (gap 0.025 ms <= 3x combined SEM 0.033 ms) [n=128, 5 trials]

### hyp_fc15d13b1b — REJECTED

**Statement.** Merge sort is the fastest pure-Python candidate on random input.

**Rationale.** Guaranteed n log n with sequential memory access; no pathological cases.

Supporting evidence: 0 | Contradicting: 1 | Experiments: 1 | Predictions confirmed: 0 | refuted: 1

- [REFUTED] merge_sort is fastest on random — fastest_on on 'random' is quick_sort, not merge_sort (85% apart, decisive) [n=128, 5 trials]

### hyp_2be7e87921 — WEAKENED

**Statement.** Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input.

**Rationale.** MO3 pivoting neutralizes ordered-input pathologies; constant factors are low.

Supporting evidence: 1 | Contradicting: 0 | Experiments: 1 | Predictions confirmed: 1 | refuted: 0

- [INCONCLUSIVE] quick_sort within 25% of best on random — quick_sort is 0% off best on 'random' (limit 25%), within the ±29% uncertainty of the threshold [n=128, 5 trials]
- [CONFIRMED] quick_sort within 200% of best on reversed — quick_sort is 0% off best on 'reversed' (limit 200%, uncertainty ±5%) [n=128, 5 trials]

### hyp_db14df8458 — WEAKENED

**Statement.** Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.

**Rationale.** Input-oblivious n log n behavior; poor cache locality keeps constants high.

Supporting evidence: 1 | Contradicting: 0 | Experiments: 1 | Predictions confirmed: 1 | refuted: 0

- [INCONCLUSIVE] heap_sort has lowest mean relative stdev — lowest mean relative stdev is quick_sort (0.069) but heap_sort is within 25% — dispersion ranking is not separable here [n=128, 5 trials]
- [CONFIRMED] heap_sort is never fastest in any regime — regime winners: ['insertion_sort', 'quick_sort', 'shell_sort'] (decisively separated in: ['nearly_sorted']) [n=128, 5 trials]

### hyp_5542e8d61c — WEAKENED

**Statement.** A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) beats plain merge sort on random AND nearly-sorted input at the tested sizes.

**Rationale.** Round-1 evidence: 'insertion_sort' won nearly_sorted and 'quick_sort' won random. Combining merge structure with insertion's strength on short/ordered runs should reduce recursion overhead without losing n log n guarantees. Derived from experiment exp_066779c791.

Supporting evidence: 1 | Contradicting: 0 | Experiments: 1 | Predictions confirmed: 1 | refuted: 0

- [INCONCLUSIVE] hybrid_sort beats merge_sort on random by >= 5% — hybrid_sort vs merge_sort on 'random': -0% but not decisive (uncertainty_overlap (gap 0.000 ms <= 3x combined SEM 0.172 ms)) [n=128, 5 trials]
- [CONFIRMED] hybrid_sort beats merge_sort on nearly_sorted — hybrid_sort vs merge_sort on 'nearly_sorted': +190% (needs >= 0%, decisive: gap 0.06 ms > required 0.06 ms) [n=128, 5 trials]

## 8. Experiments

- `exp_066779c791` [completed] Benchmark round 1 covering 4 hypothesis(es) — 0.1s (design: 5 algorithms x 4 regimes x sizes [64, 128])
- `exp_a582f67436` [completed] Benchmark round 2 covering 1 hypothesis(es) — 0.1s (design: 6 algorithms x 4 regimes x sizes [64, 128])

## 9. Results

**exp_066779c791** — Benchmark round 1 covering 4 hypothesis(es) (0.1s, n = 128 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 0.07 | 0.01 | 5 |
| 2 | shell_sort | 0.07 | 0.00 | 5 |
| 3 | heap_sort | 0.10 | 0.01 | 5 |
| 4 | merge_sort | 0.12 | 0.01 | 5 |
| 5 | insertion_sort | 0.15 | 0.01 | 5 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.01 | 0.00 | 5 |
| 2 | shell_sort | 0.03 | 0.00 | 5 |
| 3 | quick_sort | 0.04 | 0.00 | 5 |
| 4 | merge_sort | 0.09 | 0.01 | 5 |
| 5 | heap_sort | 0.09 | 0.01 | 5 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 0.04 | 0.00 | 5 |
| 2 | shell_sort | 0.05 | 0.01 | 5 |
| 3 | heap_sort | 0.09 | 0.01 | 5 |
| 4 | merge_sort | 0.09 | 0.01 | 5 |
| 5 | insertion_sort | 0.26 | 0.01 | 5 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | shell_sort | 0.05 | 0.01 | 5 |
| 2 | quick_sort | 0.06 | 0.00 | 5 |
| 3 | heap_sort | 0.09 | 0.01 | 5 |
| 4 | merge_sort | 0.11 | 0.01 | 5 |
| 5 | insertion_sort | 0.13 | 0.02 | 5 |

**exp_a582f67436** — Benchmark round 2 covering 1 hypothesis(es) (0.1s, n = 128 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 0.07 | 0.01 | 5 |
| 2 | shell_sort | 0.08 | 0.01 | 5 |
| 3 | heap_sort | 0.10 | 0.01 | 5 |
| 4 | merge_sort | 0.13 | 0.02 | 5 |
| 5 | hybrid_sort | 0.13 | 0.11 | 5 |
| 6 | insertion_sort | 0.14 | 0.01 | 5 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.01 | 0.00 | 5 |
| 2 | hybrid_sort | 0.03 | 0.03 | 5 |
| 3 | shell_sort | 0.03 | 0.01 | 5 |
| 4 | quick_sort | 0.05 | 0.01 | 5 |
| 5 | merge_sort | 0.09 | 0.01 | 5 |
| 6 | heap_sort | 0.10 | 0.01 | 5 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 0.04 | 0.00 | 5 |
| 2 | shell_sort | 0.05 | 0.00 | 5 |
| 3 | merge_sort | 0.08 | 0.00 | 5 |
| 4 | hybrid_sort | 0.09 | 0.00 | 5 |
| 5 | heap_sort | 0.10 | 0.01 | 5 |
| 6 | insertion_sort | 0.26 | 0.01 | 5 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | shell_sort | 0.06 | 0.01 | 5 |
| 2 | hybrid_sort | 0.06 | 0.00 | 5 |
| 3 | quick_sort | 0.06 | 0.01 | 5 |
| 4 | heap_sort | 0.10 | 0.01 | 5 |
| 5 | insertion_sort | 0.12 | 0.01 | 5 |
| 6 | merge_sort | 0.13 | 0.04 | 5 |

## 10. Failed approaches (failure log)

- **exp_066779c791** / hyp_fc15d13b1b: predicted “merge_sort is fastest on random”; observed: fastest_on on 'random' is quick_sort, not merge_sort (85% apart, decisive) [n=128, 5 trials]. Action: hypothesis status re-evaluated from evidence.

## 11. Decision history

- step 0 [select_investigation] → **hyp_48de48fcea** — highest expected information gain per unit cost; experiment co-tests 4 hypothesis(es)
- step 1 [select_investigation] → **hyp_5542e8d61c** — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)

## 12. Current conclusions

Weakened (mixed evidence — revision candidates):

- Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes.
- Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input.
- Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.
- A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) beats plain merge sort on random AND nearly-sorted input at the tested sizes.

Rejected by experiment:

- Merge sort is the fastest pure-Python candidate on random input.

## 13. Confidence and cautions

- Regime 'random' at n=128 in exp_066779c791: quick_sort has the lowest mean but is not statistically separable from shell_sort at 5 trials — no winner is claimed.
- Regime 'reversed' at n=128 in exp_066779c791: quick_sort has the lowest mean but is not statistically separable from shell_sort at 5 trials — no winner is claimed.
- Regime 'few_unique' at n=128 in exp_066779c791: shell_sort has the lowest mean but is not statistically separable from quick_sort at 5 trials — no winner is claimed.
- hyp_48de48fcea: no prediction could be resolved at this trial count; treat as untested rather than disproved.
- hyp_2be7e87921: no prediction could be resolved at this trial count; treat as untested rather than disproved.
- hyp_db14df8458: no prediction could be resolved at this trial count; treat as untested rather than disproved.
- Regime 'random' at n=128 in exp_a582f67436: quick_sort has the lowest mean but is not statistically separable from hybrid_sort, shell_sort at 5 trials — no winner is claimed.
- Regime 'nearly_sorted' at n=128 in exp_a582f67436: insertion_sort has the lowest mean but is not statistically separable from hybrid_sort at 5 trials — no winner is claimed.
- Regime 'few_unique' at n=128 in exp_a582f67436: shell_sort has the lowest mean but is not statistically separable from hybrid_sort, quick_sort at 5 trials — no winner is claimed.
- hyp_5542e8d61c: no prediction could be resolved at this trial count; treat as untested rather than disproved.

## 14. Novel findings

- ORIGIN synthesized a new candidate from round-1 evidence: **A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) beats plain merge sort on random AND nearly-sorted input at the tested sizes.** → outcome: **weakened**.

## 15. Remaining questions & recommended next investigations

- Investigate knowledge gap: Scaling behavior beyond n=128 is untested (asymptotic crossovers may differ).
- Investigate knowledge gap: Memory usage and comparison/move counts were not measured (wall time only).
- Investigate knowledge gap: Adversarial input patterns (sawtooth, organ-pipe, quicksort-killer) are untested.
- Investigate knowledge gap: Only one machine/interpreter was used; hardware sensitivity is unknown.
- Investigate knowledge gap: Stability of the sorts (equal-key ordering) was not evaluated.
- Revise or split hyp_48de48fcea: mixed evidence (1 for / 0 against).
- Revise or split hyp_2be7e87921: mixed evidence (1 for / 0 against).
- Revise or split hyp_db14df8458: mixed evidence (1 for / 0 against).
- Revise or split hyp_5542e8d61c: mixed evidence (1 for / 0 against).

## 15b. Measurement environment and scope of performance claims

- **CPython 3.12.3 on Linux/x86_64, 1 CPU(s)** — 2 experiment(s)
- Fixed reference workload (sorting 20k floats): median 2.43–2.69 ms across runs — use this to put timings from another machine in proportion.

**Every performance statement in this dossier is scoped to:** the machine and interpreter above; the input regimes ['random', 'nearly_sorted', 'reversed', 'few_unique']; the input sizes [64, 128]; 5 trials per measurement cell; and pure-Python implementations of the listed algorithms. Nothing here is a claim about these algorithms in general, in another language, at other input sizes, or on other hardware.

Comparisons are only called decisive when the separation exceeds 3x the combined standard error of the two means AND at least 10% of the faster mean, with at least 5 trials on both sides. Everything else is recorded as INCONCLUSIVE — not as a win, and not as a refutation.

## 16. Prediction ledger

| Hypothesis | Prediction | Check | Outcome | Basis |
|---|---|---|---|---|
| hyp_48de48fcea | insertion_sort is fastest on nearly_sorted | `fastest_on` | **confirmed** | fastest_on on 'nearly_sorted' is insertion_sort (0.0 ms, margin 407% over shell_sort, separation 0.02 ms > required 0.00 ms) [n=128, 5 trials] |
| hyp_48de48fcea | insertion_sort is slowest on random | `slowest_on` | **inconclusive** | insertion_sort has the lowest mean on 'random' (0.1 ms) but is not decisively slower than merge_sort: uncertainty_overlap (gap 0.025 ms <= 3x combined SEM 0.033 ms) [n=128, 5 trial |
| hyp_fc15d13b1b | merge_sort is fastest on random | `fastest_on` | **refuted** | fastest_on on 'random' is quick_sort, not merge_sort (85% apart, decisive) [n=128, 5 trials] |
| hyp_2be7e87921 | quick_sort within 25% of best on random | `within_pct_of_best` | **inconclusive** | quick_sort is 0% off best on 'random' (limit 25%), within the ±29% uncertainty of the threshold [n=128, 5 trials] |
| hyp_2be7e87921 | quick_sort within 200% of best on reversed | `within_pct_of_best` | **confirmed** | quick_sort is 0% off best on 'reversed' (limit 200%, uncertainty ±5%) [n=128, 5 trials] |
| hyp_db14df8458 | heap_sort has lowest mean relative stdev | `lowest_mean_rel_stdev` | **inconclusive** | lowest mean relative stdev is quick_sort (0.069) but heap_sort is within 25% — dispersion ranking is not separable here [n=128, 5 trials] |
| hyp_db14df8458 | heap_sort is never fastest in any regime | `never_fastest` | **confirmed** | regime winners: ['insertion_sort', 'quick_sort', 'shell_sort'] (decisively separated in: ['nearly_sorted']) [n=128, 5 trials] |
| hyp_5542e8d61c | hybrid_sort beats merge_sort on random by >= 5% | `beats` | **inconclusive** | hybrid_sort vs merge_sort on 'random': -0% but not decisive (uncertainty_overlap (gap 0.000 ms <= 3x combined SEM 0.172 ms)) [n=128, 5 trials] |
| hyp_5542e8d61c | hybrid_sort beats merge_sort on nearly_sorted | `beats` | **confirmed** | hybrid_sort vs merge_sort on 'nearly_sorted': +190% (needs >= 0%, decisive: gap 0.06 ms > required 0.06 ms) [n=128, 5 trials] |

`inconclusive` means the measurement could not resolve the question at this trial count — it is neither support nor refutation.

## 16b. LLM proposal ledger

- No LLM proposals were offered in this mission (brain: `none`).

## 17. Falsification attempts (critic attacks)

- No falsification attempts this run.

## 18. Budget ledger & stop reason

- Experiments: 2/8
- Compute: 0.1s / 600s
- Active runtime (controller): 0.2s (no wall-time cap)
- Provider calls: 0 (uncapped)
- Retries: 0/8
- **Stop reason**: (mission still active)

## 19. Threats to validity

- Single machine, single CPython version: absolute timings will not transfer; only within-run rankings are meaningful, and only at the tested sizes.
- Wall-clock time only: no comparison counts, memory, or cache metrics. A ranking here is a ranking of *this implementation on this host*, not of the algorithms as such.
- Trial count (5 per cell) supports the conservative separation rule used here, not a formal hypothesis test; no p-values are computed or implied.
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
- Budget consumed: 2/8 experiments, 0.1s compute
