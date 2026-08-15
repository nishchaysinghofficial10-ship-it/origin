# ORIGIN v1.5 — Autonomy Verification Report

Every figure below is the output of a command executed at the shipping commit.
Specification: `../AUTONOMY.md`. Attack surface:
`../security/AUTONOMY_THREAT_MODEL.md`. Pre-implementation findings:
`../audit/V1_5_AUTONOMY_BASELINE_AUDIT.md`.

## Environment

```
$ python3 -VV      → Python 3.12.3 (main, Mar  3 2026, 12:15:18) [GCC 13.3.0]
$ uname -sm        → Linux x86_64
$ head -1 /etc/os-release → PRETTY_NAME="Ubuntu 24.04.4 LTS"
$ nproc            → 1
```

## Executed verification sequence

```
$ python3 -m unittest discover -s tests
Ran 226 tests in 50.002s   OK

$ python3 -m unittest discover -s tests -p test_autonomy.py
Ran 40 tests in 1.630s     OK

$ python3 -m unittest discover -s tests -p test_reliability.py
Ran 10 tests in 21.392s    OK

$ python3 -m unittest discover -s tests -p test_lifecycle.py
Ran 7 tests in 0.443s      OK

$ python3 -m unittest discover -s tests -p test_retrieval_security.py
Ran 47 tests in 0.874s     OK

$ python3 -m unittest discover -s tests -p test_web_evidence.py
Ran 25 tests in 0.509s     OK

$ python3 -m unittest discover -s tests -p test_llm_integration.py
Ran 33 tests in 22.583s    OK

$ python3 tools/autonomy_demo.py --dir /tmp/origin-autonomy-demo
… Web claims stayed SPECULATION; every Evidence item came from an ORIGIN experiment.

$ python3 -m origin verify --dir /tmp/origin-autonomy-demo
State verified: counts, references, experiment artifacts and event log are consistent.

$ python3 -m origin verify --dir examples/autonomy_demo
State verified: counts, references, experiment artifacts and event log are consistent.

$ python3 tools/check_artifacts_portable.py .
PORTABILITY OK: no machine-specific absolute paths in artifacts under .
```

Support matrix, full suite:

```
CPython 3.10.20   Ran 226 tests in 80.9s   OK
CPython 3.11.15   Ran 226 tests in 71.1s   OK
CPython 3.12.3    Ran 226 tests in 66.1s   OK
CPython 3.13.13   Ran 226 tests in 92.2s   OK
CPython 3.14.4    Ran 226 tests in 61.8s   OK
```

## Test inventory

| Module | Tests |
|---|---:|
| `test_core` | 7 |
| `test_lifecycle` | 7 |
| `test_reliability` | 10 |
| `test_portability` | 12 |
| `test_sandbox` | 6 |
| `test_brain` | 7 |
| `test_evidence_redteam` | 7 |
| `test_performance_repro` | 25 |
| `test_llm_integration` | 33 |
| `test_web_evidence` | 25 |
| `test_retrieval_security` | 47 |
| **`test_autonomy`** | **40** |
| **Total** | **226** |

(Per-module counts sum to 226 under `unittest discover`; a verbose run
attributes 216 to named modules and the remainder to inherited base cases.
The authoritative number is the discover total above.)

## Demonstration outcome (`examples/autonomy_demo`)

Fixture-only, clock-injected, no network and no provider call. All twelve
required behaviours were observed in one run:

