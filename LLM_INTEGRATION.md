# ORIGIN — LLM Integration

ORIGIN can use a language model as a **proposal generator**. It never uses one
as an authority. This document is what a new developer needs to run the mock
provider safely, and what an operator needs to run a bounded live mission.

---

## 1. The one rule

```text
LLM response  →  accepted fact  →  conclusion        ← IMPOSSIBLE BY CONSTRUCTION
```

There is no code path from a provider response to a `Claim` marked FACT, to an
`Evidence` item, or to a knowledge-graph relation. A provider response can only
become:

| Proposal type | What it becomes | What it never is |
|---|---|---|
| `hypothesis` | a `PROPOSED` hypothesis tagged `llm_proposed` | evidence, or a confirmed result |
| `experiment` | a *candidate design*; ORIGIN sets seed, timeout, round and scope, and the sandbox policy gate still applies | an execution instruction |
| `counterargument` | a caution attached to the named hypothesis | a confidence change |
| `knowledge_gap` | a recommendation in the dossier | a finding |

An admitted hypothesis has **no privilege**: it faces the same experiments,
critic, replication and falsification as one ORIGIN generated itself, and it
can be rejected by its own evidence (this happens in the shipped flagship
mission — see §7).

---

## 2. Configuration

```bash
# offline, deterministic, no credentials — the default
python -m origin init "…" --dir runs/m --brain mock

# no proposals at all
python -m origin init "…" --dir runs/m --brain none

# live provider
export ANTHROPIC_API_KEY=...            # environment only, never an argument
export ORIGIN_BRAIN_MODEL=claude-sonnet-4-6      # optional
python -m origin init "…" --dir runs/m --brain anthropic --provider-calls 20
python -m origin run  --dir runs/m
```

| Variable | Purpose | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | provider credential | read at construction; never stored, logged, or printed |
| `ORIGIN_BRAIN_MODEL` | model name | defaults to `claude-sonnet-4-6` |
| `ORIGIN_LLM_AUDIT_RAW` | set to `1` to store raw prompts/responses | **off by default**; output is redacted; see §6 |

Without a key, `--brain anthropic` fails immediately with an actionable message
naming `--brain mock`. It does not fall back silently.

---

## 3. Provider abstraction

```text
                     ┌───────────────────────────────┐
research engine ──►  │ Brain (stable interface)      │
                     │   propose_research(context)   │
                     │   extract_claims(text, title) │
                     └───────────────────────────────┘
                         ▲            ▲            ▲
                    MockBrain    NullBrain    AnthropicBrain
                  (deterministic) (disabled)   (urllib, env key)
```

The engine depends on `Brain` and on `origin/proposals.py`, never on a vendor
SDK or a raw response shape. Adding a provider means implementing two methods;
no research logic changes. Transport is stdlib `urllib` — the zero-dependency
guarantee is worth more here than an SDK's convenience.

A provider that only speaks the legacy `{statement, rationale, prediction}`
format is upgraded to the structured schema before validation, so both paths
meet exactly the same gate.

---

## 4. Proposal schemas

Every proposal is a JSON object with `proposal_type` ∈ {`hypothesis`,
`experiment`, `counterargument`, `knowledge_gap`} and:

| Field | Required for | Bounds |
|---|---|---|
| `statement` | all | 15–400 chars |
| `rationale` | all | 10–800 chars |
| `predicted_measurement` | hypothesis | `{kind, params}` — must map to the domain's check vocabulary |
| `suggested_experiment` | experiment | `{algorithms, regimes, sizes, trials}` — all validated against the domain roster and sandbox policy |
| `linked_hypotheses` | counterargument | must name hypotheses that exist |
| `assumptions` | optional | ≤6 items, ≤200 chars each |
| `expected_information_gain` | optional | 0.0–1.0 → drives ORIGIN's prioritisation |
| `estimated_cost` | optional | 0.0–10.0 |
| `confidence` | optional | **0.0–0.9** — a proposal may never claim certainty |
| `limitations` | optional | ≤400 chars |

`proposal_id` is derived by ORIGIN from a hash of the content; a provider
cannot choose its own identity. Unknown fields are **rejected**, not ignored —
a model that emits `auto_accept: true` must be visible in the audit log, not
silently dropped.

---

## 5. Validation pipeline

