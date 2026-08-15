# ORIGIN Research Dossier

Generated: 2026-08-13 19:42:28  |  ORIGIN v2.0.0  |  domain: `graphbench`

## 1. Research question

> Which single-source shortest-path method wins on which graph topology at the tested sizes, does the machine-independent relaxation count agree with the wall-clock ranking, and where is the BFS candidate actually correct?

## 2. Initial assumptions

- All graphs are connected and undirected with positive integer weights, so Dijkstra's preconditions hold.
- Source vertex is always 0; results describe single-source shortest paths only.
- Pure-Python implementations: constant factors dominate at these sizes and do not transfer to compiled implementations.
- Edge relaxations are counted identically across candidates, so the count is comparable; wall-clock time is host-specific.
- All timings come from a single machine and interpreter; absolute numbers will not transfer, only rankings might.
- Conclusions hold only for the tested input regimes and sizes; extrapolation beyond them is speculation, not inference.

## 3. Existing knowledge (seeded claims)

- **[FACT]** Dijkstra with a binary heap runs in O((V+E) log V) on graphs with non-negative weights. (confidence 0.95)
- **[FACT]** Bellman-Ford runs in O(V*E) and tolerates negative weights, which are not present in this benchmark. (confidence 0.95)
- **[FACT]** Breadth-first search computes shortest paths only when every edge weight is equal. (confidence 0.95)
- **[EXPERIMENTAL_RESULT]** Fewest edge relaxations at n=512 by topology: sparse_random=dijkstra_heap, dense_random=dijkstra_heap, grid_2d=dijkstra_heap, unit_weight=dijkstra_heap (machine-independent count; measured on CPython 3.12.3) (confidence 0.60)

## 4. Evidence map (knowledge graph)


## 5. Contradictions

- None detected across experiments in this run.

## 6. Knowledge gaps

- Directed graphs and negative edge weights are not benchmarked; Bellman-Ford's actual advantage is therefore untested here.
- Only single-source queries from vertex 0 are measured.
- Memory use and cache behaviour are not instrumented, so the dense/sparse crossover is explained only by relaxation counts and wall-clock time.

## 7. Hypotheses (competing pool, with evidence ledgers)

### hyp_f3a5a9f693 — WEAKENED

**Statement.** Dijkstra with a binary heap is fastest on sparse random graphs at the tested sizes.

**Rationale.** Heap ordering avoids the O(V^2) scan that dominates the array variant when the graph is sparse.

Supporting evidence: 0 | Contradicting: 0 | Experiments: 1 | Predictions confirmed: 0 | refuted: 0

- [INCONCLUSIVE] dijkstra_heap is fastest on sparse_random — spfa leads on 'sparse_random' but is not decisively separated from dijkstra_heap: uncertainty_overlap (gap 0.114 ms <= 3x combined SEM 0.128 ms) [n=512, 5 trials]

### hyp_6076ea0451 — WEAKENED

**Statement.** The array-scan Dijkstra beats the heap variant on dense graphs, where the scan cost is amortised.

**Rationale.** With E ~ V^2/8 the heap's per-edge push cost outweighs the array's per-vertex scan.

Supporting evidence: 0 | Contradicting: 0 | Experiments: 1 | Predictions confirmed: 0 | refuted: 0

- [INCONCLUSIVE] dijkstra_array beats dijkstra_heap on dense_random — dijkstra_array vs dijkstra_heap on 'dense_random': -31% but not decisive (uncertainty_overlap (gap 7.621 ms <= 3x combined SEM 14.590 ms)) [n=512, 5 trials]

### hyp_96edc044f0 — PROVISIONALLY_SUPPORTED

**Statement.** Bellman-Ford performs the most edge relaxations of any candidate on every tested topology.

**Rationale.** It relaxes every edge on every pass rather than settling vertices once.

Supporting evidence: 2 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 1 | refuted: 0

- [CONFIRMED] bellman_ford has the highest relaxation count — highest relaxation count by topology: {'sparse_random': 'bellman_ford', 'dense_random': 'bellman_ford', 'grid_2d': 'bellman_ford', 'unit_weight': 'bellman_ford'} [n=512]

### hyp_e6bc85dbcd — ACCEPTED_WITH_SCOPE

**Statement.** SPFA performs fewer relaxations than Bellman-Ford on sparse random graphs.

