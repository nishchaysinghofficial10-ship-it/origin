# ORIGIN v1.2 — Performance Validity Report

Engagement: make ORIGIN's performance measurement and experiment replay
scientifically defensible. Every result below was produced by the command shown
above it, on the host described in §0. Specification of the rules is in
`PERFORMANCE_REPRODUCIBILITY.md`; this document is the evidence.

---

## 0. Environment

```
$ uname -a
Linux 6.18.5-fc-v20 #1 SMP PREEMPT_DYNAMIC x86_64 GNU/Linux
$ cat /etc/os-release | head -1
PRETTY_NAME="Ubuntu 24.04.4 LTS"
$ python3 -VV
Python 3.12.3 (main, Mar  3 2026, 12:15:18) [GCC 13.3.0]
$ nproc
1
```

**One core, shared virtualised host.** That is not an ideal benchmarking
machine, and it is precisely why this engagement was needed: it makes timing
noise impossible to ignore.

---

## 1. Audit of the pre-existing measurement path

| Component | State before v1.2 | Problem |
|---|---|---|
| `result.json` | `{"rows": [{algorithm, regime, n, correct, mean_s, stdev_s, trials}]}` | No per-trial samples, no median, no SEM, no environment, no provenance digests. A mean and a population stdev cannot be re-analysed later |
| Runner (`RUNNER_TEMPLATE`) | timed each cell, asserted `out == sorted(data)`, discarded everything else | Correctness existed only as a boolean the runner asserted about itself; a replay could not verify inputs or outputs independently |
| Replay | compared means with a relative tolerance + absolute floor; ranking check by argmin ordering | Timing was the verdict. No significance rule, no environment awareness, no code/input/output integrity |
| `_eval_prediction` | pure margin comparison (`mean_a` vs `mean_b`) | A 2 % difference on 3 trials became "confirmed"; noise became findings |
| Sweep analysis | reported `argmin` cutoff as "the optimum" | Ignored that neighbouring cutoffs were indistinguishable |
| Dossier | winners, margins, "threats to validity" prose | No environment, no trial count in claims, no inconclusive outcome class |
| Trials | fast 2, standard 3, flagship 3 | Below any threshold at which a spread statement is meaningful |

Nothing in the pre-existing path was *wrong about correctness* — inputs, seeds,
code and configurations were already reproduced exactly. The defect was that
performance conclusions were being drawn at a precision the measurements could
not support.

---

## 2. What changed

1. **Result schema v2** (`origin/domains/algobench.py` runner template): per-trial
   `samples`, `median_s`, `sem_s`, `min_s`; `input_digest` and `output_digest`
   per cell; `code_digest` of the runner itself; a full `environment` block;
   the resolved `config`; and a fixed `reference_workload_s` micro-benchmark for
   host-speed comparison. Version-tagged `schema_version: 2`.
2. **`origin/stats.py`** — conservative comparison rules (≥5 trials both sides,
   separation > 3×(SEM+SEM), margin ≥ 10 %), plus `indistinguishable_set()` for
   reporting ties honestly. No p-values.
3. **`origin/replay.py`** — the comparison engine, extracted from the CLI so it
   is unit-testable without spawning processes. Implements the three tiers and
   the decisive-inversion rule, including the environment gate.
4. **Analysis is significance-gated** — `fastest_on`, `slowest_on`, `beats`,
   `within_pct_of_best`, `lowest_mean_rel_stdev` and `never_fastest` can now
   return `inconclusive` with a reason. Inconclusive evidence is stored at
   strength ≤ 0.2 and joins neither the supporting nor the contradicting ledger.
5. **Sweeps report tie sets** — the optimum plus every setting statistically
   indistinguishable from it; a sweep prediction whose interval cannot be
   resolved returns inconclusive.
6. **Trial counts raised** — fast 2→5, standard 3→7, flagship 3→7, so a
   significance claim is arithmetically possible at all.
7. **Dossier §15b** — measurement environment, reference workload range, an
   explicit scope paragraph, and the decisiveness rule in plain language; the
   prediction ledger gained a "Basis" column carrying the actual reason.

---

## 3. Exact reproducibility is strict (tier 1)

### 3.1 Correctness mismatch fails, whatever the timing settings

```
$ python3 -m origin replay --dir /tmp/ctl/wrong --exp exp_a7115d9073 \
      --tolerance 100 --noise-floor-ms 100000
  FAIL ('hybrid_c8', 'random', 4096): correctness False -> True
REPLAY FAIL — see the FAIL lines above.
exit=1
```

The tolerance was set to 10 000 % and the noise floor to 100 seconds; the
correctness gate is not reachable from timing configuration.

### 3.2 An altered stored output fails

