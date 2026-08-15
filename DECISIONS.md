# ORIGIN — Engineering Decision Log

Format: decision · alternatives · evidence · tradeoffs · migration impact · date.
Pre-implementation decisions AD-1…AD-8 are recorded in
`docs/audit/DAY2_ARCHITECTURAL_DECISIONS.md`; this log continues them with what
implementation actually taught us.

## AD-9 — Lifecycle as a table over `meta["phase"]`, not a new object
2026-08-09. **Alternatives**: a `Mission` aggregate object; an enum column in a
DB. **Evidence**: v0.1 already checkpointed `meta` atomically and every
subsystem read `meta["phase"]`. **Tradeoff**: phases remain strings (weaker
typing) in exchange for a one-line migration path. **Migration**: `MIGRATION`
maps the five v0.1 names; old projects (incl. `examples/demo_run`) load and are
flagged `migrated_from` without mutating the archived project on read.

## AD-10 — Loading must never write
2026-08-09. The first migration implementation appended a `migrated` event on
load, which mutated archived missions merely by inspecting them. Changed to set
a flag persisted on the next `save()`. **Evidence**: `test_lifecycle.py::
test_v01_phase_names_migrate_on_load` loads the read-only v0.1 demo.

## AD-11 — Invalid budgets fail the mission instead of "completing" it
2026-08-09. v0.1 treated `experiments_total=0` as a mission that finished with
no research. That is a false success. Now `VALIDATING` rejects it → `FAILED`
with a reason. **Migration**: the legacy test was split into two explicit
cases (exhaustion → COMPLETED with reason; invalid spec → FAILED).

## AD-12 — Falsification probes must be able to fail honestly
2026-08-09. **Finding (RT-24)**: probing a hypothesis whose prediction types the
benchmark evaluator cannot judge produced "inconclusive" verdicts that were
then rendered as a confident "does NOT extend to …" scope. **Decision**:
non-probeable prediction types produce *no probe*; the attempt is recorded as
`inconclusive`, a caution is written, and the hypothesis is **not** promoted to
ACCEPTED_WITH_SCOPE. Scope strings now distinguish extends / does-not-extend /
untested. **Evidence**: flagship `hyp_abfa5d6b64` stays provisionally supported.

## AD-13 — Falsification does not write to the knowledge graph
2026-08-09. Probes run at 2× size on unseen regimes; feeding their winners into
the size-agnostic `fastest_on` relation would manufacture contradictions that
are really scale effects. Probes therefore update hypothesis scope/status only.
**Tradeoff**: the graph under-represents scale dependence; recorded as a threat
to validity in every dossier (§19) and as future work.

## AD-14 — `python -I` for experiment subprocesses
2026-08-09. Isolated mode ignores `PYTHON*` env vars and user site-packages, so
a poisoned environment cannot alter a runner. Determinism is unaffected because
runners seed `random.Random(seed)` explicitly rather than relying on hash seed.

## AD-15 — Internal schema validator instead of a dependency
2026-08-09. `origin/schema.py` (~50 lines) covers type/required/enum/bounds/
items/additionalProperties — everything the proposal schemas need.
**Tradeoff**: no `$ref`, no format validation. **Benefit**: the zero-dependency
guarantee survives, which is what makes `unzip && python -m unittest` work.

## AD-16 — Static HTML dashboard, no server
2026-08-09. `origin html` renders `reports/mission_control.html` from stored
state. **Alternatives**: Flask/FastAPI + live polling — rejected as speculative
infrastructure under the 90–100 h constraint. **Consequence**: the dashboard
cannot show a running mission live; `status` covers that need.

## AD-17 — Per-row `correct` field in results
2026-08-09. Replay compares correctness exactly and timings within tolerance.
That required correctness to be explicit per measurement rather than implied by
"the runner exited 0". Older v0.1 results lack the field; replay of pre-v1.0
experiments compares timings only.

---

