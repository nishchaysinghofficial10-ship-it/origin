# ORIGIN — Performance Reproducibility

What ORIGIN promises about an experiment it re-runs, and — just as important —
what it refuses to promise. This is the specification; the evidence that the
implementation matches it is in `PERFORMANCE_VALIDITY_REPORT.md`.

---

## 1. Three tiers of reproducibility

```text
TIER 1 — EXACT REPRODUCIBILITY                      asserted in every mode
  Same measurement cells, same correctness verdicts, same input data,
  same sorted output, same experiment code.
  Any difference is a hard replay failure. No timing setting can suppress it.

TIER 2 — STATISTICAL REPRODUCIBILITY                reported always; asserted with --strict
  Do the performance RELATIONSHIPS still hold? Judged only under the
  conservative rule in §3, applied to both the stored and the replayed run.

TIER 3 — ABSOLUTE TIMING VALUES                     never asserted
  Milliseconds belong to a machine, an interpreter, and a moment.
  They are recorded with their environment and reported; they are never a
  pass/fail criterion, because ORIGIN cannot control the host it runs on.
```

The separation exists because ORIGIN's own measurements proved it necessary:
replaying one flagship experiment five times on a single-core container gave
2 failures and 3 passes under the old timing-equality rule, while correctness
and input/output digests were identical every time (see the v1.1 report §4).

---

## 2. Result schema v2

Every experiment writes `result.json` next to the exact `run.py` that produced
it. Schema v2 adds everything needed to tell a real change from noise.

```jsonc
{
  "schema_version": 2,
  "environment": {
    "python_version": "3.12.3", "python_implementation": "CPython",
    "system": "Linux", "release": "…", "machine": "x86_64",
    "processor": "x86_64", "cpu_count": 1,
    "origin_version": "1.2.0",
    "timestamp_utc": "2026-08-10T10:50:18Z",
    "timer": "time.perf_counter", "timer_resolution_s": 1e-09
  },
  "config": { "algorithms": […], "regimes": […], "sizes": […],
              "trials": 7, "seed": 20260809, "origin_version": "1.2.0" },
  "code_digest": "7701eb233f1610dc",        // sha256-16 of run.py itself
  "reference_workload_s": 0.00247,           // fixed micro-benchmark, host speed
  "rows": [{
    "algorithm": "hybrid_c16", "regime": "random", "n": 4096,
    "correct": true, "trials": 7,
    "samples": [0.0047, 0.0046, …],          // every trial, not just a summary
    "mean_s": …, "median_s": …, "stdev_s": …, "sem_s": …, "min_s": …,
    "input_digest":  "ec00bf2e4c2a6429",     // the generated input
    "output_digest": "475d4b36672658f3"      // the sorted result
  }]
}
```

Notes on specific fields:

- **`samples`** — per-trial timings are kept because a mean and a standard
  deviation cannot be re-analysed later; the raw sample can.
- **`input_digest` / `output_digest`** — turn "correct" from a boolean the
  runner asserted into something a replay can *verify independently*. Changed
  inputs or changed results fail replay even when the boolean still says true.
- **`code_digest`** — the runner hashes its own source. Editing a stored
  `run.py` and replaying it is detected.
- **`reference_workload_s`** — sorting 20 000 fixed floats, median of 5. It is
  not part of any hypothesis; it exists so a reader on another machine can put
  the absolute numbers in proportion (`host speed ratio` in replay output).
- **No hostname, username, or path** is recorded. Environment metadata
  identifies the *platform*, not the *machine or person*
  (`test_environment_carries_no_host_identity`).

**Backward compatibility.** Schema-1 results (ORIGIN ≤ v1.1) have no samples,
digests, or environment. They still replay: cell coverage, correctness flags,
means and trial counts are compared, and the report states plainly which checks
were unavailable. Older results are never silently upgraded, and the absence of
a digest is never counted as a passing digest check.

---

## 3. When a performance difference is allowed to count

Implemented in `origin/stats.py`. Every gate must pass:

