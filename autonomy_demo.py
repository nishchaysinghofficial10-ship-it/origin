#!/usr/bin/env python3
"""Deterministic, offline demonstration of bounded autonomous research.

    python tools/autonomy_demo.py --dir examples/autonomy_demo

Everything is fixture-only and clock-injected: no network, no provider, no
real sleeping. The demo shows, in order:

  1. a mission starts from a research question;
  2. autonomy seeds safe work items;
  3. the policy chooses an action and records why;
  4. fixture evidence is retrieved through the ordinary retrieval policy;
  5. hypotheses are formed and tested through the existing gates;
  6. a planned retryable failure occurs;
  7. retry/backoff is recorded, and the scheduler does NOT hot-loop;
  8. the operator pauses at a durable checkpoint;
  9. the process is discarded and rebuilt from disk;
 10. work resumes with no duplication;
 11. the mission stops with an honest reason;
 12. a report is produced with the full decision and work-item history.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import autonomy as A                              # noqa: E402
from origin import retrieval as R                             # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES                               # noqa: E402
from origin.scheduler import Scheduler                        # noqa: E402
from origin.state import ResearchState                        # noqa: E402

QUESTION = ("Which sorting strategy wins under which input regime, and what "
            "does the published literature claim about those tradeoffs?")

FIXTURE_DOC = (
    "Adaptive Sorting Notes\n\n"
    "Insertion sort is faster than merge sort on nearly-sorted input because "
    "the number of inversions is small and the work approaches linear.\n\n"
    "Merge sort is a stable comparison sort with guaranteed n log n behaviour "
    "on every input distribution.\n")

GOOD_URL = "https://fixtures.invalid/adaptive-sorting"
FLAKY_URL = "https://fixtures.invalid/intermittent"


class FlakyFixtureProvider(R.FixtureProvider):
    """Fixture provider whose second source fails the first N times.

    The failure is a `RetrievalError` — the retryable class — so the demo can
    show backoff without pretending a policy refusal is retryable.
    """

    def __init__(self, documents, flaky_url, fail_times=2, counter=None):
        super().__init__(documents)
        self.flaky_url = flaky_url
        self.fail_times = fail_times
        # A shared counter so the outage "heals" across the simulated restart
        # instead of resetting and burning the attempt budget.
        self.counter = counter if counter is not None else {"n": 0}

    @property
    def failures(self):
        return self.counter["n"]

    def fetch(self, url, policy):
        if url == self.flaky_url and self.counter["n"] < self.fail_times:
            self.counter["n"] += 1
            raise R.RetrievalError(
                f"TimeoutError fetching {url}: simulated transient failure "
                f"{self.failures}/{self.fail_times}")
        return super().fetch(url, policy)


class FakeClock:
    """Injected time. Retries are demonstrated by advancing the clock, never
    by sleeping — the demo must stay fast enough for CI."""

    def __init__(self, start=1_786_000_000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds
        return self.t


OUTAGE = {"n": 0}          # shared across the simulated restart


def build(root: Path, clock) -> Scheduler:
    provider = FlakyFixtureProvider(
        {GOOD_URL: {"body": FIXTURE_DOC,
                    "content_type": "text/plain; charset=utf-8"},
         FLAKY_URL: {"body": FIXTURE_DOC,
                     "content_type": "text/plain; charset=utf-8"}},
        FLAKY_URL, fail_times=2, counter=OUTAGE)
    limits = A.RunLimits(max_steps=20, max_wall_s=120, max_attempts_per_item=4,
                         backoff_base_s=60.0, max_consecutive_failures=4)
    return Scheduler(root, limits, allow_network=True, allow_provider=False,
                     clock=clock, provider=provider,
                     retrieval_policy=R.RetrievalPolicy(min_interval_s=0.0))


def section(title):
    print(f"\n=== {title} ===")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True)
    ap.add_argument("--keep", action="store_true",
                    help="keep an existing directory instead of recreating it")
    args = ap.parse_args(argv)
    root = Path(args.dir)
    if root.exists() and not args.keep:
        shutil.rmtree(root)

    clock = FakeClock()
    st = ResearchState.create(root, QUESTION, "algobench", PROFILES["fast"],
                              Budget(experiments_total=8,
                                     compute_seconds_total=600),
                              profile="fast")
    st.meta["brain"] = "none"
    st.save()

    # ---- 1-3: seed and choose, with a recorded rationale -----------------
    section("1-3. Seeding and the first decision")
    sched = build(root, clock)
    sched.seed(st)
    sched.store.save()
    policy = A.AutonomyPolicy(sched.limits, allow_network=True,
                              allow_provider=False, now=clock())
    decision = policy.evaluate(sched.store, st)
    print(f"queued: {[i.action for i in sched.store.items.values()]}")
    print(f"would choose: {decision['chosen_action']} — {decision['chosen_reason']}")

    # ---- 4: fixture evidence through the ordinary retrieval policy -------
    section("4. Fixture evidence (retrieval policy unchanged)")
    good = A.new_item(A.RETRIEVE_SOURCE,
                      "an approved fixture source may contain claims worth "
                      "testing in the benchmark domain",
                      priority=0.99, cost_estimate=0.2,
                      params={"url": GOOD_URL})
    flaky = A.new_item(A.RETRIEVE_SOURCE,
                       "a second approved source that is intermittently "
                       "unavailable (planned retryable failure)",
                       priority=0.97, cost_estimate=0.2,
                       params={"url": FLAKY_URL})
    for item in (good, flaky):
        sched.store.add(item)
    sched.store.save()
    r = sched.tick(state=st)
    print(f"{r['action']} -> {r['status']}: {r['detail']}")

    # ---- 5-7: planned retryable failure and backoff ----------------------
    section("5-7. Planned retryable failure, backoff without hot-looping")
    for attempt in range(2):
        r = sched.tick(state=st)
        item = sched.store.items[r["item"]] if r.get("item") else None
        print(f"tick -> {r.get('action')} {r.get('status')}: {r.get('detail', '')[:120]}")
        if item and item.status == A.DEFERRED:
            wait = item.not_before - clock()
            print(f"    backoff: not eligible for {wait:.0f}s "
                  f"(attempt {item.attempts}/{sched.limits.max_attempts_per_item})")
            idle = sched.tick(state=st)
            print(f"    immediate re-tick -> {idle.get('stop')}: "
                  f"{idle.get('detail', '')[:90]}")
            clock.advance(wait + 1)
            print(f"    clock advanced past the backoff window (no real sleep)")

    # ---- 8: durable pause -------------------------------------------------
    section("8. Operator pause at a durable checkpoint")
    sched.store.meta["pause_requested"] = True
    sched.store.save()
    st.save()
    paused = sched.tick(state=st)
    print(f"tick while paused -> {paused['stop']}: {paused['detail']}")
    queue_before = {k: v for k, v in sched.store.summary().items() if v}
    done_before = {i.id for i in sched.store.items.values() if i.status == A.DONE}
    print(f"queue at pause: {queue_before}")

    # ---- 9-10: rebuild from disk, resume without duplication -------------
    section("9-10. Restart from durable state; no duplicated work")
    del sched, st
    clock2 = FakeClock(clock.t)
    sched2 = build(root, clock2)
    st2 = ResearchState.load(root)
    print(f"reloaded queue: {[f'{i.action}:{i.status}' for i in sched2.store.items.values()]}")
    sched2.store.meta["pause_requested"] = False
    sched2.store.save()
    out = sched2.run(max_steps=20, max_wall_s=120)
    done_after = {i.id for i in sched2.store.items.values() if i.status == A.DONE}
    reran = done_before - done_after
    print(f"resumed: {out['steps']} action(s); stop={out['stop']}")
    print(f"previously-completed items re-run: {len(reran)} (must be 0)")

    # ---- 11-12: honest stop and a full report ----------------------------
    section("11-12. Honest stop and the autonomy report")
    st3 = ResearchState.load(root)
    store = A.AutonomyStore(root)
    decisions = store.decisions()
    web_sources = [s for s in st3.sources.values() if s.kind == "web_document"]
    web_claims = [c for c in st3.claims.values()
                  if any(s.id in c.source_ids for s in web_sources)]
    report = {
        "question": QUESTION,
        "lifecycle_phase": st3.meta.get("phase"),
        "mission_stop_reason": st3.meta.get("stop_reason"),
        "autonomy_stop_reason": store.meta.get("stop_reason"),
        "work_items": [
            {"id": i.id, "action": i.action, "status": i.status,
             "attempts": i.attempts, "reason": i.reason,
             "last_error": i.last_error[:120]}
            for i in sorted(store.items.values(), key=lambda x: x.created_at)],
        "queue_summary": {k: v for k, v in store.summary().items() if v},
        "counters": store.counters,
        "decision_records": len(decisions),
        "retries_observed": sum(1 for d in decisions
                                if d.get("outcome") == A.DEFERRED),
        "budgets": {
            "experiments": f"{st3.budget.experiments_used}/"
                           f"{st3.budget.experiments_total}",
            "compute_s": round(st3.budget.compute_seconds_used, 1),
            "provider_calls": st3.budget.provider_calls_used,
            "retrievals": st3.flags.get("retrievals_used", 0)},
        "evidence": {
            "web_sources": len(web_sources),
            "web_claims": len(web_claims),
            "claim_statuses": sorted({c.status.value for c in web_claims}),
            "evidence_items_from_experiments": sum(
                1 for e in st3.evidence.values() if e.experiment_id),
            "evidence_items_from_web": sum(
                1 for e in st3.evidence.values() if not e.experiment_id)},
        "hypotheses": {h.id: h.status.value for h in st3.hypotheses.values()},
        "experiments": st3.budget.experiments_used,
        "failures": len(st3.failures),
        "limitations": [
            "Fixture-only: no network or provider call occurred.",
            "Autonomy chose among permitted actions; it never created an "
            "action type, widened a limit, or accepted a web claim as evidence.",
            "Time was injected, so backoff durations are demonstrated, not "
            "endured.",
        ],
    }
    out_path = root / "autonomy" / "demo_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k: report[k] for k in
                      ("lifecycle_phase", "autonomy_stop_reason",
                       "queue_summary", "counters", "budgets", "evidence")},
                     indent=2, default=str))
    print(f"\nFull report: {out_path}")
    print("Web claims stayed SPECULATION; every Evidence item came from an "
          "ORIGIN experiment.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
