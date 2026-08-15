"""Bounded-autonomy tests (v1.5).

Time is injected everywhere: no test sleeps to demonstrate a backoff, a
scheduling window, or a stale lease. Every scenario runs offline against
fixture providers, so the suite is deterministic and fast.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import autonomy as A                              # noqa: E402
from origin import lifecycle as lc                            # noqa: E402
from origin import retrieval as R                             # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES, main as cli_main             # noqa: E402
from origin.scheduler import Scheduler                        # noqa: E402
from origin.state import ResearchState                        # noqa: E402

DOC = ("Sorting Notes\n\nMerge sort is a stable comparison sort with "
       "guaranteed n log n behaviour on every input distribution.\n")
URL = "https://fixtures.invalid/notes"


class Clock:
    def __init__(self, t=1_786_000_000.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s
        return self.t


def mission(tmp, name="m", experiments=8):
    st = ResearchState.create(tmp / name, "which sort wins where?", "algobench",
                              PROFILES["fast"],
                              Budget(experiments_total=experiments,
                                     compute_seconds_total=600),
                              profile="fast")
    st.meta["brain"] = "none"
    st.save()
    return st


def sched(root, clock=None, limits=None, **kw):
    return Scheduler(root, limits or A.RunLimits(max_steps=6, max_wall_s=60),
                     clock=clock or Clock(), **kw)


def fixture_provider(documents=None):
    return R.FixtureProvider(documents or {
        URL: {"body": DOC, "content_type": "text/plain; charset=utf-8"}})


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()


# ------------------------------------------------------- queue and policy
class TestQueueAndPolicy(Base):
    def test_valid_items_are_queued_and_selected_deterministically(self):
        st = mission(self.tmp)
        s = sched(st.root)
        s.store.add(A.new_item(A.GENERATE_REPORT, "low priority", priority=0.2))
        s.store.add(A.new_item(A.CRITICISE, "high priority", priority=0.9))
        policy = A.AutonomyPolicy(s.limits)
        first = policy.evaluate(s.store, st)["chosen"]
        # Repeated evaluation is stable, and stable across a reload.
        for _ in range(5):
            self.assertEqual(policy.evaluate(s.store, st)["chosen"], first)
        s.store.save()
        reloaded = A.AutonomyStore(st.root)
        self.assertEqual(
            A.AutonomyPolicy(s.limits).evaluate(reloaded, st)["chosen"], first)
        self.assertEqual(s.store.items[first].action, A.CRITICISE)

    def test_priority_ties_break_deterministically(self):
        st = mission(self.tmp)
        s = sched(st.root)
        for i in range(4):
            item = A.new_item(A.GENERATE_REPORT, f"tied item {i}",
                              priority=0.5, cost_estimate=1.0,
                              idempotency_key=f"tie:{i}")
            item.created_at = 1000.0        # identical timestamps
            s.store.add(item)
        chosen = A.AutonomyPolicy(s.limits).evaluate(s.store, st)["chosen"]
        expected = sorted(s.store.items)[0]
        self.assertEqual(chosen, expected, "tie-break must fall back to id")

    def test_invalid_work_items_are_rejected(self):
        st = mission(self.tmp)
        s = sched(st.root)
        bad = A.WorkItem(id="wi_x", action="exfiltrate_secrets", reason="nope",
                         idempotency_key="k1")
        with self.assertRaises(A.AutonomyError):
            s.store.add(bad)
        # An experiment item may not smuggle executable content.
        for banned in ("design", "command", "code", "runner", "argv"):
            item = A.new_item(A.RUN_EXPERIMENT, "smuggling attempt",
                              params={banned: "rm -rf /"})
            with self.assertRaises(A.AutonomyError) as cm:
                s.store.add(item)
            self.assertIn(banned, str(cm.exception))
        # A retrieval item may not widen the URL policy.
        for url in ("file:///etc/passwd", "http://example.com/x", None):
            item = A.new_item(A.RETRIEVE_SOURCE, "policy widening attempt",
                              params={"url": url} if url else {})
            with self.assertRaises(A.AutonomyError):
                s.store.add(item)

    def test_dependencies_are_respected(self):
        st = mission(self.tmp)
        s = sched(st.root)
        first, _ = s.store.add(A.new_item(A.CRITICISE, "prerequisite",
                                          priority=0.3))
        second = A.new_item(A.GENERATE_REPORT, "depends on the first",
                            priority=0.99)
        second.depends_on = [first.id]
        s.store.add(second)
        decision = A.AutonomyPolicy(s.limits).evaluate(s.store, st)
        self.assertEqual(decision["chosen"], first.id)
        self.assertTrue(any("dependencies not satisfied" in r["reason"]
                            for r in decision["rejected"]))
        first.status = A.DONE
        self.assertEqual(
            A.AutonomyPolicy(s.limits).evaluate(s.store, st)["chosen"],
            second.id)

    def test_approval_gate_blocks_until_approved(self):
        st = mission(self.tmp)
        s = sched(st.root)
        item = A.new_item(A.GENERATE_REPORT, "needs sign-off", priority=0.9)
        item.status = A.NEEDS_APPROVAL
        item.requires_approval = True
        s.store.add(item)
        decision = A.AutonomyPolicy(s.limits).evaluate(s.store, st)
        self.assertIsNone(decision["chosen"])
        self.assertTrue(any("approval" in r["reason"]
                            for r in decision["rejected"]))
        item.status, item.approved_by = A.QUEUED, "operator"
        self.assertEqual(
            A.AutonomyPolicy(s.limits).evaluate(s.store, st)["chosen"], item.id)

    def test_completed_work_is_never_selected_again(self):
        st = mission(self.tmp)
        s = sched(st.root)
        item, _ = s.store.add(A.new_item(A.GENERATE_REPORT, "once"))
        item.status = A.DONE
        self.assertIsNone(A.AutonomyPolicy(s.limits).evaluate(s.store, st)["chosen"])

    def test_idempotency_key_collapses_duplicate_items(self):
        st = mission(self.tmp)
        s = sched(st.root)
        a, note_a = s.store.add(A.new_item(A.RETRIEVE_SOURCE, "first",
                                           params={"url": URL}))
        b, note_b = s.store.add(A.new_item(A.RETRIEVE_SOURCE, "again",
                                           params={"url": URL}))
        self.assertEqual(a.id, b.id)
        self.assertEqual(note_a, "queued")
        self.assertIn("duplicate", note_b)
        self.assertEqual(len(s.store.items), 1)

    def test_no_permitted_work_stops_honestly(self):
        st = mission(self.tmp)
        st.meta["phase"] = lc.COMPLETED
        st.meta["stop_reason"] = "no high-value next experiment remained"
        st.save()
        out = sched(st.root).run(max_steps=3, max_wall_s=10)
        self.assertEqual(out["stop"], A.COMPLETED)
        self.assertIn("COMPLETED", out["detail"])

    def test_network_and_provider_actions_need_explicit_permission(self):
        st = mission(self.tmp)
        s = sched(st.root)
        item, _ = s.store.add(A.new_item(A.RETRIEVE_SOURCE, "fixture source",
                                         params={"url": URL}))
        self.assertTrue(item.requires_network)
        decision = A.AutonomyPolicy(s.limits, allow_network=False).evaluate(
            s.store, st)
        self.assertIsNone(decision["chosen"])
        self.assertTrue(any("network" in r["reason"] for r in decision["rejected"]))
        self.assertEqual(
            A.AutonomyPolicy(s.limits, allow_network=True).evaluate(
                s.store, st)["chosen"], item.id)

    def test_decision_records_explain_the_choice(self):
        st = mission(self.tmp)
        s = sched(st.root)
        s.tick(state=st)
        records = s.store.decisions()
        selection = [r for r in records if r.get("kind") == "selection"]
        self.assertTrue(selection)
        rec = selection[0]
        for key in ("ts", "chosen", "candidates", "rejected", "tie_break",
                    "budget", "approvals", "policy_version"):
            self.assertIn(key, rec)


# --------------------------------------------------- persistence/recovery
class TestPersistenceAndRecovery(Base):
    def test_state_survives_reload_at_every_boundary(self):
        st = mission(self.tmp)
        s = sched(st.root)
        for _ in range(3):
            s.tick(state=st)
            st.save()
            reloaded = A.AutonomyStore(st.root)
            self.assertEqual(len(reloaded.items), len(s.store.items))
            self.assertEqual(reloaded.counters["ticks"], s.store.counters["ticks"])
            self.assertEqual(ResearchState.load(st.root).verify(), [])

    def test_crash_after_claim_is_recovered_conservatively(self):
        st = mission(self.tmp)
        s = sched(st.root)
        item, _ = s.store.add(A.new_item(A.RUN_EXPERIMENT, "claimed then lost",
                                         params={"hypothesis_id": "hyp_x"}))
        item.status = A.CLAIMED           # simulate a process death mid-action
        item.attempts = 1
        s.store.save()

        fresh = sched(st.root)
        recovered = fresh.recover(st)
        self.assertEqual(recovered, [item.id])
        after = fresh.store.items[item.id]
        self.assertEqual(after.status, A.INTERRUPTED)
        self.assertIn("UNKNOWN", after.last_error)
        # An interrupted item is never silently re-run: the operator decides.
        decision = A.AutonomyPolicy(fresh.limits).evaluate(fresh.store, st)
        self.assertNotEqual(decision["chosen"], item.id)
        self.assertTrue(any("interrupted" in r["reason"]
                            for r in decision["rejected"]))
        self.assertTrue(any(r.get("kind") == "recovery"
                            for r in fresh.store.decisions()))

    def test_duplicate_tick_does_not_duplicate_work_or_budget(self):
        st = mission(self.tmp)
        s = sched(st.root)
        s.tick(state=st)                       # plan
        s.tick(state=st)                       # hypotheses
        st.save()
        before_exp = st.budget.experiments_used
        before_done = {i.id for i in s.store.items.values() if i.status == A.DONE}

        # A second scheduler replaying the same durable state must not redo it.
        replay = sched(st.root)
        st2 = ResearchState.load(st.root)
        replay.seed(st2)
        done_now = {i.id for i in replay.store.items.values()
                    if i.status == A.DONE}
        self.assertEqual(done_now, before_done)
        decision = A.AutonomyPolicy(replay.limits).evaluate(replay.store, st2)
        self.assertNotIn(decision["chosen"], before_done)
        self.assertEqual(st2.budget.experiments_used, before_exp)

    def test_autonomy_state_is_portable_and_secret_free(self):
        st = mission(self.tmp)
        s = sched(st.root)
        s.run(max_steps=4, max_wall_s=30)
        blob = (st.root / "autonomy" / "state.json").read_text()
        decisions = (st.root / "autonomy" / "decisions.jsonl").read_text()
        for text in (blob, decisions):
            for marker in ("/home/", "/Users/", "/root/", "sk-ant-", "api_key="):
                self.assertNotIn(marker, text)
        self.assertEqual(json.loads(blob)["meta"]["schema_version"],
                         A.AUTONOMY_SCHEMA_VERSION)
        self.assertEqual(ResearchState.load(st.root).verify(), [])

    def test_malformed_autonomy_state_fails_safely(self):
        st = mission(self.tmp)
        (st.root / "autonomy").mkdir(parents=True, exist_ok=True)
        (st.root / "autonomy" / "state.json").write_text("{ not json")
        with self.assertRaises(A.AutonomyError) as cm:
            A.AutonomyStore(st.root)
        self.assertIn("research state is unaffected", str(cm.exception))
        # The mission still loads, and verify() reports the autonomy problem
        # rather than either crashing or pretending the state is fine.
        reloaded = ResearchState.load(st.root)
        problems = reloaded.verify()
        self.assertTrue(any("autonomy state is unreadable" in p
                            for p in problems), problems)
        self.assertEqual([p for p in problems if "autonomy" not in p], [],
                         "the research state itself must be untouched")

    def test_item_failing_validation_on_load_is_quarantined(self):
        st = mission(self.tmp)
        s = sched(st.root)
        s.store.add(A.new_item(A.GENERATE_REPORT, "fine"))
        s.store.save()
        raw = json.loads((st.root / "autonomy" / "state.json").read_text())
        key = next(iter(raw["items"]))
        raw["items"][key]["action"] = "run_arbitrary_shell"
        (st.root / "autonomy" / "state.json").write_text(json.dumps(raw))
        store = A.AutonomyStore(st.root)
        self.assertEqual(store.items[key].status, A.FAILED)
        self.assertIn("quarantined", store.items[key].reason)
        self.assertIsNone(
            A.AutonomyPolicy(A.RunLimits()).evaluate(store, st)["chosen"])
        # `origin verify` surfaces the quarantine rather than hiding it.
        problems = ResearchState.load(st.root).verify()
        self.assertTrue(any("quarantined" in p for p in problems), problems)

    def test_newer_schema_is_refused(self):
        st = mission(self.tmp)
        (st.root / "autonomy").mkdir(parents=True, exist_ok=True)
        (st.root / "autonomy" / "state.json").write_text(json.dumps(
            {"meta": {"schema_version": A.AUTONOMY_SCHEMA_VERSION + 1},
             "items": {}, "counters": {}}))
        with self.assertRaises(A.AutonomyError):
            A.AutonomyStore(st.root)


# ------------------------------------------------------------- locking
class TestLocking(Base):
    def test_second_scheduler_cannot_acquire_the_lease(self):
        st = mission(self.tmp)
        lease = A.MissionLease(st.root)
        lease.acquire()
        try:
            with self.assertRaises(A.LeaseHeld) as cm:
                A.MissionLease(st.root).acquire()
            msg = str(cm.exception)
            self.assertIn("leased by", msg)
            self.assertIn("recover-lock", msg)
            self.assertIn("never steals", msg)
        finally:
            lease.release(lease.owner)

    def test_lease_is_released_on_normal_completion(self):
        st = mission(self.tmp)
        s = sched(st.root)
        s.run(max_steps=2, max_wall_s=30)
        self.assertIsNone(A.MissionLease(st.root).read())
        A.MissionLease(st.root).acquire()      # free again
        A.MissionLease(st.root).release()

    def test_a_stale_lease_is_never_stolen_automatically(self):
        st = mission(self.tmp)
        lease = A.MissionLease(st.root)
        lease.acquire()
        held = json.loads(lease.path.read_text())
        held["acquired_at"] = 0.0              # ancient
        held["pid"] = 999999                   # certainly dead
        lease.path.write_text(json.dumps(held))
        with self.assertRaises(A.LeaseHeld):
            A.MissionLease(st.root).acquire()
        self.assertTrue(lease.path.exists())
        # Even a full run refuses rather than stealing.
        with self.assertRaises(A.LeaseHeld):
            sched(st.root).run(max_steps=1, max_wall_s=5)

    def test_manual_recovery_requires_force_and_is_audited(self):
        st = mission(self.tmp)
        A.MissionLease(st.root).acquire()
        rc = cli_main(["autonomy", "recover-lock", "--dir", str(st.root)])
        self.assertEqual(rc, 1, "inspection alone must not release the lease")
        self.assertTrue(A.MissionLease(st.root).path.exists())

        rc = cli_main(["autonomy", "recover-lock", "--dir", str(st.root),
                       "--force"])
        self.assertEqual(rc, 0)
        self.assertIsNone(A.MissionLease(st.root).read())
        decisions = A.AutonomyStore(st.root).decisions()
        self.assertTrue(any(d.get("kind") == "lock_recovery" for d in decisions))
        events = [e["kind"] for e in ResearchState.load(st.root).read_events()]
        self.assertIn("autonomy_lock_recovered", events)


# --------------------------------------------------- budgets and retries
class TestBudgetsAndRetries(Base):
    def test_step_limit_stops_the_scheduler(self):
        st = mission(self.tmp)
        out = sched(st.root).run(max_steps=2, max_wall_s=60)
        self.assertEqual(out["stop"], A.STEP_LIMIT)
        self.assertEqual(out["steps"], 2)

    def test_wall_clock_limit_stops_the_scheduler(self):
        st = mission(self.tmp)
        clock = Clock()
        s = sched(st.root, clock=clock)
        original = s.tick

        def slow_tick(state=None):
            clock.advance(30)
            return original(state=state)
        s.tick = slow_tick
        out = s.run(max_steps=50, max_wall_s=45)
        self.assertEqual(out["stop"], A.TIME_LIMIT)
        self.assertLess(out["steps"], 50)

    def test_experiment_budget_blocks_experiment_work(self):
        st = mission(self.tmp, experiments=1)
        st.budget.experiments_used = 1
        st.save()
        s = sched(st.root)
        item, _ = s.store.add(A.new_item(A.RUN_EXPERIMENT, "over budget",
                                         params={"hypothesis_id": "h1"}))
        decision = A.AutonomyPolicy(s.limits).evaluate(s.store, st)
        self.assertIsNone(decision["chosen"])
        self.assertTrue(any("budget" in r["reason"] for r in decision["rejected"]))

    def test_run_scoped_retrieval_limit_blocks_further_retrieval(self):
        st = mission(self.tmp)
        st.flags["retrievals_used"] = 2
        limits = A.RunLimits(max_retrievals=2)
        s = sched(st.root, limits=limits, provider=fixture_provider())
        s.store.add(A.new_item(A.RETRIEVE_SOURCE, "one too many",
                               params={"url": URL}))
        decision = A.AutonomyPolicy(limits, allow_network=True).evaluate(
            s.store, st)
        self.assertIsNone(decision["chosen"])
        self.assertTrue(any("retrieval limit" in r["reason"]
                            for r in decision["rejected"]))

    def test_retryable_failure_backs_off_then_fails_terminally(self):
        st = mission(self.tmp)
        clock = Clock()

        class AlwaysFails(R.FixtureProvider):
            def fetch(self, url, policy):
                raise R.RetrievalError("TimeoutError: simulated outage")

        limits = A.RunLimits(max_attempts_per_item=3, backoff_base_s=10.0)
        s = sched(st.root, clock=clock, limits=limits, provider=AlwaysFails({}),
                  allow_network=True, retrieval_policy=R.RetrievalPolicy(
                      min_interval_s=0.0))
        s.allow_network = True
        item, _ = s.store.add(A.new_item(A.RETRIEVE_SOURCE, "doomed",
                                         priority=0.99, params={"url": URL}))
        delays = []
        for expected_attempt in (1, 2, 3):
            result = s.tick(state=st)
            self.assertEqual(result["item"], item.id)
            if item.status == A.DEFERRED:
                delays.append(item.not_before - clock())
                # An immediate re-tick must NOT pick it again: no hot loop.
                again = s.tick(state=st)
                self.assertNotEqual(again.get("item"), item.id)
                clock.advance(delays[-1] + 1)
        self.assertEqual(item.status, A.FAILED)
        self.assertEqual(item.attempts, 3)
        self.assertEqual(delays, [10.0, 20.0], "backoff must be exponential")
        final = [d for d in s.store.decisions()
                 if d.get("kind") == "execution" and d.get("item") == item.id][-1]
        self.assertEqual(final["outcome"], A.FAILED)
        self.assertIn("attempt limit", final["detail"])

    def test_non_retryable_failures_are_never_retried(self):
        st = mission(self.tmp)
        s = sched(st.root, allow_network=True,
                  provider=fixture_provider(), retrieval_policy=R.RetrievalPolicy(
                      min_interval_s=0.0))

        class Refuses(R.FixtureProvider):
            def fetch(self, url, policy):
                raise R.PolicyViolation("host is not on the allow list")
        s.provider = Refuses({})
        item, _ = s.store.add(A.new_item(A.RETRIEVE_SOURCE, "policy refusal",
                                         priority=0.99, params={"url": URL}))
        s.tick(state=st)
        self.assertEqual(item.status, A.FAILED)
        self.assertEqual(item.attempts, 1, "a safety refusal must not be retried")
        self.assertIn("not retryable", item.last_error + " " +
                      json.dumps(s.store.decisions()[-1]))

    def test_retries_do_not_double_charge_the_experiment_budget(self):
        st = mission(self.tmp)
        s = sched(st.root)
        s.tick(state=st)                       # plan
        s.tick(state=st)                       # hypotheses
        before = st.budget.experiments_used
        s.tick(state=st)                       # one experiment
        after_one = st.budget.experiments_used
        self.assertEqual(after_one, before + 1)
        # Re-seeding and re-evaluating must not re-run the completed item.
        s.seed(st)
        done_ids = {i.id for i in s.store.items.values() if i.status == A.DONE}
        decision = A.AutonomyPolicy(s.limits).evaluate(s.store, st)
        self.assertNotIn(decision["chosen"], done_ids)

    def test_consecutive_failure_cap_stops_the_run(self):
        st = mission(self.tmp)

        class AlwaysFails(R.FixtureProvider):
            def fetch(self, url, policy):
                raise R.RetrievalError("TimeoutError: simulated outage")
        limits = A.RunLimits(max_steps=10, max_consecutive_failures=2,
                             max_attempts_per_item=5, backoff_base_s=0.0)
        s = sched(st.root, limits=limits, allow_network=True,
                  provider=AlwaysFails({}),
                  retrieval_policy=R.RetrievalPolicy(min_interval_s=0.0))
        for i in range(3):
            s.store.add(A.new_item(A.RETRIEVE_SOURCE, f"doomed {i}",
                                   priority=0.99,
                                   params={"url": f"https://fixtures.invalid/{i}"}))
        s.store.save()
        out = s.run(max_steps=10, max_wall_s=60)
        self.assertEqual(out["stop"], A.FAILURE_LIMIT)
        self.assertIn("consecutive failures", out["detail"])

    def test_idle_ticks_do_not_busy_loop(self):
        st = mission(self.tmp)
        st.meta["phase"] = lc.COMPLETED
        st.meta["stop_reason"] = "done"
        st.save()
        s = sched(st.root, limits=A.RunLimits(max_steps=50, max_idle_ticks=2))
        out = s.run(max_steps=50, max_wall_s=60)
        self.assertLessEqual(s.store.counters["ticks"], 3)
        self.assertEqual(out["steps"], 0)


# -------------------------------------------------------------- safety
class TestAutonomySafety(Base):
    def test_autonomy_cannot_bypass_experiment_validation(self):
        st = mission(self.tmp)
        s = sched(st.root)
        # Any attempt to carry a design/command is rejected at the queue.
        with self.assertRaises(A.AutonomyError):
            s.store.add(A.new_item(A.RUN_EXPERIMENT, "unsafe",
                                   params={"design": {"timeout_s": 99999,
                                                      "sizes": [10 ** 9]}}))
        # And a real experiment still goes through the sandbox gate.
        s.run(max_steps=4, max_wall_s=60)
        st2 = ResearchState.load(st.root)
        for rec in st2.experiments.values():
            self.assertLessEqual(rec.design.get("timeout_s", 0), 900)
            for n in rec.design.get("sizes", []):
                self.assertLessEqual(n, 200_000)

    def test_autonomy_cannot_bypass_url_policy(self):
        st = mission(self.tmp)
        s = sched(st.root, allow_network=True, provider=fixture_provider(),
                  retrieval_policy=R.RetrievalPolicy(min_interval_s=0.0))
        for bad in ("http://example.com/x", "file:///etc/passwd",
                    "https://127.0.0.1/admin"):
            try:
                item = A.new_item(A.RETRIEVE_SOURCE, "bad url", priority=0.99,
                                  params={"url": bad})
                s.store.add(item)
            except A.AutonomyError:
                continue          # rejected at the queue before it exists: good
            # It got past the schema (an https private address does), so the
            # retrieval policy must refuse it at execution time.
            for _ in range(3):
                if item.status in (A.FAILED, A.DEFERRED):
                    break
                s.tick(state=st)
            self.assertIn(item.status, (A.FAILED, A.DEFERRED), bad)
        self.assertEqual([s_ for s_ in st.sources.values()
                          if s_.kind == "web_document"], [])

    def test_autonomy_does_not_use_network_or_provider_without_permission(self):
        st = mission(self.tmp)
        provider = fixture_provider()
        s = sched(st.root, provider=provider)   # allow_network defaults False
        s.store.add(A.new_item(A.RETRIEVE_SOURCE, "fixture", priority=0.99,
                               params={"url": URL}))
        s.store.save()
        out = s.run(max_steps=6, max_wall_s=30)
        self.assertEqual(provider.calls, [], "no retrieval may occur")
        self.assertEqual(st.flags.get("retrievals_used", 0), 0)
        self.assertNotEqual(out["stop"], A.COMPLETED)

    def test_a_live_brain_is_not_called_without_permission(self):
        st = mission(self.tmp)
        st.meta["brain"] = "anthropic"          # configured, but not permitted
        st.save()
        os.environ.pop("ANTHROPIC_API_KEY", None)
        s = sched(st.root)                      # allow_provider=False
        out = s.run(max_steps=4, max_wall_s=30)
        self.assertGreaterEqual(out["steps"], 1)
        self.assertEqual(ResearchState.load(st.root).budget.provider_calls_used, 0)

    def test_web_claims_never_become_evidence_under_autonomy(self):
        st = mission(self.tmp)
        s = sched(st.root, allow_network=True, provider=fixture_provider(),
                  retrieval_policy=R.RetrievalPolicy(min_interval_s=0.0))
        s.store.add(A.new_item(A.RETRIEVE_SOURCE, "fixture", priority=0.99,
                               params={"url": URL}))
        s.store.save()
        s.run(max_steps=8, max_wall_s=60)
        st2 = ResearchState.load(st.root)
        web = [x for x in st2.sources.values() if x.kind == "web_document"]
        self.assertTrue(web)
        for c in st2.claims.values():
            if any(w.id in c.source_ids for w in web):
                self.assertEqual(c.status.value, "speculation")
        for e in st2.evidence.values():
            self.assertTrue(e.experiment_id,
                            "evidence must come from an experiment")

    def test_unsafe_state_stops_the_scheduler(self):
        st = mission(self.tmp)
        s = sched(st.root)
        s.tick(state=st)
        st.save()
        # Corrupt the durable record: an event references a missing experiment.
        with open(st.root / "logs" / "events.jsonl", "a") as f:
            f.write(json.dumps({"ts": 1.0, "kind": "experiment_started",
                                "msg": "ghost",
                                "refs": {"experiment": "exp_ghost"}}) + "\n")
        result = sched(st.root).tick()
        self.assertFalse(result["acted"])
        self.assertEqual(result["stop"], A.UNSAFE_STATE)

    def test_cancel_is_terminal_and_durable(self):
        st = mission(self.tmp)
        s = sched(st.root)
        s.store.add(A.new_item(A.GENERATE_REPORT, "will be cancelled"))
        s.store.save()
        rc = cli_main(["autonomy", "cancel", "--dir", str(st.root)])
        self.assertEqual(rc, 0)
        st2 = ResearchState.load(st.root)
        self.assertEqual(st2.meta["phase"], lc.CANCELLED)
        store = A.AutonomyStore(st.root)
        self.assertEqual(store.by_status(A.QUEUED), [])
        out = sched(st.root).run(max_steps=3, max_wall_s=10)
        self.assertEqual(out["stop"], A.CANCELLED_STOP)


# ------------------------------------------------------------ demo + CLI
class TestDemoAndCli(Base):
    def test_cli_surface(self):
        st = mission(self.tmp)
        for argv in (["autonomy", "plan", "--dir", str(st.root)],
                     ["autonomy", "tick", "--dir", str(st.root)],
                     ["autonomy", "status", "--dir", str(st.root)],
                     ["autonomy", "pause", "--dir", str(st.root)],
                     ["autonomy", "resume", "--dir", str(st.root)],
                     ["autonomy", "run", "--dir", str(st.root),
                      "--max-steps", "2", "--max-wall-s", "30"]):
            self.assertEqual(cli_main(argv), 0, argv)
        self.assertEqual(ResearchState.load(st.root).verify(), [])

    def test_pause_is_durable_across_processes(self):
        st = mission(self.tmp)
        cli_main(["autonomy", "pause", "--dir", str(st.root)])
        out = sched(st.root).run(max_steps=5, max_wall_s=30)
        self.assertEqual(out["stop"], A.PAUSED_BY_OPERATOR)
        self.assertEqual(out["steps"], 0)
        cli_main(["autonomy", "resume", "--dir", str(st.root)])
        out2 = sched(st.root).run(max_steps=3, max_wall_s=30)
        self.assertGreater(out2["steps"], 0)

    def test_shipped_demo_is_verifiable(self):
        demo = Path(__file__).resolve().parents[1] / "examples" / "autonomy_demo"
        if not demo.exists():
            self.skipTest("autonomy demo example not present")
        st = ResearchState.load(demo)
        self.assertEqual(st.verify(), [])
        report = json.loads((demo / "autonomy" / "demo_report.json").read_text())
        self.assertEqual(report["evidence"]["evidence_items_from_web"], 0)
        self.assertEqual(report["evidence"]["claim_statuses"], ["speculation"])
        self.assertIn(report["autonomy_stop_reason"],
                      (A.COMPLETED, A.NO_WORK, A.STEP_LIMIT))
        self.assertGreater(report["decision_records"], 0)
        store = A.AutonomyStore(demo)
        self.assertTrue(store.items)
        self.assertTrue(any(i.attempts > 1 for i in store.items.values()),
                        "the demo must exercise a retry")


if __name__ == "__main__":
    unittest.main()