| Gate | Rule | Why |
|---|---|---|
| Trials | ≥ **5** trials on **both** sides | A 3-trial standard error is not a measurement of anything |
| Separation | gap > **3 × (SEM_a + SEM_b)** | SEMs are summed, not combined in quadrature — deliberately wider than a Welch interval, because contended benchmark samples are not clean independent draws |
| Margin | gap ≥ **10 %** of the faster mean | Stops a 0.3 % difference becoming a finding no matter how many trials are run |

Anything failing a gate is `indistinguishable`, with a machine-readable reason
(`insufficient_trials`, `uncertainty_overlap`, `margin_below_floor`).

**No p-values are reported, ever.** With 5–7 trials on a shared host, a p-value
would communicate a precision the data does not contain. ORIGIN reports the
observed separation, the separation that would have been required, and a
verdict of decisive / not decisive.

### Decisive ranking inversion

The narrowest, strictest claim a replay can make about performance:

```text
A decisive inversion of (A, B) in one regime×size group requires ALL of:
  1. both cells present in both runs, with ≥ 5 trials each;
  2. the STORED run had A decisively faster than B  (all gates in §3);
  3. the REPLAY has A decisively slower than B      (all gates in §3);
  4. both runs came from the same environment
     (python_implementation, python_version, system, machine).
```

If the ordering changed but either side is not decisive, it is reported as an
`inconclusive change` and never fails a replay. If the environments differ, the
comparison is not like-for-like and is downgraded to informational **even under
`--strict`**.

---

## 4. Replay modes

```bash
python -m origin replay --dir <mission> --exp <exp_id>            # default
python -m origin replay --dir <mission> --exp <exp_id> --strict   # quiet host
```

| | default | `--strict` |
|---|---|---|
| Missing / extra cells | **FAIL** | **FAIL** |
| Correctness flag mismatch | **FAIL** | **FAIL** |
| Input or output digest mismatch | **FAIL** | **FAIL** |
| Experiment code changed | **FAIL** | **FAIL** |
| Stored artifact missing (`result.json`, `run.py`, `spec.json`) | **FAIL** | **FAIL** |
| Decisive ranking inversion (same environment) | WARN | **FAIL** |
| Timing deviation beyond tolerance + noise floor | info | **FAIL** |
| Anything in a different environment | info | info |

Tunable: `--tolerance` (relative, default 0.5), `--noise-floor-ms` (default 5),
`--min-trials` (default 5).

Use the default in CI and on shared machines: it asserts exactly the properties
that are host-independent. Use `--strict` on dedicated, unloaded hardware where
timing is a controlled variable.

---

## 5. How this changes what ORIGIN concludes

The same significance rule governs the research itself, not just replay:

- A regime "winner" is only claimed when it is decisively separated from the
  runner-up. Otherwise the dossier records that the top candidates are
  statistically indistinguishable and **no winner is claimed**.
- Predictions can now come back `inconclusive` — neither support nor
  refutation. Inconclusive evidence is stored with strength ≤ 0.2 and counts
  toward neither the supporting nor the contradicting ledger.
- A hypothesis whose predictions were all inconclusive is marked WEAKENED with
  the reason "not resolvable at this trial count", plus a caution telling the
  reader to treat it as untested rather than disproved.
- Parameter sweeps report the optimum **and** every setting statistically
  indistinguishable from it.

This is why the v1.2 flagship rerun downgraded its own cutoff hypothesis: at 7
trials, cutoffs 8, 16 and 32 could not be separated on random input, so the
claim "the optimum lies in [16, 64]" is not resolvable — an honest inconclusive
that the previous, margin-only rule reported as confirmed.

---

## 6. What is still not guaranteed

1. **Cross-machine timing.** Nothing here makes milliseconds portable. The
   reference workload lets you scale, not compare.
2. **Formal statistical inference.** The rule is conservative and defensible,
   not a hypothesis test. It can miss real effects (type II); that trade is
   deliberate.
3. **Wall-clock only.** No comparison counts, allocations, or cache metrics, so
   a ranking is of *this implementation on this host*, not of the algorithm.
4. **Interpreter behaviour** (GC timing, JIT-free CPython) is treated as part
   of the environment, not controlled for.
5. `--strict` has been exercised against synthetic and injected data; it has
   not been run on a dedicated quiet benchmarking host.
