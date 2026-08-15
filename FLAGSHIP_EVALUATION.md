# ORIGIN — Flagship Autonomous Research Evaluation

The same pre-registered question run through three workflows, to measure what
ORIGIN's machinery actually buys. Pre-registration was written to disk **before
any workflow executed** and is shipped alongside the results:
`examples/final_flagship_mission/PREREGISTRATION.json`.

## 1. Pre-registration

**Question.** Which single-source shortest-path method wins on which graph
topology at n ≤ 512, does the machine-independent relaxation count agree with
the wall-clock ranking, and under what precondition is the BFS candidate
correct?

**Baselines** `dijkstra_heap`, `dijkstra_array`, `bellman_ford`, `spfa`,
`bfs_unit`. **Metrics** correctness against a reference Dijkstra (exact);
wall-clock mean per cell (host-specific); edge relaxations (machine-independent).
**Inputs** deterministic seeded generators — `sparse_random`, `dense_random`,
`grid_2d`, `unit_weight`. **Held out** `long_chain`, `scale_free` (never used in
main rounds; only the falsifier sees them). **Sizes** 128, 512. **Trials** 5 per
cell. **Budget** 40 experiments / 30 compute-minutes.

**Replication rule** any provisionally supported hypothesis must be re-tested at
seed+1000 in a separately spawned experiment before acceptance.
**Falsification rule** a replicated hypothesis must survive a probe at 2× the
largest tested size on its own topology plus both held-out topologies.
**Significance rule** timing comparisons need ≥5 trials per side, separation
> 3× combined SEM, and ≥10% relative margin; relaxation counts are exact and
need no gate.

ORIGIN was not steered: the hypotheses are the domain's standing templates plus
whatever the proposal layer generated.

## 2. Workflows

```
baseline       benchmark everything once, report the winners
proposal_only  the LLM proposal layer speaks; nothing is tested
origin_full    hypotheses → predictions → budgeted experiments → analysis
               → criticism → falsification → replication → scoped conclusions
```

## 3. Results

```
$ python3 tools/flagship_evaluation.py --dir examples/final_flagship_mission
```

| | baseline | proposal_only | origin_full |
|---|---:|---:|---:|
| Experiments spent | 1 | 0 | 6 |
| Wall-clock | 2.7 s | 0.0 s | 12.9 s |
| Conclusions produced | 4 | 2 | 2 |
| Conclusions carrying scope | 0 | 0 | **2** |
| Independent replications | 0 | 0 | **3** |
| Falsification probes | 0 | 0 | **2** |
| Self-corrections (own hypotheses rejected/weakened) | 0 | 0 | **2** |
| Significance-gated | no | no | **yes** |
| **Incorrect candidate named a winner** | **3** | 0 | **0** |

### The finding that matters

The baseline workflow reported:

```
fastest on sparse_random is bfs_unit
fastest on dense_random  is bfs_unit
fastest on grid_2d       is bfs_unit
```

`bfs_unit` **is** the fastest on those topologies. It is also **wrong** on all
three — it returns incorrect distances whenever edge weights differ, and the
benchmark has no way to notice, because a benchmark measures speed. Three of
four headline conclusions from the plausible-looking workflow are worse than
useless: they are fast wrong answers presented as winners.

ORIGIN spent six experiments instead of one and produced *fewer* conclusions —
but zero of them are wrong in that way, and it explicitly recorded `bfs_unit` as
correct **only** on `unit_weight`. That is what the extra machinery buys, and it
is the whole case for it.

### What ORIGIN concluded

Accepted with scope (confirmed → independently replicated → survived
falsification on both held-out topologies):

1. *SPFA performs fewer relaxations than Bellman-Ford on sparse random graphs.*
   4,907 vs 21,476 relaxations — exact counts, machine-independent. Scope:
   holds to n ≤ 2× tested sizes; **extends to** `long_chain` and `scale_free`.
2. *The BFS candidate returns correct distances on unit-weight graphs and
   incorrect distances on every weighted topology.* Scope recorded from the
   probe.

### What ORIGIN rejected — using its own evidence

1. *Dijkstra with a binary heap is fastest on sparse random graphs.* SPFA led,
   and the difference did not clear the significance gate. Not confirmed.
2. *The array-scan Dijkstra beats the heap variant on dense graphs.* Measured
   the other way round; refuted.

Both were ORIGIN's own seeded hypotheses, and both are textbook-plausible. It
raised **9 cautions**, four of them stating that a topology's apparent winner
was not statistically separable from the runner-up and that therefore **no
winner is claimed**.

### What proposal-only produced

Two well-formed, validated proposals — one asking for more trials, one noting
that comparison counts are unmeasured. Both are reasonable. Neither is a
finding, and the workflow has no way to make them into one. Recorded here to
make the distinction concrete: a proposal that survives schema and vocabulary
validation is still not evidence.

## 4. Efficiency

Six experiments for two accepted conclusions is expensive — 3 experiments per
accepted claim, against the baseline's 0.25. That cost is the replication and
falsification requirement, and it is the honest price of the accuracy column.
An operator who wants speed over rigour should run the baseline and know what
they are getting.

## 5. Reproduction

```bash
python3 tools/flagship_evaluation.py --dir runs/flagship_eval
python3 -m origin verify  --dir runs/flagship_eval/origin_full
python3 -m origin report  --dir runs/flagship_eval/origin_full
python3 -m origin replay  --dir runs/flagship_eval/origin_full --exp <exp_id>
cat runs/flagship_eval/PREREGISTRATION.json
cat runs/flagship_eval/EVALUATION_RESULTS.json
```

Shipped artifacts: `examples/final_flagship_mission/` — pre-registration,
machine-readable comparison, and three complete mission directories including
the full dossier, timeline, decision log and every experiment's code, spec and
results. `origin verify` passes; the portability guard reports no absolute paths.

Environment: CPython 3.12.3, Ubuntu 24.04.4 LTS, x86-64, single core.

## 6. Limitations and threats to validity

1. **One domain, one host, one interpreter, n ≤ 512, pure Python.** Timing
   conclusions do not transfer. Relaxation counts do.
2. **The proposal workflow used the deterministic mock provider**, not a live
   model, so it measures the *pathway*, not a real model's proposal quality.
3. **The comparison is not blind.** The same author wrote all three workflows.
   The baseline is a fair representation of "benchmark and report", but a
   determined baseline could add its own correctness check — the point is that
   it has to be *added*, and ORIGIN has it by construction.
4. **Efficiency is measured in experiments, not information.** "Three
   experiments per accepted conclusion" says nothing about whether the
   conclusion was worth having.
5. **No novelty is claimed.** That SPFA relaxes fewer edges than Bellman-Ford
   and that BFS needs unit weights are textbook facts. ORIGIN rediscovered them
   from measurement, correctly scoped, having also rejected two plausible
   claims that were wrong here. Rediscovery under budget is the demonstrated
   capability; discovery is not.
6. **Inconclusive results are a real outcome.** In the shipped example mission
   at 5 trials, both timing hypotheses were inconclusive rather than confirmed.
   That is the significance gate working, and it is reported rather than tuned
   away.
