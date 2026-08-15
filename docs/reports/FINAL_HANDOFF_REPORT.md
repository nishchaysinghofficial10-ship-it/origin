# ORIGIN v1.0 — Final Handoff Report

Engagement: take the audited v0.1 prototype to a demonstrable v1.0.
Rule applied throughout: **no capability is called complete without a test,
a runnable command, or stored execution evidence.**

---

## 1. Repository baseline and audit summary

The v0.1 repository was inspected and executed *before* any change, and the
baseline was committed to git (`9062b1a`).

- Test suite as found: **6/6 passing in 0.35 s**.
- Shipped demo (`examples/demo_run`) as found: COMPLETE — 5 hypotheses,
  6 experiments, 17 evidence items, 2 real contradictions, 1 rejected
  hypothesis, 3 replicated findings.
- 2,012 LOC, zero third-party dependencies.

Honest classifications from `docs/audit/DAY1_IMPLEMENTATION_INVENTORY.md`:

| Verdict | Components |
|---|---|
| IMPLEMENTED_AND_VERIFIED | persistent state, hypotheses, predictions, experiment versioning, result analysis, replication, knowledge graph + contradictions, decision ledger, failure records, reports, deterministic experiments |
| PARTIALLY_IMPLEMENTED | controller state machine (loose strings, no validation), budgets (2 of 7 dimensions), critic (no falsification), **"sandbox" (subprocess + timeout only — an overclaim)** |
| IMPLEMENTED_BUT_UNVERIFIED | checkpoint/resume mid-run (never tested) |
| MISSING / PLANNED_ONLY | LLM layer, evidence ingestion, live web, hardened recovery, dashboard, daemon, second domain |

The single most important audit finding: **the word "sandbox" was not earned.**
That drove Phase 5 of the build.

---

## 2. Preserved / hardened / built / deferred

**Preserved unchanged** (sound, tested, no reason to touch): knowledge graph,
decision scoring heuristic, experiment versioning layout, dossier/timeline
generation, deterministic runner templates, domain plugin contract.

**Hardened**: state persistence (schema version, `.bak` rotation, safe load,
`verify()`); controller (validated lifecycle, heartbeat, stagnation guard,
retry budget); budgets (5 enforced dimensions + stop reasons); critic
(falsification stage, scoped acceptance); experiments (policy gate + rlimits +
scrubbed env + output caps); reports (4 new sections + HTML).

**Built new**: `lifecycle.py`, `schema.py`, `sandbox.py`, `brain.py`,
`evidence.py`; CLI commands `replay`, `verify`, `ingest`, `html`, `cancel`;
5 new test modules; algobench extensions (shell sort, two unseen probe regimes,
parameterised hybrid factory, cutoff sweep, falsification designs, LLM proposal
vocabulary).

**Deferred, with reasons** (see §9): live web acquisition, daemon/scheduler,
second domain, kernel-grade sandbox, API server, graph visualisation.

---

## 3. v1.0 capabilities, linked to evidence

| Capability | Where | Evidence |
|---|---|---|
| Validated mission lifecycle, legal transitions only | `origin/lifecycle.py` | `test_lifecycle.py` (6 tests) incl. illegal-transition rejection, terminal finality, v0.1 migration |
| Pause / resume / cancel with recorded reasons | controller + CLI | `test_steps_flag_pauses_then_resumes_to_completion`, `test_cancel_command` |
| Interrupt (SIGKILL) → resume without loss or duplication | state + controller | `test_reliability.py::test_sigkill_midrun_then_resume_without_loss_or_duplication` |
| Corrupt-checkpoint recovery + safe failure | `origin/state.py` | 2 tests (backup recovery; both-corrupt raises) |
| Experiment replay from recorded metadata within tolerance | `origin replay` | test + live run: `exp_f53e0d9748`, 16 cells, PASS |
| State consistency verification | `state.verify()` / `origin verify` | flagship: "State verified"; duplicate-event detection test |
| Budgets (experiments, compute, wall time, provider calls, retries) + stop reasons | `origin/budget.py` | 3 tests; flagship stop reason recorded |
| Sandbox policy: reject-before-spawn, rlimits, scrubbed env, output caps | `origin/sandbox.py`, `experiments.py` | `test_sandbox.py` (6 tests) incl. memory-bomb kill and env scrub |
| LLM proposal layer with schema + vocabulary validation, retries, redaction, budget | `origin/brain.py` | `test_brain.py` (7 tests) |
| No LLM→fact path | brain/controller design | `test_mock_proposals_flow_through_full_pipeline` asserts proposals resolve only via experiments |
| Untrusted evidence ingestion with provenance and dedupe | `origin/evidence.py` | 2 tests + live ingest into flagship (injection payload inert) |
| Falsification as a workflow stage | critic + domain | flagship: 5 attempts (4 survived, 1 honestly inconclusive) |
| Independent replication | critic + domain | flagship: 4 replication experiments |
| Scoped acceptance (`ACCEPTED_WITH_SCOPE`) | models/critic/report | flagship: 4 hypotheses with explicit scope strings |
| Confidence history (append-only) | `state.record_confidence_change` | flagship: 13 recorded changes |
| Mission control (CLI + static HTML) | `report.py` | `examples/flagship_run/reports/mission_control.html` |
| Research dossier with prediction ledger, falsification, budget ledger, threats to validity | `report.py` | `examples/flagship_run/reports/dossier.md` §16–19 |

