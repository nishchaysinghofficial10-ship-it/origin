# ORIGIN — Reliability & Portability Verification Report

Engagement: make the project portable, reproducible, and honestly verifiable
**before** adding features. Everything below was executed in this repository;
each claim carries the exact command and the observed output. Nothing is
claimed that was not run.

- Repository at start of engagement: `f6b46e8` (ORIGIN v1.0 as handed off).
- Repository at end: `origin` package version **1.1.0**, 56 tests.
- Host: Ubuntu 24.04.4 LTS, Linux 6.18.5 x86-64, **1 vCPU** (`nproc` = 1),
  CPython 3.12.3 system interpreter. The single core matters: it is why
  timing-based assertions were found to be unreliable (§4).

---

## 1. Test suite in a clean environment

The repository was copied to a fresh directory, all `__pycache__` removed, and
the suite run with the system interpreter.

```
$ cp -r /home/claude/origin-project /tmp/cleanrun/repo && cd /tmp/cleanrun/repo
$ find . -name "__pycache__" -type d -exec rm -rf {} +
$ python3 -m unittest discover -s tests -v
...
Ran 37 tests in 32.896s

OK
```

That was the inherited baseline (37 tests). After this engagement's fixes and
regression tests the suite is **56 tests**:

```
$ python3 -m unittest discover -s tests
Ran 56 tests in 28.381s

OK
```

| module | tests | scope |
|---|---:|---|
| `test_core.py` | 7 | budgets, graph, persistence, full mission, invalid spec |
| `test_lifecycle.py` | 7 | transitions, migration, pause/resume (CLI **and** library), cancel |
| `test_reliability.py` | 10 | SIGKILL/resume, checkpoint corruption (4 cases), orphan reconciliation, replay, missing project |
| `test_portability.py` | 12 | **new** — relative artifacts, relocation, archive round-trip, replay verdict stability |
| `test_sandbox.py` | 6 | policy, rlimits, env scrubbing, crash isolation |
| `test_brain.py` | 7 | provider validation, failures, redaction, budgets |
| `test_evidence_redteam.py` | 7 | untrusted ingestion, red-team scenarios |

No skips, no expected failures, zero third-party dependencies.

---

## 2. Declared support matrix — verified, not asserted

`pyproject.toml` declared `requires-python = ">=3.10"`, but only CPython 3.12
had ever been executed. Additional interpreters were installed
(`uv python install 3.10 3.11 3.13 3.14`, python-build-standalone) and the
**entire suite was run on each**:

```
$ for V in 3.10 3.11 3.12 3.13 3.14; do python$V -m unittest discover -s tests; done
  CPython 3.10.20  :: Ran 56 tests in 45.019s  OK
  CPython 3.11.15  :: Ran 56 tests in 34.919s  OK
  CPython 3.12.3   :: Ran 56 tests in 36.454s  OK
  CPython 3.13.13  :: Ran 56 tests in 38.763s  OK
  CPython 3.14.4   :: Ran 56 tests in 35.336s  OK
```

3.14 was additionally run with `-W error::DeprecationWarning` (37-test suite at
the time): OK — no deprecation warnings from ORIGIN's own code paths,
including `subprocess(preexec_fn=…)` in the parent process.

**Tested and supported:** CPython 3.10–3.14 on Linux x86-64 (Ubuntu 24.04).
**Not tested, not claimed:** macOS (should work — POSIX only — but no macOS
host was available), other architectures, PyPy.
**Not supported:** Windows. ORIGIN requires `resource` rlimits and
`os.setsid()`. `sandbox.make_preexec` now raises an explicit
`RuntimeError` naming WSL2/Linux/macOS instead of failing with an obscure
`ImportError`. *That guard has not been executed on Windows and is not claimed
to have been.* `pyproject.toml` classifiers now list only the tested matrix.

---

## 3. Portability defect P-1 — absolute artifact paths (critical)

### Reproduction (before the fix)

```
$ cp -r examples/flagship_run /tmp/portcheck/relocated_mission
$ python3 -c "…print(rec.dir)…"
exp_aa415f5a05 -> /home/claude/origin-project/examples/flagship_run/experiments/exp_aa415f5a05
```

The copy's records pointed at the **original machine's** directories. The
decisive test — delete the copy's own artifacts entirely, then verify it:

```
$ rm -rf /tmp/portcheck/relocated_mission/experiments
$ python3 -m origin verify --dir /tmp/portcheck/relocated_mission
State verified: counts, references, experiment artifacts and event log are consistent.
verify exit=0
```