**Rationale.** Queue-driven relaxation revisits only vertices whose distance improved.

Supporting evidence: 2 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 1 | refuted: 0

- [CONFIRMED] spfa uses fewer relaxations than bellman_ford on sparse_random — spfa performed 4,907 relaxations vs bellman_ford 21,476 on 'sparse_random' (+77%); exact counts, machine-independent [n=512]

### hyp_0eae29898f — ACCEPTED_WITH_SCOPE

**Statement.** The BFS candidate returns correct distances on unit-weight graphs and incorrect distances on every weighted topology.

**Rationale.** BFS assumes uniform edge cost; the benchmark should detect the boundary rather than assume it.

Supporting evidence: 4 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 2 | refuted: 0

- [CONFIRMED] bfs_unit is correct on unit_weight — bfs_unit on 'unit_weight' returned correct distances [n=512, 5 trials]
- [CONFIRMED] bfs_unit is incorrect on sparse_random — bfs_unit on 'sparse_random' returned INCORRECT distances [n=512, 5 trials]

## 8. Experiments

- `exp_de9672a659` [completed] Benchmark round 1 covering 5 hypothesis(es) — 3.8s (design: 5 algorithms x 4 regimes x sizes [128, 512])
- `exp_80c64940b6` [completed] Replication of hyp_96edc044f0 — 2.9s (design: 5 algorithms x 4 regimes x sizes [512])
- `exp_3079fc8021` [completed] Replication of hyp_e6bc85dbcd — 3.0s (design: 5 algorithms x 4 regimes x sizes [512])
- `exp_6bd2d789f8` [completed] Replication of hyp_0eae29898f — 3.1s (design: 5 algorithms x 4 regimes x sizes [512])
- `exp_42efd0db8f` [completed] Falsification probe of hyp_e6bc85dbcd — 1.1s (design: 5 algorithms x 3 regimes x sizes [1024])
- `exp_31f8e1690f` [completed] Falsification probe of hyp_0eae29898f — 1.0s (design: 5 algorithms x 3 regimes x sizes [1024])

## 9. Results

**exp_de9672a659** — Benchmark round 1 covering 5 hypothesis(es) (3.8s, n = 512 shown)

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.27 | 0.01 | 5 |
| 2 | spfa | 0.46 | 0.06 | 5 |
| 3 | dijkstra_heap | 0.57 | 0.03 | 5 |
| 4 | bellman_ford | 1.78 | 0.20 | 5 |
| 5 | dijkstra_array | 10.94 | 3.06 | 5 |

Regime `dense_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 13.50 | 1.12 | 5 |
| 2 | dijkstra_heap | 17.23 | 5.82 | 5 |
| 3 | spfa | 18.18 | 2.48 | 5 |
| 4 | dijkstra_array | 24.85 | 5.05 | 5 |
| 5 | bellman_ford | 46.90 | 14.01 | 5 |

Regime `grid_2d`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.17 | 0.02 | 5 |
| 2 | spfa | 0.26 | 0.05 | 5 |
| 3 | dijkstra_heap | 0.81 | 0.14 | 5 |
| 4 | bellman_ford | 0.84 | 0.23 | 5 |
| 5 | dijkstra_array | 7.49 | 0.68 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | spfa | 0.30 | 0.04 | 5 |
| 2 | bfs_unit | 0.32 | 0.07 | 5 |
| 3 | bellman_ford | 0.79 | 0.14 | 5 |
| 4 | dijkstra_heap | 1.01 | 0.13 | 5 |
| 5 | dijkstra_array | 8.36 | 1.33 | 5 |

**exp_80c64940b6** — Replication of hyp_96edc044f0 (2.9s, n = 512 shown)

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.33 | 0.07 | 5 |
| 2 | spfa | 0.57 | 0.10 | 5 |
| 3 | dijkstra_heap | 0.60 | 0.05 | 5 |
| 4 | bellman_ford | 1.29 | 0.06 | 5 |
| 5 | dijkstra_array | 7.48 | 0.17 | 5 |

Regime `dense_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 13.87 | 2.70 | 5 |
| 2 | dijkstra_heap | 15.13 | 2.33 | 5 |
| 3 | spfa | 19.08 | 1.47 | 5 |
| 4 | dijkstra_array | 21.50 | 0.65 | 5 |
| 5 | bellman_ford | 58.57 | 2.81 | 5 |

