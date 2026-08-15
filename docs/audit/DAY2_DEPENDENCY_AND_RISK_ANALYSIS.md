# DAY 2 — Dependency & Risk Analysis

## Dependency posture
Baseline has **zero third-party dependencies** (Python 3.10+ stdlib). Decision:
keep it that way for v1.0 core. Consequences:
- Anthropic provider implemented over `urllib.request` (stdlib), env-key only.
- JSON schema validation via a small internal validator (`origin/schema.py`)
  instead of pydantic/jsonschema. Narrower, but fully tested and auditable.
- Supply-chain risk ≈ interpreter + OS only. `pip install` not required to run.

## Environment constraints (this build environment)
- Network egress is allow-listed to package registries + api.anthropic.com.
  **General web acquisition is not feasible here** → Phase 2 live-web is
  DEFERRED with the local-ingestion pipeline built as its landing zone.
- `ANTHROPIC_API_KEY` is not present → AnthropicBrain code path is tested for
  construction, redaction, timeout/malformed handling via a stubbed HTTP layer;
  a live call is honestly classified IMPLEMENTED_BUT_UNVERIFIED (live).
- No root / user namespaces → network isolation for experiment subprocesses
  cannot be kernel-enforced. Mitigations: rlimits, scrubbed env (no proxy
  vars, no secrets), deterministic audited runner templates only (no LLM- or
  web-derived code is ever executed in v1.0). Residual risk documented in
  SECURITY_REVIEW.

## Top technical risks
1. **State migration** (loose phases → validated lifecycle) breaking old
   projects → mitigated by a migration map + test loading the v0.1 demo.
2. **rlimit side effects** (RLIMIT_AS interacting with CPython arenas) →
   generous defaults, policy-configurable, failure recorded not fatal.
3. **Flagship runtime blow-up** (sweep × regimes × sizes) → cost estimator +
   compute budget enforced before execution; sizes capped.
4. **Interruption test flakiness** (timing) → interrupt deterministically via
   step-limited runs + SIGKILL of a subprocess at a controlled point.
5. **Scope creep** vs. the 90–100h spirit → daemon, live web, second domain,
   graph viz explicitly deferred with integration plans in ROADMAP.
