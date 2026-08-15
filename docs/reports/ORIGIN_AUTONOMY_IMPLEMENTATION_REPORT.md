# ORIGIN v1.5 — Autonomy Implementation Report

Bounded autonomy: ORIGIN can continue a mission across many short sessions,
restarts and pauses, inside explicit operator-controlled limits. Every figure
below is the output of a command executed at the shipping commit on the
environment named in §9.

---

## 1. Baseline findings

Full audit: `docs/audit/V1_5_AUTONOMY_BASELINE_AUDIT.md`, completed before any
autonomy code was written and grounded in executed verification (226 → at the
time 186 tests OK, portability clean, flagship verified).

What already existed and was preserved: 17-state validated lifecycle with
`stop_reason` on every terminal; per-step checkpointing with fsync, backup
rotation and structural load validation; orphan reconciliation; six budget
dimensions enforced at named call sites; `state.verify()`; and every safety
gate (sandbox design policy, proposal schemas, retrieval policy, provenance
rules, replication/falsification).

Six honest gaps entering the phase:

1. **No work queue.** The controller decided the next action from live state
   each step, so a plan could not be *inspected before it ran*.
2. **No claim/complete record.** An interrupted action was inferred from
   orphaned directories, not known.
3. **No single-writer protection** — two `origin run` processes on one mission
   would both save, and the last writer would win silently. The largest
   correctness gap for long-running operation.
4. **No typed retry classification or backoff** — only a global counter.
5. **No per-run step or wall-clock limit**, and no consecutive-failure or idle
   cap.
6. **Decisions were recorded but not tied to a durable queue item**, so "why
   this over that" was partial.

Also corrected in this phase, as instructed: the web-evidence verification
report's stale "22 regression tests" claim. Verified counts are now stated —
v1.4.1 shipped 27, v1.4.2 added 20, `test_retrieval_security.py` holds 47.

---

## 2. Architecture implemented

```
origin/autonomy.py     WorkItem + JSON schema, MissionLease, AutonomyStore,
                       AutonomyPolicy, RunLimits, retry classification, backoff
origin/scheduler.py    Scheduler.tick() — one bounded restart-safe action
                       Scheduler.run() — bounded foreground loop, no daemon

<mission>/autonomy/state.json       durable queue + counters (schema v1)
<mission>/autonomy/decisions.jsonl  append-only decision records
<mission>/autonomy/mission.lease    single-writer lease
```

Tick sequence: load state → `verify()` → acquire lease → recover interrupted
work → seed from mission state → policy selects **one** permitted action →
dispatch to the existing engine → checkpoint result, decision and budget →
release lease.

The layer adds a *chooser*, not a capability. `run_experiment` goes through
`ExperimentEngine` (and therefore `sandbox.validate_design`), `retrieve_source`
through `web_evidence.ingest_url` (and therefore the full URL/address/host/
robots/size policy), `form_hypotheses` and `criticise` through
`ResearchController` steps. There is exactly one code path per capability, so
no gate can drift.

---

## 3. Files changed

**New:** `origin/autonomy.py`, `origin/scheduler.py`, `tools/autonomy_demo.py`,
`tests/test_autonomy.py`, `examples/autonomy_demo/`, `docs/AUTONOMY.md`,
`docs/security/AUTONOMY_THREAT_MODEL.md`,
`docs/verification/AUTONOMY_VERIFICATION_REPORT.md`,
`docs/audit/V1_5_AUTONOMY_BASELINE_AUDIT.md`.

**Modified:** `origin/cli.py` (new `autonomy` subcommand group; no existing
command or flag changed), `origin/state.py` (`verify()` extended to autonomy
state), `origin/__init__.py` + `pyproject.toml` (1.5.0), `README.md`,
`docs/ARCHITECTURE.md`, `docs/OPERATIONS.md`, `docs/REPRODUCIBILITY.md`,
`docs/SECURITY.md`, `docs/DECISIONS.md` (AD-38…AD-42), `ROADMAP.md`,
`SPECIFICATION.md`, `docs/verification/WEB_EVIDENCE_VERIFICATION_REPORT.md`
(stale count), `.github/workflows/ci.yml`.

