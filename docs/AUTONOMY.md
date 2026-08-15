# ORIGIN — Bounded Autonomy

ORIGIN can continue a research mission across many short sessions, restarts and
pauses. "Autonomous" here means *ORIGIN chooses which permitted action happens
next*. It does not mean unrestricted, self-modifying, or unsupervised.

---

## 1. What ORIGIN may decide on its own

Only these action types exist. There is no "run arbitrary code" action, and no
way to add one from data:

| Action | What it does | Gate it passes through |
|---|---|---|
| `plan_mission` | decompose the question, seed prior knowledge | validated lifecycle |
| `form_hypotheses` | generate hypotheses (+ validated LLM proposals) | proposal schema + domain vocabulary |
| `run_experiment` | one investigation step | `sandbox.validate_design()` then the confined runner |
| `criticise` | replication and falsification | `CriticEngine` rules |
| `retrieve_source` | fetch one **approved** URL | full retrieval policy (https, address, host, robots, size) |
| `review_conflict` | surface contradictions in the report | none needed; read-only |
| `generate_report` | regenerate dossier and timeline | none needed; read-only |
| `await_operator_approval` | block until a human approves | never auto-approved |

## 2. What always requires the operator

- **Live web retrieval** — `--allow-network`, plus an approved https URL. A
  retrieval work item is refused by the policy without it.
- **Live LLM calls** — `--allow-provider`. Without it, a mission configured
  with `--brain anthropic` runs the autonomy loop with the provider disabled;
  no key is read and no call is made.
- **Releasing a mission lease** — `autonomy recover-lock --force`.
- **Re-running an interrupted item** — ORIGIN marks it `interrupted` and stops
  there; it will not guess whether it completed.
- **Widening any limit.** Autonomy can only tighten, never expand.

## 3. Limits and defaults

Every autonomous run is finite. There is no unbounded default and no daemon.

| Limit | Default | Flag |
|---|---|---|
| steps per run | 10 | `--max-steps` |
| wall-clock per run | 300 s | `--max-wall-s` |
| retrievals per run | mission budget | `--max-retrievals` |
| provider calls per run | mission budget | `--max-provider-calls` |
| consecutive failures | 3 | `--max-consecutive-failures` |
| attempts per work item | 3 | (policy) |
| retry backoff | 30 s, doubling, capped at 1 h | (policy) |
| idle ticks before stopping | 2 | (policy) |

Mission-level budgets (experiments, compute seconds, wall time, provider calls,
retries) are unchanged and still authoritative.

## 4. Stop reasons

A run always ends with one of these, printed and stored:

```
completed                      paused_by_operator
budget_exhausted               time_limit_reached
step_limit_reached             awaiting_operator_input
no_permitted_work_remaining    retry_backoff_pending
unsafe_or_invalid_state        consecutive_failure_limit_reached
cancelled
```

## 5. Commands

```bash
python -m origin autonomy status  --dir runs/m     # queue, lease, budgets, next action
python -m origin autonomy plan    --dir runs/m     # candidates + why the next one wins
python -m origin autonomy tick    --dir runs/m     # at most ONE action
python -m origin autonomy run     --dir runs/m --max-steps 10 --max-wall-s 300
python -m origin autonomy pause   --dir runs/m     # durable, at the next checkpoint
python -m origin autonomy resume  --dir runs/m
python -m origin autonomy cancel  --dir runs/m     # terminal, durable
python -m origin autonomy recover-lock --dir runs/m [--force]

# external authority is opt-in, per run, and visible in the plan first
python -m origin autonomy run --dir runs/m --allow-network --max-retrievals 3
python -m origin autonomy run --dir runs/m --allow-provider --max-provider-calls 5
```

`plan` shows exactly what `tick` will do next, including a `<NETWORK>` or
`<PROVIDER>` marker on any action that reaches outside the machine — so you can
see an external action *before* it runs.

## 6. How a decision is made

The policy is deterministic. It orders permitted candidates by
`(-priority, cost, created_at, id)` and never uses model output as a reason.
Every evaluation writes an append-only record to `autonomy/decisions.jsonl`
containing the candidates, the chosen item, every rejected candidate **with its
reason**, the budget state, approval state, tie-break rule, policy version and
the next wake time. Nothing is chosen without that record existing first.

An item is not eligible if it is claimed, interrupted, awaiting approval, in
retry backoff, missing a dependency, over its attempt limit, requires
un-granted network/provider access, or cannot be afforded.

## 7. Locking

One mission, one writer. The lease is `autonomy/mission.lease`, acquired
atomically with `O_CREAT|O_EXCL`, carrying owner, pid, host and time.

**A stale lease is never stolen automatically.** From outside, a stale lease and
a live one are identical, and guessing wrong means two processes mutating one
mission. `autonomy recover-lock` shows the holder and its age; `--force`
releases it and writes an audit record to both the mission event log and the
autonomy decision log.

## 8. Retries

Failures are typed. Retryable: transport timeouts, provider outages, rate
limits, transient retrieval errors. **Never retried:** policy violations, schema
failures, unsafe experiment designs, disallowed URLs, robots refusals, operator
cancellation, invalid mission state, configuration errors — retrying a refusal
just refuses again. Unknown failure classes are not retried by default.

Backoff is deterministic (30 s × 2^(attempt−1), capped at 1 h) with no jitter,
so `plan` can tell you the exact wake time. A deferred item is invisible to the
policy until then, which is what prevents a hot loop.

## 9. Recovery after a crash

Autonomy checkpoints the **claim** before executing, so an interrupted action is
detectable rather than invisible. On the next tick:

- a `claimed` item becomes `interrupted`, with "completion is UNKNOWN" recorded;
- it is **not** re-run and **not** assumed successful;
- the operator inspects it via `autonomy status` and decides.

This is deliberate: for an experiment that may already have spawned, an
automatic re-run would double-charge the budget and could duplicate research
history.

## 10. What is guaranteed, and what is not

**Guaranteed:** durable work items and decision records; a bounded, finite run;
single-writer protection; no duplicate execution of a *completed* item
(idempotency keys); safety gates unchanged; live web and LLM opt-in per run;
truthful stop reasons; `origin verify` covers autonomy state.

**Not guaranteed:** exactly-once execution of an *external* action — if a
process dies mid-action, ORIGIN records the ambiguity rather than claiming a
guarantee it cannot provide. Also not implemented: multi-agent coordination,
distributed execution, a background daemon, crawling or source discovery,
general scientific discovery, or legal compliance with any site's terms.
