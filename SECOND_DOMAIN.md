# ORIGIN — Second Research Domain (`graphbench`)

## 1. Why this domain

The domain interface had only ever had one implementation, so "domain-agnostic
core" was an architectural claim with no evidence behind it. A second domain is
the only honest test of it.

`graphbench` (single-source shortest paths) was chosen over the alternatives
because it is deterministic, safe to execute, cheap enough to run in CI — and
because it differs from sorting in four ways that stress the core rather than
flatter it:

| | `algobench` (sorting) | `graphbench` (shortest paths) |
|---|---|---|
| Input | an array; "regime" = element order | a graph; "regime" = **topology** (sparsity, lattice, scale-free, chains) |
| Correctness | a predicate (is it sorted?) | a whole answer vector checked against a reference implementation |
| Primary metric | wall-clock time only | wall-clock **and edge relaxations — a machine-independent count** |
| Failure modes | slow candidates | a candidate that is **silently wrong outside its precondition** |

Rejected alternatives: optimisation and scheduling (objective quality is
approximate, so "correct" becomes a threshold — a weaker check than sorting
already had); search over generated data (too close to sorting's shape).

## 2. What was implemented

`origin/domains/graphbench.py` — one file, implementing only the
`ResearchDomain` hooks. No controller, state, budget, critic, replication,
reporting, replay or autonomy code was added, changed, or duplicated.

- **Baselines:** `dijkstra_heap`, `dijkstra_array` (O(V²) scan),
  `bellman_ford`, `spfa`, plus `bfs_unit` — correct *only* on unit-weight
  graphs, included deliberately so the domain contains a real correctness
  boundary rather than only performance boundaries.
- **Generators:** `sparse_random`, `dense_random`, `grid_2d`, `scale_free`,
  `long_chain`, `unit_weight`; all deterministic from a seed, all connected
  (an unreachable vertex is a broken benchmark, not a topology — which is why
  `grid_2d` returns the largest square lattice ≤ n instead of padding).
- **Correctness:** every trial is checked against a reference Dijkstra run
  inside the same runner. A wrong answer is **recorded, not crashed** — it is a
  research result about that candidate's preconditions.
- **Metrics:** per-trial timings (schema v2, with samples, SEM, digests,
  environment) **plus** a median relaxation count.
- **Hypothesis templates, experiment designs, replication, falsification
  probes** (boundary size + unseen topologies), and **knowledge gaps**.

Check vocabulary: `fastest_on`, `beats`, `fewer_relaxations`,
`most_relaxations`, `correct_on`, `incorrect_on`. The first two go through the
same conservative significance gate as sorting; the relaxation checks do not,
because **a count is exact** — no statistical test is needed or appropriate.

## 3. Architecture gaps this exposed

Two real findings, not cosmetic ones:

**3.1 The significance layer is calibrated for a metric this domain barely
needs.** In the shipped example mission, both *timing* hypotheses came back
`inconclusive` at 5 trials — the standard errors on a contended single-core
host overlap — while the *relaxation* hypotheses were decisive with exact
counts. Sorting had no machine-independent metric, so v1.2's entire
performance-validity apparatus was built around making timing claims safely.
Here the honest conclusions came from counting, not timing. The gap: the core
treats all metrics as timing-shaped, and a domain that offers a deterministic
metric has to route around the statistics layer rather than declare
"this metric is exact" to it.

**3.2 Correctness is domain-private.** `state.failures` gained an
`incorrect_output` kind by convention, not by contract — the core has no
first-class notion of "this candidate is invalid under these conditions", so
`graphbench` enforces the exclusion itself (a wrong candidate is dropped from
rankings inside `_eval`). A third domain would re-implement that. It belongs in
the core.

Neither gap was papered over: both are asserted by tests
(`test_second_domain.py`) and are the recommended next architectural work.

### Closed in v2.1

Both gaps are now fixed in the core rather than worked around in the domain:

- **Gap 3.1** — `stats` gained metric kinds. A domain declares
  `metric_kinds = {"mean_s": TIMING, "relaxations": EXACT}`, and
  `stats.compare(..., metric_kind=EXACT)` skips the trial minimum, the SEM gate
  and the margin floor, because a deterministic count has no noise to gate. An
  exact tie is reported as a tie. The dossier states which metrics are exact and
  why conclusions resting on them transfer.
- **Gap 3.2** — invalidity is a core concept: `Invalidity` in `models`,
  `state.record_invalidity()` / `is_valid()` / `valid_candidates()`, a dossier
  section, and `verify()` coverage. `graphbench` now records the BFS boundary
  through the core, and rankings ask the core who is still valid. A third domain
  inherits all of it.

**What held up well:** the controller, lifecycle, budgets, checkpointing,
critic (replication + falsification), knowledge graph, reporting, replay,
portability guard and the autonomy scheduler all took the new domain with
**zero changes**. `test_core_modules_do_not_mention_a_specific_domain` asserts
that eleven core modules never name a domain, an algorithm, or a topology.

## 4. Evidence

```bash
python -m origin init "Which single-source shortest-path method wins on which \
graph topology…" --dir runs/graph --domain graphbench --profile graph_standard \
  --max-experiments 40 --brain mock
python -m origin autonomy run --dir runs/graph --max-steps 30 --max-wall-s 1200
python -m origin verify --dir runs/graph
```

Shipped example: `examples/graph_mission/` — run autonomously (12 actions,
15 s, stop reason `completed`), 6 experiments, 5 hypotheses, 10 evidence items,
`verify` clean.

**Findings, including the negative ones:**

| Hypothesis | Outcome | Basis |
|---|---|---|
| Heap Dijkstra is fastest on sparse graphs | **weakened** | SPFA led, but the gap (0.114 ms) was inside 3× the combined SEM — inconclusive, not refuted |
| Array Dijkstra beats the heap on dense graphs | **weakened** | measured −31%, still inside the uncertainty band at 5 trials |
| Bellman-Ford performs the most relaxations everywhere | provisionally supported | highest count on all four topologies |
| SPFA uses fewer relaxations than Bellman-Ford on sparse graphs | **accepted with scope** | 4,907 vs 21,476 (+77%), exact counts; replicated; survived falsification; extends to `long_chain` and `scale_free` |
| BFS is correct on unit weights and wrong on weighted graphs | **accepted with scope** | correct on `unit_weight`; **incorrect** on `sparse_random`, `dense_random`, `grid_2d` — each recorded as a failure and excluded from rankings |

The system also cautioned itself four times that a topology's apparent winner
was not statistically separable, and refused to name one.

## 5. Scope of these conclusions

Pure-Python implementations, CPython 3.12.3 on one Linux x86-64 core, undirected
connected graphs with positive integer weights, n ≤ 512, source vertex 0,
5 trials per cell. **Relaxation counts transfer** — they are exact properties of
the algorithm on the generated graph. **Timings do not.** Nothing here is a
claim about shortest-path algorithms in general, in another language, at other
sizes, on directed graphs, or with negative weights (Bellman-Ford's actual
advantage is untested here and recorded as a knowledge gap).

## 6. No new execution capability

`graphbench` runs under the identical sandbox: generated runner from an audited
in-repo template, `validate_design()` before spawn, rlimits, scrubbed
environment, output caps, wall-clock timeout. It adds no shell access, no file
access beyond the experiment directory, and no network.
