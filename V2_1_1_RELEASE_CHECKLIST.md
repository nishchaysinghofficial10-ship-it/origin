# ORIGIN 2.1.1rc1 — Release Checklist

This is the current candidate checklist. The 2.0.0 checklist is preserved as a
historical record and must not be used to close any item below.

## Identity and documentation

- [x] `pyproject.toml` and `origin/__init__.py` agree on `2.1.1rc1`.
- [x] README names `origin-v2.1.1rc1.zip` and identifies the build as a release
      candidate, not a public release.
- [x] Current audit, verification record, checklist, final-status record, and
      release notes exist under `docs/release/`.
- [x] Older v2.0 evidence is labelled as historical rather than overwritten.

## Local evidence completed

- [x] Source inventory contains 268 test cases.
- [x] Portability scan is clean.
- [x] Shipped autonomy, graph, and flagship state artifacts verify cleanly.
- [x] A clean candidate archive imports as `2.1.1rc1`, contains no cache files,
      and repeats the portability and shipped-artifact verification checks.
- [x] Current documentation states the review-environment limitation rather
      than attributing it to ORIGIN without evidence.

## Required before public release

- [ ] Linux CPython 3.10 full suite: 268 passed; raw output retained.
- [ ] Linux CPython 3.11 full suite: 268 passed; raw output retained.
- [ ] Linux CPython 3.12 full suite: 268 passed; raw output retained.
- [ ] Linux CPython 3.13 full suite: 268 passed; raw output retained.
- [ ] Linux CPython 3.14 full suite: 268 passed; raw output retained.
- [ ] Hosted CI executed for this candidate; URL and outcome recorded.
- [ ] Clean archive extraction repeated the full supported-platform suite. The
      archive portability and shipped-artifact checks are already complete.
- [ ] Final archive has the exact candidate version in its filename and ships no
      secrets, caches, or absolute machine paths.

## Optional evidence, required only to remove the associated limitation

- [ ] Live LLM check executed with an operator-held credential; only its
      redacted summary is recorded. Until then, keep the feature `UNVERIFIED`.
- [ ] Native macOS suite executed. Until it passes, keep macOS `untested`.

## Release decision

Current decision: **NOT READY FOR PUBLIC RELEASE**. See
[`V2_1_1_FINAL_STATUS.md`](V2_1_1_FINAL_STATUS.md).