Regime `grid_2d`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.23 | 0.09 | 5 |
| 2 | dijkstra_heap | 0.34 | 0.02 | 5 |
| 3 | spfa | 0.36 | 0.04 | 5 |
| 4 | bellman_ford | 0.77 | 0.06 | 5 |
| 5 | dijkstra_array | 6.87 | 0.17 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.28 | 0.02 | 5 |
| 2 | spfa | 0.35 | 0.08 | 5 |
| 3 | dijkstra_heap | 0.43 | 0.02 | 5 |
| 4 | bellman_ford | 0.93 | 0.17 | 5 |
| 5 | dijkstra_array | 8.05 | 0.80 | 5 |

**exp_3079fc8021** — Replication of hyp_e6bc85dbcd (3.0s, n = 512 shown)

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.31 | 0.05 | 5 |
| 2 | spfa | 0.45 | 0.04 | 5 |
| 3 | dijkstra_heap | 0.58 | 0.02 | 5 |
| 4 | bellman_ford | 1.31 | 0.06 | 5 |
| 5 | dijkstra_array | 7.74 | 0.26 | 5 |

Regime `dense_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 13.81 | 0.59 | 5 |
| 2 | dijkstra_heap | 17.94 | 0.85 | 5 |
| 3 | spfa | 20.08 | 1.46 | 5 |
| 4 | dijkstra_array | 22.94 | 0.27 | 5 |
| 5 | bellman_ford | 54.63 | 2.56 | 5 |

Regime `grid_2d`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.16 | 0.02 | 5 |
| 2 | spfa | 0.26 | 0.06 | 5 |
| 3 | dijkstra_heap | 0.34 | 0.02 | 5 |
| 4 | bellman_ford | 0.73 | 0.07 | 5 |
| 5 | dijkstra_array | 7.64 | 0.96 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | spfa | 0.28 | 0.01 | 5 |
| 2 | bfs_unit | 0.28 | 0.02 | 5 |
| 3 | dijkstra_heap | 0.46 | 0.02 | 5 |
| 4 | bellman_ford | 0.77 | 0.13 | 5 |
| 5 | dijkstra_array | 7.62 | 0.17 | 5 |

**exp_6bd2d789f8** — Replication of hyp_0eae29898f (3.1s, n = 512 shown)

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.34 | 0.11 | 5 |
| 2 | spfa | 0.47 | 0.05 | 5 |
| 3 | dijkstra_heap | 0.59 | 0.04 | 5 |
| 4 | bellman_ford | 1.30 | 0.10 | 5 |
| 5 | dijkstra_array | 8.34 | 1.72 | 5 |

Regime `dense_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 14.84 | 0.56 | 5 |
| 2 | dijkstra_heap | 16.25 | 1.18 | 5 |
| 3 | spfa | 20.10 | 1.95 | 5 |
| 4 | dijkstra_array | 22.41 | 0.95 | 5 |
| 5 | bellman_ford | 60.13 | 3.73 | 5 |

Regime `grid_2d`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.18 | 0.03 | 5 |
| 2 | spfa | 0.27 | 0.05 | 5 |
| 3 | dijkstra_heap | 0.36 | 0.02 | 5 |
| 4 | bellman_ford | 0.82 | 0.04 | 5 |
| 5 | dijkstra_array | 7.33 | 0.26 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | spfa | 0.29 | 0.02 | 5 |
| 2 | bfs_unit | 0.31 | 0.04 | 5 |
| 3 | dijkstra_heap | 0.57 | 0.17 | 5 |
| 4 | bellman_ford | 0.95 | 0.32 | 5 |
| 5 | dijkstra_array | 8.88 | 2.51 | 5 |

**exp_42efd0db8f** — Falsification probe of hyp_e6bc85dbcd (1.1s, n = 1024 shown)

Regime `long_chain`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.26 | 0.04 | 5 |
| 2 | dijkstra_heap | 0.61 | 0.07 | 5 |
| 3 | spfa | 0.70 | 0.08 | 5 |
| 4 | bellman_ford | 15.31 | 4.47 | 5 |
| 5 | dijkstra_array | 37.03 | 2.02 | 5 |