| # | Requirement | Observed |
|---|---|---|
| 1 | starts from a question | mission created with the sorting-tradeoffs question |
| 2 | creates safe work items | `plan_mission`, `form_hypotheses`, `run_experiment`×4, `criticise`, `retrieve_source`×2, `review_conflict`, `generate_report` |
| 3 | records a rationale | 30 decision records in `autonomy/decisions.jsonl` |
| 4 | fixture evidence only | 1 web source, 2 SPECULATION claims |
| 5 | hypotheses through existing gates | 5 hypotheses: 2 `accepted_with_scope`, 1 `rejected`, 2 `weakened` |
| 6 | planned retryable failure | simulated timeouts on the second source |
| 7 | retry/backoff, no hot loop | deferred at 60 s then 120 s; an immediate re-tick selected a *different* item both times |
| 8 | durable pause | tick while paused → `paused_by_operator`, queue `{done: 3, deferred: 1}` |
| 9 | restart from saved state | scheduler and state objects discarded and rebuilt from disk |
| 10 | resume without duplication | 10 further actions; **0** previously-completed items re-run |
| 11 | honest stop | `completed` — the mission finished, not the limit |
| 12 | full report | `autonomy/demo_report.json`: work items, decisions, budgets, evidence, hypotheses, failures, limitations |

Evidence discipline held under autonomy: **13 Evidence items, all from
experiments; 0 from the web**, and every web-derived claim stayed
`speculation`.

## What the tests actually assert

**Queue and policy (10).** Deterministic selection stable across reloads;
tie-break falls through to id when priority, cost and timestamp are identical;
unknown action types rejected; `run_experiment` items carrying `design`,
`command`, `code`, `runner` or `argv` rejected; `retrieve_source` items with
non-https URLs rejected; dependencies enforced; approval gate blocks until
approved; completed work never reselected; idempotency keys collapse
duplicates; network/provider actions refused without permission; decision
records contain candidates, rejections, budget, approvals and tie-break.

**Persistence and recovery (7).** State survives reload at every boundary;
a claimed-then-lost item becomes `interrupted` and is never auto-re-run;
duplicate ticks change neither the done-set nor the budget; autonomy artifacts
carry no absolute paths or secrets; malformed state raises a clear error while
`verify()` reports it and the research state stays clean; a tampered item is
quarantined and surfaced by `verify`; a newer schema is refused.

**Locking (4).** A second acquisition is refused with a message naming the
holder and the recovery command; the lease is released on normal completion; a
lease with `acquired_at=0` and a dead pid is still **not** stolen, including by
a full run; recovery without `--force` refuses, with `--force` releases and
writes to both audit logs.

**Budgets and retries (8).** Step and wall-clock limits stop the run;
experiment budget and per-run retrieval limit veto work; retryable failures
back off 10 s → 20 s and then fail terminally, with an immediate re-tick
provably selecting something else; a `PolicyViolation` is never retried
(attempts stays 1); retries do not re-charge the experiment budget;
consecutive-failure cap stops the run; idle ticks are capped at 3 total.

**Safety (7).** Experiment parameters still bounded by sandbox policy after an
autonomous run; bad URLs refused at the queue or at execution with zero web
sources created; no retrieval occurs without `--allow-network` (`provider.calls
== []`); a mission configured with `--brain anthropic` makes 0 provider calls
without `--allow-provider`; web claims never become evidence; a corrupted event
log stops the scheduler with `unsafe_or_invalid_state`; cancel is terminal.

## Known limitations

1. **No exactly-once guarantee for external actions.** A crash between an
   external side effect and its checkpoint yields `interrupted`, not a claim
   about what happened. This is recorded, not solved.
2. **The lease is advisory and filesystem-local.** It assumes reliable
   `O_CREAT|O_EXCL`; it offers nothing across an unreliable network filesystem
   or for a mission copied elsewhere.
3. **Seeding is heuristic.** It proposes plausible next actions from mission
   state. It guarantees permitted, affordable and deterministic — not optimal.
4. **Backoff has no jitter**, so many missions started together would retry in
   lockstep.
5. **Wall-clock limits are checked between ticks**, so one long action can
   overrun the run limit; the sandbox's own timeout still bounds it.
6. **No daemon, no scheduler service, no multi-agent coordination, no
   distributed execution.** `run()` is a bounded foreground loop.
7. **Autonomy state is not tamper-evident.** `verify` reports *that* an item was
   malformed, not who changed it.
8. **The demo is fixture-only.** Autonomy has not been exercised against live
   web retrieval or a live provider; both paths are gated and unit-tested, but
   an end-to-end autonomous run with real external calls has not been performed.
