# Historical ORIGIN 2.0.0 — Clean-Room Onboarding Verification

> These are valid 2.0.0 results, retained for traceability. They are not a test
> result for 2.1.1rc1. Current candidate verification is recorded in
> [`V2_1_1_VERIFICATION.md`](V2_1_1_VERIFICATION.md).

Run from a fresh `git archive` extraction with nothing carried over from the
development checkout. Environment: CPython 3.12.3, Ubuntu 24.04.4 LTS, x86-64,
single core.

## Pass 1 — found two defects

| Step | Result |
|---|---|
| `python3 -m unittest discover -s tests` | **258 tests OK** (91.0s) |
| `origin init` + `run` (fast profile) | COMPLETED, stop reason "no high-value next experiment remained" |
| `origin report \| head -3` | **DEFECT: `BrokenPipeError` traceback** |
| dossier header | **DEFECT: hardcoded "ORIGIN v1.0"** — stale for five releases |
| `origin verify --dir examples/flagship_run` | State verified |
| `origin replay --dir examples/flagship_run --exp …` | REPLAY PASS |

Both defects were fixed with regression tests
(`test_cli_survives_a_closed_pipe`, `test_dossier_reports_the_real_version`),
and all shipped example dossiers were regenerated.

## Pass 2 — after the fixes

```
$ python3 -m unittest discover -s tests
Ran 261 tests in 91.774s   OK

$ python3 -m origin run --dir runs/pr --steps 2      → Research status: PAUSED
$ python3 -m origin run --dir runs/pr                → COMPLETED, verify clean
$ python3 -m origin init --domain graphbench --profile graph_fast … && run
                                                     → State verified
$ python3 tools/autonomy_demo.py --dir runs/autonomy → completed; verify clean
$ python3 tools/web_evidence_demo.py --dir runs/evidence --mode fixture
                                     → claims SPECULATION; no evidence from web
$ timeout 900 python3 tools/flagship_evaluation.py --dir runs/flageval
                                     → baseline names 3 incorrect winners,
                                       ORIGIN names 0
$ python3 tools/check_artifacts_portable.py .        → PORTABILITY OK
```

Every checklist item in `RELEASE_CHECKLIST.md` passes except one, which is
recorded rather than checked: **CI has never executed on a hosted runner.** The
workflow is committed and every job was run locally command-by-command; the
release notes say so instead of implying a green build.


---

## Re-verification at the final release commit

The clean-room sequence was re-run after the last content commits (flagship
evaluation container README, CHANGELOG restoration, the graphbench 3.10
f-string fix). Same environment: CPython 3.12.3, Ubuntu 24.04.4 LTS, x86-64,
single core.

```
$ git archive --format=zip --prefix=origin/ HEAD > /tmp/cleanroom/origin-release.zip
$ cd /tmp/cleanroom && unzip -q origin-release.zip && cd origin
$ python3 tools/check_artifacts_portable.py .
PORTABILITY OK: no machine-specific absolute paths in artifacts under .
$ python3 -c "import origin; print(origin.__version__)"
2.0.0
$ python3 -m unittest discover -s tests
Ran 261 tests in 116.123s   OK
```

Support matrix, full suite, at this commit:

```
CPython 3.10.20   Ran 261 tests in 142.3s   OK
CPython 3.11.15   Ran 261 tests in  97.3s   OK
CPython 3.12.3    Ran 261 tests in  92.8s   OK
CPython 3.13.13   Ran 261 tests in 122.4s   OK
CPython 3.14.4    Ran 261 tests in  77.9s   OK
```

Every shipped example verified individually:

```
examples/autonomy_demo/                          State verified
examples/demo_run/                               State verified
examples/evidence_demo/                          State verified
examples/flagship_run/                           State verified
examples/graph_mission/                          State verified
examples/final_flagship_mission/baseline/        State verified
examples/final_flagship_mission/origin_full/     State verified
examples/final_flagship_mission/proposal_only/   State verified
```

`examples/final_flagship_mission/` itself is a container, not a mission —
`origin verify` on it correctly reports "NO PROJECT". A README in that directory
now says so, because a tool that reports an error on a shipped example without
explanation is a documentation defect.

### One process note recorded honestly

The release pass was performed twice. The second attempt began without checking
`git log`, re-created scaffolding that already existed, and overwrote the 2.0.0
CHANGELOG with a less accurate one carrying a wrong version and stale test
counts. It was caught by a version mismatch during this clean-room run — the
archive reported 2.0.0 while the duplicate work assumed 1.8.0 — and the original
CHANGELOG was restored from git. One genuine fix was salvaged from that commit:
a multi-line f-string expression in `graphbench` that is PEP 701 syntax
(Python 3.12+) and broke the 3.10 floor, caught by the support-matrix run.

Nothing was lost. The lesson is the same one the v1.4.1 pass recorded: read the
history before assuming work is missing.
