# ORIGIN Research Dossier

Generated: 2026-08-13 19:42:28  |  ORIGIN v2.0.0  |  domain: `graphbench`

## 1. Research question

> Which single-source shortest-path method wins on which graph topology at n<=512, does the machine-independent relaxation count agree with the wall-clock ranking, and under what precondition is the BFS candidate correct?

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

### hyp_47f59f38cd — REJECTED

**Statement.** Dijkstra with a binary heap is fastest on sparse random graphs at the tested sizes.

**Rationale.** Heap ordering avoids the O(V^2) scan that dominates the array variant when the graph is sparse.

Supporting evidence: 0 | Contradicting: 1 | Experiments: 1 | Predictions confirmed: 0 | refuted: 1

- [REFUTED] dijkstra_heap is fastest on sparse_random — fastest on 'sparse_random' is spfa, not dijkstra_heap (24% apart) [n=512, 5 trials]

### hyp_df0b968ddf — REJECTED

**Statement.** The array-scan Dijkstra beats the heap variant on dense graphs, where the scan cost is amortised.

**Rationale.** With E ~ V^2/8 the heap's per-edge push cost outweighs the array's per-vertex scan.

Supporting evidence: 0 | Contradicting: 1 | Experiments: 1 | Predictions confirmed: 0 | refuted: 1

- [REFUTED] dijkstra_array beats dijkstra_heap on dense_random — dijkstra_array is decisively SLOWER than dijkstra_heap on 'dense_random' (-39%) [n=512, 5 trials]

### hyp_a155973991 — PROVISIONALLY_SUPPORTED

**Statement.** Bellman-Ford performs the most edge relaxations of any candidate on every tested topology.

**Rationale.** It relaxes every edge on every pass rather than settling vertices once.

Supporting evidence: 2 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 1 | refuted: 0

- [CONFIRMED] bellman_ford has the highest relaxation count — highest relaxation count by topology: {'sparse_random': 'bellman_ford', 'dense_random': 'bellman_ford', 'grid_2d': 'bellman_ford', 'unit_weight': 'bellman_ford'} [n=512]

### hyp_ff3e742ca3 — ACCEPTED_WITH_SCOPE

**Statement.** SPFA performs fewer relaxations than Bellman-Ford on sparse random graphs.

**Rationale.** Queue-driven relaxation revisits only vertices whose distance improved.

Supporting evidence: 2 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 1 | refuted: 0

- [CONFIRMED] spfa uses fewer relaxations than bellman_ford on sparse_random — spfa performed 4,907 relaxations vs bellman_ford 21,476 on 'sparse_random' (+77%); exact counts, machine-independent [n=512]

### hyp_dfa38e8bf8 — ACCEPTED_WITH_SCOPE

**Statement.** The BFS candidate returns correct distances on unit-weight graphs and incorrect distances on every weighted topology.

**Rationale.** BFS assumes uniform edge cost; the benchmark should detect the boundary rather than assume it.

Supporting evidence: 4 | Contradicting: 0 | Experiments: 2 | Predictions confirmed: 2 | refuted: 0

- [CONFIRMED] bfs_unit is correct on unit_weight — bfs_unit on 'unit_weight' returned correct distances [n=512, 5 trials]
- [CONFIRMED] bfs_unit is incorrect on sparse_random — bfs_unit on 'sparse_random' returned INCORRECT distances [n=512, 5 trials]

## 8. Experiments

- `exp_f6219e9785` [completed] Benchmark round 1 covering 5 hypothesis(es) — 2.9s (design: 5 algorithms x 4 regimes x sizes [128, 512])
- `exp_5ddb272042` [completed] Replication of hyp_a155973991 — 2.7s (design: 5 algorithms x 4 regimes x sizes [512])
- `exp_4ef2060bc4` [completed] Replication of hyp_ff3e742ca3 — 2.7s (design: 5 algorithms x 4 regimes x sizes [512])
- `exp_e36d780531` [completed] Replication of hyp_dfa38e8bf8 — 2.6s (design: 5 algorithms x 4 regimes x sizes [512])
- `exp_549fb806e7` [completed] Falsification probe of hyp_ff3e742ca3 — 1.0s (design: 5 algorithms x 3 regimes x sizes [1024])
- `exp_9b2777924f` [completed] Falsification probe of hyp_dfa38e8bf8 — 1.0s (design: 5 algorithms x 3 regimes x sizes [1024])

## 9. Results

