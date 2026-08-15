# ORIGIN 2.1.1rc1 — Release Audit

Date: 2026-08-15

## Scope

This audit covers the 2.1.0 source archive supplied for release preparation and
the 2.1.1rc1 candidate derived from it. The candidate changes release identity
and release evidence only; it does not claim a new research capability.

## Version authority

| Source | Candidate value | Status |
|---|---|---|
| `pyproject.toml` | `2.1.1rc1` | authoritative package metadata |
| `origin/__init__.py` | `2.1.1rc1` | runtime version |
| `CHANGELOG.md` | `2.1.1rc1` entry | current change record |
| README archive command | `origin-v2.1.1rc1.zip` | current public instruction |

The archive must retain this exact identity when packaged. A candidate is not a
public release merely because it has a version number.

## Historical records retained as history

The following documents contain legitimate evidence for the earlier 2.0.0
release, including a 261-test run. They are not proof for 2.1.1rc1 and must not
be edited to invent newer results:

| Document | Historical scope |
|---|---|
| `docs/release/RELEASE_NOTES.md` | 2.0.0 release notes |
| `docs/release/RELEASE_CHECKLIST.md` | 2.0.0 clean-room checklist |
| `docs/release/CLEAN_ROOM_VERIFICATION.md` | 2.0.0 clean-room results and 3.10–3.14 matrix |
| `docs/red_team/RED_TEAM_REPORT.md` | v1.0 baseline with later v1.3/v1.7 additions |

Their headers now point readers to the current candidate records. This preserves
the historical evidence while preventing an accidental version mismatch.

## Reconciled discrepancies

The supplied 2.1.0 source correctly declared `2.1.0` in package metadata and
contained 268 test definitions, but its README quick start and generic release
documents still instructed users to use `origin-v2.0.0.zip` and described 261
tests. The v2.1.1rc1 documentation now states 268 as a test-case inventory, not
as a fresh passing result, until the candidate has been run on its documented
Linux matrix.

## Findings that are not product defects

An inspection environment using Python 3.15 release-candidate inside a managed
macOS execution sandbox rejected the project's POSIX `preexec_fn` confinement
hook before any experiment child process could start. This is outside the
documented Linux/Python 3.10–3.14 support matrix. It prevents independent
execution of child-process tests in that environment; it is not evidence that
the ORIGIN sandbox or experiment engine is defective.

## Release gates

Before this candidate may be labelled `READY FOR PUBLIC RELEASE`:

1. Run the complete suite for this exact candidate on Linux with CPython 3.10,
   3.11, 3.12, 3.13, and 3.14, and retain the command output.
2. Run the included hosted CI workflow or record equivalent immutable build
   evidence for the candidate.
3. Perform a clean archive extraction and repeat the required artifact,
   portability, and example-verification checks.
4. Reconcile the final archive filename with the package/runtime version.

A live Anthropic call and a native macOS run are valuable additional evidence.
They are not assumed to have occurred: the former remains `UNVERIFIED` without
an operator-run, redacted result, and the latter cannot expand platform support
until it passes natively.