---

## 4. CLI added

```
origin autonomy status  --dir M     lifecycle, queue, lease, next action, budgets,
                                    retry state, interrupted items, stop reason
origin autonomy plan    --dir M     candidates in policy order, with <NETWORK> /
                                    <PROVIDER> markers, every rejection + reason,
                                    the choice, the tie-break, the next wake time
origin autonomy tick    --dir M     at most one action
origin autonomy run     --dir M --max-steps N --max-wall-s N
                                    [--allow-network --max-retrievals N]
                                    [--allow-provider --max-provider-calls N]
                                    [--max-consecutive-failures N]
origin autonomy pause|resume|cancel --dir M
origin autonomy recover-lock --dir M [--force]
```

No existing command changed. `LEASE HELD` exits 3; `recover-lock` without
`--force` exits 1 after reporting the holder.

---

## 5. Safety boundaries

Autonomy **may** decide: which permitted action runs next, in what order,
under which budget. Autonomy **may not**: create an action type; carry
executable content (a `run_experiment` item with `design`, `command`, `code`,
`runner` or `argv` is rejected at the queue); widen any limit; use the network
or a provider without a per-run flag; turn a web claim or an LLM proposal into
evidence; bypass `verify()`; or steal a lease.

Live web and live LLM are opt-in per run, refused by the policy otherwise, and
marked in the plan *before* execution. With `--brain anthropic` configured but
`--allow-provider` absent, the run proceeds with the provider disabled and
makes zero calls.

---

## 6. Work-item schema

Required: `id, action, status, priority, created_at, idempotency_key, params,
reason`. Optional: `depends_on, attempts, not_before, cost_estimate,
requires_network, requires_provider, requires_approval, approved_by,
decision_ref, result_ref, last_error, updated_at`.

Eight action types only: `plan_mission, form_hypotheses, run_experiment,
criticise, retrieve_source, review_conflict, generate_report,
await_operator_approval`. Nine statuses: `queued, claimed, done, failed,
deferred, blocked, needs_approval, cancelled, interrupted`.
`additionalProperties: false` throughout; unknown fields are rejected, not
ignored. Items are re-validated on load; anything malformed is **quarantined**
as FAILED and surfaced by `origin verify` rather than executed.

Idempotency keys are derived from `(action, params)`, so a repeated tick that
proposes the same action gets the existing item back instead of queueing a
duplicate.

---

## 7. Decision policy

Deterministic. Permitted candidates are ordered by `(-priority, cost,
created_at, id)` — the final `id` term guarantees a stable answer even when
priority, cost and timestamp are identical. Model output is never a reason.

An item is vetoed if it is claimed, interrupted, awaiting approval, in retry
backoff, missing a dependency, over its attempt limit, requires un-granted
network or provider access, or cannot be afforded. Every evaluation writes an
append-only record with the candidate list, the choice, **every rejection with
its reason**, priority factors, tie-break rule, budget state, approval state,
policy version and next wake time — written before the action runs.

---

## 8. Recovery, locking and retries

**Recovery.** The claim is checkpointed before execution. On the next tick a
`claimed` item becomes `interrupted` with "completion is UNKNOWN"; it is not
re-run and not assumed successful, and the operator resolves it. For an
experiment that may already have spawned, an automatic re-run would
double-charge the budget and could duplicate research history.

**Locking.** `autonomy/mission.lease` via `O_CREAT|O_EXCL`, carrying owner, pid,
host and time. A second process is refused with a message naming the holder and
the recovery command. A stale lease is never stolen — from outside it is
indistinguishable from a live one. `recover-lock --force` releases it and writes
to both the mission event log and the autonomy decision log.

**Retries.** Retryable: transport timeouts, provider outages, rate limits,
transient retrieval errors. Never retried: policy violations, schema failures,
unsafe designs, disallowed URLs, robots refusals, cancellation, invalid state,
configuration errors — and anything unclassified. Backoff is deterministic
(30 s × 2^(attempt−1), capped at 1 h, no jitter), persisted as `not_before`, so
a deferred item is invisible to the policy until then. That is what prevents a
hot loop, and it is asserted directly: after a failure, an immediate re-tick
provably selects a *different* item.

