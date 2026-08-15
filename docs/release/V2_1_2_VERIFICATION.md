# ORIGIN 2.1.2 — Verification Record

## Local native macOS evidence

Environment: macOS arm64, CPython 3.15.0rc1.

```text
python3 -m unittest discover -s tests
Ran 271 tests in 71.134s
OK
```

The suite includes an actual incremental allocation bomb, a forced RSS-monitor
failure, fail-closed confinement setup handling, end-to-end missions, replay,
portability, security, reliability, and bounded autonomy. Python 3.15 is a
pre-release diagnostic environment and is not added to the supported matrix.

## Hosted verification

GitHub Actions run #4 passed on candidate commit
`2ddb481e9adcaede13cad08d8bb7f4f1dad0f6c9`:

https://github.com/nishchaysinghofficial10-ship-it/origin/actions/runs/31901690419

- Linux/Ubuntu 24.04 on CPython 3.10, 3.11, 3.12, 3.13, and 3.14: **passed**.
- macOS on stable CPython 3.14: **passed**.
- Portability and archive round-trip: **passed**.
- Fresh end-to-end mission, fixture evidence, bounded autonomy, and
  interruption/resume: **passed**.

All eight jobs completed successfully in 3m06s. The macOS job ran the same
271-case suite as the Linux matrix.

## Clean archive evidence

`origin-v2.1.2-candidate.zip` was built with `git archive` from the candidate
commit, extracted into an unrelated temporary directory, and checked there:

```text
archive_version 2.1.2
PORTABILITY OK
three shipped mission states: verified
Ran 271 tests in 69.958s
OK
```

Candidate archive SHA-256:
`4d8c45df8c158745ef96d01a8af8154e17127a6ad5783cafe3011029d49291ad`.
The final public archive is rebuilt from the documentation-only finalization
commit and independently checked before upload.

## Remaining unverified capability

The live Anthropic provider path remains unverified. No credential is required
or used by the test suite.
