# DAY 1 — Implementation Inventory (verified against v0.1 baseline)

Method: direct source inspection of all 15 Python files (2,012 LOC) plus actual
execution of the test suite and the shipped demo mission. Nothing below is
taken from documentation claims alone.

| Component | Exists? | Works? | Tested? | Real/Mocked | Files | Classification | Evidence | Notes |
|---|---|---|---|---|---|---|---|---|
| Persistent research state (atomic save, typed reload, per-type views, event log) | yes | yes | yes | real | `origin/state.py` | IMPLEMENTED_AND_VERIFIED | `test_roundtrip_and_resume` ok; demo `state.json` reloads | Atomic tmp+rename; append-only `events.jsonl` |
| Mission/controller state machine | partial | yes | partial | real | `origin/controller.py` | PARTIALLY_IMPLEMENTED | e2e test reaches `complete` | Phases are loose strings; **no transition validation**, no FAILED/CANCELLED, no formal PAUSED |
| Competing hypotheses + ledgers | yes | yes | yes | real | `origin/models.py`, domain | IMPLEMENTED_AND_VERIFIED | 5 hypotheses in demo; e2e asserts pool ≥5 | 4 base + 1 evolved |
| Machine-checkable predictions | yes | yes | yes | real | `models.Prediction`, `algobench.analyze` | IMPLEMENTED_AND_VERIFIED | demo: confirmed/refuted verdicts recorded | Check kinds: fastest_on, slowest_on, within_pct_of_best, beats, lowest_mean_rel_stdev, never_fastest |
| "Sandboxed" experiment execution | partial | yes | partial | real | `origin/experiments.py` | PARTIALLY_IMPLEMENTED | 6 demo experiments ran; failure path exercised | Subprocess + timeout ONLY. **No rlimits, env not scrubbed, no output caps, network not blocked.** "Sandbox" is currently an overclaim |
| Experiment versioning (code + spec + results kept forever) | yes | yes | yes | real | `experiments.py` | IMPLEMENTED_AND_VERIFIED | every `exp_*/run.py` re-runnable; verified manually | No `replay` command / tolerance comparison yet |
| Result analysis (rankings, noise handling, verdicts) | yes | yes | yes | real | `algobench.analyze` | IMPLEMENTED_AND_VERIFIED | demo evidence: 17 items; noise caution logic present | |
| Resource budgets | partial | yes | yes | real | `origin/budget.py` | PARTIALLY_IMPLEMENTED | `test_accounting_and_exhaustion`, `test_budget_stops_research` | Experiments+compute only. **No elapsed-time, retry, or provider-call budgets; no stop-reason reporting** |
| Adversarial critic | partial | yes | partial | real | `origin/critic.py` | PARTIALLY_IMPLEMENTED | demo: replication forced, cautions emitted | Replication + assumption audit + contradiction surfacing exist. **No falsification experiments, no boundary probes, no alternative-hypothesis attack** |
| Independent replication | yes | yes | yes | real | `critic.py`, controller step 4 | IMPLEMENTED_AND_VERIFIED | demo: 3 findings replicated (fresh seeds, separate runs) | Independence = new seed + max size; env/order variation not yet used |
| Knowledge graph + contradiction detection | yes | yes | yes | real | `origin/graph.py` | IMPLEMENTED_AND_VERIFIED | `test_contradiction_detection`; demo flagged 2 real conflicts | No conditions/temporal edges; no visualization |
| Decision ledger | yes | yes | yes | real | `controller._decide` | IMPLEMENTED_AND_VERIFIED | demo dossier §11; e2e asserts decisions >0 | All candidate scores logged |
| Checkpoint / resume | partial | yes | partial | real | `state.py`, CLI `run` | IMPLEMENTED_BUT_UNVERIFIED (mid-run) | resume-after-completion tested | **No mid-run interruption test; corrupted checkpoint = unhandled crash; no backup file** |
| Failure records | yes | yes | yes | real | `state.failures` | IMPLEMENTED_AND_VERIFIED | demo failure log: 2 refuted predictions + (earlier) 10 exec failures | |
| Reports: dossier + timeline + status box | yes | yes | yes | real | `origin/report.py` | IMPLEMENTED_AND_VERIFIED | files in `examples/demo_run/reports/` | No prediction ledger table, no threats-to-validity section, no HTML |
| Deterministic experimentation | yes | yes | yes | real | domain runners | IMPLEMENTED_AND_VERIFIED | fixed seeds; re-ran `run.py` → identical output | Tolerance-based replay comparison missing |
| Live web evidence acquisition | no | — | — | — | — | PLANNED_ONLY | `Source`/`Claim` models exist as landing zone | Build env network is allow-listed to package registries; live web is **not feasible here** |
| LLM integration | no | — | — | — | — | PLANNED_ONLY | ROADMAP Phase 4a | No provider layer of any kind |
| Continuous multi-day scheduling / daemon | no | — | — | — | — | PLANNED_ONLY | pause/resume + `--steps` exist (manual) | |
| Hardened recovery (watchdog, stagnation, corrupted state) | no | — | — | — | — | MISSING | corrupted `state.json` → raw `json.JSONDecodeError` | Verified by inspection of `ResearchState.load` |
| Second research domain | no | — | — | — | — | PLANNED_ONLY | interface exists (`domains/base.py`) | |
| Dashboard | no | — | — | — | — | MISSING | | CLI status box only |
| Evaluation maturity (ORB) | no | — | — | — | — | PLANNED_ONLY | metrics groundwork present | |