**exp_f6219e9785** — Benchmark round 1 covering 5 hypothesis(es) (2.9s, n = 512 shown)

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.28 | 0.01 | 5 |
| 2 | spfa | 0.45 | 0.04 | 5 |
| 3 | dijkstra_heap | 0.56 | 0.03 | 5 |
| 4 | bellman_ford | 1.76 | 0.41 | 5 |
| 5 | dijkstra_array | 7.81 | 0.30 | 5 |

Regime `dense_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | dijkstra_heap | 12.11 | 0.35 | 5 |
| 2 | bfs_unit | 13.04 | 1.74 | 5 |
| 3 | spfa | 18.02 | 1.96 | 5 |
| 4 | dijkstra_array | 19.80 | 0.61 | 5 |
| 5 | bellman_ford | 44.99 | 9.95 | 5 |

Regime `grid_2d`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.14 | 0.00 | 5 |
| 2 | spfa | 0.25 | 0.03 | 5 |
| 3 | dijkstra_heap | 0.36 | 0.04 | 5 |
| 4 | bellman_ford | 0.77 | 0.22 | 5 |
| 5 | dijkstra_array | 6.92 | 0.12 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | spfa | 0.26 | 0.01 | 5 |
| 2 | bfs_unit | 0.26 | 0.02 | 5 |
| 3 | dijkstra_heap | 0.47 | 0.12 | 5 |
| 4 | bellman_ford | 0.78 | 0.14 | 5 |
| 5 | dijkstra_array | 7.29 | 0.14 | 5 |

**exp_5ddb272042** — Replication of hyp_a155973991 (2.7s, n = 512 shown)

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.27 | 0.05 | 5 |
| 2 | spfa | 0.42 | 0.06 | 5 |
| 3 | dijkstra_heap | 0.54 | 0.01 | 5 |
| 4 | bellman_ford | 1.35 | 0.22 | 5 |
| 5 | dijkstra_array | 7.86 | 0.84 | 5 |

Regime `dense_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 11.42 | 1.18 | 5 |
| 2 | dijkstra_heap | 12.27 | 1.75 | 5 |
| 3 | spfa | 13.18 | 1.54 | 5 |
| 4 | dijkstra_array | 19.28 | 0.93 | 5 |
| 5 | bellman_ford | 39.39 | 3.78 | 5 |

Regime `grid_2d`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.19 | 0.03 | 5 |
| 2 | spfa | 0.24 | 0.04 | 5 |
| 3 | dijkstra_heap | 0.35 | 0.02 | 5 |
| 4 | bellman_ford | 0.72 | 0.07 | 5 |
| 5 | dijkstra_array | 6.95 | 0.20 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | spfa | 0.27 | 0.02 | 5 |
| 2 | bfs_unit | 0.27 | 0.03 | 5 |
| 3 | dijkstra_heap | 0.49 | 0.10 | 5 |
| 4 | bellman_ford | 0.76 | 0.13 | 5 |
| 5 | dijkstra_array | 7.37 | 0.25 | 5 |

**exp_4ef2060bc4** — Replication of hyp_ff3e742ca3 (2.7s, n = 512 shown)

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.27 | 0.01 | 5 |
| 2 | spfa | 0.42 | 0.04 | 5 |
| 3 | dijkstra_heap | 0.59 | 0.03 | 5 |
| 4 | bellman_ford | 1.31 | 0.02 | 5 |
| 5 | dijkstra_array | 7.54 | 0.12 | 5 |

Regime `dense_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 11.03 | 1.63 | 5 |
| 2 | dijkstra_heap | 11.79 | 0.76 | 5 |
| 3 | spfa | 18.79 | 2.70 | 5 |
| 4 | dijkstra_array | 20.41 | 1.99 | 5 |
| 5 | bellman_ford | 31.92 | 4.85 | 5 |

Regime `grid_2d`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.17 | 0.02 | 5 |
| 2 | spfa | 0.26 | 0.04 | 5 |
| 3 | dijkstra_heap | 0.43 | 0.12 | 5 |
| 4 | bellman_ford | 0.75 | 0.09 | 5 |
| 5 | dijkstra_array | 6.92 | 0.26 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.27 | 0.04 | 5 |
| 2 | spfa | 0.29 | 0.01 | 5 |
| 3 | dijkstra_heap | 0.44 | 0.02 | 5 |
| 4 | bellman_ford | 0.89 | 0.35 | 5 |
| 5 | dijkstra_array | 7.41 | 0.17 | 5 |

**exp_e36d780531** — Replication of hyp_dfa38e8bf8 (2.6s, n = 512 shown)

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.25 | 0.01 | 5 |
| 2 | spfa | 0.42 | 0.06 | 5 |
| 3 | dijkstra_heap | 0.64 | 0.08 | 5 |
| 4 | bellman_ford | 1.27 | 0.11 | 5 |
| 5 | dijkstra_array | 7.72 | 0.43 | 5 |

Regime `dense_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 10.12 | 1.13 | 5 |
| 2 | dijkstra_heap | 13.03 | 1.62 | 5 |
| 3 | spfa | 13.51 | 2.34 | 5 |
| 4 | dijkstra_array | 17.83 | 1.79 | 5 |
| 5 | bellman_ford | 34.37 | 4.64 | 5 |

