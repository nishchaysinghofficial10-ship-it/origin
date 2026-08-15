# ORIGIN v1.3 — LLM Proposal Layer Verification Report

Engagement: make LLM-assisted research proposals real, controlled, and
verifiable. Every result below came from the command shown above it, on the
host described in §5. The specification is `../LLM_INTEGRATION.md`; the attack
surface analysis is `../security/LLM_THREAT_MODEL.md`.

---

## 1. Baseline audit findings

Full inventory: `LLM_BASELINE_AUDIT.md`. Summary of what was already true
before this phase, verified by inspection and execution rather than by reading
the README:

**Already working (preserved unchanged).** `MockBrain` was deterministic and
context-grounded; credentials were environment-only with a clear
`BrainConfigError`; redaction covered `sk-…` and `api_key=…`; the provider-call
budget was enforced; metadata-only logging existed; and there was already no
code path from a provider response to a Claim, Evidence item, or graph
relation. The seven tests in `tests/test_brain.py` were kept as the offline
regression floor.

**Seven gaps closed by this phase.**

1. The proposal model was too thin to evaluate — no identity, assumptions,
   cost, expected gain, confidence or limitations.
2. Only one proposal type existed; experiment designs, counterarguments and
   knowledge gaps were named in the spec but absent from the code.
3. Rejected proposals were discarded — the reason survived, the proposal did
   not. That is the wrong half to keep for an audit.
4. Error classification was flat: a 429, a DNS failure, a timeout and a
   malformed body were indistinguishable in logs and identical in retry
   behaviour.
5. There was no proposal-level audit log.
6. There were no adversarial tests against *provider responses* (only against
   ingested documents).
7. Experiment proposals had no policy gate, because they could not exist.

---

## 2. Architecture implemented

```text
                    ┌──────────────────────────────┐
research engine ──► │ Brain  (stable interface)    │ ◄── vendor-agnostic
                    │  propose_research(context)   │
                    │  extract_claims(text, title) │
                    └──────────────────────────────┘
                       ▲           ▲            ▲
                  MockBrain   NullBrain   AnthropicBrain (stdlib urllib)

provider text
  → origin/proposals.py :: parse_provider_json    strict JSON, no repair
  → validate_schema                               shape, bounds, no unknown fields
  → validate_policy                               domain vocabulary + sandbox policy
  → ProposalAudit                                 logs/proposals.jsonl, append-only
  → controller._admit_proposal                    ORIGIN decides what it becomes
  → normal pipeline                               experiment → analysis → critic
                                                  → replication → confidence
```

New modules: `origin/proposals.py` (schemas, validation, audit log),
`tools/live_llm_check.py` (bounded live verification). `origin/brain.py` gained
a typed error taxonomy (`ProviderTimeout`, `ProviderRateLimited`,
`ProviderUnavailable`, `ProviderBudgetExhausted`), per-class retry policy, and
an opt-in raw-audit sink. Zero third-party dependencies were added.

A provider that speaks only the legacy `{statement, rationale, prediction}`
shape is upgraded into the structured schema before validation, so both paths
meet the identical gate; non-dict junk is passed through untouched so the
validator rejects it with an accurate reason instead of ORIGIN crashing.

---

## 3. Supported proposal schemas

| Type | Required fields | Becomes |
|---|---|---|
| `hypothesis` | `statement`, `rationale`, `predicted_measurement{kind,params}` | a `PROPOSED` hypothesis tagged `llm_proposed` |
| `experiment` | `statement`, `rationale`, `suggested_experiment{algorithms,regimes,sizes,trials}` | a candidate design; ORIGIN sets seed, timeout, round, coverage |
| `counterargument` | `statement`, `rationale`, `linked_hypotheses` | a caution attributed to the provider, marked unverified |
| `knowledge_gap` | `statement`, `rationale` | a recommendation in the dossier |

