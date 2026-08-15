# ORIGIN — v1.5 Autonomy Baseline Audit

Completed **before** any autonomy code was written. Everything below was
established by reading the source and executing the documented verification
commands, not by reading the roadmap.

## Baseline verification (executed)

```
$ python3 -m unittest discover -s tests      → Ran 186 tests in 58.211s  OK
$ python3 tools/check_artifacts_portable.py . → PORTABILITY OK
$ python3 -m origin verify --dir examples/flagship_run → State verified
$ python3 -VV → Python 3.12.3 [GCC 13.3.0], Ubuntu 24.04.4 LTS, x86_64
```

## Existing state model (`origin/state.py`, SCHEMA_VERSION 3)

Durable snapshot keys: `schema_version, meta, budget, plan, sources, claims,
hypotheses, evidence, experiments, decisions, graph, assumptions, cautions,
failures, falsifications, confidence_history, recommendations, flags, step`.

Write path: full write + `fsync` to `state.json.tmp`, rotate `state.json` →
`state.json.bak`, atomic `os.replace`, then fsync the directory. Load tries
primary then backup and validates structure before accepting either.
`verify()` cross-checks evidence targets, experiment artifacts on disk,
hypothesis references, duplicate `experiment_started` events, orphaned
experiment directories, absolute artifact paths, and torn event-log lines.

**Autonomy integration point:** add a new top-level key, keep it optional on
load (older missions must still open), and extend `verify()` rather than
replacing it.

## Lifecycle (`origin/lifecycle.py`)

17 states. Non-terminal: `CREATED, VALIDATING, PLANNING, ACQUIRING_EVIDENCE,
FORMING_HYPOTHESES, SELECTING_NEXT_ACTION, DESIGNING_EXPERIMENT, EXECUTING,
ANALYZING, CRITICIZING, REPLICATING, FALSIFYING, UPDATING_KNOWLEDGE, PAUSED`.
Terminal: `COMPLETED, FAILED, CANCELLED`. `advance()` validates against a
transition table and refuses to move a terminal mission; `PAUSED` records
`paused_from` and `resume()` restores it. Terminals record `stop_reason` and
`ended_at`.

**Autonomy integration point:** autonomy must drive the *existing* controller
transitions, not add parallel states. A paused mission is already durable and
resumable — autonomy pause should reuse it.

## Checkpoint behaviour

`ResearchController.run()` saves after **every** step and reconciles orphaned
experiment directories on resume. `KeyboardInterrupt` → `PAUSED` + save.
`--steps N` → `PAUSED` after N steps. Verified by `tests/test_reliability.py`
(SIGKILL mid-run, backup recovery, both-corrupt failure, orphan adoption).

**Gap for v1.5:** the checkpoint boundary is a *controller step*, which is
coarse. There is no record of "an action was claimed but not finished", so a
crash between spawning an experiment and the next save is only detected by
orphan reconciliation. Autonomy needs an explicit claim record.

## CLI (`origin/cli.py`)

`init, run, status, report, timeline, html, verify, cancel, replay, ingest`.
`run` takes `--steps`; `init` takes budget flags and `--brain`.

**Autonomy integration point:** add an `autonomy` subcommand group. Do not
change any existing command's behaviour or flags.

## Budget enforcement points (`origin/budget.py`)

Fields: `experiments_total/used, compute_seconds_total/used,
searches_total/used, elapsed_seconds_total/used, provider_calls_total/used,
retries_total/used`. Enforced at: `can_run_experiment()` before a design is
executed; `can_call_provider()`/`charge_provider_call()` inside
`AnthropicBrain._call`; `can_retry()`/`charge_retry()` in the controller's
failure path; `charge_elapsed()` per controller step; `exhausted_reason()`
consulted each step. Retrieval has a separate per-mission counter
(`state.flags["retrievals_used"]`) checked in `web_evidence.ingest_url`.

**Gap for v1.5:** there is no *step* or *wall-clock-per-run* budget, and no
"maximum consecutive failures" or "maximum idle cycles". Those are new.

## Safety gates that must remain authoritative

| Gate | Where | Autonomy must route through it |
|---|---|---|
| Experiment design policy | `sandbox.validate_design()` before spawn, in `ExperimentEngine.run` | schedule designs, never construct commands |
| Sandbox execution | rlimits, scrubbed env, `python -I`, output caps | unchanged |
| LLM proposals | `proposals.review()` — schema, domain vocabulary, audit | unchanged |
| Provider budget | `budget.can_call_provider()` | unchanged |
| URL/host/robots/size policy | `retrieval.validate_url`, `RetrievalPolicy`, `robots_decision` | approved URLs only |
| Claim provenance | `web_evidence.validate_candidates` (passage must exist) | unchanged |
| Evidence origin | only experiments create `Evidence` | unchanged |
| Replication + falsification | `CriticEngine` | unchanged |
| State integrity | `state.verify()` | extended, not bypassed |

## Concurrency

**None today.** Two `python -m origin run --dir X` processes would both load,
mutate and save the same mission, and the last writer would win silently. This
is the single largest correctness gap for long-running operation and is why
v1.5 needs a mission lease.

## Honest gaps entering v1.5

1. No work queue — the controller decides the next action from live state each
   step, so a plan cannot be *inspected before it runs*.
2. No claim/complete record → interrupted actions are inferred, not known.
3. No single-writer protection.
4. No typed retry classification or backoff (only a global retry counter).
5. No per-run step/wall-clock limits.
6. Decisions are recorded (`state.decisions`) but are not tied to a durable
   queue item, so "why was this chosen over that" is partial.
