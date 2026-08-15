# ORIGIN 2.1.1 — Release Audit

Date: 2026-08-15

## Scope

This audit covers the 2.1.0 source archive supplied for release preparation,
the 2.1.1rc1 candidate derived from it, and the final 2.1.1 release. The patch
changes release identity and evidence, repairs the public repository structure,
and fixes the CI workflow syntax; it does not claim a new research capability.

## Version authority

| Source | Release value | Status |
|---|---|---|
| `pyproject.toml` | `2.1.1` | authoritative package metadata |
| `origin/__init__.py` | `2.1.1` | runtime version |
| `CHANGELOG.md` | `2.1.1` entry | current change record |
| README archive command | `origin-v2.1.1.zip` | current public instruction |

The final archive retains this exact identity and was checked after extraction.

## Historical records retained as history

The following documents contain legitimate evidence for the earlier 2.0.0
release, including a 261-test run. They are not proof for 2.1.1 and must not
be edited to invent newer results:

| Document | Historical scope |
|---|---|
| `docs/release/RELEASE_NOTES.md` | 2.0.0 release notes |
| `docs/release/RELEASE_CHECKLIST.md` | 2.0.0 clean-room checklist |
| `docs/release/CLEAN_ROOM_VERIFICATION.md` | 2.0.0 clean-room results and 3.10–3.14 matrix |
| `docs/red_team/RED_TEAM_REPORT.md` | v1.0 baseline with later v1.3/v1.7 additions |

Their headers now point readers to the current release records. This preserves
the historical evidence while preventing an accidental version mismatch.

## Reconciled discrepancies

The supplied 2.1.0 source correctly declared `2.1.0` in package metadata and
contained 268 test definitions, but its README quick start and generic release
documents still instructed users to use `origin-v2.0.0.zip` and described 261
tests. The v2.1.1 documentation now states 268 as the test-case inventory and
links the fresh passing hosted Linux matrix that verifies the claim.

## Findings that are not product defects

An inspection environment using Python 3.15 release-candidate inside a managed
macOS execution sandbox rejected the project's POSIX `preexec_fn` confinement
hook before any experiment child process could start. This is outside the
documented Linux/Python 3.10–3.14 support matrix. It prevents independent
execution of child-process tests in that environment; it is not evidence that
the ORIGIN sandbox or experiment engine is defective.

## Release gates closed

Hosted CI run #2 completed successfully for release-candidate commit
`3ed48cc142788477755015c06f546fcda9c3973d`:

https://github.com/nishchaysinghofficial10-ship-it/origin/actions/runs/31896862103

All five supported Python jobs, the portability/archive job, and the clean
end-to-end mission job passed. The final release changes only version and
evidence metadata and is submitted through the same workflow before tagging.
The final archive is also extracted locally to confirm its version, portability,
artifact consistency, and absence of cache files.

A live Anthropic call and a native macOS run are valuable additional evidence.
They are not assumed to have occurred: the former remains `UNVERIFIED` without
an operator-run, redacted result, and the latter cannot expand platform support
until it passes natively.
