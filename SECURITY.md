# Security Policy

## Reporting a vulnerability

**Do not open a public issue.** Use the repository's private vulnerability
reporting channel. Include what you did, what happened, and what you expected;
a reproducing command is ideal.

Expect an acknowledgement within a few days and an assessment of whether the
finding is material. Material findings are fixed with a regression test and
disclosed in `docs/red_team/RED_TEAM_REPORT.md`. Findings we decide not to fix
are documented as residual risks rather than quietly dropped.

## Scope

In scope: sandbox escape or execution of untrusted content; secret leakage into
state, logs, reports or artifacts; bypass of URL/host/robots/size policy;
bypass of budgets or safety gates; checkpoint corruption or tampering that
survives `origin verify`; autonomy acting beyond its granted authority; reports
that assert conclusions the stored state does not support.

Out of scope (documented limitations, not bugs — see
`docs/security/SECURITY_REVIEW.md`): the absence of kernel-level isolation;
network access from an experiment subprocess; DNS rebinding against the
unpinned fallback path; lack of TLS pinning; absence of tamper-evident storage;
no exactly-once guarantee for external actions.

## What ORIGIN already assumes

- The operator is trusted; the machine is not multi-tenant.
- Credentials live in environment variables only.
- Every experiment runs under user-space confinement — rlimits, scrubbed
  environment, cwd jail, output caps, wall-clock timeout — which is **not**
  kernel-grade isolation and is not described as such anywhere in these docs.

## Responsible use

ORIGIN is a computational-research engine. Do not use it for medical, legal,
financial or safety-critical conclusions. Retrieve only sources you are
permitted to retrieve; ORIGIN honours `robots.txt` but does not interpret terms
of service, and it does not verify licensing of anything it fetches.
