# ORIGIN v1.5 — Reproducibility

## Environment — what was actually tested

| Target | Status | Evidence |
|---|---|---|
| CPython 3.10.20 / 3.11.15 / 3.12.3 / 3.13.13 / 3.14.4, Linux x86-64 (Ubuntu 24.04) | **Tested — full suite passes** | `docs/verification/RELIABILITY_AND_PORTABILITY_REPORT.md` §2 |
| macOS (any version) | **Untested.** POSIX-only code, expected to work — not verified | — |
| Windows | **Unsupported.** Requires `resource` rlimits + `os.setsid()`; fails with an explicit message naming WSL2/Linux/macOS | guard not executed on Windows |
| PyPy / non-x86-64 | **Untested** | — |

- **Zero third-party dependencies.** No `pip install` is required, for running
  or for testing.
- Experiment confinement requires POSIX.

Reproduce the matrix yourself (any interpreter manager works; this is what the
verification run used):

```bash
uv python install 3.10 3.11 3.13 3.14
for V in 3.10 3.11 3.12 3.13 3.14; do
  find . -name "__pycache__" -type d -exec rm -rf {} +
  python$V -m unittest discover -s tests
done
```

## From clone to dossier
```bash
unzip origin-v1.4.zip && cd origin-project
python -m unittest discover -s tests -v          # 186 tests, ~65 s
python -m origin init "demo question" --dir runs/demo --profile fast
python -m origin run --dir runs/demo
python -m origin status --dir runs/demo
python -m origin report --dir runs/demo
python -m origin html --dir runs/demo            # reports/mission_control.html
```

## Reproduce the flagship mission exactly
```bash
python -m origin init "Under what input distributions and sizes does a hybrid \
merge/insertion sorting strategy outperform predefined baselines without \
violating correctness, and what insertion cutoff is optimal per regime?" \
  --dir runs/flagship --profile flagship --max-experiments 100 \
  --compute-minutes 40 --brain mock
python -m origin run --dir runs/flagship
```
Deterministic across machines: hypothesis set, experiment designs, seeds,
input data, correctness verdicts, and (barring ties within timing noise) the
prediction verdicts. **Not** deterministic: wall-clock timings, and therefore
low-margin rankings — this is why replay uses a tolerance and why noisy
evidence is strength-discounted.

## What is recorded for every experiment
`experiments/exp_*/` contains `spec.json` (complete design incl. seed, sizes,
trials, timeout), `run.py` (the exact self-contained code executed — it embeds
the algorithm sources), `result.json` (per-cell correctness, mean, stdev,
trials), and `stdout.log` (truncated at 256 KB).

Each `run.py` is independently executable:
```bash
cd runs/flagship/experiments/exp_xxxx && python run.py
```

## Portability: a mission is usable wherever its files are

Artifact references are stored **root-relative**, so a project can be copied,
archived, or unpacked anywhere and remains valid *using only its own files*:

```bash
cp -r examples/flagship_run /tmp/relocated_mission
python -m origin verify --dir /tmp/relocated_mission
python -m origin replay --dir /tmp/relocated_mission --exp exp_aa415f5a05
```

Both succeed; and a copy that is missing its own artifacts now **fails**
verification instead of silently reading the original location (that was defect
P-1 — see the verification report). Projects written by ORIGIN ≤ 1.0 with
absolute paths are migrated automatically on load; to rewrite them on disk:

```bash
python tools/normalize_paths.py path/to/mission            # idempotent
python tools/check_artifacts_portable.py .                 # CI guard: exit 1 on any leak
```

## Replay: what it certifies, and what it does not

```bash
python -m origin replay --dir runs/flagship --exp exp_xxxx \
    [--tolerance 0.5] [--noise-floor-ms 5] [--strict]
```

Re-executes the stored code+config in a temporary directory under the same
sandbox policy and compares every `(algorithm, regime, n)` cell.

**Asserted by default** (host-independent, seed-driven):
- every stored measurement cell is reproduced;
- per-cell correctness matches exactly.

**Reported, not asserted** (properties of the host, not of the experiment):
- wall-clock timing deviations beyond `--tolerance` and the noise floor;
- ranking agreement per regime×size group, and any decisive inversions.

`--strict` promotes both to failures — use it only on dedicated, unloaded
hardware. On a shared or single-core machine the default verdict is stable
while `--strict` is not: measured on a 1-vCPU host, the same experiment gave
FAIL/PASS/PASS/FAIL/PASS under timing assertions and 5/5 PASS after the change.

