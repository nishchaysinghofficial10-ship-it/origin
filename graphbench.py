"""graphbench — ORIGIN's second research domain (v1.6).

Single-source shortest paths on generated graphs. Chosen because it is
deterministic, safe, measurable, and *structurally different* from sorting in
ways that stress the core rather than flatter it:

  * the input is a graph, not an array — "regime" means topology (sparsity,
    grid, scale-free, long chains), not element order;
  * correctness is a whole answer vector checked against a reference
    implementation, not a sortedness predicate;
  * there is a **machine-independent** primary metric — edge relaxations —
    alongside wall-clock time. Sorting had only timing, so every conclusion was
    hostage to the host. Here ORIGIN can state a claim that transfers.
  * one candidate (`bfs_unit`) is *correct only under a precondition*
    (unit weights), which gives the critic a real correctness boundary to find
    rather than only a performance boundary.

Everything else — controller, state, budget, critic, replication, reporting,
autonomy — is unchanged and shared. This module implements only the domain
hooks in `ResearchDomain`.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

from .. import stats as st_
from ..models import (Claim, EpistemicStatus, Evidence, Hypothesis,
                      HypothesisStatus, Prediction, Source, new_id, now)
from .base import ResearchDomain, register


# ------------------------------------------------------------- algorithms
def dijkstra_heap(n, adj, src):
    import heapq
    INF = float("inf")
    dist = [INF] * n
    dist[src] = 0
    relax = 0
    pq = [(0, src)]
    seen = [False] * n
    while pq:
        d, u = heapq.heappop(pq)
        if seen[u]:
            continue
        seen[u] = True
        for v, w in adj[u]:
            relax += 1
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                heapq.heappush(pq, (nd, v))
    return dist, relax


def dijkstra_array(n, adj, src):
    INF = float("inf")
    dist = [INF] * n
    dist[src] = 0
    relax = 0
    done = [False] * n
    for _ in range(n):
        best, bd = -1, INF
        for i in range(n):
            if not done[i] and dist[i] < bd:
                best, bd = i, dist[i]
        if best < 0:
            break
        done[best] = True
        for v, w in adj[best]:
            relax += 1
            nd = bd + w
            if nd < dist[v]:
                dist[v] = nd
    return dist, relax


def bellman_ford(n, adj, src):
    INF = float("inf")
    dist = [INF] * n
    dist[src] = 0
    relax = 0
    for _ in range(n - 1):
        changed = False
        for u in range(n):
            du = dist[u]
            if du == INF:
                continue
            for v, w in adj[u]:
                relax += 1
                if du + w < dist[v]:
                    dist[v] = du + w
                    changed = True
        if not changed:
            break
    return dist, relax


def spfa(n, adj, src):
    from collections import deque
    INF = float("inf")
    dist = [INF] * n
    dist[src] = 0
    relax = 0
    inq = [False] * n
    q = deque([src])
    inq[src] = True
    while q:
        u = q.popleft()
        inq[u] = False
        du = dist[u]
        for v, w in adj[u]:
            relax += 1
            if du + w < dist[v]:
                dist[v] = du + w
                if not inq[v]:
                    inq[v] = True
                    q.append(v)
    return dist, relax


def bfs_unit(n, adj, src):
    """Breadth-first search. CORRECT ONLY when every edge weight is 1.

    Deliberately included: it is dramatically faster where it applies and
    silently wrong elsewhere, so the domain contains a real correctness
    boundary for the critic to find.
    """
    from collections import deque
    INF = float("inf")
    dist = [INF] * n
    dist[src] = 0
    relax = 0
    q = deque([src])
    while q:
        u = q.popleft()
        du = dist[u]
        for v, w in adj[u]:
            relax += 1
            if dist[v] == INF:
                dist[v] = du + 1
                q.append(v)
    return dist, relax


ALGORITHMS = {
    "dijkstra_heap": [dijkstra_heap],
    "dijkstra_array": [dijkstra_array],
    "bellman_ford": [bellman_ford],
    "spfa": [spfa],
    "bfs_unit": [bfs_unit],
}
BASE_ROSTER = ["dijkstra_heap", "dijkstra_array", "bellman_ford", "spfa"]
CONDITIONAL = ["bfs_unit"]          # correct only on unit-weight graphs


# ------------------------------------------------------------- generators
def gen_sparse_random(n, seed):
    import random
    rnd = random.Random(seed)
    adj = [[] for _ in range(n)]
    for u in range(1, n):                     # spanning tree keeps it connected
        v = rnd.randrange(u)
        w = rnd.randint(1, 20)
        adj[u].append((v, w))
        adj[v].append((u, w))
    for _ in range(2 * n):
        u, v = rnd.randrange(n), rnd.randrange(n)
        if u != v:
            w = rnd.randint(1, 20)
            adj[u].append((v, w))
            adj[v].append((u, w))
    return adj


def gen_dense_random(n, seed):
    import random
    rnd = random.Random(seed)
    adj = [[] for _ in range(n)]
    target = max(1, (n * n) // 8)
    for u in range(1, n):
        v = rnd.randrange(u)
        w = rnd.randint(1, 20)
        adj[u].append((v, w))
        adj[v].append((u, w))
    for _ in range(target):
        u, v = rnd.randrange(n), rnd.randrange(n)
        if u != v:
            w = rnd.randint(1, 20)
            adj[u].append((v, w))
            adj[v].append((u, w))
    return adj


def gen_grid_2d(n, seed):
    """A square lattice. The graph has side^2 vertices, which is the largest
    square <= n — padding up to n would leave isolated vertices with infinite
    distance, and an unreachable vertex is a broken benchmark, not a topology.
    """
    import math
    import random
    rnd = random.Random(seed)
    side = max(2, int(math.isqrt(n)))
    total = side * side
    adj = [[] for _ in range(total)]
    for r in range(side):
        for c in range(side):
            i = r * side + c
            if c + 1 < side:
                w = rnd.randint(1, 9)
                adj[i].append((i + 1, w))
                adj[i + 1].append((i, w))
            if r + 1 < side:
                w = rnd.randint(1, 9)
                adj[i].append((i + side, w))
                adj[i + side].append((i, w))
    return adj


def gen_scale_free(n, seed):
    import random
    rnd = random.Random(seed)
    adj = [[] for _ in range(n)]
    targets = [0]
    for u in range(1, n):
        for _ in range(2):
            v = targets[rnd.randrange(len(targets))]
            if v != u:
                w = rnd.randint(1, 20)
                adj[u].append((v, w))
                adj[v].append((u, w))
                targets.append(v)
        targets.append(u)
    return adj


def gen_long_chain(n, seed):
    """A path with a few shortcuts: adversarial for queue-based relaxation."""
    import random
    rnd = random.Random(seed)
    adj = [[] for _ in range(n)]
    for u in range(n - 1):
        w = rnd.randint(1, 5)
        adj[u].append((u + 1, w))
        adj[u + 1].append((u, w))
    for _ in range(max(1, n // 20)):
        u = rnd.randrange(n)
        v = rnd.randrange(n)
        if u != v:
            w = rnd.randint(50, 100)
            adj[u].append((v, w))
            adj[v].append((u, w))
    return adj


def gen_unit_weight(n, seed):
    """Sparse graph with every weight 1 — the precondition for bfs_unit."""
    import random
    rnd = random.Random(seed)
    adj = [[] for _ in range(n)]
    for u in range(1, n):
        v = rnd.randrange(u)
        adj[u].append((v, 1))
        adj[v].append((u, 1))
    for _ in range(2 * n):
        u, v = rnd.randrange(n), rnd.randrange(n)
        if u != v:
            adj[u].append((v, 1))
            adj[v].append((u, 1))
    return adj


GENERATORS = {"sparse_random": gen_sparse_random, "dense_random": gen_dense_random,
              "grid_2d": gen_grid_2d, "scale_free": gen_scale_free,
              "long_chain": gen_long_chain, "unit_weight": gen_unit_weight}
PROBE_REGIMES = ["long_chain", "scale_free"]     # unseen during main rounds
UNIT_ONLY = ("unit_weight",)


RUNNER_TEMPLATE = '''"""Auto-generated by ORIGIN (graphbench domain). Self-contained experiment.

