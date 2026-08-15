"""ORIGIN command line (v1.0).

    python -m origin init "QUESTION" --dir runs/demo [--brain mock|anthropic|none]
    python -m origin run --dir runs/demo [--steps N]
    python -m origin status | report | timeline | html | verify --dir runs/demo
    python -m origin replay --dir runs/demo --exp exp_xxxx [--tolerance 0.5]
    python -m origin ingest --dir runs/demo --file notes.md
    python -m origin cancel --dir runs/demo
"""
from __future__ import annotations

import argparse
import json
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import lifecycle as lc
from . import sandbox
from .brain import BrainConfigError, make_brain
from .budget import Budget
from .controller import ResearchController
from .domains.base import get_domain
from .replay import ReplayPolicy, compare_results, render
from .report import render_html, render_timeline, status_box, write_reports
from . import stats
from .state import CheckpointCorrupted, ResearchState

PROFILES = {
    "standard": {"sizes": [400, 1600], "trials": 7, "seed": 1234,
                 "regimes": ["random", "nearly_sorted", "reversed", "few_unique"],
                 "timeout_s": 600},
    "fast": {"sizes": [64, 128], "trials": 5, "seed": 1234,
             "regimes": ["random", "nearly_sorted", "reversed", "few_unique"],
             "timeout_s": 120},
    "graph_fast": {"sizes": [64, 128], "trials": 5, "seed": 4242,
                   "regimes": ["sparse_random", "dense_random", "grid_2d",
                               "unit_weight"],
                   "timeout_s": 300},
    "graph_standard": {"sizes": [128, 512], "trials": 5, "seed": 4242,
                       "regimes": ["sparse_random", "dense_random", "grid_2d",
                                   "unit_weight"],
                       "timeout_s": 600},
    "flagship": {"sizes": [256, 1024, 4096], "trials": 7, "seed": 20260809,
                 "regimes": ["random", "nearly_sorted", "reversed", "few_unique"],
                 "timeout_s": 600, "sweep": True, "cutoffs": [8, 16, 32, 64]},
}


def _brain_logger(root: Path):
    def log(meta: dict) -> None:
        (root / "logs").mkdir(parents=True, exist_ok=True)
        with open(root / "logs" / "brain.jsonl", "a") as f:
            f.write(json.dumps(meta, default=str) + "\n")
    return log


def _quiet_broken_pipe() -> None:
    """`origin report | head` must not print a traceback.

    Python turns SIGPIPE into BrokenPipeError; a command-line tool that is
    piped into `head`, `less` or `grep -m` should exit quietly instead.
    """
    try:
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    except (AttributeError, ValueError):
        pass          # not POSIX, or not on the main thread


