# ORIGIN 2.1.2 — Release Notes

This patch corrects experiment memory confinement on macOS without weakening
the existing Linux boundary.

## What changed

- Linux continues to impose the kernel-enforced `RLIMIT_AS` memory cap.
- macOS now supervises the complete child process group with a parent-side RSS
  watchdog. It kills an over-limit group and fails closed if monitoring is not
  available.
- CPU, file-size, process-count, core-dump, isolated-Python,
  scrubbed-environment, wall-time, and output limits remain in force.
- Every experiment stores `confinement.json`, including the mechanism, limits,
  observed peak RSS when available, and termination reason.
- A confinement setup failure becomes an inspectable failed experiment rather
  than aborting the whole mission.
- Hosted CI adds macOS with stable Python 3.14.

## Compatibility

Supported Python versions remain 3.10–3.14. A native diagnostic run also passes
on Python 3.15.0rc1, but pre-release Python is not part of the support claim.
Windows remains unsupported.

## Unchanged limitations

Confinement is user-space, not a kernel sandbox; there is no network or
filesystem namespace. macOS RSS enforcement is sampled and may observe a very
short allocation spike after it occurs. Live Anthropic use remains unverified
until an operator runs the bounded check with their own credential.
