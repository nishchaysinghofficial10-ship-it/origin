# Changelog

All notable changes. Every number here was produced by a command run at the
commit it describes.

## [2.1.1] — 2026-08-15 — verified public patch release

**268 tests**, Ubuntu 24.04, CPython 3.10–3.14. Hosted CI run #2 completed all
seven jobs successfully in 4m35s:
https://github.com/nishchaysinghofficial10-ship-it/origin/actions/runs/31896862103

### Fixed and verified
- Restored the repository's directory hierarchy after the first web upload
  flattened package, test, documentation, example, tool, and workflow files.
- Fixed invalid indentation in two CI workflow script blocks before any tests
  had run; the corrected workflow is YAML-valid and executed successfully.
- The hosted matrix passed the full suite on Python 3.10, 3.11, 3.12, 3.13,
  and 3.14. Separate jobs passed the clean end-to-end mission and portability,
  relocation, replay, archive round-trip, fixture evidence, bounded autonomy,
  and interrupt/resume checks.
- Public version, archive name, release records, and runtime metadata now agree
  on `2.1.1`.

### Deliberately retained limitations
- Live Anthropic provider use remains `UNVERIFIED` until an operator records a
  redacted live-check result. macOS remains untested; Windows is unsupported.

## [2.1.1rc1] — release-evidence reconciliation (not for public release)

### Changed
- The package and archive now identify this candidate consistently as
  `2.1.1rc1` rather than presenting the prior `2.1.0` implementation as a
  fully verified public release.
- README and release entry points now distinguish the 268 test *cases* from a
  fresh passing support-matrix result. Historical v2.0 records remain preserved
  as history and are not reused as evidence for this candidate.

### Outstanding release gates
- A full Linux CPython 3.10–3.14 run, preferably through the included hosted CI
  workflow, must pass and be recorded for this candidate.
- A live Anthropic provider call remains unverified until an operator runs it
  with their own credential and records the redacted summary.
- macOS remains untested; Windows remains unsupported because confinement uses
  POSIX resource limits.

## [2.1.0] — architecture gaps closed, live autonomous retrieval

**268 tests**, CPython 3.10–3.14 on Linux x86-64.

### Added
- **Metric kinds** (`stats.TIMING` / `stats.EXACT`). A domain declares what each
  metric is; exact counts are compared without the timing noise gate, and an
  exact tie is reported as a tie. Closes the first gap the second domain exposed:
  the significance layer previously assumed every metric was timing-shaped.
- **Invalidity as a core concept** (`models.Invalidity`,
  `state.record_invalidity/is_valid/valid_candidates`), with a dossier section
  and `verify()` coverage. Closes the second gap: "this candidate is wrong under
  these conditions" was domain-private, so every new domain re-implemented the
  exclusion. `graphbench` now records the BFS boundary through the core.
- Dossier states which metrics are exact and why those conclusions transfer.

### Verified
- **Live autonomous retrieval.** A bounded autonomous run made a real HTTPS
  request through the full policy stack (HTTP 200, 44,051 bytes, sha256
  `674d514b968e2a9b`, robots `absent`, address-pinned), producing 5 SPECULATION
  claims and 0 evidence items, `verify` clean. Autonomy is no longer
  fixture-only.

## [2.0.0] — 2026-08-11 — first public release

Two research domains, bounded autonomy, safe evidence acquisition, a validated
LLM proposal layer, and a pre-registered evaluation of what the machinery buys.
**261 tests**, CPython 3.10–3.14 on Linux x86-64.

### Added
- **Second research domain** (`graphbench`): single-source shortest paths with
  a machine-independent metric (edge relaxations) and a real correctness
  boundary (`bfs_unit` is correct only on unit weights). Documented the two
  architecture gaps it exposed (`docs/SECOND_DOMAIN.md`).
- **Bounded autonomy** (v1.5): durable schema-validated work items, a
  deterministic policy with append-only decision records, a restart-safe
  scheduler tick, an atomic single-writer mission lease, conservative recovery
  of interrupted work, typed retries with capped backoff, and an `autonomy` CLI
  group. No daemon.
- **Safe web evidence acquisition** (v1.4): https-only policy-restricted
  retrieval, full provenance per source, passage-linked claims capped at
  SPECULATION, visible source conflicts.
- **Live LLM proposal layer** (v1.3): four validated proposal types, an
  append-only proposal audit, typed provider errors. Live network call remains
  **unverified** — no credential was available.
- **Performance validity** (v1.2): result schema v2 (per-trial samples,
  digests, environment), conservative significance rules, three-tier replay.
- **Flagship evaluation**: pre-registered question through three workflows
  (`docs/reports/FLAGSHIP_EVALUATION.md`).
- Release scaffolding: LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY,
  issue/PR templates, CI.

### Fixed
- Absolute artifact paths broke copied/archived missions and made `verify`
  return a false PASS (v1.1).
- Replay treated host timing noise as failure (v1.1).
- Checkpoint recovery: missing primary with a valid backup, structurally
  invalid snapshots, torn event-log lines, orphaned experiments, programmatic
  resume of a paused mission (v1.1).
- `robots.txt` fetched outside the restricted path; unbounded gzip
  decompression; truncated compressed streams returning partial content
  (v1.4.1).
- Every robots failure recorded as `absent`; now only HTTP 404 is
  (v1.4.2).
- Falsification probes converting inconclusive results into confident scope
  claims (v1.0).
- Shared mission config: `create()` held a reference to the global profile
  table, so one mission's edit rewrote defaults for later missions (v1.7).

### Known limitations
No exactly-once guarantee for external actions; no kernel-grade isolation;
no cross-machine timing reproducibility; live LLM call and general-web
retrieval unverified; no daemon, multi-agent coordination, or distributed
execution. Full list in `docs/reports/ORIGIN_AUTONOMY_IMPLEMENTATION_REPORT.md`
and each verification report.
