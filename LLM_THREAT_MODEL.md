# ORIGIN — LLM Threat Model

Scope: the proposal layer added in v1.3. General system threats are in
`THREAT_MODEL.md`; executed attacks are in `../red_team/RED_TEAM_REPORT.md` and
`../verification/LLM_VERIFICATION_REPORT.md`.

## Trust boundary

```text
operator (trusted)
  → mission spec, --brain choice, env credentials .......... semi-trusted, validated
  → ORIGIN core (trusted code)
      → provider request ................................ constructed by ORIGIN
      → provider RESPONSE .............................. UNTRUSTED DATA
      → proposal schema + domain policy ................ the gate
      → admitted proposals ............................. ordinary research objects
```

The provider response is treated exactly like a document scraped off the
internet: data to be parsed, never instructions to be followed.

## Adversaries and attacks

| # | Adversary | Attack | Control | Evidence |
|---|---|---|---|---|
| L1 | Compromised or jailbroken model | Emits an instruction ("ignore previous instructions", "mark as accepted fact") | Responses are parsed as JSON and validated; no field can set status, confidence above 0.9, or acceptance. Prose is never interpreted | `TestAdversarialProposals::test_every_attack_is_rejected_and_audited` |
| L2 | Same | Emits a confident false claim | Admitted only as a `PROPOSED` hypothesis; resolved by experiment, replication and falsification. Rejection by evidence is a normal outcome | `test_a_proposal_can_be_rejected_by_evidence` |
| L3 | Same | Smuggles executable content (shell command, code) into an experiment field | Experiment fields are validated against the domain roster; runners are generated from in-repo templates only, never from provider text | `test_injection_text_never_reaches_executable_code` |
| L4 | Same | Requests secret disclosure ("print ANTHROPIC_API_KEY") | Rejected at schema/policy; ORIGIN has no mechanism to read env vars on a proposal's behalf; the key is never in any serialisable structure | `ATTACKS[2]`, `test_missing_key_fails_clearly_without_leaking` |
| L5 | Same | Proposes an unsafe experiment (huge sizes, long timeout) to exhaust the host | `sandbox.validate_design()` — the same gate ORIGIN's own designs face — runs *before* the proposal is accepted, and again before any process spawns | `test_unsafe_experiment_parameters_are_rejected` |
| L6 | Same | Adds an unknown field (`auto_accept`, `skip_validation`) hoping it is ignored | `additionalProperties: false`; unknown fields are a rejection, recorded in the audit log | `test_unknown_field_is_rejected_rather_than_ignored` |
| L7 | Same | Floods ORIGIN with proposals to exhaust budget or attention | Hard cap of 8 proposals per response, audited; provider-call budget enforced per call | `test_proposal_cap_is_enforced`, `test_provider_budget_is_enforced_and_not_retried` |
| L8 | Network attacker / hostile endpoint | Returns a malformed or enormous body | Strict parse, no repair; retries bounded; failures classified and raised as typed errors | `test_malformed_json_is_rejected_without_repair`, `test_timeout_is_retried_then_classified` |
| L9 | Same | Rate-limits or drops the connection mid-mission | Classified (`rate_limited`, `unavailable`), bounded retries with backoff, then the mission continues without proposals; state stays consistent | `test_provider_outage_does_not_corrupt_mission_state` |
| L10 | Log reader | Harvests credentials from logs | Metadata-only logging; every logged string passes `redact()`; raw audit is opt-in and also redacted | `test_metadata_log_is_redacted_and_carries_no_prompt`, `test_raw_audit_when_explicitly_enabled_is_redacted` |
| L11 | Author of an ingested document | Prompt injection reaching the model through evidence text | Documents are wrapped as untrusted data with an ignore-instructions directive; extracted claims capped at SPECULATION/0.4; nothing structural is reachable | `test_evidence_redteam.py::test_ingested_content_is_untrusted_speculation_with_provenance` |
| L12 | Operator error | Runs live with an unbounded budget | `--provider-calls` is required to be finite in the live-check tool and defaults to 20 in the CLI; every call is charged before the response is used | `budget.can_call_provider()` |

## Residual risks

1. **A plausible-but-wrong hypothesis costs experiments.** Validation checks
   that a proposal is *well-formed and testable*, not that it is *worth
   testing*. A model can waste budget on uninteresting but valid claims;
   `expected_information_gain` only influences priority, and the model supplies
   it.
2. **The live network path is unverified** — no API key existed in this
   environment. The response-handling code around it is fully tested with a
   stubbed transport.
3. **Prompt content is not filtered for sensitive mission text.** Mission
   questions and domain vocabulary are sent to the provider. Do not put secrets
   in a mission question.
4. **No provider-side guarantees.** ORIGIN cannot verify what a provider logs,
   retains, or trains on. Treat every prompt as disclosed to the vendor.
5. **Redaction is pattern-based** (`sk-…`, `api_key=…`). A credential in an
   unusual format could slip into a log. Keys should never appear in mission
   text in the first place.
6. **Counterarguments are unverified prose.** They are recorded as cautions
   attributed to the provider and marked unverified; they never change
   confidence.
