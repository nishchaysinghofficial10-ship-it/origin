# ORIGIN Research Dossier

Generated: 2026-08-13 19:42:28  |  ORIGIN v2.0.0  |  domain: `algobench`

## 1. Research question

> Under what input distributions and sizes does a hybrid merge/insertion sorting strategy outperform predefined baselines without violating correctness, and what insertion cutoff is optimal per regime?

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
- **[EXPERIMENTAL_RESULT]** Hybrid insertion-cutoff optima at n=4096 (7 trials, CPython 3.12.3 on Linux/x86_64): random=16 (indistinguishable from [8, 32]), nearly_sorted=64 (indistinguishable from [32]), reversed=8 (indistinguishable from [16]), few_unique=16 (indistinguishable from [8, 32]) (confidence 0.60)

## 4. Evidence map (knowledge graph)

- quick_sort —fastest_on→ random (confidence 0.90, evidence: 14)
- insertion_sort —fastest_on→ nearly_sorted (confidence 0.90, evidence: 14)
- quick_sort —fastest_on→ reversed (confidence 0.90, evidence: 13)
- quick_sort —fastest_on→ few_unique (confidence 0.90, evidence: 13)
- hybrid_sort —derived_from→ merge_sort (confidence 0.99, evidence: 0)
- hybrid_sort —derived_from→ insertion_sort (confidence 0.99, evidence: 0)

## 5. Contradictions

- None detected across experiments in this run.

## 6. Knowledge gaps

- Scaling behavior beyond n=4096 is untested (asymptotic crossovers may differ).
- Memory usage and comparison/move counts were not measured (wall time only).
- Adversarial input patterns (sawtooth, organ-pipe, quicksort-killer) are untested.
- Only one machine/interpreter was used; hardware sensitivity is unknown.
- Stability of the sorts (equal-key ordering) was not evaluated.

## 7. Hypotheses (competing pool, with evidence ledgers)

### hyp_dbe5f386a7 — ACCEPTED_WITH_SCOPE

**Statement.** Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes.

**Rationale.** Adaptive O(n + inversions) behavior dominates on low-inversion input; O(n^2) dominates on random input.

Supporting evidence: 4 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 2 | refuted: 0

- [CONFIRMED] insertion_sort is fastest on nearly_sorted — fastest_on on 'nearly_sorted' is insertion_sort (0.5 ms, margin 704% over shell_sort, separation 3.45 ms > required 0.07 ms) [n=4096, 7 trials]
- [CONFIRMED] insertion_sort is slowest on random — slowest_on on 'random' is insertion_sort (375.7 ms, margin 1802% over shell_sort, separation 355.94 ms > required 9.65 ms) [n=4096, 7 trials]

### hyp_fa035de7df — REJECTED

**Statement.** Merge sort is the fastest pure-Python candidate on random input.

**Rationale.** Guaranteed n log n with sequential memory access; no pathological cases.

Supporting evidence: 0 | Contradicting: 1 | Experiments: 1 | Predictions confirmed: 0 | refuted: 1

- [REFUTED] merge_sort is fastest on random — fastest_on on 'random' is quick_sort, not merge_sort (71% apart, decisive) [n=4096, 7 trials]

### hyp_cae1c60f85 — ACCEPTED_WITH_SCOPE

**Statement.** Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input.

**Rationale.** MO3 pivoting neutralizes ordered-input pathologies; constant factors are low.

Supporting evidence: 4 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 2 | refuted: 0

- [CONFIRMED] quick_sort within 25% of best on random — quick_sort is 0% off best on 'random' (limit 25%, uncertainty ±24%) [n=4096, 7 trials]
- [CONFIRMED] quick_sort within 200% of best on reversed — quick_sort is 0% off best on 'reversed' (limit 200%, uncertainty ±4%) [n=4096, 7 trials]

### hyp_ad33a3dcb5 — WEAKENED

**Statement.** Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.

**Rationale.** Input-oblivious n log n behavior; poor cache locality keeps constants high.

Supporting evidence: 1 | Contradicting: 1 | Experiments: 1 | Predictions confirmed: 1 | refuted: 1

- [REFUTED] heap_sort has lowest mean relative stdev — lowest mean relative stdev: merge_sort (0.050); next is quick_sort (0.063) [n=4096, 7 trials]
- [CONFIRMED] heap_sort is never fastest in any regime — regime winners: ['insertion_sort', 'quick_sort'] (decisively separated in: ['few_unique', 'nearly_sorted', 'random', 'reversed']) [n=4096, 7 trials]

### hyp_40df9834c7 — ACCEPTED_WITH_SCOPE

**Statement.** Shell sort beats insertion sort on random input but not on nearly-sorted input at the tested sizes.

**Rationale.** [mock proposal prop_92794c6d1c] Gap sequences reduce long-distance disorder faster than adjacent swaps; on nearly-sorted data insertion sort's adaptivity should dominate.

Supporting evidence: 2 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 1 | refuted: 0

- [CONFIRMED] Shell sort beats insertion sort on random input but not on nearly-sorted input at the tested sizes. — shell_sort vs insertion_sort on 'random': +739% (needs >= 0.0%, decisive: gap 19.45 ms > required 1.39 ms) [n=1024, 7 trials]

### hyp_f1699d47b3 — REJECTED

**Statement.** Heap sort beats shell sort on reversed input at the tested sizes.

**Rationale.** [mock proposal prop_b8a25c4aab] Reversed input is adversarial for gap/insertion strategies while heap construction cost is input-independent.

Supporting evidence: 0 | Contradicting: 1 | Experiments: 1 | Predictions confirmed: 0 | refuted: 1

- [REFUTED] Heap sort beats shell sort on reversed input at the tested sizes. — heap_sort is decisively SLOWER than shell_sort on 'reversed' (-30%) [n=4096, 7 trials]