Regime `grid_2d`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.15 | 0.01 | 5 |
| 2 | spfa | 0.24 | 0.04 | 5 |
| 3 | dijkstra_heap | 0.34 | 0.03 | 5 |
| 4 | bellman_ford | 0.75 | 0.10 | 5 |
| 5 | dijkstra_array | 7.13 | 0.93 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.25 | 0.01 | 5 |
| 2 | spfa | 0.27 | 0.03 | 5 |
| 3 | dijkstra_heap | 0.44 | 0.07 | 5 |
| 4 | bellman_ford | 0.73 | 0.13 | 5 |
| 5 | dijkstra_array | 7.23 | 0.13 | 5 |

**exp_549fb806e7** — Falsification probe of hyp_ff3e742ca3 (1.0s, n = 1024 shown)

Regime `long_chain`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.23 | 0.03 | 5 |
| 2 | dijkstra_heap | 0.56 | 0.02 | 5 |
| 3 | spfa | 0.64 | 0.09 | 5 |
| 4 | bellman_ford | 14.53 | 3.78 | 5 |
| 5 | dijkstra_array | 33.40 | 1.14 | 5 |

Regime `scale_free`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.35 | 0.02 | 5 |
| 2 | spfa | 0.53 | 0.06 | 5 |
| 3 | dijkstra_heap | 0.92 | 0.03 | 5 |
| 4 | bellman_ford | 1.40 | 0.23 | 5 |
| 5 | dijkstra_array | 34.47 | 0.95 | 5 |

Regime `sparse_random`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.54 | 0.04 | 5 |
| 2 | spfa | 0.88 | 0.13 | 5 |
| 3 | dijkstra_heap | 1.17 | 0.04 | 5 |
| 4 | bellman_ford | 3.16 | 0.64 | 5 |
| 5 | dijkstra_array | 35.28 | 0.91 | 5 |

**exp_9b2777924f** — Falsification probe of hyp_dfa38e8bf8 (1.0s, n = 1024 shown)

Regime `long_chain`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.24 | 0.01 | 5 |
| 2 | dijkstra_heap | 0.56 | 0.02 | 5 |
| 3 | spfa | 0.69 | 0.06 | 5 |
| 4 | bellman_ford | 14.92 | 2.77 | 5 |
| 5 | dijkstra_array | 36.91 | 1.43 | 5 |

Regime `scale_free`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.35 | 0.02 | 5 |
| 2 | spfa | 0.57 | 0.12 | 5 |
| 3 | dijkstra_heap | 0.88 | 0.02 | 5 |
| 4 | bellman_ford | 1.42 | 0.22 | 5 |
| 5 | dijkstra_array | 36.23 | 0.74 | 5 |

Regime `unit_weight`:

| rank | algorithm | mean (ms) | stdev (ms) | trials |
|---:|---|---:|---:|---:|
| 1 | bfs_unit | 0.51 | 0.01 | 5 |
| 2 | spfa | 0.55 | 0.03 | 5 |
| 3 | dijkstra_heap | 0.89 | 0.03 | 5 |
| 4 | bellman_ford | 1.77 | 0.04 | 5 |
| 5 | dijkstra_array | 36.24 | 1.01 | 5 |

## 10. Failed approaches (failure log)

- **exp_f6219e9785** / : predicted “(correctness)”; observed: bfs_unit returned wrong distances on 'dense_random'. Action: candidate excluded from performance rankings on this topology.
- **exp_f6219e9785** / : predicted “(correctness)”; observed: bfs_unit returned wrong distances on 'grid_2d'. Action: candidate excluded from performance rankings on this topology.
- **exp_f6219e9785** / : predicted “(correctness)”; observed: bfs_unit returned wrong distances on 'sparse_random'. Action: candidate excluded from performance rankings on this topology.
- **exp_f6219e9785** / hyp_47f59f38cd: predicted “dijkstra_heap is fastest on sparse_random”; observed: fastest on 'sparse_random' is spfa, not dijkstra_heap (24% apart) [n=512, 5 trials]. Action: hypothesis status re-evaluated.
- **exp_f6219e9785** / hyp_df0b968ddf: predicted “dijkstra_array beats dijkstra_heap on dense_random”; observed: dijkstra_array is decisively SLOWER than dijkstra_heap on 'dense_random' (-39%) [n=512, 5 trials]. Action: hypothesis status re-evaluated.