Regime `scale_free`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.38 | 0.02 | 5 |
| 2 | spfa | 0.53 | 0.04 | 5 |
| 3 | dijkstra_heap | 1.01 | 0.04 | 5 |
| 4 | bellman_ford | 1.50 | 0.22 | 5 |
| 5 | dijkstra_array | 38.59 | 2.33 | 5 |

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.67 | 0.21 | 5 |
| 2 | spfa | 0.96 | 0.13 | 5 |
| 3 | dijkstra_heap | 1.28 | 0.06 | 5 |
| 4 | bellman_ford | 3.46 | 0.61 | 5 |
| 5 | dijkstra_array | 38.32 | 0.74 | 5 |

**exp_31f8e1690f** — Falsification probe of hyp_0eae29898f (1.0s, n = 1024 shown)

Regime `long_chain`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.24 | 0.03 | 5 |
| 2 | dijkstra_heap | 0.57 | 0.02 | 5 |
| 3 | spfa | 0.68 | 0.07 | 5 |
| 4 | bellman_ford | 14.20 | 3.30 | 5 |
| 5 | dijkstra_array | 35.16 | 0.51 | 5 |

Regime `scale_free`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.38 | 0.01 | 5 |
| 2 | spfa | 0.54 | 0.07 | 5 |
| 3 | dijkstra_heap | 0.99 | 0.09 | 5 |
| 4 | bellman_ford | 1.50 | 0.26 | 5 |
| 5 | dijkstra_array | 35.65 | 0.58 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.56 | 0.03 | 5 |
| 2 | spfa | 0.63 | 0.04 | 5 |
| 3 | dijkstra_heap | 0.94 | 0.08 | 5 |
| 4 | bellman_ford | 2.19 | 0.63 | 5 |
| 5 | dijkstra_array | 35.66 | 0.85 | 5 |

## 10. Failed approaches (failure log)

- **exp_de9672a659** / : predicted “(correctness)”; observed: bfs_unit returned wrong distances on 'dense_random'. Action: candidate excluded from performance rankings on this topology.
- **exp_de9672a659** / : predicted “(correctness)”; observed: bfs_unit returned wrong distances on 'grid_2d'. Action: candidate excluded from performance rankings on this topology.
- **exp_de9672a659** / : predicted “(correctness)”; observed: bfs_unit returned wrong distances on 'sparse_random'. Action: candidate excluded from performance rankings on this topology.

## 11. Decision history

- step 0 [select_investigation] → **hyp_0eae29898f** — highest expected information gain per unit cost; experiment co-tests 5 hypothesis(es)
- step 2 [critic_replication] → **hyp_96edc044f0** — critic refuses single-experiment support; independent replication with new seeds
- step 3 [critic_replication] → **hyp_e6bc85dbcd** — critic refuses single-experiment support; independent replication with new seeds
- step 4 [critic_replication] → **hyp_0eae29898f** — critic refuses single-experiment support; independent replication with new seeds
- step 6 [critic_falsification] → **hyp_e6bc85dbcd** — falsification probes: boundary:sparse_random, scope:long_chain, scope:scale_free
- step 7 [critic_falsification] → **hyp_0eae29898f** — falsification probes: boundary:unit_weight, scope:long_chain, scope:scale_free

## 12. Current conclusions

Accepted with scope (replicated AND survived active falsification):

- SPFA performs fewer relaxations than Bellman-Ford on sparse random graphs.
  - **scope**: holds at n<=2x tested sizes on its original topology; extends to ['long_chain', 'scale_free']
- The BFS candidate returns correct distances on unit-weight graphs and incorrect distances on every weighted topology.
  - **scope**: holds at n<=2x tested sizes on its original topology; does NOT extend to ['long_chain', 'scale_free']

Provisionally supported (survived testing and replication):

- Bellman-Ford performs the most edge relaxations of any candidate on every tested topology. *(independently replicated)*

Weakened (mixed evidence — revision candidates):

- Dijkstra with a binary heap is fastest on sparse random graphs at the tested sizes.
- The array-scan Dijkstra beats the heap variant on dense graphs, where the scan cost is amortised.

## 13. Confidence and cautions