# Reliability & portability engagement (v1.1, 2026-08-09)

## AD-18 — Artifact references are root-relative, resolved through the project root
**Alternatives**: keep absolute paths and "fix" copies with a repair command;
store both. **Evidence**: a copied mission with its `experiments/` directory
deleted still reported "State verified … consistent" because it was reading the
*original* machine's files (verification report §3). **Decision**: `dir` stores
`experiments/<id>`; `ExperimentRecord.path(root)` resolves it. **Migration**:
absolute values are normalized on load (`flags["migrated_paths"]`), foreign
paths fall back to the canonical layout rather than being followed;
`tools/normalize_paths.py` rewrites stored projects. Schema bumped 2 → 3.

## AD-19 — `replay` asserts host-independent invariants; timing is reported
**Evidence**: on a 1-vCPU host the same experiment replayed FAIL/PASS/PASS/
FAIL/PASS purely from scheduler contention (deviations to 385% on 6 ms cells).
**Decision**: the verdict rests on cell coverage and per-cell correctness, which
are seed-driven and host-independent. Timing deviations and ranking inversions
are printed every run and promoted to failures only under `--strict`.
**Tradeoff**: replay no longer certifies performance equivalence by default —
stated explicitly in the output line and in the docs, rather than asserted and
silently unreliable. **Alternative rejected**: widening the tolerance until
failures stopped, which would have kept the claim while removing its meaning.

## AD-20 — A checkpoint candidate is accepted only if it *reconstructs*
Parsing was not enough: a syntactically valid `{}` raised `KeyError` and a
missing primary with an intact backup raised `FileNotFoundError`. `load()` now
tries `state.json` then `state.json.bak`, accepting the first that fully
reconstructs, and `save()` writes+fsyncs the new snapshot *before* rotating the
old one. **Migration impact**: none for readers; recovery is now silent and
flagged rather than fatal.

## AD-21 — Orphaned experiment artifacts are reconciled, never resurrected
A hard kill can leave a complete `result.json` on disk that the ledger never
recorded. **Decision**: `verify()` reports it; the next `run` adopts it as an
`interrupted` record with a failure entry, and the controller re-plans the
experiment normally. **Rejected**: adopting the stored result as `completed` —
nothing analysed it, so promoting it would fabricate history. **Consequence**:
the compute it consumed is acknowledged but not retroactively charged, because
the duration was never recorded.

## AD-22 — Support is claimed only where the suite was executed
`pyproject` previously declared `>=3.10` on the strength of a single 3.12 run.
The matrix (3.10/3.11/3.12/3.13/3.14 on Linux x86-64) was actually executed and
is now the classifier list; macOS is documented as untested and Windows as
unsupported with an explicit runtime guard. No CI badge is displayed because no
runner has executed the workflow.

## AD-23 — Timing is reported, correctness is asserted
2026-08-10. **Alternatives**: keep wall-clock equality as a replay gate (v1.0);
drop timing from replay entirely. **Evidence**: replaying one flagship
experiment five times on this single-core host gave 2 failures and 3 passes
under timing equality, while inputs, outputs and correctness were identical
every time. **Decision**: replay asserts exact reproducibility (cells,
correctness, input digest, output digest, code digest) always, and asserts
timing/ordering only under `--strict` on a matching environment.
**Tradeoff**: a genuine performance regression on a quiet host is a warning by
default. That is the right default for CI and shared machines, and `--strict`
exists for controlled hardware.

## AD-24 — Conservative separation instead of a significance test
2026-08-10. **Alternatives**: Welch's t-test with a p-value; bootstrap CIs;
raw margins (the v1.1 behaviour). **Decision**: require ≥5 trials per side,
separation > 3×(SEM_a + SEM_b) — summed, not in quadrature — and a ≥10 %
relative margin. **Rationale**: benchmark samples on a contended host are not
independent draws from a clean normal; a p-value would imply precision the data
lacks. **Tradeoff**: deliberately biased toward type II errors. Real but small
effects will be reported as inconclusive.