## 11. Decision history

- step 3 [select_investigation] → **hyp_dfa38e8bf8** — highest expected information gain per unit cost; experiment co-tests 5 hypothesis(es)
- step 5 [critic_replication] → **hyp_a155973991** — critic refuses single-experiment support; independent replication with new seeds
- step 6 [critic_replication] → **hyp_ff3e742ca3** — critic refuses single-experiment support; independent replication with new seeds
- step 7 [critic_replication] → **hyp_dfa38e8bf8** — critic refuses single-experiment support; independent replication with new seeds
- step 9 [critic_falsification] → **hyp_ff3e742ca3** — falsification probes: boundary:sparse_random, scope:long_chain, scope:scale_free
- step 10 [critic_falsification] → **hyp_dfa38e8bf8** — falsification probes: boundary:unit_weight, scope:long_chain, scope:scale_free

## 12. Current conclusions

Accepted with scope (replicated AND survived active falsification):

- SPFA performs fewer relaxations than Bellman-Ford on sparse random graphs.
  - **scope**: holds at n<=2x tested sizes on its original topology; extends to ['long_chain', 'scale_free']
- The BFS candidate returns correct distances on unit-weight graphs and incorrect distances on every weighted topology.
  - **scope**: holds at n<=2x tested sizes on its original topology; does NOT extend to ['long_chain', 'scale_free']

Provisionally supported (survived testing and replication):

- Bellman-Ford performs the most edge relaxations of any candidate on every tested topology. *(independently replicated)*

Rejected by experiment:

- Dijkstra with a binary heap is fastest on sparse random graphs at the tested sizes.
- The array-scan Dijkstra beats the heap variant on dense graphs, where the scan cost is amortised.

## 13. Confidence and cautions

- [mock counterargument, unverified] Timing rankings at these sizes may be dominated by interpreter overhead rather than algorithmic behaviour. (targets hyp_47f59f38cd)
- Topology 'unit_weight' at n=512 in exp_f6219e9785: spfa has the lowest mean but is not separable from bfs_unit at 5 trials — no winner is claimed.
- Topology 'dense_random' at n=512 in exp_5ddb272042: dijkstra_heap has the lowest mean but is not separable from spfa at 5 trials — no winner is claimed.
- Topology 'unit_weight' at n=512 in exp_5ddb272042: spfa has the lowest mean but is not separable from bfs_unit at 5 trials — no winner is claimed.
- Topology 'grid_2d' at n=512 in exp_4ef2060bc4: spfa has the lowest mean but is not separable from dijkstra_heap at 5 trials — no winner is claimed.
- Topology 'unit_weight' at n=512 in exp_4ef2060bc4: bfs_unit has the lowest mean but is not separable from spfa at 5 trials — no winner is claimed.
- Topology 'dense_random' at n=512 in exp_e36d780531: dijkstra_heap has the lowest mean but is not separable from spfa at 5 trials — no winner is claimed.
- Topology 'unit_weight' at n=512 in exp_e36d780531: bfs_unit has the lowest mean but is not separable from spfa at 5 trials — no winner is claimed.
- hyp_a155973991 could not be falsification-probed (prediction types not probeable); it remains provisionally supported, not accepted.

## 14. Novel findings

- None this run.

## 15. Remaining questions & recommended next investigations

- [mock knowledge gap] Comparison and move counts are not measured, so rankings cannot be separated from constant factors.
- Investigate knowledge gap: Directed graphs and negative edge weights are not benchmarked; Bellman-Ford's actual advantage is therefore untested here.
- Investigate knowledge gap: Only single-source queries from vertex 0 are measured.
- Investigate knowledge gap: Memory use and cache behaviour are not instrumented, so the dense/sparse crossover is explained only by relaxation counts and wall-clock time.

## 15b. Measurement environment and scope of performance claims

- **CPython 3.12.3 on Linux/x86_64, 1 CPU(s)** — 6 experiment(s)
- Fixed reference workload (sorting 20k floats): median 2.47–2.62 ms across runs — use this to put timings from another machine in proportion.

**Every performance statement in this dossier is scoped to:** the machine and interpreter above; the input regimes ['sparse_random', 'dense_random', 'grid_2d', 'unit_weight']; the input sizes [128, 512]; 5 trials per measurement cell; and pure-Python implementations of the listed algorithms. Nothing here is a claim about these algorithms in general, in another language, at other input sizes, or on other hardware.