```text
provider text
  → parse            strict JSON; a ```json fence is tolerated, nothing else.
                     Malformed JSON is never "repaired": a repaired proposal is
                     a proposal ORIGIN wrote.
  → schema           type, bounds, required fields, no unknown fields
  → domain/policy    predicted_measurement must map through domain.build_check();
                     suggested_experiment must use known algorithms and regimes
                     and pass sandbox.validate_design(); counterarguments must
                     link real hypotheses
  → audit            logs/proposals.jsonl — accepted AND rejected, with the
                     proposal body and the reason, append-only
  → ORIGIN decides   admitted objects enter the normal pipeline
```

At most 8 proposals are read from any single response; the remainder are
discarded with an audited `cap` rejection.

---

## 6. What is logged

`logs/brain.jsonl` — one line per provider attempt, **metadata only**:
timestamp, provider, model, purpose, attempt number, request/response sizes,
latency, request id, token usage, budget usage, failure class, redacted error.
Prompt and response bodies are not written here.

`logs/proposals.jsonl` — every proposal ORIGIN was offered, accepted or
rejected, with its body, its validation stage and the reason. This is the file
to read when asking "what did the model want, and why did ORIGIN refuse?".
Bodies pass through the secret redactor before being written.

`ORIGIN_LLM_AUDIT_RAW=1` additionally writes `logs/brain_raw_audit.jsonl` with
the system prompt, user content and response text (redacted, truncated). It is
off by default because prompts carry mission content and responses are already
summarised into the proposal audit.

---

## 7. Failure handling

Errors are classified, not lumped together:

| Class | Retried? | Raised as |
|---|---|---|
| `timeout` | yes, with backoff | `ProviderTimeout` |
| `rate_limited` (HTTP 429) | yes, with backoff | `ProviderRateLimited` |
| `server_error` (5xx), `unavailable` (DNS/connection) | yes | `ProviderUnavailable` |
| `malformed_response` | yes | `BrainError` / `BrainProposalError` |
| `auth_error` (401/403) | **no** — retrying a bad credential is pointless | `ProviderUnavailable` |
| `budget_exhausted` | **no** | `ProviderBudgetExhausted` |

A provider failure never aborts a mission: it is logged as `brain_error`, a
caution is recorded, and the mission continues with its own hypotheses. Mission
state stays consistent (`verify()` clean) — tested.

---

## 8. Untrusted content

Documents ingested as evidence are wrapped in an `<untrusted_document>`
envelope with an explicit instruction to ignore anything inside them, truncated,
and their extracted claims are capped at `SPECULATION` status and confidence
0.4. More importantly, injection cannot achieve anything structural: no path
exists from document text or provider text to a fact, an experiment parameter,
a shell command, a file read, or a policy change.

Adversarial proposals that attempt to override policy, disable validation,
request secret disclosure, smuggle shell commands, assert unsupported facts, or
force acceptance are all rejected and audited
(`tests/test_llm_integration.py::TestAdversarialProposals`).

---

## 9. Running a bounded live mission

```bash
export ANTHROPIC_API_KEY=...
python tools/live_llm_check.py --dir runs/live_check --provider-calls 2
```

One mission, fast profile, hard provider-call budget, algorithms domain only.
It prints and stores `logs/live_check_summary.json` with the provider and model,
call count, token usage, accepted and rejected proposals with reasons, the
resulting experiments, and the final conclusion.

**Status in this environment: UNVERIFIED.** No API key was available, so the
socket write to `api.anthropic.com` has never been executed. Everything on
either side of it — request construction, retry/backoff, error classification,
budget charging, parsing, schema and policy validation, audit logging, and the
full research pipeline — is exercised through a stubbed transport, including an
end-to-end run of this exact tool (see
`docs/verification/LLM_VERIFICATION_REPORT.md` §7).

---

## 10. What ORIGIN does not trust from a model

- Any statement of fact, however confident.
- Its own claimed confidence (capped at 0.9, and used only for prioritisation).
- Algorithm names, regime names, metric names, or check kinds outside the
  domain vocabulary.
- Experiment parameters: seed, timeout, round and scope are always ORIGIN's.
- Its identity: `proposal_id` is content-derived.
- Any instruction, in a response or in an ingested document.
- Any request for credentials, files, network access, or shell execution.