---

## 9. Demo outcome

`examples/autonomy_demo/` — fixture-only, clock-injected, no network or provider
call. All twelve required behaviours in one run: question → seeded work items →
recorded rationale (30 decision records) → fixture evidence (1 source, 2
SPECULATION claims) → 5 hypotheses through the existing gates (2
`accepted_with_scope`, 1 `rejected`, 2 `weakened`) → planned retryable failure →
backoff 60 s then 120 s with an immediate re-tick selecting something else →
durable pause → restart from disk → 10 further actions with **0** completed
items re-run → stop reason `completed` → full JSON report.

Evidence discipline held: **13 Evidence items, all from experiments, 0 from the
web.**

---

## 10. Tests run and exact results

Environment: **Python 3.12.3 [GCC 13.3.0], Ubuntu 24.04.4 LTS, Linux x86_64,
1 core.**

```
$ python3 -m unittest discover -s tests                              Ran 226   OK  (50.0s)
$ python3 -m unittest discover -s tests -p test_autonomy.py          Ran  40   OK  ( 1.6s)
$ python3 -m unittest discover -s tests -p test_reliability.py       Ran  10   OK  (21.4s)
$ python3 -m unittest discover -s tests -p test_lifecycle.py         Ran   7   OK  ( 0.4s)
$ python3 -m unittest discover -s tests -p test_retrieval_security.py Ran 47   OK  ( 0.9s)
$ python3 -m unittest discover -s tests -p test_web_evidence.py      Ran  25   OK  ( 0.5s)
$ python3 -m unittest discover -s tests -p test_llm_integration.py   Ran  33   OK  (22.6s)
$ python3 tools/autonomy_demo.py --dir /tmp/origin-autonomy-demo     completed
$ python3 -m origin verify --dir /tmp/origin-autonomy-demo           State verified
$ python3 -m origin verify --dir examples/autonomy_demo              State verified
$ python3 tools/check_artifacts_portable.py .                        PORTABILITY OK
```

Support matrix, full suite: CPython 3.10.20 (80.9s), 3.11.15 (71.1s), 3.12.3
(66.1s), 3.13.13 (92.2s), 3.14.4 (61.8s) — all **226 OK**.

The 40 autonomy tests cover queue and policy (10), persistence and recovery
(7), locking (4), budgets and retries (8), safety (7), and demo/CLI (4). Detail
per test in `docs/verification/AUTONOMY_VERIFICATION_REPORT.md`.

---

## 11. Known limitations

1. **No exactly-once guarantee for external actions.** A crash between a side
   effect and its checkpoint yields `interrupted`, not a claim. Recorded, not
   solved.
2. **The lease is advisory and filesystem-local**; it assumes reliable
   `O_CREAT|O_EXCL` and does not span an unreliable network filesystem.
3. **Seeding is heuristic** — permitted, affordable and deterministic, not
   provably optimal.
4. **No jitter in backoff**, so many missions started together retry in
   lockstep.
5. **Wall-clock limits are checked between ticks**, so one long action can
   overrun the run limit (the sandbox timeout still bounds it).
6. **Autonomy state is not tamper-evident** — `verify` reports *that* an item
   was malformed, not who changed it.
7. **The demo is fixture-only.** Autonomy has not been exercised end-to-end
   against live web retrieval or a live provider; both paths are gated and
   unit-tested, but no live autonomous run has been performed.
8. **No daemon, no multi-agent coordination, no distributed execution, no
   source discovery** — none are implemented and none are claimed.

---

## 12. Next recommended phase

**Not** a daemon. The highest-value next work is a second research domain: the
domain contract now carries proposal, falsification and sweep hooks, autonomy
schedules through it without change, and a second domain is the only honest way
to find out which parts of ORIGIN are genuinely domain-neutral and which have
quietly specialised to sorting benchmarks. Everything else — scheduling
services, richer planning, live autonomous runs — rests on that answer.
