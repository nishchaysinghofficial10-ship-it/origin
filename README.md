# Flagship evaluation artifacts

This directory is **not** a single ORIGIN mission — `origin verify --dir .` will
correctly report that there is no project here. It holds the evaluation as a
whole:

```
PREREGISTRATION.json      written before any workflow ran
EVALUATION_RESULTS.json   the machine-readable three-way comparison
baseline/                 workflow A — benchmark once, report winners
proposal_only/            workflow B — proposals only, nothing tested
origin_full/              workflow C — the full research loop  <- verify THIS
```

Verify the missions individually:

```bash
python -m origin verify --dir examples/final_flagship_mission/origin_full
python -m origin report --dir examples/final_flagship_mission/origin_full
```

Read `docs/reports/FLAGSHIP_EVALUATION.md` for the analysis. The headline: the
baseline workflow named an incorrect candidate as the winner on three of four
topologies; the full loop named zero.
