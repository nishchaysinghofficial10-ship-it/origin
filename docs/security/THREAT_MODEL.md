# ORIGIN v1.0 — Threat Model

## Assets
1. **Research integrity** — hypotheses, evidence, verdicts, confidence history.
   Corrupting these is the highest-value attack: it makes ORIGIN lie credibly.
2. **Durable state** — `state.json`, `logs/events.jsonl`, `experiments/`.
3. **Credentials** — `ANTHROPIC_API_KEY` in the operator's environment.
4. **Host resources** — CPU, memory, disk of the machine running missions.

## Trust boundaries
```
operator (trusted)
  → CLI / mission spec ....................... semi-trusted, validated
  → ORIGIN core (trusted code)
      → domain templates (audited, in-repo) ... trusted source of runner code
      → experiment subprocess ................. UNTRUSTED at runtime, confined
      → LLM provider responses ................ UNTRUSTED data, schema-gated
      → ingested documents .................... UNTRUSTED data, never executed
```

## Adversaries and attacks considered
| # | Adversary | Attack | Control |
|---|---|---|---|
| T1 | Malicious/compromised LLM provider | Emits code or instructions to execute | Provider output is never executed. It is parsed as JSON, schema-validated, then mapped through a fixed domain vocabulary (`build_check`); anything else is rejected and logged |
| T2 | Same | Emits confident false "facts" | No path from provider text to Evidence/FACT/graph. Proposals enter only as PROPOSED hypotheses that must survive experiments, replication, and falsification |
| T3 | Author of an ingested document | Prompt injection ("ignore previous instructions…") | Document content is wrapped in an explicit untrusted-data envelope, claims are capped at confidence 0.4 and SPECULATION status, and ORIGIN takes no action from document text. Tested: `test_evidence_redteam.py::test_ingested_content_is_untrusted_speculation_with_provenance` |
| T4 | Runaway/hostile experiment code | CPU/memory/disk/fork exhaustion (DoS) | rlimits (CPU, AS, FSIZE, NPROC, CORE=0), wall-clock timeout, `os.setsid`, output byte caps, per-design policy caps validated *before* spawn |
| T5 | Same | Reads operator secrets from env | Child env is constructed from scratch (PATH/HOME/TMPDIR/hash-seed/locale only); no inherited variables, no proxy vars, no API keys. Tested: `test_sandbox.py::test_child_env_is_scrubbed_of_secrets` |
| T6 | Local attacker with FS access | Corrupt/poison the checkpoint | Backup rotation + safe load + explicit `CheckpointCorrupted`; `origin verify` cross-checks references, on-disk artifacts, and duplicate events. ORIGIN does **not** cryptographically sign state — an attacker with write access to the project directory can still forge history (residual risk) |
| T7 | Anyone | Replay/duplicate events to inflate history | `verify()` detects duplicate `experiment_started` ids. Tested |
| T8 | Operator error | Impossible/contradictory mission spec | Validated at `VALIDATING`; mission enters FAILED with an explicit reason instead of running nonsense |
| T9 | Supply chain | Malicious dependency | Zero third-party runtime dependencies. Attack surface = CPython + OS |
| T10 | Log reader | Secret leakage via logs | `brain.jsonl` stores metadata only (model, purpose, latency, sizes, error class) and passes every string through `redact()`. Prompts/responses are not persisted |

| T11 | Operator or a mission spec | Request limits above policy (huge inputs, long timeouts) via `domain_config` | Two independent refusals: the cost estimator will not afford it, and `sandbox.validate_design()` rejects it pre-spawn | `test_domain_config_cannot_widen_sandbox_limits` |
| T12 | One mission | Mutate shared configuration and change another mission's limits | Config is deep-copied at creation (v1.7 fix) | `test_a_mission_config_does_not_leak_into_other_missions` |
| T13 | Anyone with file access | Tamper with a stored result or runner so a false finding survives review | Replay verifies correctness flags, input/output digests and the runner's own code digest; `verify` reports deleted artifacts | RT-48…RT-50 |
| T14 | ORIGIN itself | Publish a conclusion the stored state does not support | Report-vs-truth tests: accepted claims must exist in state with scope and a `replicated` tag; incorrect candidates cannot be called fastest; universalising phrases are banned | RT-45…RT-47 |

## Explicit non-goals (v1.0)
- Kernel-grade isolation (containers, seccomp, namespaces) — unavailable without
  privileges in the target environment.
- Network isolation of experiment subprocesses.
- Multi-tenant/hostile-operator use. ORIGIN assumes the operator is trusted.
- Signed/append-only tamper-evident storage.