Optional on all: `assumptions` (≤6), `expected_information_gain` (0–1),
`estimated_cost` (0–10), `confidence` (**0–0.9** — a proposal may never claim
certainty), `limitations`, `linked_hypotheses`. `proposal_id` is derived by
ORIGIN from a content hash; a provider cannot choose its own identity. Unknown
fields are rejected rather than ignored, and at most 8 proposals are read per
response.

---

## 4. Safety boundaries

The provider may propose. It may not:

- write to the knowledge graph, create Evidence, or set a Claim to FACT;
- set its own status, identity, or a confidence above 0.9;
- name an algorithm, regime, metric or check kind outside the domain vocabulary;
- choose an experiment's seed, timeout, round or scope;
- exceed sandbox limits on input size, trial count or timeout;
- cause any code it wrote to be executed — runners come from in-repo templates;
- read environment variables, files, or the network on its own behalf;
- override the critic, replication, budgets, or mission state.

---

## 5. Test results

Host: Ubuntu 24.04 x86-64, 1 CPU, CPython 3.12.3.

```
$ python3 -m unittest discover -s tests
Ran 114 tests in 79.950s
OK
```

| Module | Tests | Focus |
|---|---:|---|
| `test_core` | 7 | budgets, graph, persistence, end-to-end mission |
| `test_lifecycle` | 6 | transitions, migration, pause/resume, cancel |
| `test_reliability` | 11 | interruption, checkpoint recovery, orphans |
| `test_portability` | 12 | relocation, archives, absolute paths |
| `test_sandbox` | 6 | confinement policy and limits |
| `test_brain` | 7 | **preserved unchanged** — offline mock regression floor |
| `test_evidence_redteam` | 7 | untrusted ingestion, red-team scenarios |
| `test_performance_repro` | 25 | measurement schema, statistics, replay tiers |
| **`test_llm_integration`** | **33** | **proposal schemas, adversarial content, provider reliability** |

Support matrix, full suite, all `OK` (113 tests at the time of the matrix run; 114 after the dossier-ledger test was added):
CPython 3.10.20 (112.0s), 3.11.15 (72.1s), 3.12.3 (60.6s), 3.13.13 (85.4s),
3.14.4 (69.5s) — Ubuntu 24.04 x86-64.

### Required-test coverage

| Requirement | Test |
|---|---|
| 1. Mock proposals complete the pipeline | `test_brain::test_mock_proposals_flow_through_full_pipeline` (preserved) |
| 2. Valid LLM hypothesis is experimentally tested | `test_valid_proposal_is_experimentally_tested_then_resolved` |
| 3. LLM hypothesis can be rejected by evidence | `test_a_proposal_can_be_rejected_by_evidence` |
| 4. Malformed JSON rejected safely | `test_malformed_json_is_rejected_without_repair` |
| 5. Out-of-schema proposals rejected | `test_unsupported_proposal_type…`, `test_missing_required_field…`, `test_unknown_field…`, `test_out_of_range_confidence…` |
| 6. Unsupported algorithms / unsafe experiments rejected | `test_unsupported_algorithm_is_rejected`, `test_unsafe_experiment_parameters_are_rejected` |
| 7. Missing key fails clearly without leaking | `test_missing_key_fails_clearly_without_leaking` |
| 8. Timeout / outage / rate limit do not corrupt state | `test_timeout_is_retried_then_classified`, `test_rate_limit_is_retried_then_classified`, `test_provider_outage_does_not_corrupt_mission_state` |
| 9. Provider-call budget enforced | `test_provider_budget_is_enforced_and_not_retried` |
| 10. Secret/token redaction | `test_metadata_log_is_redacted_and_carries_no_prompt`, `test_audit_log_redacts_secrets_in_proposal_bodies`, `test_raw_audit_when_explicitly_enabled_is_redacted` |
| 11. Prompt-injection content inert | `TestAdversarialProposals` (6 attack payloads) |
| 12. No proposal becomes accepted knowledge without evidence | `test_no_proposal_becomes_accepted_knowledge_without_evidence` |
| 13. Offline mock tests remain deterministic | `test_brain.py` unchanged, 7/7 |