```
$ python3 -m origin replay --dir /tmp/ctl/tamper --exp exp_a7115d9073
  FAIL ('hybrid_c8', 'reversed', 4096): sorted output changed
       (digest tampered00000000 -> abea6e1b5dccd910)
REPLAY FAIL — see the FAIL lines above.
exit=1
```

Equivalent gates exist for changed inputs (`input_digest`), changed experiment
code (`code_digest`), missing cells, and extra cells
(`tests/test_performance_repro.py::TestReplayTiers`).

### 3.3 Missing artifacts fail honestly

`test_missing_artifact_fails_replay_honestly` deletes `result.json` from one
mission and `run.py` from another; both replays exit 1 with a message naming the
missing file, rather than reporting a pass on partial data.

---

## 4. Timing variation does not create false failures (tier 3)

A uniform 4× timing shift was injected into a stored flagship sweep result —
digests and correctness untouched, so nothing about the science changed:

```
$ python3 -m origin replay --dir /tmp/ctl/noise --exp exp_a7115d9073
Exact reproducibility: 16 cells compared; correctness verdicts must match exactly;
  16 input digests and 16 output digests verified; experiment code verified.
Environment: CPython 3.12.3 on Linux/x86_64, 1 CPU(s); host speed ratio 0.98x …
Timing: median deviation 306%, max 347% (absolute values are host-specific and
  are never asserted).
Ordering: 2/4 regime×size groups identical; 0 decisive inversion(s), 0 inconclusive change(s).
  info  timing ('hybrid_c64','reversed',4096): mean 1.83ms -> 7.79ms …
REPLAY PASS — exact reproducibility holds …
exit=0

$ python3 -m origin replay --dir /tmp/ctl/noise --exp exp_a7115d9073 --strict
exit=1
```

A 306 % median timing deviation with identical inputs and outputs is a statement
about the host, and the default verdict says so. `--strict` still exists for
controlled hardware and does fail.

---

## 5. A decisive ranking inversion is surfaced (tier 2)

`insertion_sort` cells in a stored flagship benchmark were rewritten to be 20×
faster, making it decisively the fastest in every group — a claim the replay
then contradicts decisively:

```
$ python3 -m origin replay --dir /tmp/ctl/invert --exp exp_819300a3a7
Ordering: 4/12 regime×size groups identical; 19 decisive inversion(s), 0 inconclusive change(s).
  WARN decisive inversion: few_unique@n=256: insertion_sort was decisively faster
       than shell_sort (+383%, gap 0.13ms > required 0.03ms) but is decisively
       slower on replay (+326%)
exit=0                      # reported, not asserted, on a shared host

$ python3 -m origin replay --dir /tmp/ctl/invert --exp exp_819300a3a7 --strict
  FAIL decisive inversion: few_unique@n=256: insertion_sort was decisively faster …
exit=1
```

Each line states the margin, the observed separation, and the separation that
was required — so a reader can check the call rather than trust it.

Counter-cases (unit-tested, `TestReplayTiers`): a 4 % reordering is **not** an
inversion (`margin_below_floor`); a 10× reordering at 3 trials is **not** an
inversion (`insufficient_trials`); an inversion across different Python versions
is **not** asserted even under `--strict`.

---

## 6. Flagship mission rerun under the new rules

```
$ python3 -m origin init "Under what input distributions and sizes does a hybrid
  merge/insertion sorting strategy outperform predefined baselines without
  violating correctness, and what insertion cutoff is optimal per regime?" \
  --dir examples/flagship_run --profile flagship --max-experiments 100 \
  --compute-minutes 60 --brain mock
$ python3 -m origin run --dir examples/flagship_run
… STOP REASON: no high-value next experiment remained
wall seconds: 220
```

14 experiments (3 benchmark, 1 sweep, 5 replication, 5 falsification), 8
hypotheses, 22 evidence items, 219.1 s compute, 151 events, 14 decisions, 14
recorded confidence changes, 7 trials per cell.

**Prediction outcomes: 9 confirmed, 2 refuted, 2 inconclusive.**

| Hypothesis | v1.1 result | v1.2 result |
|---|---|---|
| Insertion fastest on nearly-sorted / slowest on random | accepted with scope | accepted with scope (unchanged) |
| Merge fastest on random | rejected | rejected (unchanged) |
| Quick within 25 % of best on random | accepted with scope | accepted with scope |
| Heap most consistent, never fastest | accepted with scope | accepted with scope |
| Shell beats insertion on random (LLM-proposed) | accepted with scope | accepted with scope |
| Heap beats shell on reversed (LLM-proposed) | rejected | rejected |
| Hybrid (cutoff ≤32) beats merge sort | accepted with scope | accepted with scope |
| **Cutoff optimum lies in [16,64]** | **confirmed → accepted** | **INCONCLUSIVE → WEAKENED** |

