# ORIGIN v1.0 — Safe Use

Full analysis: `docs/security/AUTONOMY_THREAT_MODEL.md` (bounded
autonomy), `docs/security/THREAT_MODEL.md`,
`docs/security/SECURITY_REVIEW.md` and — for the proposal layer —
`docs/security/LLM_THREAT_MODEL.md`. Executed attacks: `docs/red_team/` and
`docs/verification/LLM_VERIFICATION_REPORT.md`.

## What ORIGIN protects
- **Secrets**: read from the environment only, never stored or logged; all log
  strings pass through a redactor.
- **Research integrity**: LLM output and ingested documents are untrusted data.
  They can propose; they cannot become evidence, facts, or graph relations.
- **Host resources**: experiment subprocesses run under CPU/memory/file-size/
  process rlimits, a wall-clock timeout, output caps, and a scrubbed
  environment. Designs exceeding policy are rejected before any process starts.
- **State**: atomic checkpoint writes with backup rotation; corrupt checkpoints
  fail loudly instead of silently truncating history.

## What ORIGIN does NOT protect against (v1.0)
1. **Network access from experiment subprocesses** — no namespace isolation is
   available unprivileged. Only audited in-repo domain templates are executed.
2. **Filesystem reads by experiment subprocesses** — they run as your user.
3. **A determined local attacker** — state is not signed or tamper-evident.
4. **Anything ORIGIN never does**: it does not fetch the web, install packages,
   call shells, or execute LLM-authored code.

## Autonomy

Autonomous operation adds a chooser, not a capability: it selects among actions
the engine already permits, and each still passes its own gate. Live web and
live LLM access are opt-in per run and shown in the plan before they execute.
One mission has one writer, enforced by an atomic lease that is never stolen
automatically. A crash mid-action is recorded as `interrupted` — ORIGIN does not
guess whether it completed. See `docs/security/AUTONOMY_THREAT_MODEL.md`.

## Operating rules
- Run missions as an unprivileged user, ideally inside a container.
- Treat any new domain plugin as production code: its templates are the *only*
  thing ORIGIN executes.
- Never paste secrets into mission questions or ingested documents — both are
  persisted in plain text inside the project directory.
- Do not use ORIGIN for medical, legal, financial, or safety-critical
  conclusions. It is a computational-experiment engine.
