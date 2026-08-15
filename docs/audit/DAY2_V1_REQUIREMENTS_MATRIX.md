# DAY 2 — v1.0 Requirements Matrix

Conservative classification of every v1.0 handoff requirement against the
verified baseline, with the build decision for this engagement.
Classifications: EXISTS_AND_VERIFIED / EXISTS_BUT_INCOMPLETE /
EXISTS_BUT_NEEDS_HARDENING / PARTIALLY_IMPLEMENTED / MOCKED / MISSING.

| # | v1.0 requirement | Baseline | Decision this engagement |
|---|---|---|---|
| 1 | Validated mission lifecycle state machine, legal transitions only, distinct terminal states | PARTIALLY_IMPLEMENTED | **BUILD**: explicit transition table + validation + migration of old phases |
| 2 | Append-only decision/event log | EXISTS_AND_VERIFIED | PRESERVE; add heartbeat + stop-reason events |
| 3 | Checkpoints: safe-write, backup, corruption fail-safe | EXISTS_BUT_NEEDS_HARDENING | **BUILD**: `.bak` rotation, integrity check, clear recovery path |
| 4 | Interrupt mid-run → restart → no loss/duplication (tested) | MISSING (untested) | **BUILD + TEST** (Phase 1 required proof) |
| 5 | Replay prior experiment from metadata within tolerance | PARTIALLY (manual only) | **BUILD**: `origin replay` command + test |
| 6 | Deterministic seeds, config capture, versioned experiments | EXISTS_AND_VERIFIED | PRESERVE |
| 7 | Structured failure records | EXISTS_AND_VERIFIED | PRESERVE; add kinds |
| 8 | Budgets: time/experiments/compute/provider-calls/retries, enforced+visible, stop reasons | PARTIALLY_IMPLEMENTED | **BUILD**: extend ledger + stop-reason reporting |
| 9 | Evidence pipeline Source→passage→claim→validation→evidence→graph, provenance, untrusted-by-default | MISSING (models exist) | **BUILD (local files)**; live web **DEFERRED** — build env has no general egress (see risk doc) |
| 10 | Contradiction handling with preserved confidence history | EXISTS_BUT_INCOMPLETE | **BUILD**: confidence-change history records |
| 11 | LLM provider abstraction, env credentials, schema-validated structured output, retries/timeouts, mock provider, injection-aware, no LLM→fact path | MISSING | **BUILD**: `origin/brain.py` (Mock + Anthropic via stdlib urllib); proposals-only pathway |
| 12 | Hypothesis lifecycle incl. ACCEPTED_WITH_SCOPE / evolution ops | PARTIALLY_IMPLEMENTED | **BUILD**: scope acceptance + revision history; evolution (mutate) exists via domain synthesis |
| 13 | Experiment plans: full spec fields | EXISTS_BUT_INCOMPLETE | **BUILD**: enrich design schema (controls, stopping criteria, interpretation) |
| 14 | Sandbox: rlimits, scrubbed env, output caps, allow-list, no secrets, reject-unsafe-with-reason | MISSING (subprocess+timeout only) | **BUILD** strongest practical confinement; document residual limits honestly |
| 15 | Critic falsification experiments + boundary probes + scoped conclusions | MISSING | **BUILD**: falsification stage with unseen-regime/boundary probes → FalsificationAttempt records |
| 16 | Independent replication | EXISTS_AND_VERIFIED | PRESERVE; falsification adds env-variation independence |
| 17 | Task queue/scheduler/watchdog/stagnation/heartbeat | MISSING | **BUILD**: stagnation detection, retries cap, heartbeat, stop reasons; daemon **DEFERRED** (manual+steps remains) |
| 18 | Mission control view + research replay | PARTIALLY (CLI box) | **BUILD**: static HTML mission-control page generated from state (no server — appropriate to zero-dep stack) |
| 19 | Dossier: prediction ledger, falsification, budget ledger, threats to validity, repro steps | EXISTS_BUT_INCOMPLETE | **BUILD**: extend dossier sections |
| 20 | Flagship fresh bounded mission with correction opportunity + conditional finding + replication + dossier | PARTIALLY (v0.1 demo exists) | **BUILD + RUN**: extended algobench (new algorithms, unseen regimes, hybrid-cutoff parameter sweep, 100-experiment cap) |
| 21 | Layered tests: unit/integration/e2e/regression | EXISTS_BUT_INCOMPLETE (6 tests) | **BUILD**: reliability, lifecycle, sandbox, brain, red-team suites |
| 22 | Security review + threat model docs | MISSING | **BUILD** |
| 23 | Red-team execution + report | MISSING | **BUILD**: executable red-team scenarios + report |
| 24 | Docs set (ARCHITECTURE/RESEARCH_MODEL/OPERATIONS/REPRODUCIBILITY/SECURITY/DECISIONS) | PARTIALLY (README/SPEC/ROADMAP) | **BUILD** |
| 25 | Final handoff report + requirements matrix with evidence | MISSING | **BUILD** at close |