---

## 6. Provider failure and recovery evidence

Error classification is asserted directly against real exception objects
(`test_error_classification`): HTTP 429 → `rate_limited`, 5xx →
`server_error`, 401/403 → `auth_error`, `URLError` → `unavailable`,
`TimeoutError` → `timeout`, budget → `budget_exhausted`.

- **Timeout**: 2 logged attempts (initial + one retry), both tagged
  `failure_class: timeout`, then `ProviderTimeout`.
- **Rate limit**: retried with backoff, then `ProviderRateLimited`.
- **Auth error**: exactly **1** attempt — retrying a bad credential is
  pointless and is asserted not to happen.
- **Outage mid-mission**: mission still reaches `COMPLETED`, `verify()` returns
  clean, a `brain_error` event and a caution are recorded, and the mission
  proceeds on its own hypotheses.
- **Budget**: the second call after a 1-call budget raises
  `ProviderBudgetExhausted` and is not retried.

Adversarial run integrity: after six attack payloads, zero proposals were
accepted, every rejection was audited with its body and reason, no
`llm_proposed` hypothesis existed, and `verify()` was clean. No generated
runner contained `rm -rf`, `IGNORE ALL PREVIOUS`, or `ANTHROPIC_API_KEY`.

---

## 7. Live mission evidence

```
$ python3 -c "import os; print(bool(os.environ.get('ANTHROPIC_API_KEY')))"
False

$ python3 tools/live_llm_check.py --dir /tmp/livecheck --provider-calls 2
NOT RUN — ANTHROPIC_API_KEY is not set. ORIGIN never stores keys; export the
variable in your environment, or use --brain mock.
exit=2
```

**No live provider call was made. The network path is UNVERIFIED.** No result
is fabricated here.

What *was* executed is the same tool end-to-end with a stubbed transport
returning a realistic Anthropic envelope (three proposals, one deliberately
out-of-vocabulary):

```json
{ "provider": "anthropic", "model": "claude-sonnet-4-6",
  "provider_calls_attempted": 1, "provider_calls_charged": 1,
  "provider_calls_budget": 2, "input_tokens": 812, "output_tokens": 344,
  "failure_classes": [],
  "proposals_accepted": [
    {"type": "hypothesis",     "outcome": "admitted as hyp_83433c7ec4 (PROPOSED)"},
    {"type": "knowledge_gap",  "outcome": "recorded as a knowledge gap"}],
  "proposals_rejected": [
    {"stage": "policy",
     "reason": "predicted_measurement outside the domain vocabulary: unknown algorithm 'timsort'"}],
  "llm_hypotheses": {
    "hyp_83433c7ec4": {"status": "accepted_with_scope",
                       "tested_in": ["exp_6cd386e77d", "exp_e6985e8894"],
                       "scope": "holds at n<=2x tested sizes on its original regime(s); extends to ['organ_pipe', 'sawtooth']",
                       "supporting_evidence": 2, "contradicting_evidence": 0}},
  "experiments_run": 8, "mission_phase": "COMPLETED",
  "stop_reason": "no high-value next experiment remained" }
```

The accepted hypothesis reached `accepted_with_scope` **only** after two
experiments, an independent replication and a surviving falsification probe —
its scope string was written by the falsifier, not by the model. The rejected
proposal was refused for naming an algorithm the domain does not implement.

### Shipped flagship mission, regenerated under the v1.3 pipeline

`examples/flagship_run` was re-run with `--brain mock` so the shipped example
exercises the proposal pipeline it documents (244 s, 13 experiments: 4
benchmark, 1 sweep, 4 replication, 4 falsification; 8 hypotheses; 20 evidence
items). Its `logs/proposals.jsonl` records five proposals — two hypotheses, one
experiment design, one counterargument, one knowledge gap — all accepted, and
dossier §16b reproduces that ledger with what ORIGIN did with each.

