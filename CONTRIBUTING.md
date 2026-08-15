# Contributing to ORIGIN

## The one rule

**No capability is complete without evidence.** A pull request that adds a
feature adds a test that exercises it, and any claim in documentation names the
command that produced it. "It should work" is not a status; `IMPLEMENTED_BUT_
UNVERIFIED` is, and saying so is welcome.

## Setup

```bash
git clone <repo> && cd origin-project
python -m unittest discover -s tests -v      # no dependencies to install
```

Python 3.10+ on Linux. Zero third-party runtime dependencies — please keep it
that way. If a dependency genuinely earns its place, justify it in
`docs/DECISIONS.md`; "convenience" is not a justification.

## Before you open a PR

```bash
python -m unittest discover -s tests            # everything must pass
python tools/check_artifacts_portable.py .      # no machine-specific paths
python -m origin verify --dir examples/flagship_run
```

## What gets merged easily

- A regression test for a bug, with the bug reproduced first.
- A new research domain implementing only `ResearchDomain` hooks (see
  `docs/SECOND_DOMAIN.md`; note the two architecture gaps it exposed).
- Honest corrections to documentation that overclaims.
- Threat-model entries with an executed attack behind them.

## What will be pushed back on

- Anything that lets untrusted content — a model response, a web page, a work
  item — reach execution, credentials, or accepted knowledge.
- Widening a safety limit to make a test pass.
- Adding a dependency for convenience.
- Claiming exactly-once, kernel-grade isolation, or cross-machine timing
  reproducibility. None of those are true, and tests assert that the docs do
  not say they are.
- Test counts or benchmark numbers in documentation that were not produced by a
  command run at that commit.

## Style

Boring and maintainable. Comments explain *why*, not *what*. If a design choice
is non-obvious, add it to `docs/DECISIONS.md` with the alternatives you rejected.

## Security

Do not open a public issue for a vulnerability — see `SECURITY.md`.