Comparisons are only called decisive when the separation exceeds 3x the combined standard error of the two means AND at least 10% of the faster mean, with at least 5 trials on both sides. Everything else is recorded as INCONCLUSIVE — not as a win, and not as a refutation.

## 16. Prediction ledger

| Hypothesis | Prediction | Check | Outcome | Basis |
|---|---|---|---|---|
| hyp_47f59f38cd | dijkstra_heap is fastest on sparse_random | `fastest_on` | **refuted** | fastest on 'sparse_random' is spfa, not dijkstra_heap (24% apart) [n=512, 5 trials] |
| hyp_df0b968ddf | dijkstra_array beats dijkstra_heap on dense_random | `beats` | **refuted** | dijkstra_array is decisively SLOWER than dijkstra_heap on 'dense_random' (-39%) [n=512, 5 trials] |
| hyp_a155973991 | bellman_ford has the highest relaxation count | `most_relaxations` | **confirmed** | highest relaxation count by topology: {'sparse_random': 'bellman_ford', 'dense_random': 'bellman_ford', 'grid_2d': 'bellman_ford', 'unit_weight': 'bellman_ford'} [n=512] |
| hyp_ff3e742ca3 | spfa uses fewer relaxations than bellman_ford on sparse_random | `fewer_relaxations` | **confirmed** | spfa performed 4,907 relaxations vs bellman_ford 21,476 on 'sparse_random' (+77%); exact counts, machine-independent [n=512] |
| hyp_dfa38e8bf8 | bfs_unit is correct on unit_weight | `correct_on` | **confirmed** | bfs_unit on 'unit_weight' returned correct distances [n=512, 5 trials] |
| hyp_dfa38e8bf8 | bfs_unit is incorrect on sparse_random | `incorrect_on` | **confirmed** | bfs_unit on 'sparse_random' returned INCORRECT distances [n=512, 5 trials] |

`inconclusive` means the measurement could not resolve the question at this trial count — it is neither support nor refutation.

## 16b. LLM proposal ledger

Provider `mock` offered 3 proposal(s): **3 accepted, 0 rejected**. Full record, including rejected bodies, in `logs/proposals.jsonl`.

| Proposal | Type | Verdict | What ORIGIN did with it |
|---|---|---|---|
| `prop_e31021938f` | experiment | accepted | stored as a candidate design |
| `prop_39c13e9d1b` | counterargument | accepted | recorded as a caution |
| `prop_a466f66485` | knowledge_gap | accepted | recorded as a knowledge gap |

An accepted proposal is **not** a finding. Accepted hypotheses entered as PROPOSED and were resolved by the experiments, replication and falsification recorded elsewhere in this dossier; counterarguments are unverified prose recorded as cautions; knowledge gaps are recommendations, not results.

## 17. Falsification attempts (critic attacks)

- **hyp_a155973991** — probe `(none)` → **inconclusive**
  - no probeable predictions for this hypothesis (its prediction types cannot be evaluated at boundary/unseen conditions)
- **hyp_ff3e742ca3** — probe `boundary:sparse_random, scope:long_chain, scope:scale_free` → **survived**
  - [boundary:sparse_random] confirmed: spfa performed 9,907 relaxations vs bellman_ford 42,980 on 'sparse_random' (+77%); exact counts, machine-independent [n=1024] | [scope:long_chain] confirmed: spfa performed 4,493 relaxations vs bellman_ford 150,360 on 'long_chain' (+97%); exact counts, machine-independent [n=1024] | [scope:scale_free] confirmed: spfa performed 5,410 relaxations vs bellman_ford 20,460 on 'scale_free' (+74%); exact counts, machine-independent [n=1024]
- **hyp_dfa38e8bf8** — probe `boundary:unit_weight, scope:long_chain, scope:scale_free` → **survived**
  - [boundary:unit_weight] confirmed: bfs_unit on 'unit_weight' returned correct distances [n=1024, 5 trials] | [scope:long_chain] refuted: bfs_unit on 'long_chain' returned INCORRECT distances [n=1024, 5 trials] | [scope:scale_free] refuted: bfs_unit on 'scale_free' returned INCORRECT distances [n=1024, 5 trials]

## 18. Budget ledger & stop reason

- Experiments: 6/40
- Compute: 12.8s / 1800s
- Active runtime (controller): 12.8s (no wall-time cap)
- Provider calls: 0 (uncapped)
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
- Budget consumed: 6/40 experiments, 12.8s compute
