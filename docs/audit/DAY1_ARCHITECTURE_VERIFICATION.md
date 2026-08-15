# DAY 1 — Architecture Verification

How each mapped stage was verified (inspection + execution, not docs):

- **State/persistence**: read `state.py`; ran roundtrip test; hand-loaded demo
  `state.json`; confirmed enums rehydrate to typed objects.
- **Controller order**: read `controller.step()`; cross-checked against demo
  `logs/events.jsonl` ordering (planned → hypothesis×4 → decision →
  experiment_started → … → critic_review → synthesis).
- **Experiment isolation**: read `experiments.py` — `subprocess.run([sys.executable,
  runner.name], cwd=exp_dir, timeout=…)`. Confirmed NO rlimits / env scrub /
  output caps → inventory classifies sandbox claim as overclaim.
- **Predictions**: read check-evaluator in `algobench.analyze`; matched demo
  dossier §7 verdicts to `result.json` numbers for exp_defeaebae2 (quick_sort
  fastest on random @1600, 60% margin → H2 refuted). Consistent.
- **Replication independence**: read `replication_design` (seed+1000, max size
  only); demo has 3 separate replication experiment dirs.
- **Contradictions**: functional predicate `fastest_on` conflict logic in
  `graph.py`; demo's 2 contradictions correspond to real cross-seed flips
  (quick vs hybrid on random / few_unique) — organic, not scripted.
- **Budgets**: read `budget.py`; exhaustion path covered by test; confirmed
  no time/retry/provider ledgers exist.
- **Recovery gap**: fed truncated JSON to `ResearchState.load` in a scratch
  copy → raw `JSONDecodeError` (no safe failure). Confirms MISSING.