A mission with **zero artifacts of its own** was certified consistent, because
the integrity checker silently read another directory. `replay` likewise
re-executed foreign code. On any other machine both would have raised
`FileNotFoundError`.

Blast radius in the published archive:

```
$ unzip -q origin-v1.0.zip && grep -rl "/home/claude" .
./origin-project/examples/demo_run/state.json
./origin-project/examples/demo_run/research_state/experiments.json
./origin-project/examples/flagship_run/state.json.bak
./origin-project/examples/flagship_run/state.json
./origin-project/examples/flagship_run/research_state/experiments.json
$ grep -rho "/home/claude" . | wc -l
51
```

### Fix

- `ExperimentRecord.dir` is now **root-relative** (`experiments/exp_…`) and is
  resolved through `ExperimentRecord.path(root)` / `ResearchState.experiment_dir()`.
  Every reader was updated (`experiments.py`, `report.py`, `cli.py replay`,
  `state.verify`).
- `ResearchState.load()` migrates legacy absolute values on read: in-tree paths
  are made relative, foreign paths fall back to the canonical layout instead of
  reading another machine's directory. The count is recorded in
  `flags["migrated_paths"]`. Schema version bumped 2 → 3.
- `verify()` now reports an absolute `dir` as a portability problem instead of
  following it.
- `tools/normalize_paths.py` rewrote the shipped examples in place
  (demo_run: 12 references, flagship_run: 39).
- `tools/check_artifacts_portable.py` is a repository-wide guard, wired into CI
  and into `tests/test_portability.py`. Deliberate synthetic paths in test
  fixtures opt out with an inline `portability-allow` marker.

### Verification (after the fix)

```
$ python3 tools/check_artifacts_portable.py .
PORTABILITY OK: no machine-specific absolute paths in artifacts under .

$ grep -rl "/home/claude" --exclude-dir=.git --exclude-dir=__pycache__ . | wc -l
0
```

Relocated copy — verifies and replays **from its own files**:

```
$ cp -r examples/flagship_run /tmp/ci/relocated_mission
$ python3 -m origin verify --dir /tmp/ci/relocated_mission
State verified: counts, references, experiment artifacts and event log are consistent.

$ python3 -m origin replay --dir /tmp/ci/relocated_mission --exp exp_aa415f5a05
Replayed exp_aa415f5a05 in 5.4s from recorded code+config (seed 20260809).
Compared 60 measurement cells; correctness must match exactly; timing tolerance
±50% above a 5ms noise floor (max observed deviation 90%).
Ranking agreement: 10/12 regime×size groups identical; 0 decisive inversion(s).
REPLAY PASS — every stored cell was reproduced from the stored code+config with
identical correctness. (Timing and ranking are reported above, not asserted.)
```

The false-PASS is gone — a gutted copy now fails honestly:

```
$ cp -r examples/flagship_run /tmp/ci/gutted && rm -rf /tmp/ci/gutted/experiments
$ python3 -m origin verify --dir /tmp/ci/gutted ; echo exit=$?
26 consistency problem(s):
 - experiment exp_aa415f5a05 missing spec.json on disk
 - experiment exp_aa415f5a05 completed but result.json missing
 …
exit=1
```

Archive round-trip, extracted somewhere unrelated with the source removed from
the equation:

```
$ git archive --format=zip --prefix=origin-project/ HEAD > /tmp/ciarch/origin.zip
$ unzip -q /tmp/ciarch/origin.zip -d /tmp/ciarch/extracted
$ cd /tmp/ciarch/extracted/origin-project
$ python3 tools/check_artifacts_portable.py .
PORTABILITY OK: no machine-specific absolute paths in artifacts under .
$ python3 -m unittest discover -s tests
Ran 54 tests … OK                      # 56 after the later R-4/R-5 fixes
$ python3 -m origin verify --dir examples/flagship_run
State verified: …
$ python3 -m origin replay --dir examples/flagship_run --exp exp_f53e0d9748
REPLAY PASS — …
```

Regression tests: `tests/test_portability.py::TestArtifactReferencesAreRelative`
(4), `::TestRelocatedMission` (3), `::TestArchiveIsSelfContained` (2).

---

## 4. Portability defect P-2 — the replay verdict depended on the host

`replay` asserted wall-clock timing equivalence (±50%, 2 ms absolute slack).
On this 1-vCPU host the **same** experiment produced different verdicts:

