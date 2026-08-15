# ORIGIN Technical Specification v0.1

**O**pen-ended **R**esearch & **I**nference through **G**enerative **I**nvestigation

Status: implemented and passing (`python -m unittest discover -s tests`).
This document is the formal contract for v0.1 and the foundation every later
phase builds on. Where the full vision exceeds v0.1, the boundary is stated
explicitly in §12.

---

## 1. Purpose and research problem

ORIGIN is not "an AI that researches anything." It is a **persistent
computational research system** that can formulate, investigate, test,
criticize, and evolve explanations over long periods of time.

The research question the system itself embodies:

> Can a computational system maintain a persistent evolving model of a
> research problem, identify its own knowledge gaps, allocate limited
> resources to investigations, generate competing hypotheses, experimentally
> test them, criticize its own conclusions, and continuously update its
> research state over long periods?

v0.1 answers the load-bearing subset: **persistent state, competing
hypotheses, real sandboxed experiments, self-criticism with forced
replication, resource budgets, hypothesis evolution, and full traceability**
— demonstrated end-to-end in one computationally testable domain.

## 2. The evidence hierarchy (core architectural principle)

Every piece of knowledge carries an explicit epistemic status
(`origin/models.py::EpistemicStatus`):

| Status | Meaning |
|---|---|
| `fact` | Directly supported by reliable sources |
| `inference` | Derived from multiple pieces of evidence |
| `hypothesis` | Proposed, insufficiently tested |
| `experimental_result` | Produced by ORIGIN's own experiments |
| `speculation` | Lacks sufficient evidence |
| `contradicted` | Significant evidence against |

Rule: **status may only be promoted by evidence, never by generation.** This
is what prevents the failure mode *AI generates → AI believes → AI cites
itself → AI becomes increasingly wrong.* Hypotheses additionally move through
their own lifecycle: `proposed → under_test → provisionally_supported /
weakened / rejected`, with `provisionally_supported` gated by the critic
(see §9).

## 3. Subsystem map (vision → v0.1 implementation)

| Subsystem (vision) | v0.1 status | Where |
|---|---|---|
| Research Controller | ✅ implemented | `controller.py` |
| Research Planner | ✅ minimal (domain decomposition tree) | `domains/*` `decompose()` |
| Source Acquisition | 🔶 interface + seeded prior knowledge | `models.Source`, `seed_knowledge()` — Phase 2 |
| Source Verification | 🔶 claim/evidence model in place; live verification Phase 2 | `models.Claim/Evidence` |
| Knowledge Graph | ✅ entities, relations, provenance, confidence, contradiction detection | `graph.py` |
| Gap Detection | ✅ domain-declared gaps → recommendations | `knowledge_gaps()` |
| Hypothesis Engine | ✅ competing pool, ledgers, machine-checkable predictions, evolution | `models.Hypothesis`, domain |
| Experiment Engine | ✅ generated self-contained code, sandboxed subprocess, timeout, versioned forever | `experiments.py` |
| Simulation Engine | 🔶 same interface; additional domains are Phase 5+ | `domains/base.py` |
| Results Analyzer | ✅ statistical rankings, prediction verdicts, noise handling | domain `analyze()` |
| Critic Engine | ✅ replication enforcement, assumption audit, contradiction surfacing | `critic.py` |
| Resource Manager | ✅ experiment + compute budgets, selection by info-gain/cost | `budget.py`, controller |

## 4. Data model

All records are dataclasses in `origin/models.py`, serialized as JSON.

- **Source** `(id, kind, title, locator, reliability)` — kinds: `internet`,
  `dataset`, `user`, `prior_knowledge`, `internal_experiment`.
- **Claim** `(id, text, status: EpistemicStatus, confidence, source_ids)`.
- **Evidence** `(id, target_id, direction: supports|contradicts, strength
  0..1, kind, summary, experiment_id, payload)` — every evidence item links a
  conclusion to its provenance.
- **Prediction** `(id, text, check: dict, outcome)` — `check` is a
  machine-checkable spec interpreted by the domain; outcomes:
  `untested | confirmed | refuted | unstable | inconclusive`.
