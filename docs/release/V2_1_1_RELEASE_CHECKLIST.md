# ORIGIN 2.1.1 — Release Checklist

This is the current release checklist. The 2.0.0 checklist is preserved as a
historical record and must not be used to close any item below.

## Identity and documentation

- [x] `pyproject.toml` and `origin/__init__.py` agree on `2.1.1`.
- [x] README names `origin-v2.1.1.zip` and links the current verification record.
- [x] Current audit, verification record, checklist, final-status record, and
      release notes exist under `docs/release/`.
- [x] Older v2.0 evidence is labelled as historical rather than overwritten.

## Local evidence completed

- [x] Source inventory contains 268 test cases.
- [x] Portability scan is clean.
- [x] Shipped autonomy, graph, and flagship state artifacts verify cleanly.
- [x] A clean release archive imports as `2.1.1`, contains no cache files,
      and repeats the portability and shipped-artifact verification checks.
- [x] Current documentation states the review-environment limitation rather
      than attributing it to ORIGIN without evidence.

## Required before public release

- [x] Linux CPython 3.10 full suite passed in hosted CI.
- [x] Linux CPython 3.11 full suite passed in hosted CI.
- [x] Linux CPython 3.12 full suite passed in hosted CI.
- [x] Linux CPython 3.13 full suite passed in hosted CI.
- [x] Linux CPython 3.14 full suite passed in hosted CI.
- [x] Hosted CI run #2 succeeded; URL and commit are recorded.
- [x] CI's archive round-trip repeated the full suite, portability, replay, and
      example verification from an independently extracted archive.
- [x] Final archive has the exact release version in its filename and ships no
      caches or machine-specific absolute paths.

## Optional evidence, required only to remove the associated limitation

- [ ] Live LLM check executed with an operator-held credential; only its
      redacted summary is recorded. Until then, keep the feature `UNVERIFIED`.
- [ ] Native macOS suite executed. Until it passes, keep macOS `untested`.

## Release decision

Current decision: **READY FOR PUBLIC RELEASE**, subject to the automatic CI run
on the metadata-only finalization commit. See
[`V2_1_1_FINAL_STATUS.md`](V2_1_1_FINAL_STATUS.md).