```
$ for i in 1 2 3; do python3 -m origin replay --dir … --exp exp_aa415f5a05; done
run 1: REPLAY FAIL  - merge_sort/few_unique/4096: 6.51ms -> 31.60ms (rel 385%)
run 2: REPLAY PASS
run 3: REPLAY PASS
```

Different cells flagged on each run (`insertion_sort` 239→372 ms,
`shell_sort` 15.5→24.6 ms), which identifies scheduler contention rather than
any content difference: the seeds, inputs and correctness results were
identical every time.

A verification tool that flakes trains operators to ignore it. The verdict was
therefore rebuilt around what a stored experiment can actually guarantee:

| property | host-independent? | default verdict |
|---|---|---|
| every stored cell reproduced | yes (seeded) | **hard fail** if missing |
| per-cell correctness | yes (seeded) | **hard fail** on mismatch |
| wall-clock timing | no | reported, `--strict` to fail |
| ranking within a regime×size group | no (near-ties flip) | reported (with "decisive inversion" count), `--strict` to fail |

Stability after the change — five consecutive replays of the largest stored
experiment on the same contended host:

```
run 1 exit=0 :: REPLAY PASS   run 2 exit=0 :: REPLAY PASS
run 3 exit=0 :: REPLAY PASS   run 4 exit=0 :: REPLAY PASS
run 5 exit=0 :: REPLAY PASS
```

The checks that matter still bite (`tests/test_portability.py::TestReplayVerdictIsStable`):
a mutated `correct` flag fails by default; a fabricated 100× ranking inversion
fails under `--strict`; a uniform 10× timing shift passes by default and fails
under `--strict --noise-floor-ms 0`.

**Honest limitation:** on this host ORIGIN can certify that a stored experiment
*reproduces its recorded results*, not that it reproduces its recorded
*timings*. Timing equivalence should be asserted only on dedicated hardware,
via `--strict`.

---

## 5. Checkpoint recovery

Each defect below was reproduced first, then fixed, then re-run.

### R-1 — crash inside the save window made a recoverable project unloadable

`save()` rotated `state.json` → `.bak` **before** writing the new snapshot.

```
before:  $ rm state.json && load()
         -> FileNotFoundError: [Errno 2] … '/tmp/probe/r1/state.json'
after:   -> loaded OK; step 4 | recovered_from_backup = True
```

Fix: `save()` writes and `fsync`s the temp file *first*, then rotates, then
renames, then `fsync`s the directory; `load()` treats a missing primary with an
intact backup as a normal crash outcome.

### R-2 — structurally invalid checkpoint raised a bare `KeyError`

```
before:  $ echo '{"schema_version": 3}' > state.json && load()
         -> KeyError: 'meta'
after:   -> loaded OK; step 4 | recovered_from_backup = True
```

Fix: a candidate snapshot is accepted only if it *reconstructs*, so a parseable
but broken file falls through to the backup.

### R-3 — a torn event-log line broke the timeline and misreported the state

```
before:  $ printf '{"ts": 1786, "kind": "partial"' >> logs/events.jsonl
         $ python3 -m origin timeline --dir …   -> exit=1 (traceback)
         $ python3 -m origin verify  --dir …
           - event log unreadable: Expecting property name…
           - event log is empty                 # false: 60+ events were readable
after:   $ python3 -m origin timeline --dir …   -> exit=0
         $ python3 -m origin verify  --dir …
           - 1 malformed line(s) in the event log (torn write?); they were skipped
```

### R-4 — orphaned experiment artifacts after a hard kill went unnoticed

Found by running the real interruption test rather than a simulation:

```
$ python3 -m origin run --dir /tmp/kill/m &   # standard profile
$ sleep 4 && kill -9 $PID
$ python3 -c "…"
dirs on disk: 10 | records in checkpoint: 9
ORPHANED experiment directories: ['exp_6acd159e36']
   exp_6acd159e36 contains: ['result.json', 'run.py', 'spec.json']
events referencing experiments absent from checkpoint: ['exp_6acd159e36']
verify() says: clean            # <-- the integrity checker did not notice
```

Compute had been spent and a *complete* result written, yet the ledger knew
nothing about it. Fix: `verify()` reports orphaned directories and event
references; `ResearchController.run()` reconciles them idempotently into the
ledger as `status="interrupted"` records with a failure entry — bookkeeping,
never resurrection of unanalysed results as findings.

```
after (before resume):
 - experiment directory experiments/exp_6acd159e36 has no record in the checkpoint
   (interrupted run?); resume the mission to reconcile it
 - event log records exp_6acd159e36 as started but it is absent from the checkpoint
after (post-resume): verify -> clean, record status = interrupted
```