Design spec: see spec.json alongside this file. Versioned and kept forever.

Emits result schema v2 with BOTH wall-clock timing and a machine-independent
operation count (edge relaxations), plus input/output digests, so a replay can
verify the answer, not merely its speed.
"""
import hashlib, json, platform, statistics, sys, time

CONFIG = __CONFIG__
RESULT_SCHEMA_VERSION = 2

__SOURCES__

ALGORITHMS = {__ALG_MAP__}
GENERATORS = {__GEN_MAP__}


def digest(obj):
    h = hashlib.sha256()
    h.update(repr(obj).encode())
    return h.hexdigest()[:16]


def file_digest(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except OSError:
        return ""


def reference(n, adj, src):
    """Trusted baseline used ONLY to check correctness, never timed."""
    import heapq
    INF = float("inf")
    dist = [INF] * n
    dist[src] = 0
    pq = [(0, src)]
    seen = [False] * n
    while pq:
        d, u = heapq.heappop(pq)
        if seen[u]:
            continue
        seen[u] = True
        for v, w in adj[u]:
            if d + w < dist[v]:
                dist[v] = d + w
                heapq.heappush(pq, (d + w, v))
    return dist


def reference_workload():
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
    import os
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "system": platform.system(), "release": platform.release(),
        "machine": platform.machine(), "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "origin_version": CONFIG.get("origin_version", "unknown"),
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timer": "time.perf_counter",
        "timer_resolution_s": time.get_clock_info("perf_counter").resolution,
    }


def main():
    rows = []
    for alg_name in CONFIG["algorithms"]:
        fn = ALGORITHMS[alg_name]
        for regime in CONFIG["regimes"]:
            gen = GENERATORS[regime]
            for n in CONFIG["sizes"]:
                times, relax_counts = [], []
                correct = True
                in_dig = out_dig = ""
                for t in range(CONFIG["trials"]):
                    adj = gen(n, CONFIG["seed"] + t)
                    size = len(adj)
                    expected = reference(size, adj, 0)
                    if t == 0:
                        in_dig = digest([sorted(e) for e in adj])
                    t0 = time.perf_counter()
                    dist, relax = fn(size, adj, 0)
                    dt = time.perf_counter() - t0
                    if list(dist) != expected:
                        correct = False       # recorded, NOT crashed: a wrong
                        # answer is a research result about this candidate's
                        # preconditions, and the run must report it honestly.
                    if t == 0:
                        out_dig = digest(list(dist))
                    times.append(dt)
                    relax_counts.append(relax)
                stdev = statistics.stdev(times) if len(times) > 1 else 0.0
                rows.append({
                    "algorithm": alg_name, "regime": regime, "n": n,
                    "correct": correct, "trials": CONFIG["trials"],
                    "samples": times,
                    "mean_s": statistics.fmean(times),
                    "median_s": statistics.median(times),
                    "stdev_s": stdev,
                    "sem_s": stdev / (len(times) ** 0.5) if len(times) > 1 else 0.0,
                    "min_s": min(times),
                    "relaxations": int(statistics.median(relax_counts)),
                    "input_digest": in_dig, "output_digest": out_dig,
                })
    payload = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "environment": environment(), "config": CONFIG,
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
class GraphBenchDomain(ResearchDomain):
    name = "graphbench"

    # v2.1: metrics declare what they are, so the core applies the right rule
    # instead of the domain routing around a timing-shaped gate (gap 7).
    metric_kinds = {"mean_s": st_.TIMING, "relaxations": st_.EXACT}

    # ------------------------------------------------------------ planning
    def decompose(self, question: str, config: dict) -> dict:
        return {
            "question": question,
            "subquestions": [
                {"id": "q1", "text": "Which shortest-path method is fastest on "
                                     "each graph topology at the tested sizes?"},
                {"id": "q2", "text": "Do the machine-independent relaxation "
                                     "counts agree with the wall-clock ranking?"},
                {"id": "q3", "text": "Under what precondition is the BFS "
                                     "candidate correct, and is it detected?"},
            ],
            "regimes": config.get("regimes", list(GENERATORS)),
            "sizes": config.get("sizes", [128, 512]),
        }

    def initial_assumptions(self) -> list[str]:
        return [
            "All graphs are connected and undirected with positive integer "
            "weights, so Dijkstra's preconditions hold.",
            "Source vertex is always 0; results describe single-source "
            "shortest paths only.",
            "Pure-Python implementations: constant factors dominate at these "
            "sizes and do not transfer to compiled implementations.",
            "Edge relaxations are counted identically across candidates, so the "
            "count is comparable; wall-clock time is host-specific.",
        ]

    def seed_knowledge(self, state) -> None:
        src = Source(id=new_id("src"), kind="prior_knowledge",
                     title="Standard shortest-path complexity results",
                     locator="textbook", reliability=0.95)
        state.add(src)
        for text in (
                "Dijkstra with a binary heap runs in O((V+E) log V) on graphs "
                "with non-negative weights.",
                "Bellman-Ford runs in O(V*E) and tolerates negative weights, "
                "which are not present in this benchmark.",
                "Breadth-first search computes shortest paths only when every "
                "edge weight is equal."):
            claim = Claim(id=new_id("clm"), text=text,
                          status=EpistemicStatus.FACT, confidence=0.95,
                          source_ids=[src.id],
                          notes="asymptotic result; says nothing about constant "
                                "factors at the tested sizes")
            state.add(claim)
        state.log_event("seeded", "prior complexity results recorded as FACT "
                                  "with an explicit constant-factor caveat")

    # --------------------------------------------------------- hypotheses
    def generate_hypotheses(self, state) -> list:
        if state.flags.get("graph_hypotheses_seeded"):
            return []
        state.flags["graph_hypotheses_seeded"] = True

        def P(text, check):
            return Prediction(id=new_id("pred"), text=text, check=check)

        return [
            Hypothesis(
                id=new_id("hyp"),
                statement="Dijkstra with a binary heap is fastest on sparse "
                          "random graphs at the tested sizes.",
                rationale="Heap ordering avoids the O(V^2) scan that dominates "
                          "the array variant when the graph is sparse.",
                predictions=[P("dijkstra_heap is fastest on sparse_random",
                               {"type": "fastest_on",
                                "algorithm": "dijkstra_heap",
                                "regime": "sparse_random"})],
                importance=0.8, cost_estimate=1.0),
            Hypothesis(
                id=new_id("hyp"),
                statement="The array-scan Dijkstra beats the heap variant on "
                          "dense graphs, where the scan cost is amortised.",
                rationale="With E ~ V^2/8 the heap's per-edge push cost "
                          "outweighs the array's per-vertex scan.",
                predictions=[P("dijkstra_array beats dijkstra_heap on dense_random",
                               {"type": "beats", "algorithm": "dijkstra_array",
                                "than": "dijkstra_heap", "regime": "dense_random",
                                "min_pct": 0.0})],
                importance=0.75, cost_estimate=1.0),
            Hypothesis(
                id=new_id("hyp"),
                statement="Bellman-Ford performs the most edge relaxations of "
                          "any candidate on every tested topology.",
                rationale="It relaxes every edge on every pass rather than "
                          "settling vertices once.",
                predictions=[P("bellman_ford has the highest relaxation count",
                               {"type": "most_relaxations",
                                "algorithm": "bellman_ford"})],
                importance=0.7, cost_estimate=1.0),
            Hypothesis(
                id=new_id("hyp"),
                statement="SPFA performs fewer relaxations than Bellman-Ford on "
                          "sparse random graphs.",
                rationale="Queue-driven relaxation revisits only vertices whose "
                          "distance improved.",
                predictions=[P("spfa uses fewer relaxations than bellman_ford "
                               "on sparse_random",
                               {"type": "fewer_relaxations",
                                "algorithm": "spfa", "than": "bellman_ford",
                                "regime": "sparse_random"})],
                importance=0.7, cost_estimate=1.0),
            Hypothesis(
                id=new_id("hyp"),
                statement="The BFS candidate returns correct distances on "
                          "unit-weight graphs and incorrect distances on every "
                          "weighted topology.",
                rationale="BFS assumes uniform edge cost; the benchmark should "
                          "detect the boundary rather than assume it.",
                predictions=[
                    P("bfs_unit is correct on unit_weight",
                      {"type": "correct_on", "algorithm": "bfs_unit",
                       "regime": "unit_weight"}),
                    P("bfs_unit is incorrect on sparse_random",
                      {"type": "incorrect_on", "algorithm": "bfs_unit",
                       "regime": "sparse_random"})],
                importance=0.9, cost_estimate=1.0,
                tags=["correctness_boundary"]),
        ]

    # ------------------------------------------------- LLM proposal contract
    def proposal_context(self, state) -> dict:
        cfg = self._config(state)
        return {
            "mission": state.meta["question"],
            "algorithms": BASE_ROSTER + CONDITIONAL,
            "regimes": cfg.get("regimes", list(GENERATORS)),
            "check_kinds": {
                "fastest_on": {"params": ["algorithm", "regime"]},
                "beats": {"params": ["a", "b", "regime"],
                          "meaning": "a has lower mean time than b"},
                "fewer_relaxations": {"params": ["a", "b", "regime"],
                                      "meaning": "machine-independent count"},
                "correct_on": {"params": ["algorithm", "regime"]},
            },
            "existing_statements": [h.statement for h in state.hypotheses.values()],
        }

    def build_check(self, kind: str, params: dict, state) -> dict:
        cfg = self._config(state)
        regimes = cfg.get("regimes", list(GENERATORS))
        roster = BASE_ROSTER + CONDITIONAL

        def alg(name):
            if name not in roster:
                raise ValueError(f"unknown algorithm {name!r}")
            return name

        def reg(r):
            if r not in regimes:
                raise ValueError(f"regime {r!r} not in mission regimes {regimes}")
            return r

        if kind == "fastest_on":
            return {"type": "fastest_on", "algorithm": alg(params["algorithm"]),
                    "regime": reg(params["regime"])}
        if kind == "beats":
            return {"type": "beats", "algorithm": alg(params["a"]),
                    "than": alg(params["b"]), "regime": reg(params["regime"]),
                    "min_pct": float(params.get("min_pct", 0.0))}
        if kind == "fewer_relaxations":
            return {"type": "fewer_relaxations", "algorithm": alg(params["a"]),
                    "than": alg(params["b"]), "regime": reg(params["regime"])}
        if kind == "correct_on":
            return {"type": "correct_on", "algorithm": alg(params["algorithm"]),
                    "regime": reg(params["regime"])}
        raise ValueError(f"unknown prediction kind {kind!r}")

    # -------------------------------------------------------- experiments
    def _config(self, state) -> dict:
        return state.meta.get("domain_config", {})

    def _roster_for(self, cfg) -> list:
        return list(BASE_ROSTER) + list(CONDITIONAL)

    def design_experiment(self, primary, pending, state) -> dict | None:
        cfg = self._config(state)
        return {
            "kind": "benchmark", "round": 1,
            "algorithms": self._roster_for(cfg),
            "regimes": cfg.get("regimes", ["sparse_random", "dense_random",
                                           "grid_2d", "unit_weight"]),
            "sizes": cfg.get("sizes", [128, 512]),
            "trials": cfg.get("trials", 5),
            "seed": cfg.get("seed", 4242),
            "timeout_s": cfg.get("timeout_s", 600),
            "hypothesis_ids": [h.id for h in pending],
        }

    def replication_design(self, hypothesis, state) -> dict | None:
        cfg = self._config(state)
        return {
            "kind": "benchmark", "round": 2,
            "algorithms": self._roster_for(cfg),
            "regimes": cfg.get("regimes", ["sparse_random", "dense_random",
                                           "grid_2d", "unit_weight"]),
            "sizes": [max(cfg.get("sizes", [512]))],
            "trials": cfg.get("trials", 5),
            "seed": cfg.get("seed", 4242) + 1000,
            "timeout_s": cfg.get("timeout_s", 600),
            "hypothesis_ids": [hypothesis.id],
        }

    def falsification_design(self, hypothesis, state) -> dict | None:
        cfg = self._config(state)
        probes = []
        for pred in hypothesis.predictions:
            chk = dict(pred.check)
            if chk.get("type") in ("fastest_on", "beats", "fewer_relaxations",
                                   "correct_on"):
                if "regime" in chk:
                    probes.append({"label": f"boundary:{chk['regime']}",
                                   "check": chk, "role": "boundary"})
                    for pr in PROBE_REGIMES:
                        c2 = dict(chk)
                        c2["regime"] = pr
                        probes.append({"label": f"scope:{pr}", "check": c2,
                                       "role": "scope"})
                else:
                    probes.append({"label": "boundary:all", "check": chk,
                                   "role": "boundary"})
        if not probes:
            return None
        needed = sorted({p["check"].get("regime") for p in probes
                         if p["check"].get("regime")})
        return {
            "kind": "falsification", "round": 9,
            "algorithms": self._roster_for(cfg),
            "regimes": needed or ["sparse_random"],
            "sizes": [2 * max(cfg.get("sizes", [512]))],
            "trials": cfg.get("trials", 5),
            "seed": cfg.get("seed", 4242) + 7777,
            "timeout_s": cfg.get("timeout_s", 600),
            "hypothesis_ids": [hypothesis.id],
            "probe_checks": probes,
        }

    def evaluate_falsification(self, record, result, hypothesis) -> dict:
        rows = result["rows"]
        design = record.design
        n_top = max(design["sizes"])
        boundary_bad, details = [], []
        per_regime: dict[str, list[str]] = {}
        for pc in design.get("probe_checks", []):
            outcome, detail, _ = self._eval(pc["check"], rows, design, n_top)
            details.append(f"[{pc['label']}] {outcome}: {detail}")
            if pc["role"] == "boundary" and outcome == "refuted":
                boundary_bad.append(pc["label"])
            if pc["role"] == "scope":
                per_regime.setdefault(pc["check"].get("regime", pc["label"]),
                                      []).append(outcome)
        if boundary_bad:
            return {"outcome": "failed", "scope": "",
                    "detail": " | ".join(details)}
        extends = sorted(r for r, v in per_regime.items()
                         if all(o == "confirmed" for o in v))
        refuted = sorted(r for r, v in per_regime.items()
                         if any(o == "refuted" for o in v))
        untested = sorted(r for r in per_regime
                          if r not in extends and r not in refuted)
        scope = ("holds at n<=2x tested sizes on its original topology"
                 + (f"; extends to {extends}" if extends else "")
                 + (f"; does NOT extend to {refuted}" if refuted else "")
                 + (f"; untested on {untested}" if untested else ""))
        return {"outcome": "survived", "scope": scope,
                "detail": " | ".join(details)}

    def estimate_cost(self, design: dict) -> float:
        return (len(design["algorithms"]) * len(design["regimes"])
                * sum(design["sizes"]) * design["trials"]) / 40_000.0

    def write_runner(self, design: dict, exp_dir: Path) -> Path:
        seen, chunks = set(), []
        for r in design["regimes"]:
            gen = GENERATORS[r]
            if gen not in seen:
                chunks.append(inspect.getsource(gen))
                seen.add(gen)
        entries = []
        for alg in design["algorithms"]:
            fn = ALGORITHMS[alg][-1]
            if fn not in seen:
                chunks.append(inspect.getsource(fn))
                seen.add(fn)
            entries.append(f'"{alg}": {fn.__name__}')
        from .. import __version__ as origin_version
        runner_config = dict(design, origin_version=origin_version)
        code = (RUNNER_TEMPLATE
                .replace("__CONFIG__", json.dumps(runner_config, indent=4))
                .replace("__SOURCES__", "\n\n".join(chunks))
                .replace("__ALG_MAP__", ", ".join(entries))
                .replace("__GEN_MAP__", ", ".join(
                    f'"{r}": {GENERATORS[r].__name__}' for r in design["regimes"])))
        path = exp_dir / "run.py"
        path.write_text(code)
        (exp_dir / "spec.json").write_text(json.dumps(runner_config, indent=2))
        return path

    # ------------------------------------------------------------ analysis
    def analyze(self, record, result: dict, state) -> dict:
        rows = result["rows"]
        design = record.design
        n_top = max(design["sizes"])
        replication = design.get("seed", 0) != self._config(state).get("seed", 4242)

        winners = {}
        for regime in design["regimes"]:
            ranked = sorted((r for r in rows
                             if r["regime"] == regime and r["n"] == n_top
                             and r["correct"]
                             and state.is_valid(r["algorithm"], regime)),
                            key=lambda r: r["mean_s"])
            if not ranked:
                continue
            cells = {r["algorithm"]: st_.row_stats(r) for r in ranked}
            tied = [x for x in st_.indistinguishable_set(cells)
                    if x != ranked[0]["algorithm"]]
            winners[regime] = {"algorithm": ranked[0]["algorithm"],
                               "decisive": not tied,
                               "indistinguishable_from": tied}
            if tied:
                state.cautions.append(
                    f"Topology '{regime}' at n={n_top} in {record.id}: "
                    f"{ranked[0]['algorithm']} has the lowest mean but is not "
                    f"separable from {', '.join(tied)} at "
                    f"{design.get('trials')} trials — no winner is claimed.")

        summary = {"winners": {k: v["algorithm"] for k, v in winners.items()},
                   "evaluated": [], "new_hypotheses": []}

        # Incorrect results are research findings, recorded before any timing.
        wrong = [(r["algorithm"], r["regime"]) for r in rows if not r["correct"]]
        for alg, regime in sorted(set(wrong)):
            known = not state.is_valid(alg, regime)
            inv = state.record_invalidity(
                alg, regime,
                "returned distances that disagree with the reference "
                "shortest-path computation",
                experiment_id=record.id)
            if not known:
                state.failures.append({
                    "experiment": record.id, "hypothesis": "",
                    "kind": "incorrect_output", "prediction": "(correctness)",
                    "expected": "distances equal to the reference",
                    "observed": f"{alg} returned wrong distances on '{regime}'",
                    "action": f"recorded as invalidity {inv.id}; the core "
                              f"excludes it from rankings on this topology",
                    "ts": now()})

        for hid in record.hypothesis_ids:
            h = state.hypotheses.get(hid)
            if h is None:
                continue
            h.tested_in.append(record.id)
            outcomes = []
            for pr in h.predictions:
                verdict, detail, strength = self._eval(pr.check, rows, design,
                                                       n_top)
                outcomes.append(verdict)
                direction = {"confirmed": "supports",
                             "refuted": "contradicts"}.get(verdict, "inconclusive")
                if verdict == "inconclusive":
                    strength = min(strength, 0.2)
                # NB: computed outside the f-string. Multi-line expressions
                # inside f-strings are PEP 701 (Python 3.12+), and ORIGIN's
                # declared support floor is 3.10 — caught by the matrix run.
                phase_label = ("replication" if replication
                               else f"round {design.get('round')}")
                ev = Evidence(id=new_id("evd"), target_id=h.id,
                              direction=direction, strength=round(strength, 3),
                              kind="experiment",
                              summary=(f"[{phase_label}] {pr.text}: "
                                       f"{verdict} ({detail})"),
                              experiment_id=record.id, payload={})
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
                            "prediction": pr.text,
                            "expected": "replicated confirmation",
                            "observed": detail,
                            "action": f"{h.id} downgraded to WEAKENED",
                            "ts": now()})
                else:
                    pr.outcome, pr.detail = verdict, detail
                    if verdict == "refuted":
                        state.failures.append({
                            "experiment": record.id, "hypothesis": h.id,
                            "prediction": pr.text, "expected": pr.text,
                            "observed": detail,
                            "action": "hypothesis status re-evaluated",
                            "ts": now()})
                summary["evaluated"].append({"hypothesis": h.id,
                                             "prediction": pr.text,
                                             "verdict": verdict,
                                             "detail": detail})
            old = h.status
            if replication:
                if any(p.outcome == "unstable" for p in h.predictions):
                    h.revise(HypothesisStatus.WEAKENED,
                             f"failed replication in {record.id}")
                elif "needs_replication" in h.tags:
                    h.tags.remove("needs_replication")
                    h.tags.append("replicated")
                    state.log_event("replicated",
                                    f"{h.id} survived independent replication")
            else:
                if all(o == "confirmed" for o in outcomes):
                    h.revise(HypothesisStatus.PROVISIONALLY_SUPPORTED,
                             f"all predictions confirmed in {record.id}")
                    if "needs_replication" not in h.tags:
                        h.tags.append("needs_replication")
                elif all(o == "refuted" for o in outcomes):
                    h.revise(HypothesisStatus.REJECTED,
                             f"all predictions refuted in {record.id}")
                elif any(o == "refuted" for o in outcomes):
                    h.revise(HypothesisStatus.WEAKENED,
                             f"mixed prediction outcomes in {record.id}")
                else:
                    h.revise(HypothesisStatus.WEAKENED,
                             f"predictions not resolvable at "
                             f"{design.get('trials')} trials in {record.id}")
                    state.cautions.append(
                        f"{h.id}: nothing resolvable at this trial count; treat "
                        f"as untested rather than disproved.")
            if h.status != old:
                state.record_confidence_change("hypothesis", h.id, old.value,
                                               h.status.value,
                                               f"evidence from {record.id}")
            h.updated_at = now()

        # Machine-independent finding: relaxation ranking, recorded once.
        if not replication and not state.flags.get("relax_claim"):
            state.flags["relax_claim"] = True
            per_regime = {}
            for regime in design["regimes"]:
                cells = [(r["algorithm"], r.get("relaxations", 0)) for r in rows
                         if r["regime"] == regime and r["n"] == n_top and r["correct"]]
                if cells:
                    per_regime[regime] = min(cells, key=lambda c: c[1])[0]
            if per_regime:
                env = result.get("environment", {})
                claim = Claim(
                    id=new_id("clm"),
                    text=("Fewest edge relaxations at n=" + str(n_top) + " by "
                          "topology: " + ", ".join(f"{k}={v}" for k, v in
                                                   per_regime.items())
                          + " (machine-independent count; measured on "
                          + f"{env.get('python_implementation', 'CPython')} "
                          + f"{env.get('python_version', '?')})"),
                    status=EpistemicStatus.EXPERIMENTAL_RESULT, confidence=0.6,
                    source_ids=[])
                state.add(claim)
                state.record_confidence_change("claim", claim.id, None, 0.6,
                                               f"measured in {record.id}")
        state.flags[f"analyzed_{record.id}"] = True
        return summary

    # -------------------------------------------------- prediction checking
    def _eval(self, check, rows, design, n_top):
        t = check["type"]

        def row(alg, regime, n=None):
            n = n_top if n is None else n
            for r in rows:
                if (r["algorithm"] == alg and r["regime"] == regime
                        and r["n"] == n):
                    return r
            return None

        scope = f"n={n_top}, {design.get('trials')} trials"

        if t in ("correct_on", "incorrect_on"):
            r = row(check["algorithm"], check["regime"])
            if r is None:
                return "inconclusive", "not measured", 0.0
            want = (t == "correct_on")
            ok = bool(r["correct"]) == want
            return ("confirmed" if ok else "refuted",
                    f"{check['algorithm']} on '{check['regime']}' returned "
                    f"{'correct' if r['correct'] else 'INCORRECT'} distances "
                    f"[{scope}]", 0.9)

        if t == "fastest_on":
            regime = check["regime"]
            ranked = sorted((r for r in rows if r["regime"] == regime
                             and r["n"] == n_top and r["correct"]),
                            key=lambda r: r["mean_s"])
            if len(ranked) < 2:
                return "inconclusive", "insufficient correct candidates", 0.0
            cmp_ = st_.compare(st_.row_stats(ranked[0]), st_.row_stats(ranked[1]))
            claimed = check["algorithm"]
            if claimed == ranked[0]["algorithm"]:
                if not cmp_["decisive"]:
                    return ("inconclusive",
                            f"{claimed} has the lowest mean on '{regime}' but is "
                            f"not decisively ahead of {ranked[1]['algorithm']}: "
                            f"{cmp_['reason']} [{scope}]", cmp_["margin"] * 0.5)
                return ("confirmed",
                        f"fastest on '{regime}' is {claimed} "
                        f"(+{cmp_['margin']*100:.0f}% over "
                        f"{ranked[1]['algorithm']}, decisive) [{scope}]",
                        cmp_["margin"])
            claimed_row = row(claimed, regime)
            if claimed_row is None:
                return ("refuted",
                        f"{claimed} produced no correct result on '{regime}'; "
                        f"fastest correct candidate is {ranked[0]['algorithm']} "
                        f"[{scope}]", 0.6)
            head = st_.compare(st_.row_stats(ranked[0]), st_.row_stats(claimed_row))
            if not head["decisive"]:
                return ("inconclusive",
                        f"{ranked[0]['algorithm']} leads on '{regime}' but is "
                        f"not decisively separated from {claimed}: "
                        f"{head['reason']} [{scope}]", head["margin"] * 0.5)
            return ("refuted",
                    f"fastest on '{regime}' is {ranked[0]['algorithm']}, not "
                    f"{claimed} ({head['margin']*100:.0f}% apart) [{scope}]",
                    head["margin"])

        if t == "beats":
            ra, rb = row(check["algorithm"], check["regime"]), row(check["than"],
                                                                  check["regime"])
            if ra is None or rb is None:
                return "inconclusive", "not measured", 0.0
            if not (ra["correct"] and rb["correct"]):
                return ("inconclusive",
                        "a candidate returned incorrect distances here; timing "
                        "comparison withheld", 0.1)
            cmp_ = st_.compare(st_.row_stats(ra), st_.row_stats(rb))
            pct = (rb["mean_s"] - ra["mean_s"]) / max(ra["mean_s"], 1e-12) * 100
            if not cmp_["decisive"]:
                return ("inconclusive",
                        f"{check['algorithm']} vs {check['than']} on "
                        f"'{check['regime']}': {pct:+.0f}% but not decisive "
                        f"({cmp_['reason']}) [{scope}]", abs(pct) / 200)
            if cmp_["relation"] == st_.SLOWER:
                return ("refuted",
                        f"{check['algorithm']} is decisively SLOWER than "
                        f"{check['than']} on '{check['regime']}' ({pct:+.0f}%) "
                        f"[{scope}]", abs(pct) / 100)
            return ("confirmed" if pct >= check.get("min_pct", 0.0) else "refuted",
                    f"{check['algorithm']} vs {check['than']} on "
                    f"'{check['regime']}': {pct:+.0f}% (decisive) [{scope}]",
                    abs(pct) / 100)

        if t == "fewer_relaxations":
            ra, rb = row(check["algorithm"], check["regime"]), row(check["than"],
                                                                  check["regime"])
            if ra is None or rb is None:
                return "inconclusive", "not measured", 0.0
            a, b = ra.get("relaxations", 0), rb.get("relaxations", 0)
            if b == 0:
                return "inconclusive", "no relaxation count recorded", 0.0
            ratio = (b - a) / b * 100
            # Declared EXACT, so the core skips the timing noise gate entirely.
            cmp_ = st_.compare({"mean_s": a}, {"mean_s": b},
                               metric_kind=self.metric_kinds["relaxations"])
            if not cmp_["decisive"]:
                return ("inconclusive",
                        f"{check['algorithm']} and {check['than']} performed the "
                        f"same number of relaxations ({a:,}) on "
                        f"'{check['regime']}' [{cmp_['reason']}]", 0.05)
            return ("confirmed" if a < b else "refuted",
                    f"{check['algorithm']} performed {a:,} relaxations vs "
                    f"{check['than']} {b:,} on '{check['regime']}' "
                    f"({ratio:+.0f}%); exact counts, machine-independent "
                    f"[n={n_top}]", min(0.9, abs(ratio) / 100))

        if t == "most_relaxations":
            worst = {}
            for regime in design["regimes"]:
                cells = [(r["algorithm"], r.get("relaxations", 0)) for r in rows
                         if r["regime"] == regime and r["n"] == n_top]
                if cells:
                    worst[regime] = max(cells, key=lambda c: c[1])[0]
            if not worst:
                return "inconclusive", "no relaxation counts", 0.0
            claimed = check["algorithm"]
            always = all(v == claimed for v in worst.values())
            return ("confirmed" if always else "refuted",
                    f"highest relaxation count by topology: "
                    f"{ {k: v for k, v in worst.items()} } [n={n_top}]", 0.7)

        return "inconclusive", f"unknown check type {t}", 0.0

    # ------------------------------------------------------------- gaps
    def knowledge_gaps(self, state) -> list[str]:
        return [
            "Directed graphs and negative edge weights are not benchmarked; "
            "Bellman-Ford's actual advantage is therefore untested here.",
            "Only single-source queries from vertex 0 are measured.",
            "Memory use and cache behaviour are not instrumented, so the "
            "dense/sparse crossover is explained only by relaxation counts and "
            "wall-clock time.",
        ]
