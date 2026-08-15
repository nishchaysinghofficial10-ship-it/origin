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

## Hosted release gates

The release workflow must pass:

- Linux/Ubuntu 24.04 on CPython 3.10, 3.11, 3.12, 3.13, and 3.14.
- macOS on stable CPython 3.14.
- The portability/archive round-trip job.
- A fresh end-to-end mission, fixture evidence, bounded autonomy, and
  interruption/resume.

The final run URL and commit are recorded here only after GitHub reports every
job successful. Until then this document is release-candidate evidence, not a
publication claim.

## Remaining unverified capability

The live Anthropic provider path remains unverified. No credential is required
or used by the test suite.
