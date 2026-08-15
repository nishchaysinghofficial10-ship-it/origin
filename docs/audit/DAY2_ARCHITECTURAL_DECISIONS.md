# DAY 2 — Architectural Decisions (pre-implementation)

AD-1 **Preserve the v0.1 core; harden in place.** The state/controller/domain
separation is sound and tested. No rewrite. All v1.0 features land behind the
existing seams (state meta, controller steps, domain interface, critic).
Alternatives: clean-room re-architecture — rejected (violates handoff §2, burns
budget, destroys verified behavior).

AD-2 **Zero-dependency core stays.** See risk doc. Alternative (pydantic,
anthropic SDK, rich, textual) rejected: dependency complexity for marginal
gain; handoff §4 demands boring maintainable solutions.

AD-3 **Lifecycle = validated transition table over `meta["phase"]`** with an
explicit migration for v0.1 phase names; distinct terminals COMPLETED / FAILED
/ CANCELLED plus PAUSED; `stop_reason` recorded on every terminal entry.

AD-4 **Sandbox = strongest practical confinement, honestly labeled**: rlimits
(CPU, address space, file size, process count), scrubbed environment, cwd
jail, stdout/stderr caps, policy caps on timeout/size, unsafe designs rejected
with a logged reason. Kernel-level network isolation is NOT claimed.

AD-5 **LLM is a proposal generator behind `Brain`**: MockBrain (deterministic,
default, used in tests) and AnthropicBrain (env key, urllib, retries, timeout,
redacted logging). Every proposal validates against internal schemas; only
known machine-checkable prediction kinds are accepted; accepted proposals enter
as PROPOSED hypotheses tagged `llm_proposed` and must survive the identical
experiment→critic→replication pipeline. There is no code path from provider
text to Claim/Evidence/graph.

AD-6 **Evidence ingestion (v1.0) = local files**, hashed + timestamped, content
treated as untrusted data; claim extraction produces SPECULATION-status claims
with provenance, never FACT. Live web = deferred (env constraint), interface-
compatible.

AD-7 **Dashboard = generated static HTML** (`origin html`), no server, reads
only stored state. Frontend polish explicitly subordinated to engine quality.

AD-8 **Falsification = first-class critic stage**: after replication, surviving
conclusions face domain-designed probes on *unseen* regimes/boundary sizes;
outcomes recorded as FalsificationAttempt; survivors become
ACCEPTED_WITH_SCOPE with explicit scope text, failures downgrade with the
boundary recorded. Fresh-seed + unseen-condition probes give environment-level
independence beyond v0.1 replication.