- [mock counterargument, unverified] Timing rankings at these sizes may be dominated by interpreter overhead rather than algorithmic behaviour. (targets hyp_f3a5a9f693)
- Topology 'sparse_random' at n=512 in exp_de9672a659: spfa has the lowest mean but is not separable from dijkstra_heap at 5 trials — no winner is claimed.
- Topology 'dense_random' at n=512 in exp_de9672a659: dijkstra_heap has the lowest mean but is not separable from dijkstra_array, spfa at 5 trials — no winner is claimed.
- Topology 'unit_weight' at n=512 in exp_de9672a659: spfa has the lowest mean but is not separable from bfs_unit at 5 trials — no winner is claimed.
- hyp_f3a5a9f693: nothing resolvable at this trial count; treat as untested rather than disproved.
- hyp_6076ea0451: nothing resolvable at this trial count; treat as untested rather than disproved.
- Topology 'sparse_random' at n=512 in exp_80c64940b6: spfa has the lowest mean but is not separable from dijkstra_heap at 5 trials — no winner is claimed.
- Topology 'dense_random' at n=512 in exp_80c64940b6: dijkstra_heap has the lowest mean but is not separable from spfa at 5 trials — no winner is claimed.
- Topology 'grid_2d' at n=512 in exp_80c64940b6: dijkstra_heap has the lowest mean but is not separable from spfa at 5 trials — no winner is claimed.
- Topology 'unit_weight' at n=512 in exp_80c64940b6: bfs_unit has the lowest mean but is not separable from spfa at 5 trials — no winner is claimed.
- Topology 'dense_random' at n=512 in exp_3079fc8021: dijkstra_heap has the lowest mean but is not separable from spfa at 5 trials — no winner is claimed.
- Topology 'grid_2d' at n=512 in exp_3079fc8021: spfa has the lowest mean but is not separable from dijkstra_heap at 5 trials — no winner is claimed.
- Topology 'unit_weight' at n=512 in exp_3079fc8021: spfa has the lowest mean but is not separable from bfs_unit at 5 trials — no winner is claimed.
- Topology 'sparse_random' at n=512 in exp_6bd2d789f8: spfa has the lowest mean but is not separable from dijkstra_heap at 5 trials — no winner is claimed.
- Topology 'dense_random' at n=512 in exp_6bd2d789f8: dijkstra_heap has the lowest mean but is not separable from spfa at 5 trials — no winner is claimed.
- Topology 'unit_weight' at n=512 in exp_6bd2d789f8: spfa has the lowest mean but is not separable from bfs_unit at 5 trials — no winner is claimed.
- hyp_96edc044f0 could not be falsification-probed (prediction types not probeable); it remains provisionally supported, not accepted.

## 14. Novel findings

- None this run.

## 15. Remaining questions & recommended next investigations

- [mock knowledge gap] Comparison and move counts are not measured, so rankings cannot be separated from constant factors.
- Investigate knowledge gap: Directed graphs and negative edge weights are not benchmarked; Bellman-Ford's actual advantage is therefore untested here.
- Investigate knowledge gap: Only single-source queries from vertex 0 are measured.
- Investigate knowledge gap: Memory use and cache behaviour are not instrumented, so the dense/sparse crossover is explained only by relaxation counts and wall-clock time.
- Revise or split hyp_f3a5a9f693: mixed evidence (0 for / 0 against).
- Revise or split hyp_6076ea0451: mixed evidence (0 for / 0 against).

## 15b. Measurement environment and scope of performance claims

- **CPython 3.12.3 on Linux/x86_64, 1 CPU(s)** — 6 experiment(s)
- Fixed reference workload (sorting 20k floats): median 2.52–2.73 ms across runs — use this to put timings from another machine in proportion.

**Every performance statement in this dossier is scoped to:** the machine and interpreter above; the input regimes ['sparse_random', 'dense_random', 'grid_2d', 'unit_weight']; the input sizes [128, 512]; 5 trials per measurement cell; and pure-Python implementations of the listed algorithms. Nothing here is a claim about these algorithms in general, in another language, at other input sizes, or on other hardware.

Comparisons are only called decisive when the separation exceeds 3x the combined standard error of the two means AND at least 10% of the faster mean, with at least 5 trials on both sides. Everything else is recorded as INCONCLUSIVE — not as a win, and not as a refutation.

## 16. Prediction ledger