### R-5 — a PAUSED mission could not be resumed through the library API

Only the CLI called `lifecycle.resume()`, so any programmatic resume hit
`IllegalTransition: PAUSED -> CRITICIZING`. Fix: `ResearchController.run()`
resumes (no-op when not paused). Regression:
`test_lifecycle.py::test_paused_mission_resumes_through_the_library_api`.

### Interrupt / resume end-to-end evidence (hard SIGKILL)

```
$ python3 -m origin init "hard kill recovery evidence" --dir /tmp/kill/m \
      --profile standard --max-experiments 12 --brain none
$ python3 -m origin run --dir /tmp/kill/m &  ; sleep 4 ; kill -9 $PID
  after kill:   phase = CRITICIZING | step = 8  | experiments = 4
$ python3 -m origin run --dir /tmp/kill/m
  after resume: phase = COMPLETED   | step = 15 | experiments = 9
  pre-kill experiments preserved: True
  experiment_started events: 10 | unique: 10 | duplicates: 0
  events before/after: 55 -> 103
  verify: clean
```

Both-checkpoints-corrupt still fails safely and says where the history lives:

```
$ echo garbage > state.json && echo garbage > state.json.bak
$ python3 -m origin verify --dir …          # exit 2
CHECKPOINT ERROR: Checkpoint at …/state.json could not be loaded and no usable
backup exists (state.json: JSONDecodeError…; state.json.bak: JSONDecodeError…).
Research history in logs/ and experiments/ is intact; state.json needs manual repair.
```

A corrupt **backup alone** is harmless (primary is used, no recovery flag), and
a missing project now yields `NO PROJECT: …` with exit 2 rather than a
traceback. Covered by `test_reliability.py` (10 tests).

---

## 6. Continuous integration

`.github/workflows/ci.yml` defines three jobs on `ubuntu-24.04`:

1. **tests** — matrix CPython 3.10/3.11/3.12/3.13/3.14; prints interpreter and
   OS; asserts no third-party packages are pulled in (`pip list` diff around the
   import); runs the full suite.
2. **portability** — artifact guard; both shipped examples verify in place; a
   relocated flagship copy verifies **and replays**; a gutted copy **must fail**
   verify (guards the false-PASS defect); `git archive` → extract → full suite +
   verify in the extraction.
3. **fresh-mission** — init/run/verify/status/html on a clean checkout, artifact
   guard on the produced mission, then a pause (`--steps 2`) and resume.

**Status: committed, never executed.** There is no GitHub runner in this
environment, so no CI result is claimed. Every job's commands were instead run
locally and are reproduced in §1–§5 above; the fresh-mission job's local run:

```
$ python3 -m origin verify --dir /tmp/cifresh/ci_mission
State verified: …
$ python3 tools/check_artifacts_portable.py /tmp/cifresh/ci_mission
PORTABILITY OK: …
$ python3 -m origin run --dir /tmp/cifresh/ci_resume --steps 2
  phase after --steps 2: PAUSED
$ python3 -m origin run --dir /tmp/cifresh/ci_resume
  phase after resume: COMPLETED
  experiments started: 8 | unique: 8 | duplicates: 0
  verify problems: []
```

---

## 7. Defect register

| id | severity | defect | fix | regression test |
|---|---|---|---|---|
| P-1 | critical | Absolute artifact paths: copied missions read the original machine; `verify` false PASS; 51 leaked path references in the published archive | root-relative `dir` + load-time migration + `verify` check + guard tool | `test_portability.py` (9) |
| P-2 | high | Replay verdict driven by host timing noise (2 of 5 runs disagreed) | verdict on reproducible invariants; timing/ranking reported; `--strict` opt-in | `test_portability.py::TestReplayVerdictIsStable` (3) |
| R-1 | high | Crash in the save window → unloadable despite valid backup | write+fsync before rotate; recover from backup | `test_missing_primary_with_intact_backup_recovers` |
| R-2 | medium | Structurally invalid checkpoint → bare `KeyError` | reconstruct-to-accept, fall through to backup | `test_structurally_invalid_primary_falls_back_to_backup` |
| R-3 | medium | Torn event-log line broke `timeline`/`report`, misreported "empty" | tolerant reader + explicit `verify` problem | `test_torn_event_log_line_is_survivable` |
| R-4 | high | Orphaned experiment artifacts after a hard kill were invisible to `verify` | orphan detection + idempotent reconciliation on resume | `test_orphaned_experiment_artifacts_are_reconciled` |
| R-5 | medium | PAUSED mission unresumable via the library API | `ResearchController.run()` resumes | `test_paused_mission_resumes_through_the_library_api` |
| D-1 | low | `pyproject` claimed 3.10+ with only 3.12 ever run; no OS classifiers | matrix actually executed; classifiers list only tested targets | §2 evidence + CI matrix |