---

## 4. Commands executed and results

```
python -m unittest discover -s tests -v         → 37 tests, OK (~22 s)
python -m origin init … --profile flagship      → project created
python -m origin run --dir examples/flagship_run→ COMPLETED, step 20,
                                                   13 experiments, 80.3 s compute
python -m origin verify --dir examples/flagship_run
                                                → "State verified: …consistent."
python -m origin replay --dir … --exp exp_f53e0d9748
                                                → REPLAY PASS (16 cells, ±50 %)
python -m origin ingest --dir … --file /tmp/sorting_notes.md
                                                → 3 SPECULATION claims, sha256 recorded
python -m origin html --dir …                   → reports/mission_control.html
python -m origin status/report/timeline --dir … → consistent with stored state
```

---

## 5. Test-suite summary

**37 tests, all passing, ~22 s, no skips, no third-party dependencies.**

| Module | Tests | Covers |
|---|---:|---|
| `test_core.py` | 7 | budgets, graph roundtrip + contradictions, state persistence, full deterministic mission, budget exhaustion, invalid-spec failure |
| `test_lifecycle.py` | 6 | illegal transitions, terminal finality + stop reasons, pause/resume, `--steps`, v0.1 migration, cancel |
| `test_reliability.py` | 4 | SIGKILL mid-run + resume, backup recovery, both-corrupt failure, replay tolerance |
| `test_sandbox.py` | 6 | design policy, reject-without-execution, memory-limit kill, output truncation, env scrubbing, crash isolation |
| `test_brain.py` | 7 | mock proposals end-to-end, malformed/out-of-vocabulary rejection, missing key, malformed provider output + redaction, provider budget, provider outage |
| `test_evidence_redteam.py` | 7 | untrusted ingestion + injection inertness, dedupe, malformed specs, wall-time stop, timeout handling, duplicate events, report-vs-truth |

Regression tests added for bugs fixed during the engagement: runner-template
corruption (caught by replay/correctness assertions), invalid-budget false
success, dishonest falsification scope.

---

## 6. Flagship mission — summary and reproduction

Question: *Under what input distributions and sizes does a hybrid
merge/insertion sorting strategy outperform predefined baselines without
violating correctness, and what insertion cutoff is optimal per regime?*

Configuration: profile `flagship` (sizes 256/1024/4096, 3 trials, seed
20260809, cutoffs 8/16/32/64), budget 100 experiments / 40 min compute,
brain `mock`.

Executed: **13 experiments** — 3 benchmark rounds, 2 cutoff sweeps, 4 independent
replications (seed +1000), 4 falsification probes (n = 8192 on original regimes
plus the unseen `sawtooth` and `organ_pipe` regimes). 8 hypotheses, 22 evidence
items, 13 decisions, 148 events, 80.3 s compute, 5 assumptions, 6 recommended
follow-ups. Stop reason: *no high-value next experiment remained* (13/100
experiments used — it stopped because it ran out of valuable work, not budget).

Reproduce: the exact `init`/`run` pair in §4 (also in README and
`docs/REPRODUCIBILITY.md`). Reference run ships in `examples/flagship_run/`.

---

## 7. Findings — including negative ones

**Accepted with scope** (confirmed → independently replicated → survived
falsification probes):
1. Insertion sort is fastest on nearly-sorted input and slowest on random input.
   *Scope: holds to n ≤ 8192 on its own regimes; **does not extend** to
   `sawtooth` or `organ_pipe`.*
2. Quick sort (median-of-three) stays within 25 % of the best candidate on
   random input and does not collapse on reversed input.
   *Scope: also holds on both unseen regimes.*
3. Shell sort beats insertion sort on random input but not on nearly-sorted
   input — an **LLM-proposed** hypothesis that earned its place experimentally
   (+3206 % margin at n = 8192).
4. The ORIGIN-synthesized hybrid (merge sort with an insertion cutoff) beats
   plain merge sort on random and nearly-sorted input (+43 % on random at
   n = 8192), and extends to both unseen regimes.

