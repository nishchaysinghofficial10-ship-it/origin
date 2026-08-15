# ORIGIN 2.1.2 — Final Status

**Current verdict: RELEASE CANDIDATE — HOSTED CI PENDING.**

The macOS defect is reproduced, corrected, and covered by fail-closed tests. A
native macOS/arm64 run passes all 271 tests, including the memory boundary and
complete research workflows. Linux retains its prior kernel-enforced memory
limit.

Publication remains blocked until the exact candidate commit passes the hosted
Linux 3.10–3.14 matrix, stable macOS 3.14 job, portability/archive checks, and
fresh mission checks. The live Anthropic provider is independent optional
evidence and remains explicitly unverified.
