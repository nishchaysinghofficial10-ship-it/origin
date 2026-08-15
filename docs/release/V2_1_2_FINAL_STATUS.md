# ORIGIN 2.1.2 — Final Status

**Current verdict: READY FOR FINALIZATION.**

The macOS defect is reproduced, corrected, and covered by fail-closed tests. A
native macOS/arm64 run passes all 271 tests, including the memory boundary and
complete research workflows. Linux retains its prior kernel-enforced memory
limit.

GitHub Actions run #4 passed all eight jobs on candidate commit `2ddb481`:
Linux 3.10–3.14, stable macOS 3.14, portability/archive round-trip, and the
fresh end-to-end mission. A separately extracted candidate archive also passed
all 271 tests and artifact checks.

Publication now requires only a green workflow on the documentation-only
finalization commit and validation/upload of the archive rebuilt from that
commit. The live Anthropic provider is independent optional evidence and
remains explicitly unverified.
