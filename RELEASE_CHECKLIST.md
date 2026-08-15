# Historical ORIGIN 2.0.0 — Release Checklist

> This is the preserved checklist for the 2.0.0 release. It must not be used to
> close candidate-specific 2.1.1rc1 work. The current checklist is
> [`V2_1_1_RELEASE_CHECKLIST.md`](V2_1_1_RELEASE_CHECKLIST.md).

Executed for 2.0.0. Every line has a command behind it; a box is only ticked if
the command was run at the release commit.

## Clean-room onboarding

Performed from a fresh `git archive` extracted to a new directory, using the
public documentation only.

| # | Step | Command | Result |
|---|---|---|---|
| 1 | Fresh archive extracts | `git archive --format=zip HEAD` → unzip | 13 top-level entries, no caches |
| 2 | Install | *(none required)* `python3 -c "import origin"` | imported with zero installs, v2.0.0 |
| 3 | Run tests | `python3 -m unittest discover -s tests` | **261 tests, OK, 99.8s** |
| 4 | Run a demo | `origin init … --profile fast && origin run` | COMPLETED — "no high-value next experiment remained" |
| 5 | Inspect a dossier | `origin report --dir runs/demo` | all sections present incl. prediction ledger, falsification, threats to validity |
| 6 | Pause and resume | `origin run --steps 2` then `origin run` | paused durably, resumed to completion, `verify` clean |
| 7 | Reproduce an experiment | `origin replay --dir examples/graph_mission --exp …` | **REPLAY PASS** — correctness, inputs, outputs identical; timing reported, not asserted |
| 8 | Autonomy demo | `tools/autonomy_demo.py` + `origin autonomy status` | COMPLETED, queue `{done: 11, queued: 2}`, lease free, `verify` clean |
| 9 | Flagship evaluation | `tools/flagship_evaluation.py` | reproduced: baseline names 3 incorrect winners, ORIGIN names 0 |
| 10 | Hygiene | portability guard; cache/secret scan | no absolute paths, 0 cache artifacts in the archive, no keys outside test fixtures |

**Note on step 3:** the count is **261** once every shipped example is present.
An earlier working-tree run reported 258 because three tests skip when the
example mission they inspect is absent — they execute, and pass, when it is
there. Both runs were real; 261 is the number for a complete checkout and is
what the documentation quotes.

## Repository hygiene

- [x] No secrets in source, artifacts, logs, reports or history — scanned for
      `sk-ant-`, `api_key=`; only synthetic fixtures in `tests/` match
- [x] No machine-specific absolute paths — `tools/check_artifacts_portable.py`
      is clean and runs in CI
- [x] No cache or build artifacts tracked — `.gitignore` added; `git ls-files`
      shows 0 `__pycache__`/`.pyc` entries
- [x] No unsupported claims — a grep for "kernel-grade", "fully isolated",
      "exactly-once" finds only explicit **denials**, and
      `test_documentation_does_not_claim_kernel_grade_isolation` fails the
      build if that changes

## Required files

- [x] `README.md` — what ORIGIN is and is not, domains, install, demo,
      reproduction, safety boundaries, limitations, contributing
- [x] `LICENSE` (MIT) · `CHANGELOG.md` · `CONTRIBUTING.md` ·
      `CODE_OF_CONDUCT.md` · `SECURITY.md` (with responsible-use statement)
- [x] Issue templates (bug, feature) and a PR template that demands evidence
- [x] CI workflow — matrix, portability, fresh mission, autonomy, evidence
- [x] `docs/release/RELEASE_NOTES.md`, this checklist
- [x] Architecture, operations, reproducibility, autonomy, evidence, LLM,
      second-domain, security and verification documentation
- [x] Example missions: `demo_run`, `flagship_run`, `graph_mission`,
      `evidence_demo`, `autonomy_demo`, `final_flagship_mission`

## Evidence-backed claims

- [x] Every test count in documentation was produced by a command at this commit
- [x] Every benchmark figure names its environment and scope
- [x] Live LLM call labelled **UNVERIFIED**, with the one command that would
      verify it
- [x] General-web retrieval labelled verified **only against allow-listed
      hosts**
- [x] No novelty claimed — the flagship evaluation says plainly that ORIGIN
      rediscovered textbook results under budget

## Not ticked, deliberately

- [ ] **CI has never executed.** There is no runner in the build environment.
      **Closes on the first push** to a host with Actions enabled — the
      workflow already covers the 3.10–3.14 matrix, portability, the relocated
      mission, the archive round-trip, the fixture evidence pipeline and the
      autonomy demo. Nothing to write; just run it once and record the URL.
      Every job's commands were run locally and are recorded as
      "CI-equivalent"; the workflow file itself is unexecuted. A first push
      will be its first real run.
- [ ] **macOS untested.** Linux only — one `python -m unittest discover -s tests`
      on a Mac either closes this or produces a real bug report. Windows is
      unsupported and fails with an
      explicit message.
- [ ] **Live provider call unperformed.** No credential existed here.
      **One command closes it:**
      `export ANTHROPIC_API_KEY=... && python tools/live_llm_check.py --dir runs/live_check --provider-calls 2`
      Then paste `runs/live_check/logs/live_check_summary.json` into
      `docs/verification/LLM_VERIFICATION_REPORT.md` §7 and tick this box.

## Release readiness

Ready for public release **with those three exceptions stated in the release
notes**, not hidden in a footnote. The clean-room test passed end to end using
public documentation alone, which was the gating condition.
