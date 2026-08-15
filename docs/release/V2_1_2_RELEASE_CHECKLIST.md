# ORIGIN 2.1.2 — Release Checklist

## Implementation and local evidence

- [x] Darwin no longer attempts the unusable `RLIMIT_AS` alias.
- [x] macOS over-limit process groups are killed by the RSS watchdog.
- [x] Monitor failure and confinement setup failure both fail closed.
- [x] Active confinement is recorded per experiment.
- [x] Linux retains `RLIMIT_AS`.
- [x] Native macOS full suite passes: 271 tests.
- [x] Package, runtime, README, changelog, and archive identity say `2.1.2`.

## Required before publication

- [ ] Hosted Linux CPython 3.10–3.14 jobs pass.
- [ ] Hosted macOS CPython 3.14 job passes.
- [ ] Portability, archive, clean mission, autonomy, and recovery jobs pass.
- [ ] Clean `origin-v2.1.2.zip` imports as `2.1.2` and passes verification.
- [ ] Final CI URL and commit are recorded in the verification document.

## Optional

- [ ] Operator-run live Anthropic check. Until supplied, keep it unverified.

Current decision: **NOT YET RELEASED — HOSTED CI PENDING**.