## AD-25 — Digests make correctness independently checkable
2026-08-10. The runner previously asserted `out == sorted(data)` and recorded a
boolean. A replay could not check that claim. Now each cell records a digest of
its generated input and of its sorted output, and the runner hashes its own
source. **Migration**: schema v1 results have no digests; they still replay and
the report names the unavailable checks rather than passing them silently.

## AD-26 — Report tie sets, not argmin
2026-08-10. Parameter sweeps reported the fastest setting as "the optimum".
With 4 cutoffs within a few hundred microseconds that is an artifact of the
random seed. Sweeps now report the optimum plus every setting statistically
indistinguishable from it, and a sweep prediction whose interval cannot be
resolved returns inconclusive. **Impact**: the flagship cutoff hypothesis moved
from confirmed to inconclusive — a correction, not a regression.

## AD-27 — Trial counts raised to make significance arithmetically possible
2026-08-10. fast 2→5, standard 3→7, flagship 3→7. Below 5 trials the standard
error is not a measurement, and every comparison would be `insufficient_trials`.
Cost: the flagship mission went from ~80 s to 219 s of compute on one core.

## AD-28 — Retrieval refuses loudly, transport fails quietly
2026-08-10. A policy violation (bad scheme, private address, denied host,
oversized body) raises with its reason: it is an operator error and silence
would hide a misconfiguration. A transport failure (timeout, reset, malformed
response) is contained, logged and returned: it is weather, and a mission must
survive it. **Evidence**: the first version caught both alike, so a provider
raising a bare `TimeoutError` escaped containment entirely — found by
`test_timeout_and_malformed_response_do_not_corrupt_state`.

## AD-29 — Every resolved address is checked, not just the first
2026-08-10. `getaddrinfo` can return a public and a private address for the
same name. Checking one invites DNS rebinding, so all are checked and any
non-public answer refuses the whole request. Redirects get the same treatment:
each hop is a fresh validation rather than a followed `Location`.

## AD-30 — A claim must cite text that exists
2026-08-10. Extraction is only auditable if the passage can be found again.
Claims carry the passage and its offset, and validation rejects any claim whose
passage is not present in the retrieved document. ORIGIN does not repair
provenance to rescue a plausible claim. **Alternative rejected**: fuzzy
matching, which would manufacture provenance.

## AD-31 — Reliability is a stored explanation, not a number
2026-08-10. `reliability_basis` records each rule that fired and its
contribution; the score is derived from them and ceilinged at 0.6. A retrieved
source can never look as solid as ORIGIN's own measurement, however well hosted.

## AD-32 — Conflict detection favours precision over reach
2026-08-10. The first implementation matched arbitrary noun phrases and
"detected" a conflict between "our" and "than". Rebuilt over a known subject
vocabulary: it fires only when two known subjects appear with opposite
direction words. A false "sources disagree" is itself misinformation, and
absence of a flag is documented as not being evidence of agreement.

## AD-33 — One request path, or the policy is a suggestion
2026-08-10. **Defect**: `robots.txt` was fetched with a default `urlopen`,
giving it automatic redirects, no `validate_url()` on any hop, and its own read
cap — so the file that decides whether ORIGIN may fetch a document was itself
retrieved outside the rules ORIGIN applies to documents. **Fix**: a single
`_request()` used for both. A second, looser way to reach the network is a
policy bypass by construction, not a rough edge.

## AD-34 — Robots outcomes are recorded, not assumed
2026-08-10. The old code turned any robots failure into "no rules == allowed"
while the source record still read "robots policy honoured". Now every source
stores one of `fetched_and_honoured` / `absent` / `unavailable` /
`disallowed_by_policy` / `disabled_by_configuration`. The permissive default on
absence is unchanged — what changed is that ORIGIN stops claiming it obeyed
rules it never read. `require_robots=True` refuses instead.

