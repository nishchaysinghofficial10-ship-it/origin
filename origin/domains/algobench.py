"""algobench — ORIGIN's first research domain (computer science / algorithms).

Chosen deliberately as the v0.1 domain because success is objectively
measurable: ORIGIN can generate real code, execute it in a sandbox, measure
it, and be *wrong* in ways it can detect.

The domain studies comparison sorting under different input regimes, states
competing falsifiable hypotheses about the candidates, benchmarks them, and
— after round 1 — synthesizes a NEW candidate (a hybrid algorithm) from what
the evidence showed. That last part is hypothesis/algorithm evolution: the
research state produces an artifact that was not in the initial roster.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

from .. import stats as st_
from ..models import (Claim, EpistemicStatus, Evidence, Hypothesis,
                      HypothesisStatus, Prediction, Source, new_id, now)
from .base import ResearchDomain, register

# ============================================================================
# Candidate algorithms (module-level so their source can be embedded verbatim
# into generated, self-contained experiment runners).
# ============================================================================

def insertion_sort(a):
    a = list(a)
    for i in range(1, len(a)):
        key = a[i]
        j = i - 1
        while j >= 0 and a[j] > key:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = key
    return a


def _merge(left, right):
    out = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            out.append(left[i]); i += 1
        else:
            out.append(right[j]); j += 1
    out.extend(left[i:])
    out.extend(right[j:])
    return out


def merge_sort(a):
    a = list(a)
    if len(a) <= 1:
        return a
    mid = len(a) // 2
    return _merge(merge_sort(a[:mid]), merge_sort(a[mid:]))


def quick_sort(a):
    a = list(a)
    stack = [(0, len(a) - 1)]
    while stack:
        lo, hi = stack.pop()
        while lo < hi:
            mid = (lo + hi) // 2
            if a[mid] < a[lo]:
                a[lo], a[mid] = a[mid], a[lo]
            if a[hi] < a[lo]:
                a[lo], a[hi] = a[hi], a[lo]
            if a[hi] < a[mid]:
                a[mid], a[hi] = a[hi], a[mid]
            pivot = a[mid]
            i, j = lo - 1, hi + 1
            while True:
                i += 1
                while a[i] < pivot:
                    i += 1
                j -= 1
                while a[j] > pivot:
                    j -= 1
                if i >= j:
                    break
                a[i], a[j] = a[j], a[i]
            if j - lo < hi - (j + 1):
                stack.append((j + 1, hi))
                hi = j
            else:
                stack.append((lo, j))
                lo = j + 1
    return a


def shell_sort(a):
    a = list(a)
    n = len(a)
    gap = n // 2
    while gap > 0:
        for i in range(gap, n):
            tmp = a[i]
            j = i
            while j >= gap and a[j - gap] > tmp:
                a[j] = a[j - gap]
                j -= gap
            a[j] = tmp
        gap //= 2
    return a


def heap_sort(a):
    a = list(a)
    n = len(a)

    def sift(start, end):
        root = start
        while 2 * root + 1 <= end:
            child = 2 * root + 1
            if child + 1 <= end and a[child] < a[child + 1]:
                child += 1
            if a[root] < a[child]:
                a[root], a[child] = a[child], a[root]
                root = child
            else:
                return

    for s in range(n // 2 - 1, -1, -1):
        sift(s, n - 1)
    for e in range(n - 1, 0, -1):
        a[0], a[e] = a[e], a[0]
        sift(0, e - 1)
    return a


def hybrid_sort(a):
    """ORIGIN-generated candidate: merge sort with an insertion-sort cutoff.

    Synthesized after round 1 from the observed strengths of the base
    candidates (insertion on short/ordered runs, merge on random input).
    """
    CUTOFF = 32

    def ins(seg):
        for i in range(1, len(seg)):
            key = seg[i]
            j = i - 1
            while j >= 0 and seg[j] > key:
                seg[j + 1] = seg[j]
                j -= 1
            seg[j + 1] = key
        return seg

    def ms(seg):
        if len(seg) <= CUTOFF:
            return ins(seg)
        mid = len(seg) // 2
        left = ms(seg[:mid])
        right = ms(seg[mid:])
        out = []
        i = j = 0
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                out.append(left[i]); i += 1
            else:
                out.append(right[j]); j += 1
        out.extend(left[i:])
        out.extend(right[j:])
        return out

    return ms(list(a))


# ---------------------------------------------------------------------------
# Input regime generators (also embedded into runners).
# ---------------------------------------------------------------------------

def gen_random(n, seed):
    import random
    r = random.Random(seed)
    return [r.randrange(n * 10) for _ in range(n)]


def gen_nearly_sorted(n, seed):
    import random
    r = random.Random(seed)
    a = list(range(n))
    for _ in range(max(1, n // 100)):
        i = r.randrange(n - 1)
        a[i], a[i + 1] = a[i + 1], a[i]
    return a


def gen_reversed(n, seed):
    return list(range(n, 0, -1))


def gen_sawtooth(n, seed):
    import random
    rnd = random.Random(seed)
    period = max(8, n // 32)
    return [(i % period) + rnd.randint(0, 2) for i in range(n)]


def gen_organ_pipe(n, seed):
    import random
    rnd = random.Random(seed)
    half = n // 2
    up = list(range(half))
    down = list(range(n - half, 0, -1))
    a = up + down
    for _ in range(max(1, n // 100)):
        i, j = rnd.randrange(n), rnd.randrange(n)
        a[i], a[j] = a[j], a[i]
    return a


def make_hybrid(cutoff):
    """Factory for hybrid merge/insertion sorts parameterized by cutoff
    (used by ORIGIN's cutoff parameter-sweep experiments)."""
    def _hybrid(a):
        a = list(a)

        def ins(seg):
            for i in range(1, len(seg)):
                key = seg[i]
                j = i - 1
                while j >= 0 and seg[j] > key:
                    seg[j + 1] = seg[j]
                    j -= 1
                seg[j + 1] = key
            return seg

        def ms(seg):
            if len(seg) <= cutoff:
                return ins(seg)
            mid = len(seg) // 2
            left, right = ms(seg[:mid]), ms(seg[mid:])
            out = []
            i = j = 0
            while i < len(left) and j < len(right):
                if left[i] <= right[j]:
                    out.append(left[i]); i += 1
                else:
                    out.append(right[j]); j += 1
            out.extend(left[i:]); out.extend(right[j:])
            return out

        return ms(a)
    _hybrid.__name__ = f"hybrid_c{cutoff}"
    return _hybrid


def gen_few_unique(n, seed):
    import random
    r = random.Random(seed)
    return [r.randrange(8) for _ in range(n)]


ALGORITHMS = {
    "shell_sort": [shell_sort],
    "insertion_sort": [insertion_sort],
    "merge_sort": [_merge, merge_sort],
    "quick_sort": [quick_sort],
    "heap_sort": [heap_sort],
    "hybrid_sort": [hybrid_sort],
}
BASE_ROSTER = ["insertion_sort", "merge_sort", "quick_sort", "heap_sort", "shell_sort"]
PROBE_REGIMES = ["sawtooth", "organ_pipe"]   # unseen during main rounds; used by the falsifier
GENERATORS = {"random": gen_random, "nearly_sorted": gen_nearly_sorted,
              "sawtooth": gen_sawtooth, "organ_pipe": gen_organ_pipe,
              "reversed": gen_reversed, "few_unique": gen_few_unique}

RUNNER_TEMPLATE = '''"""Auto-generated by ORIGIN (algobench domain). Self-contained experiment.

Design spec: see spec.json alongside this file. This file is versioned and
kept forever as part of the research history.

Emits result schema v2: per-trial samples, descriptive statistics, input and
output digests (so a replay can prove the inputs and results are identical,
not merely similar), the exact environment the measurements came from, and a
fixed reference micro-benchmark used to express host speed.
"""
import hashlib, json, platform, statistics, sys, time

CONFIG = __CONFIG__
RESULT_SCHEMA_VERSION = 2

# ---- embedded candidate algorithms -----------------------------------------
__SOURCES__

ALGORITHMS = {__ALG_MAP__}
GENERATORS = {__GEN_MAP__}


def digest(seq):
    """Stable content digest of a sequence of numbers."""
    h = hashlib.sha256()
    for x in seq:
        h.update(repr(x).encode())
        h.update(b",")
    return h.hexdigest()[:16]


def file_digest(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except OSError:
        return ""


def reference_workload():
    """Fixed, deterministic micro-benchmark: lets a reader compare hosts.

    It is NOT part of any hypothesis; it exists so absolute timings from
    different machines can be put in proportion.
    """
    import random
    rnd = random.Random(987654321)
    data = [rnd.random() for _ in range(20000)]
    times = []
    for _ in range(5):
        copy = list(data)
        t0 = time.perf_counter()
        copy.sort()
        times.append(time.perf_counter() - t0)
    return statistics.median(times)


def environment():
    info = {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": __import__("os").cpu_count(),
        "origin_version": CONFIG.get("origin_version", "unknown"),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timer": "time.perf_counter",
        "timer_resolution_s": time.get_clock_info("perf_counter").resolution,
    }
    return info


def main():
    rows = []
    input_digests = {}
    for alg_name in CONFIG["algorithms"]:
        fn = ALGORITHMS[alg_name]
        for regime in CONFIG["regimes"]:
            gen = GENERATORS[regime]
            for n in CONFIG["sizes"]:
                times = []
                out_digest = ""
                for t in range(CONFIG["trials"]):
                    data = gen(n, CONFIG["seed"] + t)
                    expected = sorted(data)
                    if t == 0:
                        input_digests.setdefault((regime, n), digest(data))
                    t0 = time.perf_counter()
                    out = fn(data)
                    dt = time.perf_counter() - t0
                    if out != expected:
                        json.dump({"error": "INCORRECT OUTPUT: " + alg_name},
                                  open("result.json", "w"))
                        print("CORRECTNESS FAILURE:", alg_name)
                        sys.exit(2)
                    if t == 0:
                        out_digest = digest(out)
                    times.append(dt)
                stdev = statistics.stdev(times) if len(times) > 1 else 0.0
                rows.append({
                    "algorithm": alg_name, "regime": regime, "n": n,
                    "correct": True,
                    "trials": CONFIG["trials"],
                    "samples": times,
                    "mean_s": statistics.fmean(times),
                    "median_s": statistics.median(times),
                    "stdev_s": stdev,
                    "sem_s": stdev / (len(times) ** 0.5) if len(times) > 1 else 0.0,
                    "min_s": min(times),
                    "input_digest": input_digests[(regime, n)],
                    "output_digest": out_digest,
                })
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "environment": environment(),
        "config": CONFIG,
        "code_digest": file_digest(__file__),
        "reference_workload_s": reference_workload(),
        "rows": rows,
    }
    with open("result.json", "w") as f:
        json.dump(payload, f, indent=2)
    print("OK", len(rows), "measurements")


main()
'''


@register
class AlgoBenchDomain(ResearchDomain):
    name = "algobench"

    # ------------------------------------------------------------------ plan
    def decompose(self, question: str, config: dict) -> dict:
        return {
            "question": question,
            "branches": {
                "input_regimes": list(config.get("regimes", list(GENERATORS))),
                "metrics": {"wall_time": "measured in v0.1",
                            "memory": "gap (untested)",
                            "comparison_count": "gap (untested)"},
                "candidates": {"base": BASE_ROSTER,
                               "generated": "to be synthesized from evidence"},
                "scales": {"tested": config.get("sizes", []),
                           "large_n": "gap (untested)"},
            },
        }

    def initial_assumptions(self) -> list[str]:
        return [
            "Wall-clock time on a single machine/interpreter is an acceptable proxy for algorithmic cost at these sizes.",
            "Pure-Python implementations are compared against each other only; C-accelerated builtins are out of scope for fairness.",
            "The four tested input regimes are representative of the distributions of interest.",
        ]

    def seed_knowledge(self, state) -> None:
        src = Source(id=new_id("src"), kind="prior_knowledge",
                     title="Standard algorithm-analysis results (seeded; Phase 2 replaces with live source acquisition)",
                     reliability=0.95)
        state.add(src)
        for text in [
            "Any comparison sort requires Omega(n log n) comparisons in the worst case.",
            "Insertion sort runs in O(n + inversions); it is linear on nearly-sorted input.",
            "Quicksort's worst case is O(n^2), but median-of-three pivoting avoids it on sorted/reversed inputs.",
        ]:
            state.add(Claim(id=new_id("clm"), text=text, status=EpistemicStatus.FACT,
                            confidence=0.97, source_ids=[src.id]))

    # ------------------------------------------------------------- hypotheses
    def generate_hypotheses(self, state) -> list:
        if state.flags.get("base_hypotheses_done"):
            return []
        state.flags["base_hypotheses_done"] = True

        def P(text, check):
            return Prediction(id=new_id("pred"), text=text, check=check)

        hs = [
            Hypothesis(
                id=new_id("hyp"),
                statement="Insertion sort is the fastest candidate on nearly-sorted input, and the slowest on random input, at the tested sizes.",
                rationale="Adaptive O(n + inversions) behavior dominates on low-inversion input; O(n^2) dominates on random input.",
                predictions=[
                    P("insertion_sort is fastest on nearly_sorted", {"type": "fastest_on", "algorithm": "insertion_sort", "regime": "nearly_sorted"}),
                    P("insertion_sort is slowest on random", {"type": "slowest_on", "algorithm": "insertion_sort", "regime": "random"}),
                ],
                importance=1.0, cost_estimate=1.0, tags=["base"],
            ),
            Hypothesis(
                id=new_id("hyp"),
                statement="Merge sort is the fastest pure-Python candidate on random input.",
                rationale="Guaranteed n log n with sequential memory access; no pathological cases.",
                predictions=[
                    P("merge_sort is fastest on random", {"type": "fastest_on", "algorithm": "merge_sort", "regime": "random"}),
                ],
                importance=1.0, cost_estimate=1.0, tags=["base"],
            ),
            Hypothesis(
                id=new_id("hyp"),
                statement="Quick sort (median-of-three, Hoare) stays within 25% of the best candidate on random input and does not collapse on reversed input.",
                rationale="MO3 pivoting neutralizes ordered-input pathologies; constant factors are low.",
                predictions=[
                    P("quick_sort within 25% of best on random", {"type": "within_pct_of_best", "algorithm": "quick_sort", "regime": "random", "pct": 25}),
                    P("quick_sort within 200% of best on reversed", {"type": "within_pct_of_best", "algorithm": "quick_sort", "regime": "reversed", "pct": 200}),
                ],
                importance=0.9, cost_estimate=1.0, tags=["base"],
            ),
            Hypothesis(
                id=new_id("hyp"),
                statement="Heap sort is the most consistent candidate (lowest relative timing variance across regimes) but is never the fastest in any regime.",
                rationale="Input-oblivious n log n behavior; poor cache locality keeps constants high.",
                predictions=[
                    P("heap_sort has lowest mean relative stdev", {"type": "lowest_mean_rel_stdev", "algorithm": "heap_sort"}),
                    P("heap_sort is never fastest in any regime", {"type": "never_fastest", "algorithm": "heap_sort"}),
                ],
                importance=0.8, cost_estimate=1.0, tags=["base"],
            ),
        ]
        return hs

    # ------------------------------------------------- LLM proposal contract
    def proposal_context(self, state) -> dict:
        cfg = self._config(state)
        return {
            "mission": state.meta["question"],
            "algorithms": BASE_ROSTER,
            "regimes": cfg.get("regimes", ["random", "nearly_sorted",
                                           "reversed", "few_unique"]),
            "check_kinds": {
                "beats": {"params": ["a", "b", "regime"],
                          "meaning": "algorithm a has lower mean time than b on regime"},
                "fastest_on": {"params": ["algorithm", "regime"]},
                "within_pct_of_best": {"params": ["algorithm", "regime", "pct"]},
            },
            "existing_statements": [h.statement for h in state.hypotheses.values()],
        }

    def build_check(self, kind: str, params: dict, state) -> dict:
        """Translate a validated brain proposal into an internal machine-checkable
        check. Raises ValueError for anything outside the known vocabulary."""
        cfg = self._config(state)
        regimes = cfg.get("regimes", ["random", "nearly_sorted", "reversed",
                                      "few_unique"])

        def need_alg(name):
            if name not in BASE_ROSTER + ["hybrid_sort"]:
                raise ValueError(f"unknown algorithm {name!r}")
            return name

        def need_regime(r):
            if r not in regimes:
                raise ValueError(f"regime {r!r} not in mission regimes {regimes}")
            return r

        if kind == "beats":
            return {"type": "beats", "algorithm": need_alg(params["a"]),
                    "than": need_alg(params["b"]),
                    "regime": need_regime(params["regime"]),
                    "min_pct": float(params.get("min_pct", 0.0))}
        if kind == "fastest_on":
            return {"type": "fastest_on", "algorithm": need_alg(params["algorithm"]),
                    "regime": need_regime(params["regime"])}
        if kind == "within_pct_of_best":
            return {"type": "within_pct_of_best",
                    "algorithm": need_alg(params["algorithm"]),
                    "regime": need_regime(params["regime"]),
                    "pct": float(params["pct"])}
        raise ValueError(f"unknown prediction kind {kind!r}")

    # ------------------------------------------------------------ experiments
    def _config(self, state) -> dict:
        return state.meta.get("domain_config", {})

    def design_experiment(self, primary, pending, state) -> dict | None:
        cfg = self._config(state)
        if "sweep" in primary.tags:
            return self._sweep_design(primary, cfg, seed_shift=0)
        roster = list(BASE_ROSTER)
        if any("generated" in h.tags for h in pending) or "generated" in primary.tags:
            roster = BASE_ROSTER + ["hybrid_sort"]
        cover = [h.id for h in pending if set(h.tags) & set(primary.tags)] or [primary.id]
        rnd = 2 if "hybrid_sort" in roster else 1
        return {
            "kind": "benchmark", "round": rnd,
            "algorithms": roster,
            "regimes": cfg.get("regimes", list(GENERATORS)),
            "sizes": cfg.get("sizes", [400, 1600]),
            "trials": cfg.get("trials", 3),
            "seed": cfg.get("seed", 1234),
            "timeout_s": cfg.get("timeout_s", 600),
            "hypothesis_ids": cover,
        }

    def _sweep_design(self, hypothesis, cfg, seed_shift: int) -> dict:
        sizes = cfg.get("sizes", [400, 1600])
        return {
            "kind": "sweep", "round": 3,
            "algorithms": [f"hybrid_c{c}" for c in cfg.get("cutoffs", [8, 16, 32, 64])],
            "regimes": cfg.get("regimes", ["random", "nearly_sorted",
                                           "reversed", "few_unique"]),
            "sizes": [max(sizes)],
            "trials": cfg.get("trials", 3),
            "seed": cfg.get("seed", 1234) + seed_shift,
            "timeout_s": cfg.get("timeout_s", 600),
            "hypothesis_ids": [hypothesis.id],
        }

    def replication_design(self, hypothesis, state) -> dict | None:
        cfg = self._config(state)
        if "sweep" in hypothesis.tags:
            return self._sweep_design(hypothesis, cfg, seed_shift=1000)
        roster = list(BASE_ROSTER)
        if "generated" in hypothesis.tags:
            roster = BASE_ROSTER + ["hybrid_sort"]
        sizes = cfg.get("sizes", [400, 1600])
        return {
            "kind": "replication", "round": 0,
            "algorithms": roster,
            "regimes": cfg.get("regimes", list(GENERATORS)),
            "sizes": [max(sizes)],
            "trials": cfg.get("trials", 3),
            "seed": cfg.get("seed", 1234) + 1000,   # independent inputs
            "timeout_s": cfg.get("timeout_s", 600),
            "hypothesis_ids": [hypothesis.id],
        }

    def falsification_design(self, hypothesis, state) -> dict | None:
        """Critic attack: re-evaluate the hypothesis' regime-bound predictions at
        a boundary size (2x the largest tested n) on the ORIGINAL regime, and on
        input regimes never seen during the main rounds (scope probes)."""
        cfg = self._config(state)
        probe_checks = []
        # Only prediction types the benchmark evaluator can actually judge are
        # probeable; anything else (e.g. sweep optima) yields no probe rather
        # than an uninformative "inconclusive" dressed up as a result.
        PROBEABLE = {"fastest_on", "slowest_on", "within_pct_of_best", "beats",
                     "lowest_mean_rel_stdev", "never_fastest"}
        for pred in hypothesis.predictions:
            chk = dict(pred.check)
            if chk.get("type") not in PROBEABLE:
                continue
            if "regime" in chk:
                probe_checks.append({"label": f"boundary:{chk['regime']}",
                                     "check": chk, "role": "boundary"})
                for pr in PROBE_REGIMES:
                    c2 = dict(chk); c2["regime"] = pr
                    probe_checks.append({"label": f"scope:{pr}", "check": c2,
                                         "role": "scope"})
            elif chk.get("type") in ("never_fastest", "lowest_mean_rel_stdev"):
                probe_checks.append({"label": "boundary:all", "check": chk,
                                     "role": "boundary"})
        if not probe_checks:
            return None
        roster = list(BASE_ROSTER)
        if "generated" in hypothesis.tags:
            roster.append("hybrid_sort")
        sizes = cfg.get("sizes", [400, 1600])
        need = {c["check"].get("regime") for c in probe_checks if c["check"].get("regime")}
        regimes = sorted(need) or cfg.get("regimes", ["random"])
        return {
            "kind": "falsification", "round": 9,
            "algorithms": roster,
            "regimes": regimes,
            "sizes": [2 * max(sizes)],
            "trials": cfg.get("trials", 3),
            "seed": cfg.get("seed", 1234) + 7777,
            "timeout_s": cfg.get("timeout_s", 600),
            "hypothesis_ids": [hypothesis.id],
            "probe_checks": probe_checks,
        }

    def evaluate_falsification(self, record, result, hypothesis) -> dict:
        rows = result["rows"]
        design = record.design
        n_top = max(design["sizes"])
        winners = {}
        for regime in design["regimes"]:
            ranked = sorted((r for r in rows if r["regime"] == regime and r["n"] == n_top),
                            key=lambda r: r["mean_s"])
            if ranked:
                winners[regime] = ranked[0]
        boundary_bad, details = [], []
        per_regime: dict[str, list[bool]] = {}
        for pc in design.get("probe_checks", []):
            outcome, detail, _ = self._eval_prediction(pc["check"], rows, design,
                                                       n_top, winners)
            details.append(f"[{pc['label']}] {outcome}: {detail}")
            if pc["role"] == "boundary" and outcome == "refuted":
                boundary_bad.append(pc["label"])
            if pc["role"] == "scope":
                per_regime.setdefault(pc["check"].get("regime", pc["label"]),
                                      []).append(outcome)
        if boundary_bad:
            outcome = "failed"
            scope = ""
        else:
            extends = sorted(r for r, v in per_regime.items()
                             if all(o == "confirmed" for o in v))
            refuted = sorted(r for r, v in per_regime.items()
                             if any(o == "refuted" for o in v))
            untested = sorted(r for r, v in per_regime.items()
                              if r not in extends and r not in refuted)
            outcome = "survived"
            scope = ("holds at n<=2x tested sizes on its original regime(s)"
                     + (f"; extends to {extends}" if extends else "")
                     + (f"; does NOT extend to {refuted}" if refuted else "")
                     + (f"; untested on {untested}" if untested else ""))
        return {"outcome": outcome, "scope": scope, "detail": " | ".join(details)}

    def estimate_cost(self, design: dict) -> float:
        cells = (len(design["algorithms"]) * len(design["regimes"])
                 * len(design["sizes"]) * design["trials"])
        return max(0.2, cells * 0.02)

    def write_runner(self, design: dict, exp_dir: Path) -> Path:
        seen, chunks = set(), []
        for r in design["regimes"]:
            gen = GENERATORS[r]
            if gen not in seen:
                chunks.append(inspect.getsource(gen)); seen.add(gen)
        entries = []
        for alg in design["algorithms"]:
            if alg.startswith("hybrid_c"):            # sweep variant
                if make_hybrid not in seen:
                    chunks.append(inspect.getsource(make_hybrid)); seen.add(make_hybrid)
                entries.append(f'"{alg}": make_hybrid({int(alg[8:])})')
            else:
                for fn in ALGORITHMS[alg]:
                    if fn not in seen:
                        chunks.append(inspect.getsource(fn)); seen.add(fn)
                entries.append(f'"{alg}": {ALGORITHMS[alg][-1].__name__}')
        alg_map = ", ".join(entries)
        gen_map = ", ".join(f'"{r}": {GENERATORS[r].__name__}' for r in design["regimes"])
        from .. import __version__ as origin_version
        runner_config = dict(design, origin_version=origin_version)
        code = (RUNNER_TEMPLATE
                .replace("__CONFIG__", json.dumps(runner_config, indent=4))
                .replace("__SOURCES__", "\n\n".join(chunks))
                .replace("__ALG_MAP__", alg_map)
                .replace("__GEN_MAP__", gen_map))
        runner = exp_dir / "run.py"
        runner.write_text(code)
        return runner

    # ---------------------------------------------------------------- analyze
    def analyze(self, record, result: dict, state) -> dict:
        rows = result["rows"]
        design = record.design
        sizes = design["sizes"]
        n_top = max(sizes)
        if design.get("kind") == "sweep":
            return self._analyze_sweep(record, result, state)

        def cells(regime, n):
            return sorted((r for r in rows if r["regime"] == regime and r["n"] == n),
                          key=lambda r: r["mean_s"])

        winners = {}
        for regime in design["regimes"]:
            ranked = cells(regime, n_top)
            if not ranked:
                continue
            best = ranked[0]
            margin = ((ranked[1]["mean_s"] - best["mean_s"]) / best["mean_s"]) if len(ranked) > 1 else 0.0
            noise = (best["stdev_s"] / best["mean_s"]) if best["mean_s"] > 0 else 0.0
            decisive = False
            tied = []
            if len(ranked) > 1:
                cells_map = {r["algorithm"]: st_.row_stats(r) for r in ranked}
                tied = [x for x in st_.indistinguishable_set(cells_map)
                        if x != best["algorithm"]]
                decisive = not tied
            winners[regime] = {"algorithm": best["algorithm"], "margin": margin,
                               "noise": noise, "decisive": decisive,
                               "indistinguishable_from": tied}
            if tied:
                state.cautions.append(
                    f"Regime '{regime}' at n={n_top} in {record.id}: "
                    f"{best['algorithm']} has the lowest mean but is not "
                    f"statistically separable from {', '.join(tied)} at "
                    f"{design.get('trials')} trials — no winner is claimed.")
            if noise > 0.30:
                state.cautions.append(
                    f"High timing noise for winner in regime '{regime}' "
                    f"(stdev/mean = {noise:.2f}) in {record.id}; evidence strength capped.")

        # ---- evaluate predictions of the covered hypotheses -----------------
        summary = {"winners": {k: v["algorithm"] for k, v in winners.items()},
                   "evaluated": [], "new_hypotheses": []}
        replication = design.get("kind") == "replication"

        for hid in record.hypothesis_ids:
            h = state.hypotheses.get(hid)
            if h is None:
                continue
            h.tested_in.append(record.id)
            outcomes = []
            for p in h.predictions:
                verdict, detail, margin = self._eval_prediction(p.check, rows, design, n_top, winners)
                outcomes.append(verdict)
                strength = min(0.85, 0.35 + min(abs(margin), 0.5))
                regime = p.check.get("regime")
                if regime and winners.get(regime, {}).get("noise", 0) > 0.30:
                    strength *= 0.6
                direction = {"confirmed": "supports", "refuted": "contradicts"}.get(
                    verdict, "inconclusive")
                if verdict == "inconclusive":
                    strength = min(strength, 0.2)
                ev = Evidence(id=new_id("evd"), target_id=h.id,
                              direction=direction,
                              strength=round(strength, 3), kind="experiment",
                              summary=f"[{'replication' if replication else 'test'}] {p.text}: {verdict} ({detail})",
                              experiment_id=record.id,
                              payload={"margin": round(margin, 4)})
                state.add(ev)
                if verdict == "confirmed":
                    h.supporting_evidence.append(ev.id)
                elif verdict == "refuted":
                    h.contradicting_evidence.append(ev.id)
                # inconclusive evidence is recorded but counts for neither side

                if replication:
                    if p.outcome == "confirmed" and verdict == "refuted":
                        p.outcome, p.detail = "unstable", f"failed replication: {detail}"
                        state.failures.append({
                            "experiment": record.id, "hypothesis": h.id,
                            "prediction": p.text, "expected": "replicated confirmation",
                            "observed": detail, "action": f"{h.id} downgraded to WEAKENED",
                            "ts": now()})
                    # a replicated confirmation leaves outcome as-is, evidence added
                else:
                    p.outcome, p.detail = verdict, detail
                    if verdict == "refuted":
                        state.failures.append({
                            "experiment": record.id, "hypothesis": h.id,
                            "prediction": p.text, "expected": p.text,
                            "observed": detail,
                            "action": "hypothesis status re-evaluated from evidence",
                            "ts": now()})
                summary["evaluated"].append({"hypothesis": h.id, "prediction": p.text,
                                             "verdict": verdict, "detail": detail})

            # ---- status update (recorded, never silent) --------------------
            old = h.status
            if replication:
                if any(p.outcome == "unstable" for p in h.predictions):
                    h.revise(HypothesisStatus.WEAKENED, f"failed replication in {record.id}")
                elif "needs_replication" in h.tags:
                    h.tags.remove("needs_replication")
                    h.tags.append("replicated")
                    state.log_event("replicated", f"{h.id} survived independent replication")
            else:
                if all(o == "confirmed" for o in outcomes):
                    h.revise(HypothesisStatus.PROVISIONALLY_SUPPORTED,
                             f"all predictions confirmed in {record.id}")
                    if len(h.tested_in) == 1 and "needs_replication" not in h.tags:
                        h.tags.append("needs_replication")
                elif all(o == "refuted" for o in outcomes):
                    h.revise(HypothesisStatus.REJECTED,
                             f"all predictions refuted in {record.id}")
                elif any(o == "refuted" for o in outcomes):
                    h.revise(HypothesisStatus.WEAKENED,
                             f"mixed prediction outcomes in {record.id}")
                else:
                    h.revise(HypothesisStatus.WEAKENED,
                             f"predictions were not resolvable at "
                             f"{design.get('trials')} trials in {record.id} "
                             f"(differences within measurement uncertainty)")
                    state.cautions.append(
                        f"{h.id}: no prediction could be resolved at this trial "
                        f"count; treat as untested rather than disproved.")
            if h.status != old:
                state.record_confidence_change("hypothesis", h.id, old.value,
                                               h.status.value,
                                               f"evidence from {record.id}")
            h.updated_at = now()

        # ---- knowledge graph update ----------------------------------------
        for regime, w in winners.items():
            a_ent = state.graph.entity(w["algorithm"], "algorithm")
            r_ent = state.graph.entity(regime, "input_regime")
            conf = max(0.3, min(0.9, 0.5 + w["margin"] - w["noise"]))
            ev_ids = [e.id for e in state.evidence.values() if e.experiment_id == record.id]
            state.graph.add_relation(a_ent, "fastest_on", r_ent, conf, ev_ids[:3])

        # ---- hypothesis evolution: synthesize a new candidate after round 1 -
        if design.get("round") == 1 and not state.flags.get("hybrid_proposed"):
            state.flags["hybrid_proposed"] = True
            ns_w = winners.get("nearly_sorted", {}).get("algorithm", "?")
            rnd_w = winners.get("random", {}).get("algorithm", "?")
            h5 = Hypothesis(
                id=new_id("hyp"),
                statement=("A hybrid algorithm (merge sort with insertion-sort cutoff <= 32) "
                           "beats plain merge sort on random AND nearly-sorted input at the tested sizes."),
                rationale=(f"Round-1 evidence: '{ns_w}' won nearly_sorted and '{rnd_w}' won random. "
                           "Combining merge structure with insertion's strength on short/ordered runs "
                           "should reduce recursion overhead without losing n log n guarantees. "
                           f"Derived from experiment {record.id}."),
                predictions=[
                    Prediction(id=new_id("pred"),
                               text="hybrid_sort beats merge_sort on random by >= 5%",
                               check={"type": "beats", "algorithm": "hybrid_sort",
                                      "than": "merge_sort", "regime": "random", "min_pct": 5}),
                    Prediction(id=new_id("pred"),
                               text="hybrid_sort beats merge_sort on nearly_sorted",
                               check={"type": "beats", "algorithm": "hybrid_sort",
                                      "than": "merge_sort", "regime": "nearly_sorted", "min_pct": 0}),
                ],
                importance=1.2, cost_estimate=1.2, tags=["generated"],
            )
            state.add(h5)
            g1 = state.graph.entity("hybrid_sort", "algorithm")
            for parent in ("merge_sort", "insertion_sort"):
                state.graph.add_relation(g1, "derived_from",
                                         state.graph.entity(parent, "algorithm"), 0.99)
            state.log_event("hypothesis_generated",
                            f"New candidate synthesized from evidence: {h5.id} (hybrid_sort)",
                            hypothesis=h5.id)
            summary["new_hypotheses"].append(h5.id)

        # ---- parameter-sweep hypothesis, pre-registered before any sweep runs
        cfg = self._config(state)
        if (cfg.get("sweep") and not state.flags.get("sweep_proposed")
                and any("generated" in h.tags
                        and h.status == HypothesisStatus.PROVISIONALLY_SUPPORTED
                        for h in state.hypotheses.values())):
            state.flags["sweep_proposed"] = True
            h6 = Hypothesis(
                id=new_id("hyp"),
                statement=("The hybrid's optimal insertion cutoff on random input "
                           "lies in [16, 64], and the optimal cutoff on "
                           "nearly-sorted input is >= the optimum on random input."),
                rationale=("Python call overhead favors moderate cutoffs; insertion "
                           "sort's adaptivity should tolerate larger segments on "
                           "nearly-sorted data. Pre-registered before any sweep ran."),
                predictions=[
                    Prediction(id=new_id("pred"),
                               text="optimal cutoff on random in [16, 64]",
                               check={"type": "sweep_optimum_in",
                                      "regime": "random", "lo": 16, "hi": 64}),
                    Prediction(id=new_id("pred"),
                               text="optimal cutoff on nearly_sorted >= optimal on random",
                               check={"type": "sweep_optimum_ge",
                                      "regime_a": "nearly_sorted",
                                      "regime_b": "random"}),
                ],
                importance=0.95, cost_estimate=0.8,
                tags=["generated", "sweep"],
            )
            state.add(h6)
            summary["new_hypotheses"].append(h6.id)
            state.log_event("hypothesis_generated",
                            f"Parameter-sweep hypothesis pre-registered: {h6.id}",
                            hypothesis=h6.id)

        return summary

    # ------------------------------------------------------- sweep analysis
    def _analyze_sweep(self, record, result, state):
        rows = result["rows"]
        design = record.design
        n_top = max(design["sizes"])
        replication = design.get("seed", 0) != self._config(state).get("seed", 1234)
        optima = {}
        for regime in design["regimes"]:
            ranked = sorted((r for r in rows if r["regime"] == regime and r["n"] == n_top),
                            key=lambda r: r["mean_s"])
            if ranked:
                cells_map = {r["algorithm"]: st_.row_stats(r) for r in ranked}
                tied = st_.indistinguishable_set(cells_map)
                optima[regime] = {
                    "cutoff": int(ranked[0]["algorithm"][8:]),
                    "mean_s": ranked[0]["mean_s"],
                    "indistinguishable": sorted(int(x[8:]) for x in tied),
                    "table": {r["algorithm"]: round(r["mean_s"] * 1000, 3)
                              for r in ranked}}
        summary = {"winners": {k: f"cutoff {v['cutoff']}" for k, v in optima.items()},
                   "evaluated": [], "new_hypotheses": [], "optima": optima}

        for hid in record.hypothesis_ids:
            h = state.hypotheses.get(hid)
            if h is None:
                continue
            h.tested_in.append(record.id)
            outcomes = []
            for pr in h.predictions:
                c = pr.check
                if c["type"] == "sweep_optimum_in":
                    entry = optima.get(c["regime"], {})
                    got = entry.get("cutoff")
                    tied = entry.get("indistinguishable", [])
                    in_range = got is not None and c["lo"] <= got <= c["hi"]
                    outside = [x for x in tied if not (c["lo"] <= x <= c["hi"])]
                    if got is None:
                        ok, detail = None, "no data"
                    elif not in_range:
                        ok = False
                        detail = (f"best cutoff on {c['regime']} = {got}, outside "
                                  f"[{c['lo']},{c['hi']}]; table {entry.get('table')}")
                    elif outside:
                        ok = None
                        detail = (f"best cutoff on {c['regime']} = {got} (inside "
                                  f"[{c['lo']},{c['hi']}]) but cutoffs {outside} are "
                                  f"statistically indistinguishable from it at "
                                  f"{design.get('trials')} trials — the optimum is "
                                  f"not resolvable to that interval")
                    else:
                        ok = True
                        detail = (f"best cutoff on {c['regime']} = {got}, inside "
                                  f"[{c['lo']},{c['hi']}] and decisively separated "
                                  f"from every other cutoff tested; table "
                                  f"{entry.get('table')}")
                elif c["type"] == "sweep_optimum_ge":
                    ea = optima.get(c["regime_a"], {})
                    eb = optima.get(c["regime_b"], {})
                    ga, gb = ea.get("cutoff"), eb.get("cutoff")
                    if ga is None or gb is None:
                        ok, detail = None, "no data"
                    elif ea.get("indistinguishable") and len(ea["indistinguishable"]) > 1 \
                            or (eb.get("indistinguishable") and len(eb["indistinguishable"]) > 1):
                        ok = None
                        detail = (f"optimum {c['regime_a']}={ga} vs {c['regime_b']}={gb}, "
                                  f"but the optima are not uniquely identified "
                                  f"(indistinguishable sets: {c['regime_a']}="
                                  f"{ea.get('indistinguishable')}, {c['regime_b']}="
                                  f"{eb.get('indistinguishable')})")
                    else:
                        ok = ga >= gb
                        detail = f"optimum {c['regime_a']}={ga} vs {c['regime_b']}={gb}"
                else:
                    ok, detail = None, f"unknown sweep check {c['type']}"
                verdict = "inconclusive" if ok is None else ("confirmed" if ok else "refuted")
                outcomes.append(verdict)
                ev = Evidence(id=new_id("evd"), target_id=h.id,
                              direction={"confirmed": "supports",
                                         "refuted": "contradicts"}.get(verdict, "inconclusive"),
                              strength=0.6 if verdict != "inconclusive" else 0.15,
                              kind="experiment",
                              summary=f"[{'replication' if replication else 'sweep'}] "
                                      f"{pr.text}: {verdict} ({detail})",
                              experiment_id=record.id,
                              payload={"optima": {k: v["cutoff"] for k, v in optima.items()}})
                state.add(ev)
                if verdict == "confirmed":
                    h.supporting_evidence.append(ev.id)
                elif verdict == "refuted":
                    h.contradicting_evidence.append(ev.id)
                if replication:
                    if pr.outcome == "confirmed" and verdict == "refuted":
                        pr.outcome, pr.detail = "unstable", f"failed replication: {detail}"
                        state.failures.append({
                            "experiment": record.id, "hypothesis": h.id,
                            "prediction": pr.text, "expected": "replicated confirmation",
                            "observed": detail, "action": f"{h.id} downgraded to WEAKENED",
                            "ts": now()})
                else:
                    pr.outcome, pr.detail = verdict, detail
                    if verdict == "refuted":
                        state.failures.append({
                            "experiment": record.id, "hypothesis": h.id,
                            "prediction": pr.text, "expected": pr.text, "observed": detail,
                            "action": "hypothesis status re-evaluated from evidence",
                            "ts": now()})
                summary["evaluated"].append({"hypothesis": h.id, "prediction": pr.text,
                                             "verdict": verdict, "detail": detail})
            old = h.status
            if replication:
                if any(p.outcome == "unstable" for p in h.predictions):
                    h.revise(HypothesisStatus.WEAKENED,
                             f"failed sweep replication in {record.id}")
                elif "needs_replication" in h.tags:
                    h.tags.remove("needs_replication")
                    h.tags.append("replicated")
                    state.log_event("replicated",
                                    f"{h.id} sweep survived independent replication")
            else:
                if all(o == "confirmed" for o in outcomes):
                    h.revise(HypothesisStatus.PROVISIONALLY_SUPPORTED,
                             f"sweep confirmed all predictions in {record.id}")
                    if "needs_replication" not in h.tags:
                        h.tags.append("needs_replication")
                elif all(o == "refuted" for o in outcomes):
                    h.revise(HypothesisStatus.REJECTED, f"sweep refuted in {record.id}")
                else:
                    h.revise(HypothesisStatus.WEAKENED, f"sweep mixed outcomes in {record.id}")
            if h.status != old:
                state.record_confidence_change("hypothesis", h.id, old.value,
                                               h.status.value, f"sweep {record.id}")
            h.updated_at = now()

        if not replication and optima:
            env = result.get("environment", {})
            c = Claim(id=new_id("clm"),
                      text=("Hybrid insertion-cutoff optima at n="
                            f"{n_top} ({design.get('trials')} trials, "
                            f"{env.get('python_implementation', 'CPython')} "
                            f"{env.get('python_version', '?')} on "
                            f"{env.get('system', '?')}/{env.get('machine', '?')}): "
                            + ", ".join(
                                f"{k}={v['cutoff']}"
                                + (f" (indistinguishable from "
                                   f"{[x for x in v['indistinguishable'] if x != v['cutoff']]})"
                                   if len(v.get("indistinguishable", [])) > 1 else "")
                                for k, v in optima.items())),
                      status=EpistemicStatus.EXPERIMENTAL_RESULT, confidence=0.6,
                      source_ids=[])
            state.add(c)
            state.record_confidence_change("claim", c.id, None, 0.6,
                                           f"measured in sweep {record.id}")
            state.log_event("analysis",
                            f"Sweep {record.id}: cutoff optima " +
                            ", ".join(f"{k}={v['cutoff']}" for k, v in optima.items()),
                            experiment=record.id)
        return summary

    # ---------------------------------------------------- prediction checking
    def _eval_prediction(self, check, rows, design, n_top, winners):
        """Evaluate one machine-checkable prediction.

        Comparative claims are gated by the conservative significance rule in
        `origin.stats`: a difference that the trial count and spread cannot
        resolve is reported as INCONCLUSIVE rather than being called a win or a
        loss. This is what keeps ORIGIN from turning scheduler noise into a
        finding.
        """
        t = check["type"]

        def row_of(alg, regime, n=None):
            n = n_top if n is None else n
            for r in rows:
                if r["algorithm"] == alg and r["regime"] == regime and r["n"] == n:
                    return r
            return None

        def stat(row):
            return st_.row_stats(row) if row else None

        def mean_of(alg, regime):
            r = row_of(alg, regime)
            return r["mean_s"] if r else None

        scope = f"n={n_top}, {design.get('trials')} trials"

        if t in ("fastest_on", "slowest_on"):
            regime = check["regime"]
            ranked = sorted((r for r in rows if r["regime"] == regime and r["n"] == n_top),
                            key=lambda r: r["mean_s"])
            if len(ranked) < 2:
                return "inconclusive", "insufficient data for a ranking", 0.0
            extreme = ranked[0] if t == "fastest_on" else ranked[-1]
            runner_up = ranked[1] if t == "fastest_on" else ranked[-2]
            cmp_ = st_.compare(stat(extreme), stat(runner_up))
            margin = cmp_["margin"]
            claimed = check["algorithm"]
            if claimed == extreme["algorithm"]:
                if not cmp_["decisive"]:
                    return ("inconclusive",
                            f"{claimed} has the lowest mean on '{regime}' "
                            f"({extreme['mean_s']*1000:.1f} ms) but is not "
                            f"decisively {'faster' if t == 'fastest_on' else 'slower'} "
                            f"than {runner_up['algorithm']}: {cmp_['reason']} [{scope}]",
                            margin * 0.5)
                return ("confirmed",
                        f"{t} on '{regime}' is {claimed} "
                        f"({extreme['mean_s']*1000:.1f} ms, margin "
                        f"{margin*100:.0f}% over {runner_up['algorithm']}, "
                        f"separation {cmp_['gap_s']*1000:.2f} ms > required "
                        f"{cmp_['required_s']*1000:.2f} ms) [{scope}]", margin)
            claimed_row = row_of(claimed, regime)
            if claimed_row is None:
                return "inconclusive", f"{claimed} not measured on '{regime}'", 0.0
            head = st_.compare(stat(extreme), stat(claimed_row))
            if not head["decisive"]:
                return ("inconclusive",
                        f"{extreme['algorithm']} leads on '{regime}' but is not "
                        f"decisively separated from {claimed}: {head['reason']} [{scope}]",
                        head["margin"] * 0.5)
            return ("refuted",
                    f"{t} on '{regime}' is {extreme['algorithm']}, not {claimed} "
                    f"({head['margin']*100:.0f}% apart, decisive) [{scope}]",
                    head["margin"])

        if t == "within_pct_of_best":
            regime = check["regime"]
            ranked = sorted((r for r in rows if r["regime"] == regime and r["n"] == n_top),
                            key=lambda r: r["mean_s"])
            if not ranked:
                return "inconclusive", "no data", 0.0
            best = ranked[0]
            row = row_of(check["algorithm"], regime)
            if row is None:
                return "inconclusive", "no data", 0.0
            sb, sr = stat(best), stat(row)
            pct = (sr["mean_s"] - sb["mean_s"]) / max(sb["mean_s"], 1e-12) * 100
            # Uncertainty on that percentage, propagated conservatively.
            unc = (st_.K_SEM * (sb["sem_s"] + sr["sem_s"]) /
                   max(sb["mean_s"], 1e-12) * 100)
            limit = check["pct"]
            if abs(pct - limit) <= unc:
                return ("inconclusive",
                        f"{check['algorithm']} is {pct:.0f}% off best on "
                        f"'{regime}' (limit {limit}%), within the "
                        f"±{unc:.0f}% uncertainty of the threshold [{scope}]",
                        0.05)
            return ("confirmed" if pct <= limit else "refuted",
                    f"{check['algorithm']} is {pct:.0f}% off best on '{regime}' "
                    f"(limit {limit}%, uncertainty ±{unc:.0f}%) [{scope}]",
                    abs(pct - limit) / 100)

        if t == "beats":
            ra = row_of(check["algorithm"], check["regime"])
            rb = row_of(check["than"], check["regime"])
            if ra is None or rb is None:
                return "inconclusive", "no data", 0.0
            cmp_ = st_.compare(stat(ra), stat(rb))
            pct = (rb["mean_s"] - ra["mean_s"]) / max(ra["mean_s"], 1e-12) * 100
            if not cmp_["decisive"]:
                return ("inconclusive",
                        f"{check['algorithm']} vs {check['than']} on "
                        f"'{check['regime']}': {pct:+.0f}% but not decisive "
                        f"({cmp_['reason']}) [{scope}]", abs(pct) / 200)
            if cmp_["relation"] == st_.SLOWER:
                return ("refuted",
                        f"{check['algorithm']} is decisively SLOWER than "
                        f"{check['than']} on '{check['regime']}' ({pct:+.0f}%) [{scope}]",
                        abs(pct) / 100)
            ok = pct >= check.get("min_pct", 0.0)
            return ("confirmed" if ok else "refuted",
                    f"{check['algorithm']} vs {check['than']} on "
                    f"'{check['regime']}': {pct:+.0f}% "
                    f"(needs >= {check.get('min_pct', 0.0)}%, decisive: gap "
                    f"{cmp_['gap_s']*1000:.2f} ms > required "
                    f"{cmp_['required_s']*1000:.2f} ms) [{scope}]",
                    abs(pct) / 100)

        if t == "lowest_mean_rel_stdev":
            per_alg = {}
            for r in rows:
                if r["mean_s"] > 0:
                    per_alg.setdefault(r["algorithm"], []).append(r["stdev_s"] / r["mean_s"])
            scores = {a: sum(v) / len(v) for a, v in per_alg.items() if v}
            if len(scores) < 2:
                return "inconclusive", "no data", 0.0
            ordered = sorted(scores, key=scores.get)
            winner, second = ordered[0], ordered[1]
            spread = (scores[second] - scores[winner]) / max(scores[winner], 1e-12)
            if spread < 0.25:
                return ("inconclusive",
                        f"lowest mean relative stdev is {winner} "
                        f"({scores[winner]:.3f}) but {second} is within "
                        f"{spread*100:.0f}% — dispersion ranking is not "
                        f"separable here [{scope}]", 0.05)
            ok = winner == check["algorithm"]
            return ("confirmed" if ok else "refuted",
                    f"lowest mean relative stdev: {winner} "
                    f"({scores[winner]:.3f}); next is {second} "
                    f"({scores[second]:.3f}) [{scope}]", 0.1)

        if t == "never_fastest":
            fastest = {w["algorithm"] for w in winners.values()}
            decisive_regimes = [r for r, w in winners.items() if w.get("decisive")]
            ok = check["algorithm"] not in fastest
            if ok and not decisive_regimes:
                return ("inconclusive",
                        f"{check['algorithm']} never had the lowest mean, but no "
                        f"regime winner was decisively separated at this trial "
                        f"count [{scope}]", 0.05)
            return ("confirmed" if ok else "refuted",
                    f"regime winners: {sorted(fastest)} (decisively separated "
                    f"in: {sorted(decisive_regimes) or 'none'}) [{scope}]", 0.1)

        return "inconclusive", f"unknown check type {t}", 0.0

    # -------------------------------------------------------------------- gaps
    def knowledge_gaps(self, state) -> list[str]:
        cfg = self._config(state)
        max_n = max(cfg.get("sizes", [1600]))
        return [
            f"Scaling behavior beyond n={max_n} is untested (asymptotic crossovers may differ).",
            "Memory usage and comparison/move counts were not measured (wall time only).",
            "Adversarial input patterns (sawtooth, organ-pipe, quicksort-killer) are untested.",
            "Only one machine/interpreter was used; hardware sensitivity is unknown.",
            "Stability of the sorts (equal-key ordering) was not evaluated.",
        ]
