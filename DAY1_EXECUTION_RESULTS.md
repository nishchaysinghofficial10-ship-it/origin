# DAY 1 — Execution Results (baseline, before any v1.0 changes)

Environment: Ubuntu 24.04 container, Python 3.12.3, zero third-party deps.

## Command: `python -m unittest discover -s tests -v`
Result: **6/6 OK in 0.35s** — TestBudget (accounting/exhaustion), TestEndToEnd
(full autonomous run; budget-stops-research), TestGraph (contradiction,
roundtrip), TestStatePersistence (roundtrip+resume). No warnings, no skips.

## Command: `python -m origin status --dir examples/demo_run`
Result: COMPLETE at step 10 — 1 source, 3 claims, 5 hypotheses, 6 experiments,
17 evidence, 2 failures, 2 contradictions, budget 6/10 experiments, 3s/1200s
compute. Matches stored `state.json` counts exactly.

## Command: `python -m origin timeline --dir examples/demo_run`
Result: full replayable event narrative; final events `critic_review`
(5 assumptions, 2 cautions, 6 follow-ups) and `synthesis` present.

## Command: re-execute stored experiment code (`cd exp_*/ && python run.py`)
Result: `OK 20 measurements` — deterministic re-run succeeded (performed
during v0.1 close-out; identical result.json content on fixed seed).

## Known baseline incident (recorded, already fixed pre-baseline)
The first-ever demo run failed 10/10 experiments due to a relative-path bug in
the executor. The system degraded gracefully (all failures logged, budget
charged, honest report) but also **retried a broken design until the budget
died** — a retry guard (2 attempts, then park hypothesis) was added and is in
the baseline. Both behaviors inform Phase 1 hardening below.

## Pre-existing failures encountered during this audit
None. No fixes of any kind were applied during the audit phase.