def main(argv: list[str] | None = None) -> int:
    _quiet_broken_pipe()
    ap = argparse.ArgumentParser(
        prog="origin",
        description="ORIGIN — persistent computational research engine (v1.0)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="create a new research project")
    p_init.add_argument("question")
    p_init.add_argument("--dir", required=True)
    p_init.add_argument("--domain", default="algobench",
                        choices=["algobench", "graphbench"])
    p_init.add_argument("--profile", default="standard", choices=sorted(PROFILES))
    p_init.add_argument("--max-experiments", type=int, default=12)
    p_init.add_argument("--compute-minutes", type=float, default=30.0)
    p_init.add_argument("--max-minutes", type=float, default=0.0,
                        help="mission wall-time budget in active minutes (0 = uncapped)")
    p_init.add_argument("--provider-calls", type=int, default=20,
                        help="LLM provider call cap")
    p_init.add_argument("--brain", default="mock",
                        choices=["mock", "anthropic", "none"],
                        help="LLM proposal layer (mock is deterministic and default)")

    for name, help_ in [("run", "run/resume autonomous research"),
                        ("status", "show mission-control status"),
                        ("report", "regenerate the research dossier"),
                        ("timeline", "print the replayable research timeline"),
                        ("html", "write reports/mission_control.html"),
                        ("verify", "check durable-state consistency"),
                        ("cancel", "cancel the mission (terminal)")]:
        p = sub.add_parser(name, help=help_)
        p.add_argument("--dir", required=True)
        if name == "run":
            p.add_argument("--steps", type=int, default=None,
                           help="run at most N steps, then checkpoint and pause")

    p_rep = sub.add_parser("replay",
                           help="re-execute a stored experiment from its recorded "
                                "code+config and compare results within tolerance")
    p_rep.add_argument("--dir", required=True)
    p_rep.add_argument("--exp", required=True)
    p_rep.add_argument("--tolerance", type=float, default=0.5,
                       help="relative timing tolerance (0.5 = ±50%%)")
    p_rep.add_argument("--noise-floor-ms", type=float, default=5.0,
                       help="absolute timing noise floor in ms; deviations "
                            "smaller than this are never reported")
    p_rep.add_argument("--strict", action="store_true",
                       help="also fail on timing deviations and decisive "
                            "ranking inversions (only applied when the replay "
                            "environment matches the stored one, and only "
                            "meaningful on dedicated, unloaded hardware)")
    p_rep.add_argument("--min-trials", type=int, default=stats.MIN_TRIALS,
                       help="minimum trials per side before any ordering claim "
                            "is considered decisive")


    p_auto = sub.add_parser(
        "autonomy",
        help="bounded autonomous operation (always finite; never a daemon)")
    auto_sub = p_auto.add_subparsers(dest="autocmd", required=True)
    for name, help_ in [
            ("status", "lifecycle, queue, lease, next action, budgets, stop reason"),
            ("plan", "show candidates and why the policy would pick the next one"),
            ("tick", "perform at most one safe action"),
            ("pause", "request a durable pause at the next safe checkpoint"),
            ("resume", "clear a pause and continue from durable state"),
            ("cancel", "terminal cancellation with a durable record"),
            ("recover-lock", "inspect, and with --force release, a mission lease")]:
        sp = auto_sub.add_parser(name, help=help_)
        sp.add_argument("--dir", required=True)
        if name == "recover-lock":
            sp.add_argument("--force", action="store_true",
                            help="release the lease. Only do this when you are "
                                 "certain no other process is running.")
        if name in ("tick", "plan"):
            sp.add_argument("--allow-network", action="store_true")
            sp.add_argument("--allow-provider", action="store_true")
    p_run = auto_sub.add_parser("run", help="bounded autonomous run")
    p_run.add_argument("--dir", required=True)
    p_run.add_argument("--max-steps", type=int, default=10)
    p_run.add_argument("--max-wall-s", type=float, default=300.0)
    p_run.add_argument("--max-retrievals", type=int, default=0)
    p_run.add_argument("--max-provider-calls", type=int, default=0)
    p_run.add_argument("--max-consecutive-failures", type=int, default=3)
    p_run.add_argument("--allow-network", action="store_true",
                       help="permit approved-URL retrieval during this run")
    p_run.add_argument("--allow-provider", action="store_true",
                       help="permit live LLM provider calls during this run")

    p_ing = sub.add_parser("ingest",
                           help="ingest a local document or an approved URL as "
                                "untrusted evidence")
    p_ing.add_argument("--dir", required=True)
    p_ing.add_argument("--file", help="local document path")
    p_ing.add_argument("--url", action="append", default=[],
                       help="https URL to retrieve (repeatable)")
    p_ing.add_argument("--provider", default="https",
                       choices=["https", "fixture"],
                       help="retrieval provider (fixture = offline, deterministic)")
    p_ing.add_argument("--fixtures", help="directory of fixture documents "
                                          "(with an index.json URL map)")
    p_ing.add_argument("--max-requests", type=int, default=20)
    p_ing.add_argument("--max-bytes", type=int, default=400_000)
    p_ing.add_argument("--allow-host", action="append", default=[],
                       help="restrict retrieval to these hosts (repeatable)")
    p_ing.add_argument("--ignore-robots", action="store_true",
                       help="skip robots.txt (documented, not recommended)")

    args = ap.parse_args(argv)
    root = Path(args.dir)

    if args.cmd == "init":
        budget = Budget(experiments_total=args.max_experiments,
                        compute_seconds_total=args.compute_minutes * 60,
                        elapsed_seconds_total=args.max_minutes * 60,
                        provider_calls_total=args.provider_calls)
        st = ResearchState.create(root, args.question, args.domain,
                                  PROFILES[args.profile], budget,
                                  profile=args.profile)
        st.meta["brain"] = args.brain
        (root / "project.json").write_text(json.dumps(st.meta, indent=2))
        st.save()
        print(f"Research project created at {root}  (brain: {args.brain})")
        print(status_box(st))
        print("\nNext:  python -m origin run --dir", root)
        return 0

    try:
        st = ResearchState.load(root)
    except CheckpointCorrupted as e:
        print(f"CHECKPOINT ERROR: {e}", file=sys.stderr)
        return 2
    except FileNotFoundError as e:
        print(f"NO PROJECT: {e}\nCreate one with: python -m origin init "
              f'"QUESTION" --dir {root}', file=sys.stderr)
        return 2
    domain = get_domain(st.meta["domain"])

    if args.cmd == "run":
        if st.meta.get("phase") in lc.TERMINAL:
            print(f"Mission is terminal ({st.meta['phase']}): "
                  f"{st.meta.get('stop_reason', '')}")
            print(status_box(st))
            return 0
        lc.resume(st)
        try:
            brain = make_brain(st.meta.get("brain", "mock"),
                               logger=_brain_logger(root), budget=st.budget)
        except BrainConfigError as e:
            print(f"BRAIN CONFIG ERROR: {e}", file=sys.stderr)
            return 2
        ctl = ResearchController(st, domain, brain=brain)
        try:
            ctl.run(max_steps=args.steps)
        except KeyboardInterrupt:
            print("\nInterrupted — state saved. Resume with: "
                  "python -m origin run --dir", root)
            return 130
        print(status_box(st))
        if st.meta.get("phase") == lc.COMPLETED:
            print(f"\nResearch complete. Dossier: {root / 'reports' / 'dossier.md'}")
        elif st.meta.get("phase") in lc.TERMINAL:
            print(f"\nMission {st.meta['phase']}: {st.meta.get('stop_reason')}")
        else:
            print("\nPaused. Resume with: python -m origin run --dir", root)
        return 0


    if args.cmd == "autonomy":
        return _autonomy(args, root, st, domain)

    if args.cmd == "status":
        print(status_box(st))
        return 0

    if args.cmd == "report":
        write_reports(st, domain)
        print((root / "reports" / "dossier.md").read_text())
        return 0

    if args.cmd == "timeline":
        print(render_timeline(st))
        return 0

    if args.cmd == "html":
        out = root / "reports" / "mission_control.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_html(st))
        print(f"Wrote {out}")
        return 0

    if args.cmd == "verify":
        problems = st.verify()
        if problems:
            print(f"{len(problems)} consistency problem(s):")
            for p in problems:
                print(" -", p)
            return 1
        print("State verified: counts, references, experiment artifacts and "
              "event log are consistent.")
        return 0

    if args.cmd == "cancel":
        if st.meta.get("phase") in lc.TERMINAL:
            print(f"Already terminal: {st.meta['phase']}")
            return 0
        lc.advance(st, lc.CANCELLED, "cancelled by user")
        st.save()
        print("Mission cancelled. Stop reason recorded; state remains inspectable.")
        return 0

    if args.cmd == "ingest":
        from .evidence import ingest_file
        from .retrieval import (PolicyViolation, RetrievalError,
                                RetrievalPolicy, make_provider)
        from .web_evidence import ingest_url
        if not args.file and not args.url:
            print("ingest needs --file or --url", file=sys.stderr)
            return 2
        try:
            brain = make_brain(st.meta.get("brain", "mock"),
                               logger=_brain_logger(root), budget=st.budget)
        except BrainConfigError as e:
            print(f"BRAIN CONFIG ERROR: {e}", file=sys.stderr)
            return 2
        results = []
        if args.file:
            results.append(ingest_file(st, args.file, brain))
        if args.url:
            documents = {}
            if args.provider == "fixture":
                fx = Path(args.fixtures or (root / "fixtures"))
                index = json.loads((fx / "index.json").read_text())
                for canon, spec in index.items():
                    body = (fx / spec["file"]).read_bytes()
                    documents[canon] = {"body": body,
                                        "content_type": spec.get("content_type",
                                                                 "text/plain"),
                                        "status": spec.get("status", 200),
                                        "redirects": spec.get("redirects", [])}
            provider = make_provider(args.provider, documents)
            policy = RetrievalPolicy(max_requests=args.max_requests,
                                     max_bytes=args.max_bytes,
                                     allow_hosts=tuple(args.allow_host),
                                     respect_robots=not args.ignore_robots)
            for url in args.url:
                try:
                    results.append(ingest_url(st, url, provider, brain, policy))
                except (PolicyViolation, RetrievalError) as e:
                    results.append({"ok": False, "url": url,
                                    "refused": f"{type(e).__name__}: {e}"})
                    st.log_event("retrieval_refused", f"{url}: {e}")
        st.save()
        print(json.dumps(results, indent=2, default=str))
        return 0 if all(r.get("ok", True) for r in results) else 1

    if args.cmd == "replay":
        rec = st.experiments.get(args.exp)
        if rec is None:
            print(f"No such experiment {args.exp}. Known: "
                  f"{', '.join(sorted(st.experiments))}", file=sys.stderr)
            return 2
        stored_dir = rec.path(st.root)
        stored_path = stored_dir / "result.json"
        if not stored_path.exists():
            print(f"REPLAY FAIL: {rec.id} has no stored result.json at "
                  f"{stored_dir} (artifact missing)", file=sys.stderr)
            return 1
        for needed in ("run.py", "spec.json"):
            if not (stored_dir / needed).exists():
                print(f"REPLAY FAIL: {rec.id} is missing {needed}; the "
                      f"experiment cannot be reproduced from its record",
                      file=sys.stderr)
                return 1
        stored = json.loads(stored_path.read_text())
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            shutil.copy(stored_dir / "run.py", tmp / "run.py")
            shutil.copy(stored_dir / "spec.json", tmp / "spec.json")
            timeout = rec.design.get("timeout_s", 600)
            t0 = time.perf_counter()
            proc = subprocess.run([sys.executable, "-I", "run.py"], cwd=td,
                                  capture_output=True, text=True, timeout=timeout,
                                  env=sandbox.scrubbed_env(td),
                                  preexec_fn=sandbox.make_preexec(timeout))
            dur = time.perf_counter() - t0
            fresh_path = tmp / "result.json"
            if proc.returncode != 0 or not fresh_path.exists():
                print("REPLAY FAIL — the stored experiment did not re-execute "
                      "cleanly (exit "
                      f"{proc.returncode}):\n" + proc.stderr[-800:],
                      file=sys.stderr)
                return 1
            fresh = json.loads(fresh_path.read_text())

        policy = ReplayPolicy(tolerance=args.tolerance,
                              noise_floor_ms=args.noise_floor_ms,
                              min_trials=args.min_trials,
                              strict=args.strict)
        rep = compare_results(stored, fresh, policy)
        header = (f"Replayed {rec.id} in {dur:.1f}s from its recorded code and "
                  f"config (seed {rec.design.get('seed')}, "
                  f"{rec.design.get('trials')} trials/cell).")
        for line in render(rep, policy, header):
            print(line)
        return 1 if rep.failed(policy) else 0

    return 1


def _fmt_limits(limits) -> str:
    return (f"steps<={limits.max_steps}, wall<={limits.max_wall_s:.0f}s, "
            f"consecutive failures<={limits.max_consecutive_failures}, "
            f"attempts/item<={limits.max_attempts_per_item}")


def _autonomy(args, root, st, domain) -> int:
    """Bounded autonomy CLI. Every path prints why, not just what."""
    from . import autonomy as A
    from . import lifecycle as lc
    from .scheduler import Scheduler

    cmd = args.autocmd
    lease = A.MissionLease(root)

    if cmd == "recover-lock":
        held = lease.read()
        if held is None:
            print("No lease is held on this mission.")
            return 0
        age = time.time() - float(held.get("acquired_at", 0) or 0)
        print(f"Lease holder : {held.get('owner')}")
        print(f"Process      : pid {held.get('pid')} on {held.get('host')}")
        print(f"Held for     : {age:.0f}s")
        if not args.force:
            print("\nORIGIN does not steal leases: a stale lease and a live one "
                  "look identical from here.\nConfirm no autonomy process is "
                  "running, then re-run with --force to release it.")
            return 1
        lease.release()
        store = A.AutonomyStore(root)
        store.record_decision({
            "kind": "lock_recovery", "released_owner": held.get("owner"),
            "held_seconds": round(age, 1),
            "detail": "operator released the mission lease with --force"})
        st.log_event("autonomy_lock_recovered",
                     f"operator released a lease held by {held.get('owner')} "
                     f"for {age:.0f}s")
        st.save()
        print("\nLease released and the action was recorded in the mission "
              "event log and autonomy decision log.")
        return 0

    store = A.AutonomyStore(root)

    if cmd == "pause":
        store.meta["pause_requested"] = True
        store.record_decision({"kind": "operator", "detail": "pause requested"})
        store.save()
        st.log_event("autonomy_pause", "operator requested an autonomy pause")
        st.save()
        print("Pause requested. The current tick finishes and checkpoints; no "
              "further action starts.\nResume with: python -m origin autonomy "
              f"resume --dir {root}")
        return 0

    if cmd == "resume":
        store.meta["pause_requested"] = False
        store.meta["stop_reason"] = ""
        store.record_decision({"kind": "operator", "detail": "resume requested"})
        store.save()
        st.log_event("autonomy_resume", "operator cleared the autonomy pause")
        st.save()
        print("Pause cleared. Completed work is never repeated; the queue "
              "continues from durable state.")
        return 0

    if cmd == "cancel":
        if st.meta.get("phase") not in lc.TERMINAL:
            lc.advance(st, lc.CANCELLED, "cancelled by operator via autonomy")
        for item in store.open_items():
            item.status = A.CANCELLED
            item.updated_at = time.time()
        store.meta["stop_reason"] = A.CANCELLED_STOP
        store.record_decision({"kind": "operator",
                               "detail": "mission cancelled; open work items "
                                         "cancelled with it"})
        store.save()
        st.save()
        print("Mission cancelled. The record is durable and inspectable; "
              "nothing further will run.")
        return 0

    limits = A.RunLimits(
        max_steps=getattr(args, "max_steps", 10),
        max_wall_s=getattr(args, "max_wall_s", 300.0),
        max_retrievals=getattr(args, "max_retrievals", 0),
        max_provider_calls=getattr(args, "max_provider_calls", 0),
        max_consecutive_failures=getattr(args, "max_consecutive_failures", 3))
    allow_net = getattr(args, "allow_network", False)
    allow_prov = getattr(args, "allow_provider", False)

    if cmd == "status":
        held = lease.read()
        print(status_box(st))
        print(f"\nAUTONOMY (policy {A.POLICY_VERSION}, schema "
              f"v{A.AUTONOMY_SCHEMA_VERSION})")
        print(f"  lifecycle      : {st.meta.get('phase')}"
              + (f" — {st.meta.get('stop_reason')}"
                 if st.meta.get("stop_reason") else ""))
        counts = {k: v for k, v in store.summary().items() if v}
        print(f"  work queue     : {counts or 'empty'}")
        print(f"  lease          : "
              + (f"HELD by {held.get('owner')} (pid {held.get('pid')} on "
                 f"{held.get('host')})" if held else "free"))
        print(f"  pause requested: {bool(store.meta.get('pause_requested'))}")
        print(f"  last stop      : {store.meta.get('stop_reason') or '(none)'}")
        print(f"  counters       : {store.counters}")
        print(f"  budgets        : experiments "
              f"{st.budget.experiments_used}/{st.budget.experiments_total}, "
              f"compute {st.budget.compute_seconds_used:.0f}s/"
              f"{st.budget.compute_seconds_total:.0f}s, provider calls "
              f"{st.budget.provider_calls_used}, retrievals "
              f"{st.flags.get('retrievals_used', 0)}")
        deferred = [i for i in store.by_status(A.DEFERRED)]
        if deferred:
            print("  retry backoff  :")
            for i in deferred:
                when = time.strftime("%H:%M:%S", time.localtime(i.not_before))
                print(f"      {i.id} {i.action} attempt {i.attempts} "
                      f"eligible {when} — {i.last_error[:70]}")
        interrupted = store.by_status(A.INTERRUPTED)
        if interrupted:
            print("  INTERRUPTED (outcome unknown, operator decision needed):")
            for i in interrupted:
                print(f"      {i.id} {i.action} — {i.last_error[:90]}")
        sched = Scheduler(root, limits, allow_net, allow_prov)
        decision = A.AutonomyPolicy(limits, allow_net, allow_prov).evaluate(
            sched.store, st)
        print(f"  next action    : "
              f"{decision['chosen_action'] or '(none permitted)'}"
              + (f" [{decision['chosen']}]" if decision["chosen"] else ""))
        return 0

    if cmd == "plan":
        sched = Scheduler(root, limits, allow_net, allow_prov)
        sched.seed(st)
        sched.store.save()
        decision = A.AutonomyPolicy(limits, allow_net, allow_prov).evaluate(
            sched.store, st)
        print(f"PLAN for {root}  (policy {decision['policy_version']}, "
              f"limits: {_fmt_limits(limits)})")
        print(f"\nExternal authority for this run: network="
              f"{'ENABLED' if allow_net else 'disabled'}, provider="
              f"{'ENABLED' if allow_prov else 'disabled'}")
        print("\nPermitted candidates (in the order the policy would take them):")
        if not decision["candidates"]:
            print("  (none)")
        for cid in sorted(decision["candidates"],
                          key=lambda c: (-sched.store.items[c].priority,
                                         sched.store.items[c].cost_estimate,
                                         sched.store.items[c].created_at, c)):
            i = sched.store.items[cid]
            flags = []
            if i.requires_network:
                flags.append("NETWORK")
            if i.requires_provider:
                flags.append("PROVIDER")
            if i.requires_approval:
                flags.append("APPROVAL")
            print(f"  [{i.priority:.2f}] {i.action:22} {i.id}"
                  + (f"  <{'+'.join(flags)}>" if flags else ""))
            print(f"       queued because: {i.reason}")
        print("\nNot eligible:")
        for r in decision["rejected"] or [{"id": "-", "action": "-",
                                           "reason": "(none)"}]:
            print(f"  {r['action']:22} {r['id']}: {r['reason']}")
        print(f"\nWould choose : {decision['chosen'] or '(nothing)'}")
        print(f"Because      : {decision['chosen_reason']}")
        print(f"Tie-break    : {decision['tie_break']}")
        if decision.get("next_wake_at"):
            print(f"Next wake    : "
                  f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(decision['next_wake_at']))}")
        return 0

    if cmd == "tick":
        sched = Scheduler(root, limits, allow_net, allow_prov)
        try:
            result = sched.tick()
        except A.LeaseHeld as e:
            print(f"LEASE HELD: {e}", file=sys.stderr)
            return 3
        if result.get("acted"):
            print(f"Performed {result['action']} ({result['item']}) -> "
                  f"{result['status']}")
            print(f"  {result['detail']}")
        else:
            print(f"No action taken. Stop reason: {result['stop']}")
            print(f"  {result.get('detail', '')}")
        return 0

    if cmd == "run":
        sched = Scheduler(root, limits, allow_net, allow_prov)
        print(f"Autonomous run bounded by: {_fmt_limits(limits)}")
        print(f"External authority: network="
              f"{'ENABLED' if allow_net else 'disabled'}, provider="
              f"{'ENABLED' if allow_prov else 'disabled'}")
        try:
            out = sched.run(limits.max_steps, limits.max_wall_s)
        except A.LeaseHeld as e:
            print(f"LEASE HELD: {e}", file=sys.stderr)
            return 3
        print(f"\nPerformed {out['steps']} action(s) in {out['elapsed_s']}s")
        print(f"Stopped because: {out['stop']}")
        if out.get("detail"):
            print(f"  {out['detail']}")
        print(f"\nInspect with: python -m origin autonomy status --dir {root}")
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
