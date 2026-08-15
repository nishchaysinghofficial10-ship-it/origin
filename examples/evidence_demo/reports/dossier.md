# ORIGIN Research Dossier

Generated: 2026-08-13 19:42:28  |  ORIGIN v2.0.0  |  domain: `algobench`

## 1. Research question

> What source-backed conditions are commonly associated with algorithmic performance tradeoffs, and which of those claims can ORIGIN test in its own controlled benchmark domain?

## 2. Initial assumptions


## 3. Existing knowledge (seeded claims)

- **[SPECULATION]** It has supernatural performance on many
kinds of partially ordered arrays (less than lg(N!) comparisons needed, and
as few as N-1), yet as fast as Python's previous highly tuned samplesort
hybrid on random arrays. (confidence 0.25)
- **[SPECULATION]** In a nutshell, the main routine marches over the array once, left to right,
alternately identifying the next run, then merging it into the previous
runs "intelligently". (confidence 0.25)
- **[SPECULATION]** Everything else is complication for speed, and some
hard-won measure of memory efficiency. (confidence 0.25)
- **[SPECULATION]** Comparison with Python's Samplesort Hybrid
------------------------------------------
+ timsort can require a temp array containing as many as N//2 pointers,
  which means as many as 2*N extra bytes on 32-bit boxes. (confidence 0.25)
- **[SPECULATION]** It can be
  expected to require a temp array this large when sorting random data; on
  data with significant structure, it may get away without using any extra
  heap memory. (confidence 0.25)
- **[SPECULATION]** Python lists have a built-in :meth:`list.sort` method that modifies the list
in-place. (confidence 0.25)
- **[SPECULATION]** There is also a :func:`sorted` built-in function that builds a new
sorted list from an iterable. (confidence 0.25)
- **[SPECULATION]** A simple ascending sort is very easy: just call the :func:`sorted` function. (confidence 0.25)
- **[SPECULATION]** You can also use the :meth:`list.sort` method. (confidence 0.25)
- **[SPECULATION]** Another difference is that the :meth:`list.sort` method is only defined for
lists. (confidence 0.25)

## 4. Evidence map (knowledge graph)


## 5. Contradictions

- None detected across experiments in this run.

## 6. Knowledge gaps

- Scaling behavior beyond n=128 is untested (asymptotic crossovers may differ).
- Memory usage and comparison/move counts were not measured (wall time only).
- Adversarial input patterns (sawtooth, organ-pipe, quicksort-killer) are untested.
- Only one machine/interpreter was used; hardware sensitivity is unknown.
- Stability of the sorts (equal-key ordering) was not evaluated.

## 7. Hypotheses (competing pool, with evidence ledgers)

## 8. Experiments


## 9. Results

## 10. Failed approaches (failure log)

- No failed predictions or failed runs in this investigation.

## 11. Decision history


## 12. Current conclusions

## 13. Confidence and cautions

- No cautions recorded.

## 14. Novel findings

- None this run.

## 15. Remaining questions & recommended next investigations

- (none recorded)

## 15b. Measurement environment and scope of performance claims

- Environment metadata was not recorded for these experiments (result schema v1); timings cannot be attributed to a specific interpreter or machine.

**Every performance statement in this dossier is scoped to:** the machine and interpreter above; the input regimes ['random', 'nearly_sorted', 'reversed', 'few_unique']; the input sizes [64, 128]; 5 trials per measurement cell; and pure-Python implementations of the listed algorithms. Nothing here is a claim about these algorithms in general, in another language, at other input sizes, or on other hardware.

Comparisons are only called decisive when the separation exceeds 3x the combined standard error of the two means AND at least 10% of the faster mean, with at least 5 trials on both sides. Everything else is recorded as INCONCLUSIVE — not as a win, and not as a refutation.

## 16. Prediction ledger

| Hypothesis | Prediction | Check | Outcome | Basis |
|---|---|---|---|---|

`inconclusive` means the measurement could not resolve the question at this trial count — it is neither support nor refutation.

## 16b. LLM proposal ledger

- No LLM proposals were offered in this mission (brain: `none`).

## 17. Falsification attempts (critic attacks)

- No falsification attempts this run.

## 18. Budget ledger & stop reason

- Experiments: 0/12
- Compute: 0.0s / 1800s
- Active runtime (controller): 0.0s (no wall-time cap)
- Provider calls: 0 (uncapped)
- Retries: 0/8
- **Stop reason**: (mission still active)

## 19. Threats to validity

- Single machine, single CPython version: absolute timings will not transfer; only within-run rankings are meaningful, and only at the tested sizes.
- Wall-clock time only: no comparison counts, memory, or cache metrics. A ranking here is a ranking of *this implementation on this host*, not of the algorithms as such.
- Trial count (5 per cell) supports the conservative separation rule used here, not a formal hypothesis test; no p-values are computed or implied.
- Timing noise: evidence strength is capped when winner stdev/mean > 0.30, but low-margin rankings can still flip between seeds (observed as recorded contradictions).
- Scope: falsification probes cover boundary sizes (2x) and two unseen regimes; conclusions say nothing beyond that envelope.
- Knowledge-graph `fastest_on` relations are size-agnostic by design in v1.0; scale-dependent flips appear as contradictions rather than conditioned relations.

## Appendix — reproducibility

- Recreate this mission: `python -m origin init "<question>" --dir <new_dir> --profile <profile>` then `python -m origin run --dir <new_dir>`
- Replay any experiment from stored metadata: `python -m origin replay --dir <this_dir> --exp <exp_id>`
- Verify state consistency: `python -m origin verify --dir <this_dir>`
- Full machine-readable state: `state.json`, browsable views in `research_state/`
- Every experiment's generated code + raw results: `experiments/exp_*/` (each `run.py` is self-contained and re-runnable)
- Append-only event log: `logs/events.jsonl` — rendered as `reports/timeline.md`
- Budget consumed: 0/12 experiments, 0.0s compute