### hyp_38e7e1fe16 — ACCEPTED_WITH_SCOPE

**Statement.** A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) beats plain merge sort on random AND nearly-sorted input at the tested sizes.

**Rationale.** Round-1 evidence: 'insertion_sort' won nearly_sorted and 'quick_sort' won random. Combining merge structure with insertion's strength on short/ordered runs should reduce recursion overhead without losing n log n guarantees. Derived from experiment exp_c512323528.

Supporting evidence: 4 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 2 | refuted: 0

- [CONFIRMED] hybrid_sort beats merge_sort on random by >= 5% — hybrid_sort vs merge_sort on 'random': +53% (needs >= 5%, decisive: gap 3.24 ms > required 0.62 ms) [n=4096, 7 trials]
- [CONFIRMED] hybrid_sort beats merge_sort on nearly_sorted — hybrid_sort vs merge_sort on 'nearly_sorted': +182% (needs >= 0%, decisive: gap 4.41 ms > required 0.93 ms) [n=4096, 7 trials]

### hyp_bf17e1f36c — WEAKENED

**Statement.** The hybrid's optimal insertion cutoff on random input lies in [16, 64], and the optimal cutoff on nearly-sorted input is >= the optimum on random input.

**Rationale.** Python call overhead favors moderate cutoffs; insertion sort's adaptivity should tolerate larger segments on nearly-sorted data. Pre-registered before any sweep ran.

Supporting evidence: 0 | Contradicting: 0 | Experiments: 1 | Predictions confirmed: 0 | refuted: 0

- [INCONCLUSIVE] optimal cutoff on random in [16, 64] — best cutoff on random = 16 (inside [16,64]) but cutoffs [8] are statistically indistinguishable from it at 7 trials — the optimum is not resolvable to that interval
- [INCONCLUSIVE] optimal cutoff on nearly_sorted >= optimal on random — optimum nearly_sorted=64 vs random=16, but the optima are not uniquely identified (indistinguishable sets: nearly_sorted=[32, 64], random=[8, 16, 32])

## 8. Experiments

- `exp_c512323528` [completed] Benchmark round 1 covering 4 hypothesis(es) — 12.0s (design: 5 algorithms x 4 regimes x sizes [256, 1024, 4096])
- `exp_48613ed686` [completed] Benchmark round 2 covering 1 hypothesis(es) — 12.3s (design: 6 algorithms x 4 regimes x sizes [256, 1024, 4096])
- `exp_42d46105c8` [completed] Benchmark round 3 covering 1 hypothesis(es) — 0.8s (design: 4 algorithms x 4 regimes x sizes [4096])
- `exp_2593d8e300` [completed] Benchmark round 5 covering 1 hypothesis(es) — 0.4s (design: 5 algorithms x 2 regimes x sizes [256, 1024])
- `exp_409be65fa9` [completed] Benchmark round 1 covering 1 hypothesis(es) — 12.1s (design: 5 algorithms x 4 regimes x sizes [256, 1024, 4096])
- `exp_dac3afe6aa` [completed] Replication of hyp_dbe5f386a7 — 11.6s (design: 5 algorithms x 4 regimes x sizes [4096])
- `exp_ac020259d2` [completed] Replication of hyp_cae1c60f85 — 11.1s (design: 5 algorithms x 4 regimes x sizes [4096])
- `exp_13f5f8410a` [completed] Replication of hyp_40df9834c7 — 11.4s (design: 5 algorithms x 4 regimes x sizes [4096])
- `exp_1351d074bc` [completed] Replication of hyp_38e7e1fe16 — 11.4s (design: 6 algorithms x 4 regimes x sizes [4096])
- `exp_9c23de511f` [completed] Falsification probe of hyp_dbe5f386a7 — 34.7s (design: 5 algorithms x 4 regimes x sizes [8192])
- `exp_98238f5fae` [completed] Falsification probe of hyp_cae1c60f85 — 56.3s (design: 5 algorithms x 4 regimes x sizes [8192])
- `exp_6590a2f6db` [completed] Falsification probe of hyp_40df9834c7 — 34.7s (design: 5 algorithms x 3 regimes x sizes [8192])
- `exp_20b306145c` [completed] Falsification probe of hyp_38e7e1fe16 — 35.2s (design: 6 algorithms x 4 regimes x sizes [8192])

## 9. Results