| Hypothesis | Prediction | Check | Outcome | Basis |
|---|---|---|---|---|
| hyp_f3a5a9f693 | dijkstra_heap is fastest on sparse_random | `fastest_on` | **inconclusive** | spfa leads on 'sparse_random' but is not decisively separated from dijkstra_heap: uncertainty_overlap (gap 0.114 ms <= 3x combined SEM 0.128 ms) [n=512, 5 trials] |
| hyp_6076ea0451 | dijkstra_array beats dijkstra_heap on dense_random | `beats` | **inconclusive** | dijkstra_array vs dijkstra_heap on 'dense_random': -31% but not decisive (uncertainty_overlap (gap 7.621 ms <= 3x combined SEM 14.590 ms)) [n=512, 5 trials] |
| hyp_96edc044f0 | bellman_ford has the highest relaxation count | `most_relaxations` | **confirmed** | highest relaxation count by topology: {'sparse_random': 'bellman_ford', 'dense_random': 'bellman_ford', 'grid_2d': 'bellman_ford', 'unit_weight': 'bellman_ford'} [n=512] |
| hyp_e6bc85dbcd | spfa uses fewer relaxations than bellman_ford on sparse_random | `fewer_relaxations` | **confirmed** | spfa performed 4,907 relaxations vs bellman_ford 21,476 on 'sparse_random' (+77%); exact counts, machine-independent [n=512] |
| hyp_0eae29898f | bfs_unit is correct on unit_weight | `correct_on` | **confirmed** | bfs_unit on 'unit_weight' returned correct distances [n=512, 5 trials] |
| hyp_0eae29898f | bfs_unit is incorrect on sparse_random | `incorrect_on` | **confirmed** | bfs_unit on 'sparse_random' returned INCORRECT distances [n=512, 5 trials] |

`inconclusive` means the measurement could not resolve the question at this trial count — it is neither support nor refutation.

## 16b. LLM proposal ledger

Provider `mock` offered 3 proposal(s): **3 accepted, 0 rejected**. Full record, including rejected bodies, in `logs/proposals.jsonl`.

| Proposal | Type | Verdict | What ORIGIN did with it |
|---|---|---|---|
| `prop_e31021938f` | experiment | accepted | stored as a candidate design |
| `prop_8abe6e9c96` | counterargument | accepted | recorded as a caution |
| `prop_a466f66485` | knowledge_gap | accepted | recorded as a knowledge gap |

An accepted proposal is **not** a finding. Accepted hypotheses entered as PROPOSED and were resolved by the experiments, replication and falsification recorded elsewhere in this dossier; counterarguments are unverified prose recorded as cautions; knowledge gaps are recommendations, not results.

## 17. Falsification attempts (critic attacks)

- **hyp_96edc044f0** — probe `(none)` → **inconclusive**
  - no probeable predictions for this hypothesis (its prediction types cannot be evaluated at boundary/unseen conditions)
- **hyp_e6bc85dbcd** — probe `boundary:sparse_random, scope:long_chain, scope:scale_free` → **survived**
  - [boundary:sparse_random] confirmed: spfa performed 9,907 relaxations vs bellman_ford 42,980 on 'sparse_random' (+77%); exact counts, machine-independent [n=1024] | [scope:long_chain] confirmed: spfa performed 4,493 relaxations vs bellman_ford 150,360 on 'long_chain' (+97%); exact counts, machine-independent [n=1024] | [scope:scale_free] confirmed: spfa performed 5,410 relaxations vs bellman_ford 20,460 on 'scale_free' (+74%); exact counts, machine-independent [n=1024]
- **hyp_0eae29898f** — probe `boundary:unit_weight, scope:long_chain, scope:scale_free` → **survived**
  - [boundary:unit_weight] confirmed: bfs_unit on 'unit_weight' returned correct distances [n=1024, 5 trials] | [scope:long_chain] refuted: bfs_unit on 'long_chain' returned INCORRECT distances [n=1024, 5 trials] | [scope:scale_free] refuted: bfs_unit on 'scale_free' returned INCORRECT distances [n=1024, 5 trials]

## 18. Budget ledger & stop reason

- Experiments: 6/40
- Compute: 14.8s / 1800s
- Active runtime (controller): 14.9s (no wall-time cap)
- Provider calls: 0/20
- Retries: 0/8
- **Stop reason**: no high-value next experiment remained

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
- Budget consumed: 6/40 experiments, 14.8s compute
