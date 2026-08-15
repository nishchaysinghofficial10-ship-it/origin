"""Autonomy scheduler (v1.5): one bounded, restart-safe tick at a time.

    load and verify state
      → acquire single-writer lease
      → recover interrupted work conservatively
      → seed the queue from the mission's real needs
      → policy selects at most ONE permitted action
      → dispatch through the EXISTING engine (all gates apply)
      → checkpoint the result, the decision and the budget
      → release the lease

`run()` calls `tick()` repeatedly under explicit step and wall-clock limits.
There is no daemon and no hidden always-running service: when a bounded run
ends, nothing of ORIGIN is left executing.
"""
from __future__ import annotations

import time
from pathlib import Path

from . import autonomy as A
from . import lifecycle as lc
from .brain import make_brain
from .controller import ResearchController
from .domains.base import get_domain
from .report import write_reports
from .state import ResearchState


class Scheduler:
    def __init__(self, root: Path, limits: A.RunLimits | None = None,
                 allow_network: bool = False, allow_provider: bool = False,
                 clock=None, provider=None, retrieval_policy=None):
        self.root = Path(root)
        self.limits = limits or A.RunLimits()
        self.allow_network = allow_network
        self.allow_provider = allow_provider
        # Injected clock: tests control time instead of sleeping through it.
        self._clock = clock or time.time
        self.provider = provider              # evidence provider (fixture/https)
        self.retrieval_policy = retrieval_policy
        self.store = A.AutonomyStore(self.root)

    def now(self) -> float:
        return self._clock()

    # ------------------------------------------------------------ seeding
    def seed(self, state) -> list[str]:
        """Derive work items from what the mission actually needs next.

        Seeding reads mission state; it never invents an action type and never
        widens a limit. Every item is idempotency-keyed, so re-seeding on each
        tick converges instead of piling up duplicates.
        """
        added = []
        phase = state.meta.get("phase", lc.CREATED)

        def offer(item):
            got, note = self.store.add(item)
            if note == "queued":
                added.append(got.id)
            return got

        if phase in (lc.CREATED, lc.VALIDATING, lc.PLANNING):
            offer(A.new_item(A.PLAN_MISSION,
                             "mission has not been decomposed yet",
                             priority=0.95, cost_estimate=0.1))
        elif phase == lc.FORMING_HYPOTHESES or not state.hypotheses:
            offer(A.new_item(A.FORM_HYPOTHESES,
                             "no hypotheses exist to test",
                             priority=0.9, cost_estimate=0.2,
                             requires_provider=state.meta.get("brain", "none")
                             not in ("none", "mock")))
        else:
            pending = [h for h in state.hypotheses.values()
                       if h.status.value == "proposed"]
            for h in sorted(pending, key=lambda x: x.id)[:4]:
                offer(A.new_item(
                    A.RUN_EXPERIMENT,
                    f"{h.id} is proposed and untested "
                    f"(importance {h.importance})",
                    priority=min(0.85, 0.4 + h.importance / 2),
                    cost_estimate=max(0.2, h.cost_estimate),
                    params={"hypothesis_id": h.id}))
            needs_critic = any(
                h.status.value == "provisionally_supported"
                and "falsification_done" not in h.tags
                for h in state.hypotheses.values())
            if needs_critic or not pending:
                cycle = sum(1 for i in self.store.items.values()
                            if i.action == A.CRITICISE
                            and i.status in (A.DONE, A.FAILED))
                offer(A.new_item(
                    A.CRITICISE,
                    "supported conclusions need replication and falsification "
                    f"before acceptance (criticism cycle {cycle + 1})",
                    priority=0.6, cost_estimate=0.5,
                    idempotency_key=f"criticise:cycle:{cycle}"))
        conflicts = [c for c in state.graph.contradictions
                     if isinstance(c, dict)]
        if conflicts:
            offer(A.new_item(A.REVIEW_CONFLICT,
                             f"{len(conflicts)} recorded contradiction(s) need "
                             f"surfacing in the report",
                             priority=0.5, cost_estimate=0.1,
                             idempotency_key="review_conflict:mission"))
        if state.meta.get("phase") in lc.TERMINAL or state.experiments:
            offer(A.new_item(A.GENERATE_REPORT,
                             "mission has results worth reporting",
                             priority=0.2, cost_estimate=0.1))
        return added

    # ---------------------------------------------------------- recovery
    def recover(self, state) -> list[str]:
        """Conservative recovery of work claimed by a process that died.

        ORIGIN does not guess whether a claimed action completed. The item is
        marked INTERRUPTED, the ambiguity is recorded, and the operator decides.
        The one thing autonomy will not do is silently re-run it: for an
        experiment that may already have spawned, that would double-charge the
        budget and could duplicate research history.
        """
        recovered = []
        for item in self.store.by_status(A.CLAIMED):
            item.status = A.INTERRUPTED
            item.updated_at = self.now()
            item.last_error = (
                "process ended after this item was claimed and before its "
                "outcome was checkpointed; completion is UNKNOWN")
            recovered.append(item.id)
            self.store.record_decision({
                "kind": "recovery", "item": item.id, "action": item.action,
                "outcome": "interrupted",
                "detail": "claimed but not completed; ORIGIN will not assume "
                          "success or re-run it automatically",
                "operator_action": "inspect with 'origin autonomy status', then "
                                   "requeue or cancel the item deliberately"})
            state.log_event("autonomy_recovery",
                            f"{item.id} ({item.action}) was interrupted; "
                            f"outcome unknown, left for operator review")
        if recovered:
            self.store.save()
        return recovered

    # -------------------------------------------------------------- tick
    def tick(self, state=None) -> dict:
        """Execute at most one permitted action. Always returns a verdict."""
        own_lease = state is None
        lease = A.MissionLease(self.root)
        if own_lease:
            lease.acquire()
        try:
            st = state if state is not None else ResearchState.load(self.root)
            problems = st.verify()
            if problems:
                blocking = [p for p in problems if "malformed line" not in p]
                if blocking:
                    self.store.meta["stop_reason"] = A.UNSAFE_STATE
                    self.store.save()
                    return {"acted": False, "stop": A.UNSAFE_STATE,
                            "detail": "; ".join(blocking[:3])}
            if self.store.meta.get("pause_requested"):
                self.store.meta["stop_reason"] = A.PAUSED_BY_OPERATOR
                self.store.save()
                return {"acted": False, "stop": A.PAUSED_BY_OPERATOR,
                        "detail": "operator pause is in effect; resume with "
                                  "'origin autonomy resume'"}
            if st.meta.get("phase") in lc.TERMINAL:
                reason = (A.CANCELLED_STOP
                          if st.meta["phase"] == lc.CANCELLED else A.COMPLETED)
                self.store.meta["stop_reason"] = reason
                self.store.save()
                return {"acted": False, "stop": reason,
                        "detail": f"mission is {st.meta['phase']}: "
                                  f"{st.meta.get('stop_reason', '')}"}

            self.recover(st)
            self.seed(st)
            policy = A.AutonomyPolicy(self.limits, self.allow_network,
                                      self.allow_provider, now=self.now())
            decision = policy.evaluate(self.store, st)
            self.store.counters["ticks"] += 1

            if decision["chosen"] is None:
                stop = self._idle_reason(decision)
                decision.update(kind="selection", outcome="no_action",
                                stop_reason=stop)
                self.store.record_decision(decision)
                self.store.counters["idle_ticks"] += 1
                self.store.meta["stop_reason"] = stop
                self.store.save()
                return {"acted": False, "stop": stop, "decision": decision,
                        "detail": self._idle_detail(stop, decision)}

            item = self.store.items[decision["chosen"]]
            decision.update(kind="selection", outcome="claimed")
            dec_id = self.store.record_decision(decision)
            # Checkpoint the CLAIM before doing anything, so a crash during the
            # action is detectable rather than invisible.
            item.status = A.CLAIMED
            item.attempts += 1
            item.decision_ref = dec_id
            item.updated_at = self.now()
            self.store.save()

            verdict = self._dispatch(item, st)

            item.updated_at = self.now()
            if verdict["ok"]:
                item.status = A.DONE
                item.result_ref = verdict.get("detail", "")[:300]
                self.store.counters["actions_completed"] += 1
                self.store.counters["consecutive_failures"] = 0
                self.store.counters["idle_ticks"] = 0
            else:
                retryable, cls = verdict["retryable"], verdict["class"]
                item.last_error = f"{cls}: {verdict['detail']}"[:400]
                self.store.counters["actions_failed"] += 1
                self.store.counters["consecutive_failures"] += 1
                if retryable and item.attempts < self.limits.max_attempts_per_item:
                    delay = A.backoff_delay(item.attempts, self.limits)
                    item.status = A.DEFERRED
                    item.not_before = self.now() + delay
                    verdict["detail"] += (f" — retry {item.attempts + 1}/"
                                          f"{self.limits.max_attempts_per_item} "
                                          f"in {delay:.0f}s")
                else:
                    item.status = A.FAILED
                    if retryable:
                        verdict["detail"] += " — attempt limit reached"
                    else:
                        verdict["detail"] += (" — not retryable (safety or "
                                              "schema failure)")
            self.store.record_decision({
                "kind": "execution", "item": item.id, "action": item.action,
                "outcome": item.status, "detail": verdict["detail"][:400],
                "attempts": item.attempts,
                "not_before": item.not_before or None,
                "budget_after": {
                    "experiments": f"{st.budget.experiments_used}/"
                                   f"{st.budget.experiments_total}",
                    "provider_calls": st.budget.provider_calls_used,
                    "retrievals": st.flags.get("retrievals_used", 0)}})
            st.save()
            self.store.save()
            return {"acted": True, "item": item.id, "action": item.action,
                    "status": item.status, "detail": verdict["detail"],
                    "decision": decision}
        finally:
            if own_lease:
                lease.release(lease.owner)

    def _idle_reason(self, decision: dict) -> str:
        reasons = " ".join(r["reason"] for r in decision["rejected"])
        if "awaiting operator approval" in reasons:
            return A.AWAITING_OPERATOR
        if "retry backoff pending" in reasons:
            return A.RETRY_PENDING
        if "budget" in reasons or "limit for this run reached" in reasons:
            return A.BUDGET_EXHAUSTED
        return A.NO_WORK

    def _idle_detail(self, stop: str, decision: dict) -> str:
        if stop == A.RETRY_PENDING and decision.get("next_wake_at"):
            return (f"all remaining work is in retry backoff; next item becomes "
                    f"eligible at "
                    f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(decision['next_wake_at']))}")
        if stop == A.AWAITING_OPERATOR:
            return ("work is queued but needs explicit operator approval; "
                    "see 'origin autonomy plan'")
        if stop == A.NO_WORK:
            return "no permitted work remains in the queue"
        return "; ".join(r["reason"] for r in decision["rejected"][:3])

    # ---------------------------------------------------------- dispatch
    def _dispatch(self, item: A.WorkItem, st) -> dict:
        """Route an action to the existing engine. Nothing executes here.

        Every branch calls a component that already enforces its own gates:
        the controller advances the validated lifecycle, the experiment engine
        applies sandbox policy, retrieval applies URL/robots/size policy, the
        critic applies replication and falsification rules.
        """
        domain = get_domain(st.meta["domain"])
        try:
            if item.action == A.PLAN_MISSION:
                ctl = self._controller(st, domain)
                while st.meta.get("phase") in (lc.CREATED, lc.VALIDATING,
                                               lc.PLANNING):
                    if not ctl.step():
                        break
                return self._ok(f"mission planned; phase is now "
                                f"{st.meta.get('phase')}")

            if item.action == A.FORM_HYPOTHESES:
                ctl = self._controller(st, domain)
                before = len(st.hypotheses)
                while st.meta.get("phase") == lc.FORMING_HYPOTHESES:
                    if not ctl.step():
                        break
                return self._ok(f"{len(st.hypotheses) - before} hypothesis(es) "
                                f"formed; {len(st.hypotheses)} total")

            if item.action == A.RUN_EXPERIMENT:
                ctl = self._controller(st, domain)
                before = st.budget.experiments_used
                # One controller step performs exactly one investigation, and
                # ExperimentEngine.run applies sandbox.validate_design first.
                ctl.step()
                st.step += 1
                ran = st.budget.experiments_used - before
                if ran == 0:
                    return self._ok("no experiment was run: the engine had no "
                                    "affordable or valid design for this step")
                return self._ok(f"{ran} experiment(s) executed through the "
                                f"sandbox gate; budget now "
                                f"{st.budget.experiments_used}/"
                                f"{st.budget.experiments_total}")

            if item.action == A.CRITICISE:
                ctl = self._controller(st, domain)
                if st.meta.get("phase") not in lc.TERMINAL:
                    if st.meta.get("phase") != lc.CRITICIZING:
                        lc.advance(st, lc.CRITICIZING,
                                   "autonomy scheduled criticism")
                    ctl.step()
                    st.step += 1
                return self._ok("criticism step executed (replication and "
                                "falsification gates unchanged)")

            if item.action == A.RETRIEVE_SOURCE:
                if not self.allow_network:
                    raise A.AutonomyError(
                        "network access is not enabled for this run")
                if self.provider is None:
                    raise A.AutonomyError(
                        "no evidence provider configured for this run")
                from .web_evidence import ingest_url
                out = ingest_url(st, item.params["url"], self.provider, None,
                                 self.retrieval_policy)
                self.store.counters["retrievals"] += 1
                if not out.get("ok"):
                    # ingest_url contains transport failures rather than
                    # raising; re-raise as the typed error so the retry
                    # classifier sees a transient failure for what it is.
                    from .retrieval import RetrievalError
                    err = out.get("error", "retrieval failed")
                    return self._fail(RetrievalError(err), err)
                if out.get("skipped"):
                    return self._ok(f"already ingested ({out['skipped']}); "
                                    f"source {out['source']}")
                return self._ok(f"source {out['source']} ingested with "
                                f"{len(out.get('claims', []))} SPECULATION "
                                f"claim(s); nothing became evidence")

            if item.action == A.REVIEW_CONFLICT:
                n = len(st.graph.contradictions)
                st.log_event("autonomy_conflict_review",
                             f"{n} contradiction(s) reviewed and left visible; "
                             f"only an experiment can settle them")
                return self._ok(f"{n} contradiction(s) surfaced for the report")

            if item.action == A.GENERATE_REPORT:
                write_reports(st, domain)
                return self._ok("dossier and timeline regenerated")

            if item.action == A.AWAIT_APPROVAL:
                return self._fail(A.AutonomyError(
                    "this item requires operator approval"),
                    "operator approval required")

            return self._fail(A.AutonomyError(
                f"unknown action {item.action!r}"), f"unknown action")
        except Exception as e:      # noqa: BLE001 — classified, never swallowed
            return self._fail(e, str(e)[:300])

    def _controller(self, st, domain):
        brain_name = st.meta.get("brain", "none")
        if not self.allow_provider and brain_name == "anthropic":
            brain_name = "none"     # never call a live provider implicitly
        return ResearchController(st, domain, brain=make_brain(brain_name))

    @staticmethod
    def _ok(detail: str) -> dict:
        return {"ok": True, "detail": detail}

    @staticmethod
    def _fail(exc: Exception, detail: str) -> dict:
        retryable, cls = A.classify_failure(exc)
        return {"ok": False, "detail": detail, "retryable": retryable,
                "class": cls}

    # ------------------------------------------------------------- run
    def run(self, max_steps: int | None = None,
            max_wall_s: float | None = None) -> dict:
        """Bounded foreground loop. Always finite, always with a stop reason."""
        steps = max_steps if max_steps is not None else self.limits.max_steps
        wall = max_wall_s if max_wall_s is not None else self.limits.max_wall_s
        started = self.now()
        lease = A.MissionLease(self.root)
        lease.acquire()
        performed, stop, detail = 0, A.STEP_LIMIT, ""
        try:
            for _ in range(steps):
                if self.now() - started >= wall:
                    stop, detail = A.TIME_LIMIT, (
                        f"wall-clock limit of {wall:.0f}s reached after "
                        f"{performed} step(s)")
                    break
                st = ResearchState.load(self.root)
                result = self.tick(state=st)
                if result.get("acted"):
                    performed += 1
                    if (self.store.counters["consecutive_failures"]
                            >= self.limits.max_consecutive_failures):
                        stop, detail = A.FAILURE_LIMIT, (
                            f"{self.store.counters['consecutive_failures']} "
                            f"consecutive failures; stopping rather than "
                            f"retrying into a wall")
                        break
                    continue
                stop = result.get("stop", A.NO_WORK)
                detail = result.get("detail", "")
                if stop in (A.RETRY_PENDING, A.NO_WORK, A.AWAITING_OPERATOR,
                            A.PAUSED_BY_OPERATOR, A.COMPLETED,
                            A.CANCELLED_STOP, A.UNSAFE_STATE,
                            A.BUDGET_EXHAUSTED):
                    break
                self.store.counters["idle_ticks"] += 1
                if self.store.counters["idle_ticks"] >= self.limits.max_idle_ticks:
                    stop, detail = A.NO_WORK, "idle tick limit reached"
                    break
            else:
                stop, detail = A.STEP_LIMIT, (
                    f"step limit of {steps} reached; the mission is unfinished "
                    f"and resumable")
            self.store.meta["stop_reason"] = stop
            self.store.save()
            return {"steps": performed, "stop": stop, "detail": detail,
                    "elapsed_s": round(self.now() - started, 2)}
        finally:
            lease.release(lease.owner)
