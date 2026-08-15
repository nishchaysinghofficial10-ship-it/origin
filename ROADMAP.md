# ORIGIN Roadmap

Phase plan from the project brief, mapped to what v0.1 delivers and what
comes next. Each phase lands behind interfaces that already exist in v0.1
(marked in SPECIFICATION.md §3), so nothing here requires rewriting the core.

| Phase | Scope | Status |
|---|---|---|
| 0 | Research design: definitions, data model, architecture, evaluation plan | ✅ `SPECIFICATION.md` v0.1 |
| 1 | Research core: project creation, state, task loop, persistence, checkpoints, resume | ✅ shipped |
| 2 | Knowledge acquisition: search interface, document ingestion, claim extraction, source ranking, citation tracking | 🔜 next — lands in `Source`/`Claim`, `seed_knowledge()` → live pipeline, `searches` budget |
| 3 | Knowledge graph maturity: richer relations, conditions, graph visualization | 🔶 core graph + contradiction detection shipped; viz pending |
| 4 | Hypothesis & planning: gap-driven generation, LLM brain option, plan modification | 🔶 competing pool + evolution shipped (deterministic); LLM adapter pending |
| 5 | Experiment engine growth: more domains (simulation/physics), richer stats, experiment queues | 🔶 sandbox + versioned generated code shipped; one domain (`algobench`) |
| 6 | Criticism & self-correction: falsification tests, alternative-hypothesis generation | 🔶 replication enforcement, assumption audit, contradiction surfacing shipped |
| 7 | Long-running autonomy: scheduler/daemon, multi-day runs, recovery, monitoring dashboard | 🔶 pause/resume + `--steps` shipped; daemon + dashboard pending |
| 8 | Evaluation: ORB benchmark, baselines, metrics reports | 🔜 metrics groundwork in place (decisions, evidence ledgers, replication) |

## Concrete next milestones (recommended order)

1. **Phase 2a — local ingestion.** Feed ORIGIN PDFs/notes/datasets from
   `sources/`; extract claims with provenance into the existing `Claim`
   model. No internet needed to make this valuable.
2. **Phase 4a — LLM brain adapter.** A `Brain` interface with two
   implementations: the current deterministic heuristics and an Anthropic
   API client (hypothesis text, decomposition, criticism prompts). Behind a
   flag so runs stay reproducible.
3. **Phase 2b — bounded web acquisition.** Budgeted searches, source
   reliability scoring, claim support/contradict trees.
4. **Phase 5a — second domain.** A simulation domain (e.g. simple physics or
   network models) to prove the domain interface generalizes.
5. **Phase 3a — graph & dashboard.** Visualize the knowledge graph and the
   mission-control view in a local web UI.
6. **Phase 7 — scheduler.** Background worker + queue for genuine multi-day
   runs with periodic critic sweeps.
7. **Phase 8 — ORB.** 20–50 budgeted, experimentally checkable problems;
   compare ORIGIN vs one-shot answers vs fixed pipelines.

## Research Reincarnation (post-1.0 direction)

Completed projects are already fully persisted. Reincarnation = a registry
that lets a new project import prior projects' graphs, claims, and failure
logs as `prior_knowledge` sources — accumulating a research history across
investigations.


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
