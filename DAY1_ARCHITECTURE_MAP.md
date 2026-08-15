# DAY 1 — Architecture Map (actual, not aspirational)

Verified control flow of the v0.1 baseline. `NOT IMPLEMENTED` marks absent
stages of the v1.0 target pipeline.

```text
User (CLI: init/run/status/report/timeline)
→ Mission                    [project.json + state.json; loose phase strings]
→ Controller                 [step(): plan → hypothesize → investigate → critic → synthesis]
→ Domain (algobench)         [decompose, seed, hypotheses, designs, analyze]
→ Hypothesis                 [competing pool; PROPOSED→UNDER_TEST→PS/WEAK/REJ]
→ Prediction                 [machine-checkable check dicts; verdicts recorded]
→ Experiment                 [generated run.py; subprocess+timeout; versioned dirs]
→ Result                     [result.json → analyze(): evidence, graph, failures]
→ Critic                     [replication enforcement; assumptions; contradictions]
   → Falsification attack    NOT IMPLEMENTED
→ Replication                [fresh seed, separate run, downgrade on instability]
→ Knowledge Update           [graph relations + contradiction records + claims]
→ Next Investigation         [score = importance/(1+evidence)/cost; decision logged]

Evidence acquisition (web/local ingestion)   NOT IMPLEMENTED (models exist)
LLM proposal layer                            NOT IMPLEMENTED
Scheduler/daemon/watchdog/stagnation          NOT IMPLEMENTED (manual pause/resume only)
Corrupted-checkpoint recovery                 NOT IMPLEMENTED
Dashboard                                     NOT IMPLEMENTED (CLI status box only)
Replay-with-tolerance command                 NOT IMPLEMENTED (manual re-run works)
```

Durability substrate (verified): atomic `state.json` writes; append-only
`logs/events.jsonl`; per-type `research_state/*.json` views; experiment dirs
preserved forever.
