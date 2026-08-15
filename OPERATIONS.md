# ORIGIN v1.0 — Operations

## Commands
```bash
python -m origin init "QUESTION" --dir runs/m1 \
    [--domain algobench] [--profile fast|standard|flagship] \
    [--max-experiments N] [--compute-minutes M] [--max-minutes W] \
    [--provider-calls P] [--brain mock|anthropic|none]

python -m origin run     --dir runs/m1 [--steps N]   # run or resume
python -m origin status  --dir runs/m1               # mission-control box
python -m origin report  --dir runs/m1               # regenerate + print dossier
python -m origin timeline --dir runs/m1              # replayable event narrative
python -m origin html    --dir runs/m1               # static dashboard
python -m origin verify  --dir runs/m1               # durable-state consistency
python -m origin replay  --dir runs/m1 --exp exp_ID [--tolerance 0.5]
python -m origin ingest  --dir runs/m1 --file notes.md          # local document
python -m origin ingest  --dir runs/m1 --url https://example.org/notes \
        [--allow-host example.org] [--max-requests N] [--max-bytes N] \
        [--provider https|fixture] [--fixtures DIR] [--ignore-robots]
python -m origin cancel  --dir runs/m1               # terminal, with reason
```

## Profiles
| profile | sizes | trials | seed | extras |
|---|---|---|---|---|
| `fast` | 64, 128 | 2 | 1234 | smoke/demo (~10 s) |
| `standard` | 400, 1600 | 3 | 1234 | default |
| `flagship` | 256, 1024, 4096 | 3 | 20260809 | `sweep: true`, cutoffs 8/16/32/64 |

## Budgets and stopping
Five enforced dimensions: experiments, compute seconds, mission wall time,
provider calls, retries. The mission always ends with one of:
- `no high-value next experiment remained`
- `<dimension> budget exhausted (used/total)`
- `cancelled by user`
- `invalid mission spec: …` (FAILED)

`status` prints the stop reason; the dossier records the full budget ledger.

## Pause, resume, recover
- `--steps N` → PAUSED after N steps; `run` resumes from `paused_from`.
- Ctrl-C → PAUSED, checkpointed, resumable (exit code 130).
- Hard kill → the last per-step checkpoint is authoritative; `run` resumes.
- Corrupt `state.json` → automatic recovery from `state.json.bak` (flagged).
- Both corrupt → `CheckpointCorrupted`; `logs/` and `experiments/` still hold
  the full history for manual repair.

Run `python -m origin verify` after any recovery.

## Using an LLM proposal layer

```bash
--brain mock        # default: deterministic, offline, no credentials
--brain none        # proposals disabled entirely
--brain anthropic   # live provider; requires ANTHROPIC_API_KEY in the environment
```

```bash
export ANTHROPIC_API_KEY=...              # never passed as a CLI argument
export ORIGIN_BRAIN_MODEL=claude-sonnet-4-6   # optional
python -m origin init "…" --dir runs/m --brain anthropic --provider-calls 20
python -m origin run --dir runs/m
```

Without the variable, `--brain anthropic` fails immediately with an actionable
message naming `--brain mock`; it never falls back silently.

### What to read after a run

| File | Contents |
|---|---|
| `logs/proposals.jsonl` | every proposal offered — accepted and rejected — with its body, validation stage and reason |
| `logs/brain.jsonl` | one line per provider attempt: model, purpose, attempt, latency, request id, token usage, budget usage, failure class, redacted error. **No prompts or responses.** |
| `logs/brain_raw_audit.jsonl` | only when `ORIGIN_LLM_AUDIT_RAW=1`; redacted, truncated prompts and responses |
| `reports/dossier.md` | counterarguments appear as cautions, knowledge gaps as recommendations, both attributed to the provider and marked unverified |

### Failure classes and what they mean

`timeout`, `rate_limited`, `server_error`, `unavailable` and
`malformed_response` are retried with backoff. `auth_error` (401/403) and
`budget_exhausted` are **not** retried. A provider failure never aborts a
mission: it logs `brain_error`, records a caution, and the mission continues on
its own hypotheses.