The last row is the point of the engagement. The measured claim now reads:

> Hybrid insertion-cutoff optima at n=4096 (7 trials, CPython 3.12.3 on
> Linux/x86_64): random=16 (indistinguishable from [8, 32]), nearly_sorted=64,
> reversed=8, few_unique=16 (indistinguishable from [8, 32])

Because cutoffs 8, 16 and 32 cannot be separated at 7 trials, "the optimum lies
in [16, 64]" is not resolvable, and the hypothesis was downgraded rather than
confirmed. A second caution was raised automatically:

> Regime 'few_unique' at n=4096: quick_sort has the lowest mean but is not
> statistically separable from shell_sort at 7 trials — no winner is claimed.

Verification and replay of the regenerated mission:

```
$ python3 -m origin verify --dir examples/flagship_run
State verified: counts, references, experiment artifacts and event log are consistent.

$ python3 -m origin replay --dir examples/flagship_run --exp exp_a7115d9073
Exact reproducibility: 16 cells compared; … 16 input digests and 16 output
  digests verified; experiment code verified.
Environment: CPython 3.12.3 on Linux/x86_64, 1 CPU(s); host speed ratio 0.96x …
Timing: median deviation 2%, max 18%.
Ordering: 2/4 regime×size groups identical; 0 decisive inversion(s).
REPLAY PASS
exit=0
```

---

## 7. Backward compatibility with schema-1 results

The shipped v0.1-era demo mission still replays; the report states exactly which
checks were unavailable instead of counting them as passes:

```
$ python3 -m origin replay --dir examples/demo_run --exp exp_defeaebae2
Exact reproducibility: 32 cells compared; … 0 input digests and 0 output digests
  verified; experiment code unavailable.
Note: stored result uses schema v1: no per-trial samples, digests or environment
  were recorded, so input/output equality and significance testing are
  unavailable for it (means and trial counts are still compared)
REPLAY PASS
exit=0
```

No migration is performed on stored results: an old result is read as what it
is. New experiments write v2. `test_legacy_schema1_payload_still_compares` and
`test_legacy_rows_without_samples_still_summarize` lock this in.

---

## 8. Test suite

```
$ python3 -m unittest discover -s tests
Ran 81 tests in 51.727s
OK
```

| Module | Tests | Focus |
|---|---:|---|
| `test_core` | 7 | budgets, graph, persistence, end-to-end mission |
| `test_lifecycle` | 7 | transitions, migration, pause/resume, cancel |
| `test_reliability` | 11 | interruption, checkpoint recovery, orphans, replay |
| `test_portability` | 12 | relocation, archives, absolute paths, replay stability |
| `test_sandbox` | 6 | confinement policy and limits |
| `test_brain` | 7 | LLM proposal validation, redaction, budgets |
| `test_evidence_redteam` | 7 | untrusted ingestion, red-team scenarios |
| **`test_performance_repro`** | **25** | **schema v2, statistics, replay tiers, migration, dossier scoping** |

Support matrix re-run at this commit — **81 tests, `OK` on every interpreter**:
CPython 3.10.20 (64.2s), 3.11.15 (52.9s), 3.12.3 (51.4s), 3.13.13 (57.4s),
3.14.4 (42.7s), all on Ubuntu 24.04 x86-64.

The 25 new tests cover every item the brief required: replay after relocation;
correctness change fails; missing artifact fails; ordinary timing noise does not
fail; deliberate decisive inversion is surfaced; environment metadata is stored
(and carries no host identity); the dossier distinguishes correctness from
timing variability.

---

## 9. Limitations — what this phase did not achieve

1. **`--strict` has never run on quiet hardware.** It is exercised against
   injected and synthetic data only. On a dedicated benchmarking host its
   failure rate is unknown.
2. **No formal statistical inference.** The rule is conservative by
   construction and will miss real effects (type II errors). It reports
   separations, not confidence levels, and never a p-value.
3. **Wall-clock only.** No comparison counts, allocation counts, or cache
   metrics were added, so rankings remain properties of an implementation on a
   host, not of algorithms.
4. **The reference workload is a single micro-benchmark** (sorting 20k floats).
   It captures gross host speed, not memory bandwidth or cache behaviour, and
   should not be used to normalise timings quantitatively.
5. **Trial counts are still modest** (5–7). Raising them raises confidence and
   cost linearly; the flagship at 7 trials takes 220 s of compute on one core.
6. **Cross-machine reproduction has not been performed.** Everything in this
   report is single-host. The environment gate is implemented and unit-tested
   with synthetic environments, but no second physical machine was available.
7. **The significance rule is applied at `n_top` only** for most prediction
   types; smaller sizes in the same experiment inform the tables but not the
   verdicts.