**exp_c512323528** — Benchmark round 1 covering 4 hypothesis(es) (12.0s, n = 4096 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 5.45 | 0.57 | 7 |
| 2 | merge_sort | 9.31 | 0.19 | 7 |
| 3 | heap_sort | 9.90 | 0.15 | 7 |
| 4 | shell_sort | 19.75 | 1.84 | 7 |
| 5 | insertion_sort | 375.69 | 6.68 | 7 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.49 | 0.01 | 7 |
| 2 | shell_sort | 3.94 | 0.05 | 7 |
| 3 | quick_sort | 4.02 | 0.03 | 7 |
| 4 | merge_sort | 6.61 | 0.08 | 7 |
| 5 | heap_sort | 10.13 | 0.10 | 7 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.11 | 0.07 | 7 |
| 2 | shell_sort | 6.43 | 0.12 | 7 |
| 3 | merge_sort | 6.98 | 0.72 | 7 |
| 4 | heap_sort | 9.07 | 0.12 | 7 |
| 5 | insertion_sort | 726.79 | 10.23 | 7 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.89 | 0.08 | 7 |
| 2 | shell_sort | 6.59 | 0.26 | 7 |
| 3 | heap_sort | 8.51 | 0.08 | 7 |
| 4 | merge_sort | 8.81 | 0.40 | 7 |
| 5 | insertion_sort | 326.48 | 9.63 | 7 |

**exp_48613ed686** — Benchmark round 2 covering 1 hypothesis(es) (12.3s, n = 4096 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 5.30 | 0.22 | 7 |
| 2 | hybrid_sort | 6.11 | 0.08 | 7 |
| 3 | merge_sort | 9.35 | 0.46 | 7 |
| 4 | heap_sort | 9.87 | 0.19 | 7 |
| 5 | shell_sort | 19.93 | 1.66 | 7 |
| 6 | insertion_sort | 381.68 | 7.42 | 7 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.52 | 0.03 | 7 |
| 2 | hybrid_sort | 2.42 | 0.26 | 7 |
| 3 | shell_sort | 3.91 | 0.01 | 7 |
| 4 | quick_sort | 4.09 | 0.18 | 7 |
| 5 | merge_sort | 6.83 | 0.56 | 7 |
| 6 | heap_sort | 10.26 | 0.57 | 7 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.11 | 0.05 | 7 |
| 2 | shell_sort | 6.39 | 0.11 | 7 |
| 3 | merge_sort | 6.66 | 0.14 | 7 |
| 4 | hybrid_sort | 7.16 | 1.35 | 7 |
| 5 | heap_sort | 9.47 | 0.93 | 7 |
| 6 | insertion_sort | 738.19 | 8.02 | 7 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.84 | 0.10 | 7 |
| 2 | hybrid_sort | 5.35 | 0.20 | 7 |
| 3 | shell_sort | 6.59 | 0.36 | 7 |
| 4 | merge_sort | 8.48 | 0.22 | 7 |
| 5 | heap_sort | 9.00 | 0.95 | 7 |
| 6 | insertion_sort | 318.44 | 5.81 | 7 |

**exp_42d46105c8** — Benchmark round 3 covering 1 hypothesis(es) (0.8s, n = 4096 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_c16 | 6.10 | 0.87 | 7 |
| 2 | hybrid_c32 | 6.14 | 0.03 | 7 |
| 3 | hybrid_c8 | 6.14 | 0.25 | 7 |
| 4 | hybrid_c64 | 7.62 | 0.24 | 7 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_c64 | 2.13 | 0.17 | 7 |
| 2 | hybrid_c32 | 2.42 | 0.16 | 7 |
| 3 | hybrid_c16 | 2.74 | 0.10 | 7 |
| 4 | hybrid_c8 | 3.11 | 0.02 | 7 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_c8 | 4.13 | 0.35 | 7 |
| 2 | hybrid_c16 | 4.40 | 0.03 | 7 |
| 3 | hybrid_c32 | 6.26 | 0.49 | 7 |
| 4 | hybrid_c64 | 10.01 | 1.23 | 7 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_c16 | 5.03 | 0.08 | 7 |
| 2 | hybrid_c8 | 5.19 | 0.03 | 7 |
| 3 | hybrid_c32 | 5.55 | 0.54 | 7 |
| 4 | hybrid_c64 | 6.50 | 0.08 | 7 |

**exp_2593d8e300** — Benchmark round 5 covering 1 hypothesis(es) (0.4s, n = 1024 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 1.12 | 0.03 | 7 |
| 2 | merge_sort | 1.96 | 0.03 | 7 |
| 3 | heap_sort | 2.01 | 0.21 | 7 |
| 4 | shell_sort | 2.63 | 0.27 | 7 |
| 5 | insertion_sort | 22.09 | 0.96 | 7 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.12 | 0.01 | 7 |
| 2 | shell_sort | 0.77 | 0.05 | 7 |
| 3 | quick_sort | 0.86 | 0.03 | 7 |
| 4 | merge_sort | 1.51 | 0.06 | 7 |
| 5 | heap_sort | 1.95 | 0.03 | 7 |

**exp_409be65fa9** — Benchmark round 1 covering 1 hypothesis(es) (12.1s, n = 4096 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 5.45 | 0.29 | 7 |
| 2 | merge_sort | 9.35 | 0.17 | 7 |
| 3 | heap_sort | 9.92 | 0.19 | 7 |
| 4 | shell_sort | 20.56 | 1.52 | 7 |
| 5 | insertion_sort | 380.19 | 6.21 | 7 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.50 | 0.04 | 7 |
| 2 | quick_sort | 4.03 | 0.07 | 7 |
| 3 | shell_sort | 4.14 | 0.22 | 7 |
| 4 | merge_sort | 6.66 | 0.14 | 7 |
| 5 | heap_sort | 10.18 | 0.17 | 7 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.07 | 0.05 | 7 |
| 2 | shell_sort | 6.49 | 0.20 | 7 |
| 3 | merge_sort | 6.53 | 0.06 | 7 |
| 4 | heap_sort | 9.32 | 0.25 | 7 |
| 5 | insertion_sort | 736.91 | 14.98 | 7 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.98 | 0.43 | 7 |
| 2 | shell_sort | 6.67 | 0.29 | 7 |
| 3 | heap_sort | 8.60 | 0.11 | 7 |
| 4 | merge_sort | 8.72 | 0.68 | 7 |
| 5 | insertion_sort | 325.91 | 11.76 | 7 |

**exp_dac3afe6aa** — Replication of hyp_dbe5f386a7 (11.6s, n = 4096 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 5.62 | 0.88 | 7 |
| 2 | merge_sort | 9.61 | 0.39 | 7 |
| 3 | heap_sort | 9.88 | 0.08 | 7 |
| 4 | shell_sort | 18.47 | 1.63 | 7 |
| 5 | insertion_sort | 388.86 | 2.99 | 7 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.51 | 0.03 | 7 |
| 2 | quick_sort | 4.13 | 0.08 | 7 |
| 3 | shell_sort | 4.34 | 0.74 | 7 |
| 4 | merge_sort | 6.57 | 0.08 | 7 |
| 5 | heap_sort | 10.83 | 0.34 | 7 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.24 | 0.22 | 7 |
| 2 | shell_sort | 6.54 | 0.14 | 7 |
| 3 | merge_sort | 6.68 | 0.16 | 7 |
| 4 | heap_sort | 9.39 | 0.24 | 7 |
| 5 | insertion_sort | 776.16 | 54.83 | 7 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.85 | 0.07 | 7 |
| 2 | shell_sort | 7.46 | 1.36 | 7 |
| 3 | heap_sort | 8.98 | 0.67 | 7 |
| 4 | merge_sort | 9.00 | 0.55 | 7 |
| 5 | insertion_sort | 331.08 | 3.86 | 7 |

**exp_ac020259d2** — Replication of hyp_cae1c60f85 (11.1s, n = 4096 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 5.12 | 0.03 | 7 |
| 2 | merge_sort | 9.22 | 0.04 | 7 |
| 3 | heap_sort | 9.77 | 0.06 | 7 |
| 4 | shell_sort | 18.66 | 1.45 | 7 |
| 5 | insertion_sort | 378.47 | 6.55 | 7 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.49 | 0.02 | 7 |
| 2 | shell_sort | 3.94 | 0.05 | 7 |
| 3 | quick_sort | 4.06 | 0.05 | 7 |
| 4 | merge_sort | 6.53 | 0.07 | 7 |
| 5 | heap_sort | 10.28 | 0.14 | 7 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.36 | 0.69 | 7 |
| 2 | shell_sort | 6.30 | 0.06 | 7 |
| 3 | merge_sort | 6.63 | 0.20 | 7 |
| 4 | heap_sort | 9.12 | 0.13 | 7 |
| 5 | insertion_sort | 726.39 | 7.22 | 7 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.80 | 0.05 | 7 |
| 2 | shell_sort | 6.93 | 0.27 | 7 |
| 3 | merge_sort | 8.47 | 0.05 | 7 |
| 4 | heap_sort | 8.95 | 0.71 | 7 |
| 5 | insertion_sort | 316.12 | 4.07 | 7 |

**exp_13f5f8410a** — Replication of hyp_40df9834c7 (11.4s, n = 4096 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 5.27 | 0.27 | 7 |
| 2 | merge_sort | 9.65 | 0.78 | 7 |
| 3 | heap_sort | 10.05 | 0.35 | 7 |
| 4 | shell_sort | 18.16 | 1.66 | 7 |
| 5 | insertion_sort | 376.96 | 3.34 | 7 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.51 | 0.04 | 7 |
| 2 | shell_sort | 3.94 | 0.10 | 7 |
| 3 | quick_sort | 4.09 | 0.10 | 7 |
| 4 | merge_sort | 6.74 | 0.29 | 7 |
| 5 | heap_sort | 10.31 | 0.24 | 7 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.09 | 0.04 | 7 |
| 2 | shell_sort | 6.29 | 0.05 | 7 |
| 3 | merge_sort | 6.61 | 0.11 | 7 |
| 4 | heap_sort | 9.35 | 0.54 | 7 |
| 5 | insertion_sort | 757.54 | 36.15 | 7 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.89 | 0.19 | 7 |
| 2 | shell_sort | 7.50 | 1.26 | 7 |
| 3 | merge_sort | 8.73 | 0.25 | 7 |
| 4 | heap_sort | 8.80 | 0.40 | 7 |
| 5 | insertion_sort | 330.31 | 7.84 | 7 |

**exp_1351d074bc** — Replication of hyp_38e7e1fe16 (11.4s, n = 4096 shown)

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 5.29 | 0.19 | 7 |
| 2 | hybrid_sort | 6.18 | 0.06 | 7 |
| 3 | merge_sort | 9.43 | 0.27 | 7 |
| 4 | heap_sort | 9.96 | 0.26 | 7 |
| 5 | shell_sort | 18.47 | 2.22 | 7 |
| 6 | insertion_sort | 393.89 | 11.65 | 7 |

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 0.60 | 0.18 | 7 |
| 2 | hybrid_sort | 2.40 | 0.05 | 7 |
| 3 | shell_sort | 3.92 | 0.04 | 7 |
| 4 | quick_sort | 4.14 | 0.10 | 7 |
| 5 | merge_sort | 6.57 | 0.04 | 7 |
| 6 | heap_sort | 10.16 | 0.09 | 7 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.11 | 0.04 | 7 |
| 2 | hybrid_sort | 6.05 | 0.13 | 7 |
| 3 | shell_sort | 6.39 | 0.06 | 7 |
| 4 | merge_sort | 6.69 | 0.20 | 7 |
| 5 | heap_sort | 9.10 | 0.09 | 7 |
| 6 | insertion_sort | 723.29 | 7.90 | 7 |

Regime `few_unique`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 4.81 | 0.05 | 7 |
| 2 | hybrid_sort | 5.53 | 0.15 | 7 |
| 3 | shell_sort | 7.00 | 0.34 | 7 |
| 4 | merge_sort | 8.48 | 0.09 | 7 |
| 5 | heap_sort | 8.77 | 0.49 | 7 |
| 6 | insertion_sort | 321.43 | 1.79 | 7 |

**exp_9c23de511f** — Falsification probe of hyp_dbe5f386a7 (34.7s, n = 8192 shown)

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 1.00 | 0.02 | 7 |
| 2 | quick_sort | 9.04 | 0.93 | 7 |
| 3 | shell_sort | 14.01 | 0.93 | 7 |
| 4 | merge_sort | 14.79 | 0.51 | 7 |
| 5 | heap_sort | 24.74 | 1.03 | 7 |

Regime `organ_pipe`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 16.01 | 1.35 | 7 |
| 2 | merge_sort | 18.38 | 0.58 | 7 |
| 3 | shell_sort | 21.40 | 4.91 | 7 |
| 4 | heap_sort | 23.80 | 1.83 | 7 |
| 5 | insertion_sort | 1517.98 | 29.66 | 7 |

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 11.02 | 0.14 | 7 |
| 2 | merge_sort | 20.14 | 0.14 | 7 |
| 3 | heap_sort | 22.97 | 1.35 | 7 |
| 4 | shell_sort | 53.90 | 14.11 | 7 |
| 5 | insertion_sort | 1535.60 | 17.31 | 7 |

Regime `sawtooth`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 11.21 | 0.77 | 7 |
| 2 | merge_sort | 16.92 | 0.37 | 7 |
| 3 | heap_sort | 21.15 | 0.46 | 7 |
| 4 | shell_sort | 68.10 | 14.96 | 7 |
| 5 | insertion_sort | 1462.06 | 43.61 | 7 |

**exp_98238f5fae** — Falsification probe of hyp_cae1c60f85 (56.3s, n = 8192 shown)

Regime `organ_pipe`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 15.69 | 1.54 | 7 |
| 2 | merge_sort | 17.98 | 0.61 | 7 |
| 3 | shell_sort | 19.37 | 2.51 | 7 |
| 4 | heap_sort | 22.53 | 0.22 | 7 |
| 5 | insertion_sort | 1574.20 | 45.18 | 7 |

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 12.28 | 1.19 | 7 |
| 2 | merge_sort | 21.10 | 0.90 | 7 |
| 3 | heap_sort | 22.78 | 1.28 | 7 |
| 4 | shell_sort | 49.95 | 8.97 | 7 |
| 5 | insertion_sort | 1520.49 | 20.53 | 7 |

Regime `reversed`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 8.92 | 0.20 | 7 |
| 2 | shell_sort | 14.38 | 0.14 | 7 |
| 3 | merge_sort | 14.90 | 0.86 | 7 |
| 4 | heap_sort | 20.86 | 0.70 | 7 |
| 5 | insertion_sort | 3076.16 | 64.19 | 7 |

Regime `sawtooth`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 11.06 | 0.39 | 7 |
| 2 | merge_sort | 18.40 | 1.46 | 7 |
| 3 | heap_sort | 21.08 | 0.09 | 7 |
| 4 | shell_sort | 60.00 | 0.98 | 7 |
| 5 | insertion_sort | 1442.79 | 21.47 | 7 |

**exp_6590a2f6db** — Falsification probe of hyp_40df9834c7 (34.7s, n = 8192 shown)

Regime `organ_pipe`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 16.05 | 1.70 | 7 |
| 2 | merge_sort | 17.54 | 0.15 | 7 |
| 3 | shell_sort | 20.25 | 2.75 | 7 |
| 4 | heap_sort | 22.73 | 0.31 | 7 |
| 5 | insertion_sort | 1564.34 | 22.25 | 7 |

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 11.26 | 0.26 | 7 |
| 2 | merge_sort | 20.29 | 0.17 | 7 |
| 3 | heap_sort | 22.47 | 0.22 | 7 |
| 4 | shell_sort | 51.49 | 8.99 | 7 |
| 5 | insertion_sort | 1577.56 | 17.17 | 7 |

Regime `sawtooth`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 11.32 | 0.72 | 7 |
| 2 | merge_sort | 16.76 | 0.36 | 7 |
| 3 | heap_sort | 21.48 | 0.68 | 7 |
| 4 | shell_sort | 62.27 | 3.55 | 7 |
| 5 | insertion_sort | 1451.57 | 34.45 | 7 |

**exp_20b306145c** — Falsification probe of hyp_38e7e1fe16 (35.2s, n = 8192 shown)

Regime `nearly_sorted`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | insertion_sort | 1.06 | 0.06 | 7 |
| 2 | hybrid_sort | 5.72 | 0.82 | 7 |
| 3 | quick_sort | 8.73 | 0.15 | 7 |
| 4 | shell_sort | 9.10 | 0.14 | 7 |
| 5 | merge_sort | 15.07 | 0.78 | 7 |
| 6 | heap_sort | 23.88 | 1.21 | 7 |

Regime `organ_pipe`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_sort | 12.84 | 0.94 | 7 |
| 2 | quick_sort | 16.20 | 2.06 | 7 |
| 3 | merge_sort | 18.38 | 1.06 | 7 |
| 4 | shell_sort | 19.41 | 1.86 | 7 |
| 5 | heap_sort | 22.42 | 0.50 | 7 |
| 6 | insertion_sort | 1546.95 | 33.17 | 7 |

Regime `random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | quick_sort | 11.72 | 0.46 | 7 |
| 2 | hybrid_sort | 14.21 | 0.44 | 7 |
| 3 | merge_sort | 21.29 | 0.97 | 7 |
| 4 | heap_sort | 23.32 | 1.29 | 7 |
| 5 | shell_sort | 52.18 | 9.20 | 7 |
| 6 | insertion_sort | 1542.99 | 27.35 | 7 |

Regime `sawtooth`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | hybrid_sort | 8.10 | 0.39 | 7 |
| 2 | quick_sort | 11.17 | 0.48 | 7 |
| 3 | merge_sort | 16.97 | 0.69 | 7 |
| 4 | heap_sort | 21.41 | 0.49 | 7 |
| 5 | shell_sort | 60.42 | 1.79 | 7 |
| 6 | insertion_sort | 1460.18 | 19.43 | 7 |

## 10. Failed approaches (failure log)

- **exp_c512323528** / hyp_fa035de7df: predicted “merge_sort is fastest on random”; observed: fastest_on on 'random' is quick_sort, not merge_sort (71% apart, decisive) [n=4096, 7 trials]. Action: hypothesis status re-evaluated from evidence.
- **exp_c512323528** / hyp_ad33a3dcb5: predicted “heap_sort has lowest mean relative stdev”; observed: lowest mean relative stdev: merge_sort (0.050); next is quick_sort (0.063) [n=4096, 7 trials]. Action: hypothesis status re-evaluated from evidence.
- **exp_409be65fa9** / hyp_f1699d47b3: predicted “Heap sort beats shell sort on reversed input at the tested sizes.”; observed: heap_sort is decisively SLOWER than shell_sort on 'reversed' (-30%) [n=4096, 7 trials]. Action: hypothesis status re-evaluated from evidence.

## 11. Decision history

- step 3 [select_investigation] → **hyp_dbe5f386a7** — highest expected information gain per unit cost; experiment co-tests 4 hypothesis(es)
- step 4 [select_investigation] → **hyp_38e7e1fe16** — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)
- step 5 [select_investigation] → **hyp_bf17e1f36c** — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)
- step 6 [select_investigation] → **hyp_40df9834c7** — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)
- step 7 [select_investigation] → **hyp_f1699d47b3** — highest expected information gain per unit cost; experiment co-tests 1 hypothesis(es)
- step 9 [critic_replication] → **hyp_dbe5f386a7** — critic refuses single-experiment support; independent replication with new seeds
- step 10 [critic_replication] → **hyp_cae1c60f85** — critic refuses single-experiment support; independent replication with new seeds
- step 11 [critic_replication] → **hyp_40df9834c7** — critic refuses single-experiment support; independent replication with new seeds
- step 12 [critic_replication] → **hyp_38e7e1fe16** — critic refuses single-experiment support; independent replication with new seeds
- step 13 [critic_falsification] → **hyp_dbe5f386a7** — falsification probes: boundary:nearly_sorted, scope:sawtooth, scope:organ_pipe, boundary:random, scope:sawtooth, scope:organ_pipe
- step 14 [critic_falsification] → **hyp_cae1c60f85** — falsification probes: boundary:random, scope:sawtooth, scope:organ_pipe, boundary:reversed, scope:sawtooth, scope:organ_pipe
- step 15 [critic_falsification] → **hyp_40df9834c7** — falsification probes: boundary:random, scope:sawtooth, scope:organ_pipe
- step 16 [critic_falsification] → **hyp_38e7e1fe16** — falsification probes: boundary:random, scope:sawtooth, scope:organ_pipe, boundary:nearly_sorted, scope:sawtooth, scope:organ_pipe

## 12. Current conclusions

Accepted with scope (replicated AND survived active falsification):

- Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes.
  - **scope**: holds at n<=2x tested sizes on its original regime(s); does NOT extend to ['organ_pipe', 'sawtooth']
- Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input.
  - **scope**: holds at n<=2x tested sizes on its original regime(s); extends to ['organ_pipe', 'sawtooth']
- Shell sort beats insertion sort on random input but not on nearly-sorted input at the tested sizes.
  - **scope**: holds at n<=2x tested sizes on its original regime(s); extends to ['organ_pipe', 'sawtooth']
- A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) beats plain merge sort on random AND nearly-sorted input at the tested sizes.
  - **scope**: holds at n<=2x tested sizes on its original regime(s); extends to ['organ_pipe', 'sawtooth']

Weakened (mixed evidence — revision candidates):

- Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.
- The hybrid's optimal insertion cutoff on random input lies in [16, 64], and the optimal cutoff on nearly-sorted input is >= the optimum on random input.

Rejected by experiment:

- Merge sort is the fastest pure-Python candidate on random input.
- Heap sort beats shell sort on reversed input at the tested sizes.

## 13. Confidence and cautions

- [mock counterargument, unverified] Timing rankings at these sizes may be dominated by interpreter overhead rather than algorithmic behaviour. (targets hyp_dbe5f386a7)
- High timing noise for winner in regime 'nearly_sorted' (stdev/mean = 0.30) in exp_1351d074bc; evidence strength capped.

## 14. Novel findings

- ORIGIN synthesized a new candidate from round-1 evidence: **A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) beats plain merge sort on random AND nearly-sorted input at the tested sizes.** → outcome: **accepted_with_scope**.
- ORIGIN synthesized a new candidate from round-1 evidence: **The hybrid's optimal insertion cutoff on random input lies in [16, 64], and the optimal cutoff on nearly-sorted input is >= the optimum on random input.** → outcome: **weakened**.

## 15. Remaining questions & recommended next investigations

- [mock knowledge gap] Comparison and move counts are not measured, so rankings cannot be separated from constant factors.
- Investigate knowledge gap: Scaling behavior beyond n=4096 is untested (asymptotic crossovers may differ).
- Investigate knowledge gap: Memory usage and comparison/move counts were not measured (wall time only).
- Investigate knowledge gap: Adversarial input patterns (sawtooth, organ-pipe, quicksort-killer) are untested.
- Investigate knowledge gap: Only one machine/interpreter was used; hardware sensitivity is unknown.
- Investigate knowledge gap: Stability of the sorts (equal-key ordering) was not evaluated.
- Revise or split hyp_ad33a3dcb5: mixed evidence (1 for / 1 against).
- Revise or split hyp_bf17e1f36c: mixed evidence (0 for / 0 against).

## 15b. Measurement environment and scope of performance claims

- **CPython 3.12.3 on Linux/x86_64, 1 CPU(s)** — 13 experiment(s)
- Fixed reference workload (sorting 20k floats): median 2.78–2.97 ms across runs — use this to put timings from another machine in proportion.

**Every performance statement in this dossier is scoped to:** the machine and interpreter above; the input regimes ['random', 'nearly_sorted', 'reversed', 'few_unique']; the input sizes [256, 1024, 4096]; 7 trials per measurement cell; and pure-Python implementations of the listed algorithms. Nothing here is a claim about these algorithms in general, in another language, at other input sizes, or on other hardware.

Comparisons are only called decisive when the separation exceeds 3x the combined standard error of the two means AND at least 10% of the faster mean, with at least 5 trials on both sides. Everything else is recorded as INCONCLUSIVE — not as a win, and not as a refutation.

## 16. Prediction ledger

| Hypothesis | Prediction | Check | Outcome | Basis |
|---|---|---|---|---|
| hyp_dbe5f386a7 | insertion_sort is fastest on nearly_sorted | `fastest_on` | **confirmed** | fastest_on on 'nearly_sorted' is insertion_sort (0.5 ms, margin 704% over shell_sort, separation 3.45 ms > required 0.07 ms) [n=4096, 7 trials] |
| hyp_dbe5f386a7 | insertion_sort is slowest on random | `slowest_on` | **confirmed** | slowest_on on 'random' is insertion_sort (375.7 ms, margin 1802% over shell_sort, separation 355.94 ms > required 9.65 ms) [n=4096, 7 trials] |
| hyp_fa035de7df | merge_sort is fastest on random | `fastest_on` | **refuted** | fastest_on on 'random' is quick_sort, not merge_sort (71% apart, decisive) [n=4096, 7 trials] |
| hyp_cae1c60f85 | quick_sort within 25% of best on random | `within_pct_of_best` | **confirmed** | quick_sort is 0% off best on 'random' (limit 25%, uncertainty ±24%) [n=4096, 7 trials] |
| hyp_cae1c60f85 | quick_sort within 200% of best on reversed | `within_pct_of_best` | **confirmed** | quick_sort is 0% off best on 'reversed' (limit 200%, uncertainty ±4%) [n=4096, 7 trials] |
| hyp_ad33a3dcb5 | heap_sort has lowest mean relative stdev | `lowest_mean_rel_stdev` | **refuted** | lowest mean relative stdev: merge_sort (0.050); next is quick_sort (0.063) [n=4096, 7 trials] |
| hyp_ad33a3dcb5 | heap_sort is never fastest in any regime | `never_fastest` | **confirmed** | regime winners: ['insertion_sort', 'quick_sort'] (decisively separated in: ['few_unique', 'nearly_sorted', 'random', 'reversed']) [n=4096, 7 trials] |
| hyp_40df9834c7 | Shell sort beats insertion sort on random input but not on nearly-sorted input at the tested sizes. | `beats` | **confirmed** | shell_sort vs insertion_sort on 'random': +739% (needs >= 0.0%, decisive: gap 19.45 ms > required 1.39 ms) [n=1024, 7 trials] |
| hyp_f1699d47b3 | Heap sort beats shell sort on reversed input at the tested sizes. | `beats` | **refuted** | heap_sort is decisively SLOWER than shell_sort on 'reversed' (-30%) [n=4096, 7 trials] |
| hyp_38e7e1fe16 | hybrid_sort beats merge_sort on random by >= 5% | `beats` | **confirmed** | hybrid_sort vs merge_sort on 'random': +53% (needs >= 5%, decisive: gap 3.24 ms > required 0.62 ms) [n=4096, 7 trials] |
| hyp_38e7e1fe16 | hybrid_sort beats merge_sort on nearly_sorted | `beats` | **confirmed** | hybrid_sort vs merge_sort on 'nearly_sorted': +182% (needs >= 0%, decisive: gap 4.41 ms > required 0.93 ms) [n=4096, 7 trials] |
| hyp_bf17e1f36c | optimal cutoff on random in [16, 64] | `sweep_optimum_in` | **inconclusive** | best cutoff on random = 16 (inside [16,64]) but cutoffs [8] are statistically indistinguishable from it at 7 trials — the optimum is not resolvable to that interval |
| hyp_bf17e1f36c | optimal cutoff on nearly_sorted >= optimal on random | `sweep_optimum_ge` | **inconclusive** | optimum nearly_sorted=64 vs random=16, but the optima are not uniquely identified (indistinguishable sets: nearly_sorted=[32, 64], random=[8, 16, 32]) |

`inconclusive` means the measurement could not resolve the question at this trial count — it is neither support nor refutation.

## 16b. LLM proposal ledger

Provider `mock` offered 5 proposal(s): **5 accepted, 0 rejected**. Full record, including rejected bodies, in `logs/proposals.jsonl`.

| Proposal | Type | Verdict | What ORIGIN did with it |
|---|---|---|---|
| `prop_92794c6d1c` | hypothesis | accepted | admitted as hyp_40df9834c7 (PROPOSED) |
| `prop_b8a25c4aab` | hypothesis | accepted | admitted as hyp_f1699d47b3 (PROPOSED) |
| `prop_68ed269780` | experiment | accepted | stored as a candidate design |
| `prop_ae9b78e435` | counterargument | accepted | recorded as a caution |
| `prop_a466f66485` | knowledge_gap | accepted | recorded as a knowledge gap |

An accepted proposal is **not** a finding. Accepted hypotheses entered as PROPOSED and were resolved by the experiments, replication and falsification recorded elsewhere in this dossier; counterarguments are unverified prose recorded as cautions; knowledge gaps are recommendations, not results.

## 17. Falsification attempts (critic attacks)

- **hyp_dbe5f386a7** — probe `boundary:nearly_sorted, scope:sawtooth, scope:organ_pipe, boundary:random, scope:sawtooth, scope:organ_pipe` → **survived**
  - [boundary:nearly_sorted] confirmed: fastest_on on 'nearly_sorted' is insertion_sort (1.0 ms, margin 805% over quick_sort, separation 8.04 ms > required 1.07 ms) [n=8192, 7 trials] | [scope:sawtooth] refuted: fastest_on on 'sawtooth' is quick_sort, not insertion_sort (12945% apart, decisive) [n=8192, 7 trials] | [scope:organ_pipe] refuted: fastest_on on 'organ_pipe' is quick_sort, not insertion_sort (9380% apart, decisive) [n=8192, 7 trials] | [boundary:random] confirmed: slowest_on on 'random' is insertion_sort (1535.6 ms, margin 2749% over shell_sort, separation 1481.70 ms > required 35.63 ms) [n=8192, 7 trials] | [scope:sawtooth] confirmed: slowest_on on 'sawtooth' is insertion_sort (1462.1 ms, margin 2047% over shell_sort, separation 1393.96 ms > required 66.41 ms) [n=8192, 7 trials] | [scope:organ_pipe] confirmed: slowest_on on 'organ_pipe' is insertion_sort (1518.0 ms, margin 6277% over heap_sort, separation 1494.18 ms > required 35.71 ms) [n=8192, 7 trials]
- **hyp_cae1c60f85** — probe `boundary:random, scope:sawtooth, scope:organ_pipe, boundary:reversed, scope:sawtooth, scope:organ_pipe` → **survived**
  - [boundary:random] confirmed: quick_sort is 0% off best on 'random' (limit 25%, uncertainty ±22%) [n=8192, 7 trials] | [scope:sawtooth] confirmed: quick_sort is 0% off best on 'sawtooth' (limit 25%, uncertainty ±8%) [n=8192, 7 trials] | [scope:organ_pipe] confirmed: quick_sort is 0% off best on 'organ_pipe' (limit 25%, uncertainty ±22%) [n=8192, 7 trials] | [boundary:reversed] confirmed: quick_sort is 0% off best on 'reversed' (limit 200%, uncertainty ±5%) [n=8192, 7 trials] | [scope:sawtooth] confirmed: quick_sort is 0% off best on 'sawtooth' (limit 200%, uncertainty ±8%) [n=8192, 7 trials] | [scope:organ_pipe] confirmed: quick_sort is 0% off best on 'organ_pipe' (limit 200%, uncertainty ±22%) [n=8192, 7 trials]
- **hyp_40df9834c7** — probe `boundary:random, scope:sawtooth, scope:organ_pipe` → **survived**
  - [boundary:random] confirmed: shell_sort vs insertion_sort on 'random': +2964% (needs >= 0.0%, decisive: gap 1526.07 ms > required 29.67 ms) [n=8192, 7 trials] | [scope:sawtooth] confirmed: shell_sort vs insertion_sort on 'sawtooth': +2231% (needs >= 0.0%, decisive: gap 1389.30 ms > required 43.08 ms) [n=8192, 7 trials] | [scope:organ_pipe] confirmed: shell_sort vs insertion_sort on 'organ_pipe': +7624% (needs >= 0.0%, decisive: gap 1544.09 ms > required 28.35 ms) [n=8192, 7 trials]
- **hyp_38e7e1fe16** — probe `boundary:random, scope:sawtooth, scope:organ_pipe, boundary:nearly_sorted, scope:sawtooth, scope:organ_pipe` → **survived**
  - [boundary:random] confirmed: hybrid_sort vs merge_sort on 'random': +50% (needs >= 5%, decisive: gap 7.07 ms > required 1.59 ms) [n=8192, 7 trials] | [scope:sawtooth] confirmed: hybrid_sort vs merge_sort on 'sawtooth': +109% (needs >= 5%, decisive: gap 8.87 ms > required 1.23 ms) [n=8192, 7 trials] | [scope:organ_pipe] confirmed: hybrid_sort vs merge_sort on 'organ_pipe': +43% (needs >= 5%, decisive: gap 5.54 ms > required 2.27 ms) [n=8192, 7 trials] | [boundary:nearly_sorted] confirmed: hybrid_sort vs merge_sort on 'nearly_sorted': +164% (needs >= 0%, decisive: gap 9.35 ms > required 1.81 ms) [n=8192, 7 trials] | [scope:sawtooth] confirmed: hybrid_sort vs merge_sort on 'sawtooth': +109% (needs >= 0%, decisive: gap 8.87 ms > required 1.23 ms) [n=8192, 7 trials] | [scope:organ_pipe] confirmed: hybrid_sort vs merge_sort on 'organ_pipe': +43% (needs >= 0%, decisive: gap 5.54 ms > required 2.27 ms) [n=8192, 7 trials]

## 18. Budget ledger & stop reason

- Experiments: 13/100
- Compute: 244.1s / 3600s
- Active runtime (controller): 244.2s (no wall-time cap)
- Provider calls: 0/20
- Retries: 0/8
- **Stop reason**: no high-value next experiment remained

## 19. Threats to validity

- Single machine, single CPython version: absolute timings will not transfer; only within-run rankings are meaningful, and only at the tested sizes.
- Wall-clock time only: no comparison counts, memory, or cache metrics. A ranking here is a ranking of *this implementation on this host*, not of the algorithms as such.
- Trial count (7 per cell) supports the conservative separation rule used here, not a formal hypothesis test; no p-values are computed or implied.
- Timing noise: evidence strength is capped when winner stdev/mean > 0.30, but low-margin rankings can still flip between seeds (observed as recorded contradictions).
- Scope: falsification probes cover boundary sizes (2x) and two unseen regimes; conclusions say nothing beyond that envelope.
- Knowledge-graph `fastest_on` relations are size-agnostic by design in v1.0; scale-dependent flips appear as contradictions rather than conditioned relations.
- LLM-proposed hypotheses passed schema+vocabulary validation and the full experimental pipeline; their *statements* are still author-biased toward the proposer's framing.

## Appendix — reproducibility

- Recreate this mission: `python -m origin init "<question>" --dir <new_dir> --profile <profile>` then `python -m origin run --dir <new_dir>`
- Replay any experiment from stored metadata: `python -m origin replay --dir <this_dir> --exp <exp_id>`
- Verify state consistency: `python -m origin verify --dir <this_dir>`
- Full machine-readable state: `state.json`, browsable views in `research_state/`
- Every experiment's generated code + raw results: `experiments/exp_*/` (each `run.py` is self-contained and re-runnable)
- Append-only event log: `logs/events.jsonl` — rendered as `reports/timeline.md`
- Budget consumed: 13/100 experiments, 244.1s compute