Verified during this engagement: `exp_f53e0d9748` (flagship sweep, seed
20260809, 16 cells) and `exp_aa415f5a05` (flagship benchmark, 60 cells) — both
PASS, including from a relocated copy and from a fresh archive extraction.

## Interruption, resume, and crash recovery

A checkpoint is written after every controller step. Exact commands:

```bash
python -m origin run --dir runs/m --steps 2     # stop early -> PAUSED
python -m origin run --dir runs/m               # resume (CLI or library API)
python -m origin verify --dir runs/m            # always safe to run afterwards
```

Guarantees that were tested (see verification report §5), not just designed:

| Situation | Behaviour |
|---|---|
| `--steps N`, or Ctrl-C | mission is `PAUSED`, checkpointed, resumable; exit 130 for Ctrl-C |
| `SIGKILL` mid-experiment | last per-step checkpoint is authoritative; resume completes the mission with no lost or duplicated experiments/events |
| `state.json` corrupt | automatic recovery from `state.json.bak`, `recovered_from_backup` flag set |
| `state.json` missing but backup intact (crash inside the save window) | recovered from the backup |
| `state.json` structurally invalid (e.g. truncated to `{}`) | falls through to the backup rather than raising |
| both checkpoints unusable | `CheckpointCorrupted`, exit 2, pointing at the intact `logs/` and `experiments/` |
| torn final line in `logs/events.jsonl` | line skipped, history still readable, counted and reported by `verify` |
| experiment artifacts on disk with no checkpoint record | reported by `verify`; adopted as `interrupted` on the next `run` |

Recovery is idempotent: resuming twice, or reconciling twice, changes nothing.

## Reproducing evidence acquisition

Retrieval is reproducible in the sense that matters for provenance: the source
record stores the canonical URL, the HTTP status, the content type and the
sha256 of the exact bytes received, plus a cached copy of the extracted text.
Re-retrieving later and comparing hashes tells you whether the source changed.

```bash
# fully deterministic, no network
python tools/web_evidence_demo.py --dir runs/evidence_demo --mode fixture

# live, bounded to approved hosts
python tools/web_evidence_demo.py --dir runs/evidence_demo --mode live

# what was retrieved, and with what provenance
python - <<'PY'
import json
from origin.state import ResearchState
st = ResearchState.load("runs/evidence_demo")
for s in st.sources.values():
    if s.kind != "web_document":
        continue
    print(s.id, s.canonical_url, s.http_status, s.content_hash[:16])
    print("  reliability", s.reliability, "because",
          [b.get("reason") for b in s.reliability_basis])
for c in st.claims.values():
    print(c.id, c.status.value, c.claim_type, "offset", c.passage_offset)
    print("  ", c.text[:90])
PY
```

**What is not reproducible:** the content of a live page. Web documents change
and disappear; the stored hash and cached text are what ORIGIN can guarantee
about what it saw, at the time it saw it. Fixture mode exists so the pipeline
itself stays byte-for-byte deterministic in tests and demos.

## Reproducing an autonomous run

The autonomy demo is fixture-only and clock-injected, so it is deterministic:

```bash
python tools/autonomy_demo.py --dir runs/autonomy_demo
python -m origin verify --dir runs/autonomy_demo
cat runs/autonomy_demo/autonomy/demo_report.json
```

What is reproducible: the work items created, the order the policy chooses
them in (ties break on `(-priority, cost, created_at, id)`), the backoff
durations, and the fact that no completed item is ever re-run. Identifiers
(`wi_*`, `hyp_*`) are random per run by design; the *structure* repeats.

To inspect any autonomous mission afterwards:

```bash
python -m origin autonomy status --dir runs/m     # queue, lease, budgets, stop reason
cat runs/m/autonomy/decisions.jsonl               # every choice, with what it beat
cat runs/m/autonomy/state.json                    # durable queue + counters
```

## Inspecting how a conclusion was reached
1. `reports/dossier.md` §7 (hypotheses + ledgers), §16 (prediction ledger),
   §17 (falsification attempts), §18 (budget + stop reason).
2. `reports/timeline.md` — every event in order.
3. `research_state/*.json` — machine-readable per-type views.
4. `state.json` → `confidence_history` — every status/confidence change with a
   reason.
5. `python -m origin verify --dir …` — cross-checks references, on-disk
   artifacts, duplicate events, orphaned experiment directories, and absolute
   path references. Exit 0 = consistent, 1 = problems listed, 2 = checkpoint
   unloadable or no project at that path.