### Bounded live verification

```bash
python tools/live_llm_check.py --dir runs/live_check --provider-calls 2
cat runs/live_check/logs/live_check_summary.json
```

One mission, fast profile, hard call budget, algorithms domain only. Prints
provider/model, call count, token usage, accepted and rejected proposals with
reasons, resulting experiments, and the final conclusion.

**Live status in the shipped build: UNVERIFIED** — no API key was available.
See `docs/verification/LLM_VERIFICATION_REPORT.md` §7.

## Web evidence acquisition

```bash
# offline, deterministic
python tools/web_evidence_demo.py --dir runs/evidence_demo --mode fixture
# bounded live retrieval from approved hosts
python tools/web_evidence_demo.py --dir runs/evidence_demo --mode live
```

Defaults: https only, public addresses only, 3 redirects (each re-validated),
10 s connect / 20 s read, 400 KB cap, allow-listed content types, 20 requests
per mission, 1 s per-host interval, robots.txt honoured.

| Signal | Meaning |
|---|---|
| `retrieval` event | a fetch succeeded; records status, type, bytes, hash, provider |
| `retrieval_refused` | policy rejected the request — scheme, address, host list, size, content type, redirects |
| `retrieval_failed` | transport failure (timeout, reset, malformed response); mission continues |
| `claim_rejected` | an extracted claim failed schema or passage-provenance validation |
| `claim_conflict` | two sources assert opposite directions; both remain SPECULATION |

Sources land in `research_state/sources.json` with full provenance and a cached
copy under `sources/`; claims keep their passage and offset. Nothing retrieved
becomes evidence — in the algorithms domain, evidence comes from experiments.

**Responsible use:** retrieve only what you are permitted to retrieve; ORIGIN
honours robots.txt but does not parse terms of service, and `license_note`
records that licensing was *not* verified. Do not ingest pages containing
credentials — the cached copy is kept verbatim because its hash is the
provenance.

## Bounded autonomy

```bash
python -m origin autonomy status --dir runs/m
python -m origin autonomy plan   --dir runs/m
python -m origin autonomy tick   --dir runs/m
python -m origin autonomy run    --dir runs/m --max-steps 10 --max-wall-s 300 \
    [--allow-network --max-retrievals 3] [--allow-provider --max-provider-calls 5]
python -m origin autonomy pause|resume|cancel --dir runs/m
python -m origin autonomy recover-lock --dir runs/m [--force]
```

Defaults: 10 steps, 300 s wall clock, 3 consecutive failures, 3 attempts per
item, 30 s backoff doubling to a 1 h cap, 2 idle ticks. Network and provider
access are **off** unless the flag is given for that run.

| Signal | Meaning |
|---|---|
| `autonomy status` → `INTERRUPTED` | an action was claimed and the process died; the outcome is unknown and needs your decision. ORIGIN will not re-run it |
| `autonomy status` → `retry backoff` | a retryable failure; the eligible time is shown |
| stop `retry_backoff_pending` | everything left is waiting out a backoff |
| stop `awaiting_operator_input` | queued work needs approval |
| stop `unsafe_or_invalid_state` | `state.verify()` found a problem; fix it before continuing |
| stop `consecutive_failure_limit_reached` | repeated failures; stopping beats retrying into a wall |
| `LEASE HELD` (exit 3) | another process holds the mission |

**Recovering a lease.** `recover-lock` without `--force` only *reports* the
holder, its pid/host and age. ORIGIN never steals a lease: a stale one and a
live one look identical from outside. Confirm no autonomy process is running,
then re-run with `--force`; the release is written to the mission event log and
the autonomy decision log.

## Health signals
- `heartbeat` events every step: phase, counts, budget snapshot.
- `stagnation` event if three consecutive investigation steps yield no new
  evidence (pending hypotheses are parked as WEAKENED with a caution).
- `experiment_rejected` — a design violated sandbox policy (nothing executed).
- `brain_error` — provider failure; the mission continues without proposals.
