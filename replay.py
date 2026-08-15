"""Replay comparison engine (v1.2).

`origin replay` re-executes a stored experiment from its recorded code and
configuration and compares the new result against the stored one. This module
holds the comparison logic so it can be unit-tested without spawning anything.

What a replay actually guarantees, in three tiers:

  EXACT REPRODUCIBILITY — asserted always, in every mode.
      Same cells, same correctness verdicts, same input digests, same output
      digests, same experiment code. Any difference is a hard failure. No
      timing tolerance can suppress one of these.

  STATISTICAL REPRODUCIBILITY — reported always, asserted only with --strict.
      Do the performance *relationships* still hold? A stored ordering counts
      as overturned only under the conservative rule in `origin.stats`
      (enough trials on both sides, separation beyond 3x the combined SEM, and
      at least a 10% relative margin) applied to BOTH the stored comparison and
      the replayed one. Anything weaker is an "ordering change (inconclusive)".

  NON-TRANSFERABLE VALUES — never asserted.
      Absolute milliseconds belong to a machine, an interpreter, and a moment.
      They are reported with the environment they came from and a host-speed
      ratio derived from a fixed reference workload. If the replay ran in a
      different environment, timing and ordering checks are downgraded to
      informational even under --strict, because the comparison is no longer
      like-for-like.

Backward compatibility: schema-1 results (ORIGIN <= v1.1) have no samples,
digests, or environment block. They still replay; the checks that need those
fields are reported as unavailable rather than silently passing.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import stats

RESULT_SCHEMA_VERSION = 2

# Environment fields that must match for a like-for-like timing comparison.
ENV_KEYS = ("python_version", "python_implementation", "system", "machine")


@dataclass
class ReplayPolicy:
    tolerance: float = 0.5           # relative timing deviation worth reporting
    noise_floor_ms: float = 5.0      # ...and an absolute floor below which we stay quiet
    min_trials: int = stats.MIN_TRIALS
    k_sem: float = stats.K_SEM
    min_rel_margin: float = stats.MIN_REL_MARGIN
    strict: bool = False

    @property
    def stat_kw(self) -> dict:
        return {"min_trials": self.min_trials, "k_sem": self.k_sem,
                "min_rel_margin": self.min_rel_margin}


@dataclass
class ReplayReport:
    hard_failures: list = field(default_factory=list)     # exact-reproducibility breaches
    timing: list = field(default_factory=list)            # informational deviations
    inversions: list = field(default_factory=list)        # decisive ordering reversals
    ordering_changes: list = field(default_factory=list)  # non-decisive reorderings
    notes: list = field(default_factory=list)
    cells_compared: int = 0
    groups: int = 0
    groups_identical: int = 0
    max_rel_deviation: float = 0.0
    median_rel_deviation: float = 0.0
    host_speed_ratio: float | None = None
    env_stored: dict = field(default_factory=dict)
    env_fresh: dict = field(default_factory=dict)
    env_mismatches: list = field(default_factory=list)
    integrity: dict = field(default_factory=dict)

    @property
    def env_matches(self) -> bool:
        return not self.env_mismatches

    def failed(self, policy: ReplayPolicy) -> bool:
        if self.hard_failures:
            return True
        if policy.strict and self.env_matches:
            return bool(self.timing or self.inversions)
        return False


def _key(row: dict) -> tuple:
    return (row["algorithm"], row["regime"], row["n"])


def compare_results(stored: dict, fresh: dict,
                    policy: ReplayPolicy | None = None) -> ReplayReport:
    """Compare a stored result payload against a freshly replayed one."""
    policy = policy or ReplayPolicy()
    rep = ReplayReport()

    # ---- runner-level failure -------------------------------------------
    for name, payload in (("stored", stored), ("replay", fresh)):
        if payload.get("error"):
            rep.hard_failures.append(f"{name} result records a runner error: "
                                     f"{payload['error']}")

    old = {_key(r): r for r in stored.get("rows", [])}
    new = {_key(r): r for r in fresh.get("rows", [])}
    if not old:
        rep.hard_failures.append("stored result contains no measurement rows")
    if not new:
        rep.hard_failures.append("replay produced no measurement rows")

    # ---- tier 1: exact reproducibility ----------------------------------
    integrity = {"cells": 0, "output_digests": 0, "input_digests": 0,
                 "code_digest": "unavailable"}
    for k in sorted(set(new) - set(old)):
        rep.hard_failures.append(f"{k}: cell present in replay but not stored")
    for k, o in old.items():
        n = new.get(k)
        if n is None:
            rep.hard_failures.append(f"{k}: missing in replay")
            continue
        integrity["cells"] += 1
        if bool(o.get("correct")) != bool(n.get("correct")):
            rep.hard_failures.append(
                f"{k}: correctness {o.get('correct')} -> {n.get('correct')}")
        if o.get("input_digest") and n.get("input_digest"):
            if o["input_digest"] != n["input_digest"]:
                rep.hard_failures.append(
                    f"{k}: input data changed (digest {o['input_digest']} -> "
                    f"{n['input_digest']})")
            else:
                integrity["input_digests"] += 1
        if o.get("output_digest") and n.get("output_digest"):
            if o["output_digest"] != n["output_digest"]:
                rep.hard_failures.append(
                    f"{k}: sorted output changed (digest {o['output_digest']} "
                    f"-> {n['output_digest']})")
            else:
                integrity["output_digests"] += 1

    sd, fd = stored.get("code_digest"), fresh.get("code_digest")
    if sd and fd:
        if sd != fd:
            rep.hard_failures.append(
                f"experiment code changed since it was recorded "
                f"(run.py digest {sd} -> {fd})")
        else:
            integrity["code_digest"] = "verified"
    rep.cells_compared = integrity["cells"]
    rep.integrity = integrity

    if stored.get("schema_version", 1) < RESULT_SCHEMA_VERSION:
        rep.notes.append(
            f"stored result uses schema v{stored.get('schema_version', 1)}: no "
            f"per-trial samples, digests or environment were recorded, so "
            f"input/output equality and significance testing are unavailable "
            f"for it (means and trial counts are still compared)")

    # ---- environment ------------------------------------------------------
    rep.env_stored = stored.get("environment", {}) or {}
    rep.env_fresh = fresh.get("environment", {}) or {}
    if rep.env_stored and rep.env_fresh:
        for k in ENV_KEYS:
            if rep.env_stored.get(k) != rep.env_fresh.get(k):
                rep.env_mismatches.append(
                    f"{k}: {rep.env_stored.get(k)!r} -> {rep.env_fresh.get(k)!r}")
    else:
        rep.notes.append("environment metadata unavailable on at least one "
                         "side; treating the comparison as cross-environment")
        rep.env_mismatches.append("environment metadata missing")
    r_old, r_new = stored.get("reference_workload_s"), fresh.get("reference_workload_s")
    if r_old and r_new:
        rep.host_speed_ratio = r_new / r_old

    # ---- tier 2/3: timing and ordering ------------------------------------
    floor_s = policy.noise_floor_ms / 1000.0
    deviations = []
    for k, o in old.items():
        n = new.get(k)
        if n is None:
            continue
        om, nm = o.get("mean_s", 0.0), n.get("mean_s", 0.0)
        rel = abs(nm - om) / max(om, 1e-9)
        deviations.append(rel)
        if rel > policy.tolerance and abs(nm - om) > floor_s:
            rep.timing.append(
                f"{k}: mean {om*1000:.2f}ms -> {nm*1000:.2f}ms "
                f"(rel {rel:.0%} > {policy.tolerance:.0%}, abs "
                f"{abs(nm-om)*1000:.1f}ms > {policy.noise_floor_ms:.0f}ms floor)")
    if deviations:
        deviations.sort()
        rep.max_rel_deviation = deviations[-1]
        rep.median_rel_deviation = deviations[len(deviations) // 2]

    groups: dict[tuple, list[str]] = {}
    for (alg, regime, n) in old:
        groups.setdefault((regime, n), []).append(alg)
    for (regime, n), algs in sorted(groups.items()):
        if any((a, regime, n) not in new for a in algs):
            continue
        rep.groups += 1
        rank_old = sorted(algs, key=lambda a: old[(a, regime, n)].get("mean_s", 0.0))
        rank_new = sorted(algs, key=lambda a: new[(a, regime, n)].get("mean_s", 0.0))
        if rank_old == rank_new:
            rep.groups_identical += 1
            continue
        # Only a reversal that was decisive THEN and is decisive NOW counts.
        for i, a in enumerate(rank_old):
            for b in rank_old[i + 1:]:
                was = stats.compare(stats.row_stats(old[(a, regime, n)]),
                                    stats.row_stats(old[(b, regime, n)]),
                                    **policy.stat_kw)
                if not (was["decisive"] and was["relation"] == stats.FASTER):
                    continue
                now = stats.compare(stats.row_stats(new[(a, regime, n)]),
                                    stats.row_stats(new[(b, regime, n)]),
                                    **policy.stat_kw)
                if now["decisive"] and now["relation"] == stats.SLOWER:
                    rep.inversions.append(
                        f"{regime}@n={n}: {a} was decisively faster than {b} "
                        f"(+{was['margin']*100:.0f}%, gap {was['gap_s']*1000:.2f}ms "
                        f"> required {was['required_s']*1000:.2f}ms) but is "
                        f"decisively slower on replay "
                        f"(+{now['margin']*100:.0f}%)")
                elif now["relation"] == stats.SLOWER:
                    rep.ordering_changes.append(
                        f"{regime}@n={n}: {a}/{b} order flipped but the replay "
                        f"comparison is not decisive ({now['reason'] or 'margin too small'})")
    return rep


def render(rep: ReplayReport, policy: ReplayPolicy, header: str) -> list[str]:
    """Human-readable replay report lines."""
    out = [header]
    integ = rep.integrity
    out.append(
        f"Exact reproducibility: {integ.get('cells', 0)} cells compared; "
        f"correctness verdicts must match exactly; "
        f"{integ.get('input_digests', 0)} input digests and "
        f"{integ.get('output_digests', 0)} output digests verified; "
        f"experiment code {integ.get('code_digest', 'unavailable')}.")
    if rep.env_stored or rep.env_fresh:
        e = rep.env_fresh or rep.env_stored
        out.append(
            f"Environment: {e.get('python_implementation', '?')} "
            f"{e.get('python_version', '?')} on {e.get('system', '?')}/"
            f"{e.get('machine', '?')}, {e.get('cpu_count', '?')} CPU(s)"
            + (f"; host speed ratio {rep.host_speed_ratio:.2f}x vs the stored run "
               f"(reference workload)" if rep.host_speed_ratio else ""))
    if rep.env_mismatches:
        out.append("Environment differs from the stored run — timing and "
                   "ordering are informational only: "
                   + "; ".join(rep.env_mismatches))
    out.append(
        f"Timing: median deviation {rep.median_rel_deviation:.0%}, max "
        f"{rep.max_rel_deviation:.0%} (absolute values are host-specific and "
        f"are never asserted).")
    out.append(
        f"Ordering: {rep.groups_identical}/{rep.groups} regime×size groups "
        f"identical; {len(rep.inversions)} decisive inversion(s), "
        f"{len(rep.ordering_changes)} inconclusive change(s).")
    for note in rep.notes:
        out.append(f"Note: {note}")
    for line in rep.hard_failures[:12]:
        out.append(f"  FAIL {line}")
    for line in rep.inversions[:8]:
        out.append(f"  {'FAIL' if policy.strict and rep.env_matches else 'WARN'}"
                   f" decisive inversion: {line}")
    for line in rep.ordering_changes[:6]:
        out.append(f"  info  {line}")
    for line in rep.timing[:8]:
        out.append(f"  {'FAIL' if policy.strict and rep.env_matches else 'info'}"
                   f"  timing {line}")
    if rep.failed(policy):
        out.append("REPLAY FAIL — see the FAIL lines above.")
    else:
        out.append("REPLAY PASS — exact reproducibility holds: every stored "
                   "cell reproduced with identical correctness"
                   + (", inputs and outputs"
                      if rep.integrity.get("output_digests") else "")
                   + ". Timing and ordering are reported above"
                   + ("" if policy.strict else
                      "; rerun with --strict on a quiet, like-for-like host to "
                      "assert them")
                   + ".")
    return out