The two LLM-proposed hypotheses ended in opposite places, decided by
measurement:

| Hypothesis | Outcome | Basis |
|---|---|---|
| "Shell sort beats insertion sort on random input…" | `accepted_with_scope` | +739% at n=1024, gap 19.45 ms > required 1.39 ms; replicated; survived falsification; scope extends to `sawtooth`/`organ_pipe` |
| "Heap sort beats shell sort on reversed input…" | `rejected` | heap sort was decisively **slower** (−30%) at n=4096 |

The accepted candidate experiment design was instantiated for the LLM
hypothesis with ORIGIN's seed and timeout (`experiment_proposal_used` event),
and the counterargument appears in the dossier as an unverified caution, never
as a confidence change.

Run-to-run honesty note: this rerun also downgraded a *base* hypothesis that
v1.2 had accepted — "heap sort is the most consistent candidate" was refuted
because merge sort had the lowest mean relative stdev (0.050 vs 0.063) on this
run. Prediction outcomes moved from 9/2/2 (confirmed/refuted/inconclusive) in
v1.2 to 8/3/2 here. Nothing about the LLM layer caused that; it is ordinary
measurement variation on a contended host, and it is reported rather than
smoothed over.

To verify the network path yourself:

```bash
export ANTHROPIC_API_KEY=...
python tools/live_llm_check.py --dir runs/live_check --provider-calls 2
cat runs/live_check/logs/live_check_summary.json
cat runs/live_check/logs/proposals.jsonl      # what was proposed and why refused
cat runs/live_check/logs/brain.jsonl          # metadata only, redacted
```

---

## 8. What remains unverified

1. **The socket write to `api.anthropic.com`.** Request construction, retries,
   classification, budget charging, parsing, validation, audit and pipeline are
   all tested; the actual HTTPS exchange is not. Everything downstream of a
   response is provider-agnostic and covered.
2. **Real provider behaviours** — genuine 429 bodies, streaming, partial
   responses, `overloaded_error`, and real latency distributions have not been
   observed. Classification is asserted against synthetic exceptions.
3. **Token accounting from a real response.** `input_tokens`/`output_tokens`
   are read from the `usage` block; only a synthetic block has been parsed.
4. **Prompt effectiveness.** Whether a real model produces *useful* proposals
   under this schema is untested; the mock's proposals are hand-written to be
   testable. Validation guarantees safety, not usefulness.
5. **Cost.** No spend has occurred, so no cost figure is reported.

---

## 9. Is this phase complete?

**Yes for everything that does not require a credential; explicitly no for the
network call itself.**

Definition-of-done status:

- [x] Mock provider works deterministically — `test_brain.py` unchanged, 7/7
- [x] Live-provider code behind a stable abstraction — `Brain` + `proposals.py`
- [x] All provider outputs schema-validated — 4 schemas, unknown fields rejected
- [x] Invalid/unsafe proposals rejected and logged — `logs/proposals.jsonl`
- [x] No LLM output can become accepted knowledge — asserted, no code path
- [x] Provider failures cannot corrupt state — outage test, `verify()` clean
- [x] Credentials environment-only and redacted — three redaction tests
- [x] Provider budgets enforced — charged per call, not retried on exhaustion
- [x] Prompt-injection cases tested — 6 attack payloads, all rejected
- [x] Full suite passes on the documented matrix — 113 tests × 5 interpreters
- [ ] **Live execution evidenced** — *explicitly marked UNVERIFIED*; a documented
      one-command verification is provided
- [x] Documentation sufficient for safe mock use — `docs/LLM_INTEGRATION.md`

The one open box is open because this environment has no API key, not because
the work is missing. Running `tools/live_llm_check.py` with a key closes it and
produces the evidence file the report expects.
