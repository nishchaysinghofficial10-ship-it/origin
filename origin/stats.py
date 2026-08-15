"""Conservative statistics for benchmark comparisons (v1.2).

ORIGIN measures wall-clock time on whatever machine it happens to run on.
That makes *absolute* timings non-transferable and *small* differences
meaningless. This module encodes the only performance statements the system is
willing to make, and it is deliberately conservative: when the data cannot
support a call, the answer is `indistinguishable`, never a coin flip.

Design rules (documented in docs/verification/PERFORMANCE_REPRODUCIBILITY.md):

  * A comparison needs a minimum number of trials on BOTH sides
    (`MIN_TRIALS`). Fewer trials => `insufficient_trials`, reported as
    indistinguishable.
  * Separation uses the standard error of the mean, combined by SUM rather
    than in quadrature (`sem_a + sem_b`). That is wider than a Welch interval
    and is chosen because benchmark samples on a contended host are not
    independent draws from a clean normal distribution — we would rather miss a
    real effect than announce a fake one.
  * A separation must also clear a minimum RELATIVE margin (`MIN_REL_MARGIN`),
    so a 0.3% difference never becomes a finding no matter how many trials are
    run.
  * No p-values are reported. With the trial counts ORIGIN can afford, a
    p-value would imply more certainty than the data carries.
"""
from __future__ import annotations

import statistics

MIN_TRIALS = 5          # per side, for any "significant" claim
K_SEM = 3.0             # separation must exceed K_SEM * (sem_a + sem_b)
MIN_REL_MARGIN = 0.10   # ...and at least 10% of the faster mean

# --- metric kinds -----------------------------------------------------------
# v2.1 (gap 7). Until now every metric was assumed to be wall-clock time, so a
# domain with a DETERMINISTIC metric — an operation count, a comparison count —
# had to route around this module to avoid having exact numbers put through a
# noise gate designed for timing. A metric now declares what it is.
TIMING = "timing"     # host-specific, noisy: full significance gate applies
EXACT = "exact"       # deterministic count: any difference is real
METRIC_KINDS = (TIMING, EXACT)

FASTER = "faster"
SLOWER = "slower"
INDISTINGUISHABLE = "indistinguishable"


def summarize(samples: list[float]) -> dict:
    """Descriptive statistics for a list of per-trial timings (seconds)."""
    n = len(samples)
    if n == 0:
        return {"trials": 0, "mean_s": 0.0, "median_s": 0.0, "stdev_s": 0.0,
                "min_s": 0.0, "sem_s": 0.0}
    mean = statistics.fmean(samples)
    stdev = statistics.stdev(samples) if n > 1 else 0.0
    return {
        "trials": n,
        "mean_s": mean,
        "median_s": statistics.median(samples),
        "stdev_s": stdev,                       # sample stdev (n-1)
        "min_s": min(samples),
        "sem_s": stdev / (n ** 0.5) if n > 1 else 0.0,
    }


def row_stats(row: dict) -> dict:
    """Normalize a result row from any schema version into stats fields.

    Schema 2 rows carry per-trial `samples`. Schema 1 rows (ORIGIN <= v1.1)
    carry only mean/stdev/trials — usable, but with a population stdev and no
    median, so they are marked `legacy` and held to the same trial minimum.
    """
    samples = row.get("samples")
    if isinstance(samples, list) and samples:
        s = summarize([float(x) for x in samples])
        s["legacy"] = False
        return s
    trials = int(row.get("trials", 0) or 0)
    stdev = float(row.get("stdev_s", 0.0) or 0.0)
    mean = float(row.get("mean_s", 0.0) or 0.0)
    return {
        "trials": trials,
        "mean_s": mean,
        "median_s": float(row.get("median_s", mean) or mean),
        "stdev_s": stdev,
        "min_s": float(row.get("min_s", mean) or mean),
        "sem_s": (stdev / (trials ** 0.5)) if trials > 1 else 0.0,
        "legacy": True,
    }