**Negative / corrective results (the system's own predictions failing):**
- *Rejected*: "Merge sort is the fastest pure-Python candidate on random input"
  — quick sort won by 77 % at n = 4096.
- *Rejected*: the LLM proposal "Heap sort beats shell sort on reversed input"
  — heap sort was 33 % slower. The LLM layer received no protection from
  refutation.
- *Weakened*: "Heap sort is the most consistent candidate" — merge sort had the
  lowest mean relative stdev (0.027).

**Measured parameter result** (`EXPERIMENTAL_RESULT` claim, confidence 0.6):
hybrid insertion-cutoff optima at n = 4096 — random **16**, nearly_sorted **64**,
reversed **8**, few_unique **16**.

**Honestly inconclusive**: the pre-registered cutoff hypothesis
(`hyp_abfa5d6b64`) was confirmed and independently replicated, but its
prediction types cannot be evaluated at boundary/unseen conditions, so no
falsification probe was possible. It remains *provisionally supported* with a
recorded caution — deliberately **not** promoted.

**Zero contradictions** arose in this flagship run. That is reported as-is; the
contradiction machinery is exercised by unit test and by the archived v0.1 demo
(2 real cross-seed conflicts).

---

## 8. Security and red-team summary

- `docs/security/THREAT_MODEL.md` — 10 adversary/attack rows with controls.
- `docs/security/SECURITY_REVIEW.md` — 8 control areas, each tied to an executed
  test; residual risks enumerated.
- `docs/red_team/RED_TEAM_REPORT.md` — **26 executed scenarios** (RT-1…RT-26).

Three material findings were found and fixed: dishonest falsification scope
(high — an honesty defect), invalid-budget false success (medium), and a
generated-runner template corruption (high, caught by replay assertions).

Disclosed residual risks: no network/filesystem namespacing for experiment
subprocesses; state is not tamper-evident; `RLIMIT_NPROC` may be un-lowerable;
the live Anthropic call path is unverified in this environment.

---

## 9. Known limitations and honest next steps

1. **Live web acquisition — deferred.** The build environment allows egress only
   to package registries, so a fetcher could not be built *and verified*.
   `evidence.py` is its landing zone: a URL fetcher would produce the same
   `Source` + passage inputs. Next: fetcher + robots/rate policy + reliability
   scoring, reusing the untrusted-content rules already in place.
2. **Live LLM call — unverified.** No API key existed here. Everything except
   the socket write is tested via `_transport`. Next: run one mission with
   `--brain anthropic` and record the `logs/brain.jsonl` metadata.
3. **Confinement is user-space.** Next: optional container/nsjail executor
   behind the same `sandbox` policy interface.
4. **No daemon.** Long runs are driven by `run`/`--steps`/resume. Next: a thin
   scheduler loop reusing the existing checkpoint semantics.
5. **Single domain.** The plugin contract now carries proposal/falsification
   hooks; a second domain is a well-defined next unit of work.
6. **Size-agnostic knowledge graph** (AD-13) — conditioned relations are future
   work; today scale effects appear as contradictions or scope strings.
7. **Timing-based science.** Rankings only, single machine, noise-discounted
   evidence, tolerance-based replay.

---

## 10. Requirements matrix

| # | Requested capability | Status | Evidence |
|---|---|---|---|
| 1 | Audit before building | **Verified complete** | 7 docs in `docs/audit/`, baseline commit `9062b1a` |
| 2 | Preserve existing functionality | **Verified complete** | v0.1 demo still loads and reports; documented migrations only |
| 3 | Explicit, validated, durable mission state | **Verified complete** | `test_lifecycle.py`, `test_core.py` |
| 4 | Inspectable events/decisions | **Verified complete** | 148 flagship events, 13 decisions, `timeline.md` |
| 5 | Checkpoint/restart tested | **Verified complete** | `test_reliability.py` (SIGKILL + 2 corruption cases) |
| 6 | Pause/resume | **Verified complete** | `--steps` + resume test; Ctrl-C path in CLI |
| 7 | Budgets enforced and visible | **Verified complete** | 5 dimensions; status box, dossier §18 |
| 8 | Failures recorded without corruption | **Verified complete** | crash/timeout tests + `verify()` clean afterwards |
| 9 | Competing hypotheses | **Verified complete** | flagship: 8 hypotheses, 4 outcomes |
| 10 | Hypotheses ↔ evidence/predictions/experiments | **Verified complete** | ledgers in dossier §7; `verify()` checks references |
| 11 | Machine-checkable predictions | **Verified complete** | 8 check types; prediction ledger §16 |
| 12 | Versioned, reproducible experiments | **Verified complete** | `spec.json`+`run.py`+`result.json`; `replay` PASS |
| 13 | Results update state through recorded logic | **Verified complete** | `confidence_history` (13 entries), `revisions` per hypothesis |
| 14 | Criticism + falsification as real stages | **Verified complete** | FALSIFYING stage, 5 attempts, scope outcomes |
| 15 | Independent replication | **Verified complete** | 4 replication experiments, seed +1000, separate processes |
| 16 | Contradictions/inconclusive stay visible | **Verified complete** | graph contradictions + §13 cautions + inconclusive falsification |
| 17 | LLM structured/validated outputs | **Verified complete** (mock + stubbed transport) | `test_brain.py` |
| 18 | LLM never accepted as evidence | **Verified complete** | no code path; asserted in tests |
| 19 | Untrusted code/content handled safely | **Verified complete** (user-space) | `test_sandbox.py`, injection ingest |
| 20 | Secret handling + provider failures tested | **Verified complete** | redaction, missing key, malformed output, budget |
| 21 | Security review + red-team report | **Verified complete** | `docs/security/`, `docs/red_team/` |
| 22 | Full suite passes | **Verified complete** | 37/37 |
| 23 | End-to-end deterministic mission | **Verified complete** | `test_core.py::test_full_run` + `examples/demo_run` |
| 24 | Flagship bounded autonomous mission + dossier | **Verified complete** | `examples/flagship_run/` |
| 25 | Replay a selected experiment | **Verified complete** | `exp_f53e0d9748` PASS |
| 26 | Interruption/restart test | **Verified complete** | SIGKILL test |
| 27 | Claims match stored artifacts | **Verified complete** | `test_report_claims_match_stored_truth` |
| 28 | Documentation sufficient for a new developer | **Verified complete** | README + 6 docs + audit/security/red-team sets |
| 29 | Live evidence acquisition from the web | **Deferred** | env egress restricted; ingestion pipeline built as landing zone |
| 30 | Live provider call executed | **Partially complete** | code paths tested via stub; no key available |
| 31 | Continuous multi-day daemon | **Deferred** | manual `run`/`--steps`/resume works |
| 32 | Second research domain | **Deferred** | contract ready |
| 33 | Kernel-grade sandbox isolation | **Not feasible in this environment** | no privileges; strongest practical confinement built and documented |
| 34 | Web dashboard/server | **Partially complete** | static HTML mission control; no live server (AD-16) |

---

## Definition-of-done checklist

Core system — audited before changes ✅ · functionality preserved ✅ · state
explicit/validated/durable ✅ · events inspectable ✅ · checkpoint/restart tested
✅ · pause/resume ✅ · budgets enforced ✅ · failures non-corrupting ✅

Research workflow — competing hypotheses ✅ · linked evidence/predictions ✅ ·
machine-checkable predictions ✅ · versioned reproducible experiments ✅ ·
recorded update logic ✅ · criticism + falsification ✅ · independent replication
✅ · contradictions/inconclusive visible ✅

Intelligence & safety — validated structured LLM output ✅ · no LLM→evidence path
✅ · untrusted code/content handled ✅ (user-space limits documented) · secret
handling + provider failures tested ✅ · security review + red team ✅

Demonstration — full suite passes ✅ (37/37) · e2e deterministic mission ✅ ·
flagship mission run ✅ · dossier ✅ · experiment replay ✅ · interruption test ✅ ·
claims match artifacts ✅

Documentation — install/test/run/reproduce/inspect/resume from docs alone ✅ ·
architecture, limits, safety boundaries, gaps documented ✅ · nothing labelled
complete without evidence ✅


---

## Addendum — reliability & portability engagement (v1.1)

After this report was written, a dedicated reliability/portability pass audited
the delivered artifacts. It found and fixed **seven defects**, three of them
affecting claims made above:

- **P-1 (critical)**: experiment artifacts were referenced by absolute path, so
  a copied or unpacked mission read the *original* machine's directories.
  `verify` returned a false PASS on a mission with no artifacts of its own, and
  the published `origin-v1.0.zip` embedded 51 machine-specific paths. The
  "experiment replay" and "state verification" evidence in §3/§4 above was
  therefore only valid *in place* on the build host.
- **P-2**: the replay verdict asserted wall-clock timing and flaked on shared
  hardware (FAIL/PASS/PASS/FAIL/PASS for one experiment).
- **R-1…R-5**: checkpoint recovery gaps (missing primary with valid backup,
  structurally invalid snapshot, torn event-log line, orphaned experiment
  artifacts, library-API resume of a PAUSED mission).

All are fixed, regression-tested (56 tests, up from 37) and documented in
`docs/verification/RELIABILITY_AND_PORTABILITY_REPORT.md`. The support matrix
claimed above as "Python 3.10+" has now actually been executed on 3.10, 3.11,
3.12, 3.13 and 3.14 on Linux x86-64.

`origin-v1.0.zip` is superseded and should not be redistributed.