---

## 8. Residual risks and honest gaps

1. **CI has never run.** The workflow is a proposal until a runner executes it.
2. **macOS untested.** No host available. The code is POSIX-only and should
   work; that is an expectation, not a result.
3. **Windows unsupported.** The new guard raises a clear error, but it has not
   been executed on Windows.
4. **Timing reproducibility is not certified** (§4) — by design on shared
   hardware. `--strict` exists for controlled environments; it has been
   exercised only with synthetic data, not on quiet hardware.
5. **State is still not tamper-evident.** `verify()` detects accidental
   corruption, naive event replay, orphaned artifacts and missing files — not a
   determined forger with write access.
6. **Reconciled orphans are not analysed.** Their artifacts are preserved and
   marked `interrupted`; the compute they consumed is not retroactively charged
   to the budget (the duration was never recorded).
7. **`origin-v1.0.zip` as previously published is defective** (P-1). It is
   superseded by the v1.1 archive; the old one should not be redistributed.


---

## 9. Final verification pass (post-fix, end of engagement)

Executed at commit head after all fixes and documentation, on the host
described at the top of this report.

```
$ python3 -m unittest discover -s tests
Ran 56 tests in 38.363s
OK

$ python3 tools/check_artifacts_portable.py .
PORTABILITY OK: no machine-specific absolute paths in artifacts under .

$ python3 -m origin verify --dir examples/flagship_run
State verified: counts, references, experiment artifacts and event log are consistent.
$ python3 -m origin verify --dir examples/demo_run
State verified: counts, references, experiment artifacts and event log are consistent.

$ cp -r examples/flagship_run /tmp/final/relocated
$ python3 -m origin verify --dir /tmp/final/relocated
State verified: counts, references, experiment artifacts and event log are consistent.
$ python3 -m origin replay --dir /tmp/final/relocated --exp exp_f53e0d9748
Ranking agreement: 2/4 regime×size groups identical; 0 decisive inversion(s).
REPLAY PASS — every stored cell was reproduced from the stored code+config with
identical correctness. (Timing and ranking are reported above, not asserted.)

$ cp -r examples/flagship_run /tmp/final/gutted && rm -rf /tmp/final/gutted/experiments
$ python3 -m origin verify --dir /tmp/final/gutted ; echo $?
26 consistency problem(s):
1                       # no phantom pass: the copy cannot borrow another mission's files

$ git archive --format=zip --prefix=origin-project/ HEAD > /tmp/final/arch/origin.zip
$ cd /tmp/final/arch && unzip -q origin.zip && cd origin-project
$ python3 tools/check_artifacts_portable.py .
PORTABILITY OK: no machine-specific absolute paths in artifacts under .
$ python3 -m unittest discover -s tests
Ran 56 tests in 36.523s
OK
$ python3 -m origin verify --dir examples/flagship_run
State verified: counts, references, experiment artifacts and event log are consistent.
$ python3 -m origin replay --dir examples/flagship_run --exp exp_aa415f5a05
Ranking agreement: 11/12 regime×size groups identical; 0 decisive inversion(s).
REPLAY PASS — every stored cell was reproduced from the stored code+config with
identical correctness. (Timing and ranking are reported above, not asserted.)
```

Support matrix re-run at the same commit (56 tests each, all `OK`):
CPython 3.10.20, 3.11.15, 3.12.3, 3.13.13, 3.14.4 on Ubuntu 24.04 x86-64.

### Definition of done

| Requirement | Status | Evidence |
|---|---|---|
| Full suite passes in the documented environment | **met** | §1, §9; 56/56 on five interpreters |
| A copied flagship mission verifies successfully | **met** | §3, §9 (`/tmp/final/relocated`) |
| At least one stored experiment replays successfully | **met** | `exp_f53e0d9748` (16 cells) and `exp_aa415f5a05` (60 cells), in place, relocated, and from a fresh archive |
| No public artifact depends on a private absolute path | **met** | guard exits 0 over the repo, `examples/`, and an extracted archive; 51 prior occurrences removed |
| Every claimed result includes exact commands and observed output | **met** | every section of this report |
| No untested cross-platform claim | **met** | §2; macOS untested, Windows unsupported, CI unexecuted — all stated |