## AD-35 — Bound the decompressor, not just the result
2026-08-10. The byte cap was applied to the compressed body and re-checked
after `gzip.decompress()` — so an oversized body was rejected, but only after
it had been fully expanded in memory. A ~49 KB payload expands to 50 MB. Fixed
with a chunked `zlib.decompressobj` carrying an output limit; malformed
compressed data now raises instead of being silently treated as text.

## AD-36 — Pin the address, and record whether pinning happened
2026-08-10. Validating DNS and then letting `urlopen` resolve again leaves a
rebinding race. ORIGIN now connects to a validated address while keeping SNI
and certificate checks on the hostname. Pinning can fail (interpreter
internals, proxied environments); rather than claiming protection it cannot
guarantee, ORIGIN falls back and stores `pinned_address` — empty means the race
was not closed for that fetch.

## AD-35 — "Absent" is a claim about the site, not about our request
2026-08-11. v1.4.1 caught every `RetrievalError` during robots retrieval and
recorded `absent`, so a timeout wrote a durable claim that a site publishes no
rules. **Decision**: `absent` is reserved for HTTP 404; every other failure —
timeout, DNS/TLS, 5xx, non-404 status, policy refusal, oversized, malformed
compressed body, undecodable content — is `unavailable`. `_request()` now
raises a typed `HttpStatusError` carrying the status so the caller can tell
them apart. **Tradeoff**: more handlers instead of one catch-all, which is the
point — the brief's own instruction was not to hide the distinction.

## AD-36 — Robots bytes are decoded strictly
2026-08-11. Decoding with `errors="replace"` turned undecodable bytes into
mojibake that was then parsed as if it were rules. Strict decoding raises, and
the outcome is `unavailable`. A document ORIGIN cannot read is not a document
whose rules it can honour.

## AD-37 — Reported numbers come from executed commands only
2026-08-11. The v1.4.1 report claimed "22 new tests" while the file held 27,
and quoted both 161 and 186 as suite totals. Every count in the v1.4.2 report
is the output of a command run at the shipping commit, with the interpreter and
platform named; the superseded figures are labelled historical rather than
quietly rewritten.

## AD-38 — Autonomy chooses; it never executes
2026-08-11. The scheduler dispatches to `ResearchController`,
`ExperimentEngine` and `web_evidence`, so every existing gate stays
authoritative and there is exactly one code path per capability.
**Alternative rejected**: a self-contained executor inside the autonomy layer,
which would have duplicated the sandbox and retrieval policies and given them
somewhere to drift apart.

## AD-39 — A claim is checkpointed before the action runs
2026-08-11. Otherwise a crash mid-action is invisible and the only recovery is
inference. With a claim record, an interrupted item is *known* — and is then
marked `interrupted` rather than re-run, because re-running an experiment that
may already have spawned would double-charge the budget and could duplicate
research history. **Tradeoff**: a human must resolve it. That is the honest
cost of not guessing.

## AD-40 — A stale lease is never stolen automatically
2026-08-11. From outside, a stale lease and a live one are identical: pid
reuse, a paused debugger and a hung NFS mount all look the same. Automatic
stealing would trade a visible inconvenience for silent concurrent mutation.
Release is `recover-lock --force`, audited in two logs.

## AD-41 — Unknown failure classes are not retried
2026-08-11. Retryable and non-retryable are both explicit lists; anything
unrecognised defaults to *not* retried. Retrying an unclassified failure risks
repeating a side effect ORIGIN does not understand, and a safety refusal
retried is just a refusal repeated.

## AD-42 — Deterministic backoff, no jitter
2026-08-11. `plan` can then state the exact wake time and tests can assert
`[10.0, 20.0]` instead of a range. **Tradeoff**: many missions started together
would retry in lockstep — documented as a residual risk rather than papered
over with randomness that would make the schedule uninspectable.
