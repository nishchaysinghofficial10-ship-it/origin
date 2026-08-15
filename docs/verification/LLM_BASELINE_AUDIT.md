# ORIGIN — LLM Layer Baseline Audit (before v1.3)

Method: direct inspection of `origin/brain.py` (272 lines), its call sites in
`controller.py`, `cli.py` and `evidence.py`, `tests/test_brain.py` (7 tests),
and every LLM claim in README / docs. Classifications follow the project's
audit vocabulary. Nothing below is taken from documentation alone.

## Environment fact
```
$ python3 -c "import os; print(bool(os.environ.get('ANTHROPIC_API_KEY')))"
False
```
No API key is present in this environment. Any statement about a real network
call to a provider is therefore **UNVERIFIED** and is labelled as such
throughout.

## Component inventory

| Component | State | Classification | Evidence |
|---|---|---|---|
| `Brain` ABC (`propose_hypotheses`, `extract_claims`) | Two methods only; research code depends on this, not on a vendor format | PARTIALLY_IMPLEMENTED | `brain.py:92` |
| `MockBrain` | Deterministic, context-grounded, offline; proposes two testable "beats" hypotheses | IMPLEMENTED_AND_VERIFIED | `test_brain.py::test_mock_proposals_flow_through_full_pipeline` |
| `NullBrain` | Returns nothing; used by `--brain none` | IMPLEMENTED_AND_VERIFIED | lifecycle/portability suites run with it |
| `AnthropicBrain` transport | stdlib `urllib`, env key only, 2 retries, fixed 60 s timeout, `_transport` test seam | IMPLEMENTED_BUT_UNVERIFIED (live) | `brain.py:184`; exercised only through a stub |
| HTTP error classification | All of `URLError`/`OSError`/`TimeoutError`/`JSONDecodeError` collapse into one retry path | **PARTIALLY_IMPLEMENTED** | no distinction between 429, 5xx, timeout, or DNS failure; a rate limit is retried the same as a malformed body |
| Retry/backoff | `time.sleep(min(2**attempt, 4))`, max 2 retries | IMPLEMENTED_AND_VERIFIED (stub) | `test_malformed_provider_output_raises_and_logs_redacted` |
| Provider-call budget | `can_call_provider` / `charge_provider_call` checked before each call | IMPLEMENTED_AND_VERIFIED | `test_provider_call_budget_enforced` |
| Credential handling | `os.environ["ANTHROPIC_API_KEY"]` only; never persisted; `BrainConfigError` if absent | IMPLEMENTED_AND_VERIFIED | `test_anthropic_requires_env_key` |
| Redaction | `redact()` over `sk-…` and `api_key=…`; applied to logged errors | IMPLEMENTED_AND_VERIFIED | `test_redaction_strips_key_material` |
| Provider metadata log | `logs/brain.jsonl`, metadata only (model, purpose, attempt, latency, sizes) | IMPLEMENTED_AND_VERIFIED | `cli.py:45` |
| Proposal schemas | Two: `HYPOTHESIS_PROPOSAL_SCHEMA`, `CLAIM_PROPOSAL_SCHEMA` | **PARTIALLY_IMPLEMENTED** | only statement/rationale/importance/prediction — no assumptions, no linked hypotheses, no cost, no limitations, no proposal identity |
| Proposal types | Hypotheses and document claims only | **MISSING** | no ExperimentProposal, CounterargumentProposal, or KnowledgeGapProposal |
| Domain/policy validation | `domain.build_check()` maps a proposal's prediction to a machine-checkable check; unknown algorithm/regime/kind raises | IMPLEMENTED_AND_VERIFIED | `test_malformed_and_out_of_vocabulary_proposals_rejected` |
| Rejection audit trail | `proposal_rejected` events in the mission event log, reason included | PARTIALLY_IMPLEMENTED | the **rejected proposal body is not preserved** — only the reason string |
| No LLM→fact path | Proposals become `PROPOSED` hypotheses tagged `llm_proposed`; nothing writes Claims/Evidence/graph | IMPLEMENTED_AND_VERIFIED | inspection of `controller._merge_brain_proposals` + `test_mock_proposals_flow_through_full_pipeline` |
| Prompt-injection handling | `extract_claims` wraps documents in `<untrusted_document>` with an ignore-instructions directive; ingested claims capped at SPECULATION/0.4 | IMPLEMENTED_AND_VERIFIED | `test_evidence_redteam.py` |
| Raw prompt/response storage | Never stored | IMPLEMENTED_AND_VERIFIED | only metadata reaches `brain.jsonl`; no audit opt-in exists either |

## Gaps this phase must close

1. **Proposal model is too thin to evaluate.** No `proposal_id`, assumptions,
   linked hypotheses, expected information gain, estimated cost, confidence, or
   limitations — so ORIGIN cannot reason about a proposal's cost/benefit, and a
   rejected proposal cannot be audited after the fact.
2. **Only one proposal type is usable.** Experiment designs, counterarguments
   and knowledge gaps are named in the specification but do not exist in code.
3. **Rejected content is discarded.** The reason survives; the proposal does
   not. That is the wrong half to keep for an audit trail.
4. **Error classification is flat.** Rate limits, server errors, timeouts and
   malformed bodies are indistinguishable in logs and in retry behaviour.
5. **No proposal-level audit log.** Accepted and rejected proposals should be
   append-only and inspectable independently of the mission event log.
6. **No adversarial-proposal tests.** Injection tests exist for *ingested
   documents*, not for *provider responses* that try to override policy,
   request secrets, or smuggle shell commands.
7. **Experiment proposals have no policy gate of their own.** Today an LLM
   cannot propose an experiment at all; when it can, that path must run through
   sandbox policy and domain vocabulary before anything is scheduled.

## Explicitly preserved

`tests/test_brain.py` (7 tests) is deterministic offline coverage of the mock
provider, redaction, budget enforcement and failure isolation. It is **kept
unchanged** as the regression floor for this phase.