- **Hypothesis** `(id, statement, rationale, status, predictions[],
  supporting_evidence[], contradicting_evidence[], importance,
  cost_estimate, tags[], tested_in[])` — the ledger (§7 of the dossier)
  reports counts, never a bare confidence number.
- **ExperimentRecord** `(id, title, hypothesis_ids, design, status, dir,
  duration_s, summary, error)` — `dir` contains the generated `run.py`,
  `spec.json`, `stdout.log`, `result.json`, kept forever.
- **Decision** (dict) `(step, context, options[{label, score, reason}],
  chosen, reason)` — the controller's reasoning is itself data.

## 5. Persistent research state

`origin/state.py`. Per-project on-disk layout:

```
project.json            immutable metadata
state.json              full atomic snapshot (tmp-write + rename)
research_state/         per-type JSON views (hypotheses, claims, evidence,
                        experiments, decisions, failure_log, graph)
experiments/exp_*/      generated code + raw results, versioned forever
logs/events.jsonl       append-only event log (the research timeline)
reports/                dossier.md, timeline.md
sources/                reserved for Phase 2 ingested documents
```

Contract: the state is **checkpointed after every controller step**; a
`KeyboardInterrupt` or power loss costs at most one step. `ResearchState.load`
fully reconstructs typed objects (enums included). This is what makes
research runs pausable, resumable, and eventually multi-day.

## 6. Controller state machine

One question per step — *what should happen next?* — scored, logged as a
Decision, executed, checkpointed.

```
initialized ─► planned ─► hypothesized ─► investigating ─► criticized ─► complete
                              ▲               │  ▲              │
                              └── new hyps ◄──┘  └── replication┘
```

Step priority order:

1. **Plan** — decompose question; seed assumptions + prior claims.
2. **Hypothesize** — create the competing pool (never a single hypothesis).
3. **Investigate** — score pending hypotheses by
   `importance / (1 + evidence) / cost` (expected information gain per unit
   resource), log the decision with all candidate scores, design one
   experiment (co-testing compatible hypotheses), execute, analyze.
   Failed executions retry at most once, then the hypothesis is parked as
   `weakened` with a caution (no budget death-spirals).
4. **Critic: replication** — any hypothesis supported by a single experiment
   is re-tested on independent inputs (new seeds) before it may stand.
5. **Critic: final review** — assumptions on record, unreplicated-support
   cautions, graph contradictions surfaced, gaps → recommendations.
6. **Synthesis** — dossier + timeline written; phase = `complete`.

Budget exhaustion at any point short-circuits to 5→6: ORIGIN reports what it
has rather than pretending completeness.

## 7. Research domain interface

`origin/domains/base.py::ResearchDomain` — the core is domain-agnostic:

```
decompose(question, config) -> research tree
initial_assumptions() / seed_knowledge(state)
generate_hypotheses(state) -> [Hypothesis]          # may run again later
design_experiment(primary, pending, state) -> design dict
write_runner(design, exp_dir) -> path to self-contained run.py
analyze(record, result, state) -> summary           # evidence, graph, failures,
                                                    # status changes, NEW hypotheses
replication_design(hypothesis, state) -> design
estimate_cost(design) -> float
knowledge_gaps(state) -> [str]
```

A domain that emits new hypotheses from `analyze()` gives ORIGIN
**hypothesis/algorithm evolution**: v0.1's `algobench` synthesizes a hybrid
sorting algorithm from round-1 evidence and then subjects it to the same
testing + replication as everything else.

## 8. Resource model

`Budget(experiments_total, compute_seconds_total, searches_total)`. Every
experiment charges wall-clock compute; the controller refuses designs it
cannot afford and records the refusal. Selection is explicitly
value-per-cost, making ORIGIN an active allocator rather than a crawler.
`searches` is reserved for Phase 2 source acquisition.

## 9. Critic policy (v0.1)

1. **No single-experiment truths.** `provisionally_supported` + one
   experiment ⇒ mandatory independent replication (fresh seeds). Failed
   replication ⇒ prediction marked `unstable`, hypothesis `weakened`,
   failure-log entry.