def compare_exact(a: float, b: float, *, label_a: str = "a",
                  label_b: str = "b") -> dict:
    """Compare two DETERMINISTIC measurements (counts, not timings).

    No trial minimum, no standard-error gate, no margin floor: those exist to
    stop timing noise becoming a finding, and a count has no noise. Re-running
    the same algorithm on the same generated input yields the same number, so
    a difference of one is a real difference of one. Equality is reported as
    `indistinguishable` because it genuinely is.
    """
    gap = abs(b - a)
    smaller = min(a, b) or 1e-12
    out = {"relation": INDISTINGUISHABLE, "decisive": False, "reason": "",
           "margin": gap / smaller, "gap_s": gap, "required_s": 0.0,
           "trials": (1, 1), "metric_kind": EXACT}
    if a == b:
        out["reason"] = f"exact tie ({label_a} and {label_b} both {a})"
        return out
    out["relation"] = FASTER if a < b else SLOWER
    out["decisive"] = True
    out["reason"] = (f"exact counts, deterministic: {label_a}={a:,} vs "
                     f"{label_b}={b:,}")
    return out


def compare(a: dict, b: dict, *, min_trials: int = MIN_TRIALS,
            k_sem: float = K_SEM,
            min_rel_margin: float = MIN_REL_MARGIN,
            metric_kind: str = TIMING) -> dict:
    """Compare two measured cells, `a` vs `b` (both from `row_stats`).

    `metric_kind=EXACT` routes to `compare_exact`: a domain with a
    deterministic metric declares that here instead of working around it.

    Returns a verdict dict:
        relation : faster | slower | indistinguishable  (a relative to b)
        decisive : bool   — passed every conservative gate
        reason   : short machine-readable reason when not decisive
        margin   : relative difference vs the faster mean
        gap_s / required_s : observed separation and the separation required
    """
    if metric_kind == EXACT:
        return compare_exact(a.get("mean_s", 0.0), b.get("mean_s", 0.0))
    ma, mb = a.get("mean_s", 0.0), b.get("mean_s", 0.0)
    gap = abs(mb - ma)
    faster_mean = min(ma, mb) or 1e-12
    margin = gap / faster_mean
    required_sem = k_sem * (a.get("sem_s", 0.0) + b.get("sem_s", 0.0))
    required_margin = min_rel_margin * faster_mean
    required = max(required_sem, required_margin)
    out = {
        "relation": INDISTINGUISHABLE, "decisive": False, "reason": "",
        "margin": margin, "gap_s": gap, "required_s": required,
        "trials": (a.get("trials", 0), b.get("trials", 0)),
        "metric_kind": TIMING,
    }
    if min(a.get("trials", 0), b.get("trials", 0)) < min_trials:
        out["reason"] = (f"insufficient_trials (have "
                         f"{a.get('trials', 0)}/{b.get('trials', 0)}, "
                         f"need {min_trials} each)")
        return out
    if gap <= required_sem:
        out["reason"] = (f"uncertainty_overlap (gap {gap*1000:.3f} ms <= "
                         f"{k_sem:g}x combined SEM {required_sem*1000:.3f} ms)")
        return out
    if margin < min_rel_margin:
        out["reason"] = (f"margin_below_floor ({margin*100:.1f}% < "
                         f"{min_rel_margin*100:.0f}%)")
        return out
    out["relation"] = FASTER if ma < mb else SLOWER
    out["decisive"] = True
    return out


def indistinguishable_set(cells: dict[str, dict], **kw) -> list[str]:
    """Names whose measurement is not decisively slower than the best one.

    `cells` maps a name to a `row_stats` dict. Used for sweep optima so the
    system reports "16 (indistinguishable from 8, 32)" instead of pretending
    the argmin is the answer.
    """
    if not cells:
        return []
    best = min(cells, key=lambda k: cells[k].get("mean_s", float("inf")))
    tied = []
    for name, st in cells.items():
        if name == best:
            tied.append(name)
            continue
        v = compare(cells[best], st, **kw)
        if not v["decisive"]:
            tied.append(name)
    return sorted(tied)