2. **Assumption audit.** Domain assumptions + generic external-validity
   caveats are first-class dossier content.
3. **Contradiction surfacing.** Functional relations (e.g. `fastest_on`)
   conflicting across experiments become contradiction records — research
   targets, not silent overwrites.
4. **Gaps → next investigations.** Untested dimensions are converted into
   the recommended-research list.

## 10. Reporting

- `reports/dossier.md` — question, assumptions, seeded knowledge, evidence
  map, contradictions, gaps, hypothesis ledgers with per-prediction verdicts,
  experiments, result tables, **failure log**, decision history, conclusions,
  cautions, novel findings, recommendations, reproducibility appendix.
- `reports/timeline.md` — replayable `DAY n — HH:MM:SS` event narrative.
- `origin status` — mission-control box (counts, budgets, current
  investigation).

## 11. Evaluation methodology (Phase 8 preview)

Metrics ORIGIN is built to expose from day one: research efficiency
(discoveries per resource), hypothesis quality (% surviving independent
tests — measurable now via replication), self-correction rate (refuted →
revised), novelty (generated candidates outperforming the given roster —
demonstrated by `hybrid_sort`), reproducibility (deterministic seeds; every
`run.py` re-runnable standalone). ORB (ORIGIN Research Benchmark): a suite
of bounded, experimentally checkable problems with fixed budgets, comparing
ORIGIN against one-shot answers and fixed pipelines. Deferred to Phase 8;
the state/decision/evidence records it needs already exist.

## 12. MVP boundary — explicitly out of v0.1

Live internet search & source ingestion (Phase 2 — `Source`/`Claim` models
and `searches` budget are the landing zone) · LLM-driven hypothesis/plan
generation (Phase 4 — the domain interface is where an LLM brain plugs in;
v0.1 uses deterministic domain heuristics so behavior is testable) ·
multi-day scheduling daemon (Phase 7 — pause/resume already works;
`run --steps N` is the manual form) · graph visualization & web dashboard
(Phase 3/7) · additional domains (physics/simulation, Phase 5+) · real-world
actions, foundation-model training, and claims of genuine scientific
discovery (excluded by design).

## 13. Non-negotiables carried into every future phase

Evidence hierarchy on all knowledge · every conclusion traceable to
experiments/sources · failures preserved, never hidden · budgets enforced ·
state resumable · critic runs before synthesis, always.


---

## v1.0 delta (2026-08-09)

Built and verified in the v1.0 engagement: validated mission lifecycle with
migration; hardened checkpoints (backup rotation, safe load, `verify`); five
budget dimensions with explicit stop reasons; user-space experiment confinement
with pre-spawn design rejection; LLM proposal layer (Mock/Anthropic) with schema
+ vocabulary validation and redacted metadata logging; untrusted local-document
ingestion; first-class falsification stage with scoped acceptance; `replay`,
`verify`, `ingest`, `html`, `cancel` commands; static mission-control page;
37-test layered suite; flagship mission in `examples/flagship_run/`.

Still deferred (with integration plans in `docs/reports/FINAL_HANDOFF_REPORT.md`
§9): live web acquisition, verified live provider call, daemon/scheduler,
second domain, kernel-grade sandbox, live web dashboard.


---

## v1.5 delta (2026-08-11) — bounded autonomy

Added: durable schema-validated work items; a deterministic autonomy policy
with append-only decision records; a restart-safe scheduler tick and a bounded
run loop; an atomic single-writer mission lease that is never auto-stolen;
conservative recovery of interrupted work; typed retry classification with
capped exponential backoff; an `autonomy` CLI group (status/plan/tick/run/
pause/resume/cancel/recover-lock); `origin verify` coverage of autonomy state;
a fixture-only demonstration in `examples/autonomy_demo/`; 40 autonomy tests
(226 total).

Still deliberately absent: any daemon or background service, multi-agent
coordination, distributed execution, source discovery or crawling, and any
exactly-once guarantee for external actions.
