"""ORIGIN research controller (v1.0) — the orchestrator of the loop.

The controller never does domain work itself. Each step it advances the
mission through the validated lifecycle, asks "what should happen next?",
scores the options, logs the decision with its reasoning, executes it, and
checkpoints the entire research state. Interrupt it at any point; `origin
run` resumes from the durable checkpoint.

Loop:  VALIDATING -> PLANNING -> FORMING_HYPOTHESES (base + validated LLM
       proposals) -> [SELECTING_NEXT_ACTION -> DESIGNING_EXPERIMENT ->
       EXECUTING -> ANALYZING -> UPDATING_KNOWLEDGE]* -> CRITICIZING
       (replication -> falsification -> final review) -> COMPLETED

Every terminal carries an explicit stop reason: budget exhausted, no
high-value next experiment remained, cancelled, or failure.
"""
from __future__ import annotations

import json
import time

from . import lifecycle as lc
from . import proposals as prop
from .brain import BrainError, NullBrain
from .critic import CriticEngine
from .experiments import ExperimentEngine
from .models import (FalsificationAttempt, Hypothesis, HypothesisStatus,
                     Prediction, new_id)
from .report import write_reports

STAGNATION_LIMIT = 3   # consecutive investigate steps with no new evidence


class ResearchController:
    def __init__(self, state, domain, brain=None) -> None:
        self.state = state
        self.domain = domain
        self.brain = brain or NullBrain()
        self.experiments = ExperimentEngine(state, domain)
        self.critic = CriticEngine(state, domain)

    # ------------------------------------------------------------------ helpers
    def _pending(self):
        return [h for h in self.state.hypotheses.values()
                if h.status == HypothesisStatus.PROPOSED]

    def _decide(self, context: str, options: list[dict], chosen: str, reason: str) -> None:
        self.state.decisions.append({
            "id": new_id("dec"), "step": self.state.step, "context": context,
            "options": options, "chosen": chosen, "reason": reason, "ts": time.time()})
        self.state.log_event("decision", f"[{context}] chose: {chosen} — {reason}")

    def _set_current(self, text: str) -> None:
        self.state.flags["current"] = text

    def _heartbeat(self) -> None:
        st = self.state
        st.log_event("heartbeat",
                     f"step {st.step} phase {st.meta.get('phase')} | "
                     f"hyp {len(st.hypotheses)} exp {len(st.experiments)} "
                     f"evd {len(st.evidence)} fail {len(st.failures)} | "
                     f"budget exp {st.budget.experiments_used}/{st.budget.experiments_total} "
                     f"compute {st.budget.compute_seconds_used:.1f}s "
                     f"retries {st.budget.retries_used}/{st.budget.retries_total}")

    def _stop_for_budget(self, reason: str) -> None:
        st = self.state
        st.log_event("budget", f"Stopping investigation: {reason}")
        if st.meta["phase"] not in (lc.CRITICIZING,):
            lc.advance(st, lc.CRITICIZING, f"budget: {reason}")
        st.flags["budget_stop_reason"] = reason

    # --------------------------------------------------- LLM proposal pathway
    def _merge_brain_proposals(self) -> None:
        """Ask the provider for structured proposals; validate; admit.

        Pipeline (origin/proposals.py owns every gate):
            provider response -> strict JSON parse -> schema validation
            -> domain/policy validation -> append-only audit log -> ORIGIN decides

        Accepted proposals get NO evidential privilege:
          * hypotheses enter as PROPOSED, tagged `llm_proposed`, and must
            survive the same experiment -> critic -> replication pipeline;
          * experiment designs are stored as *candidate* designs whose
            ORIGIN-controlled fields (seed, timeout, round, hypothesis ids) are
            filled in by ORIGIN and which still pass the sandbox policy gate at
            execution time;
          * counterarguments become cautions, never confidence changes;
          * knowledge gaps become recommendations.
        Nothing here writes a Claim, Evidence, or a knowledge-graph relation.
        """
        st, dom = self.state, self.domain
        if isinstance(self.brain, NullBrain) or not hasattr(dom, "proposal_context"):
            return
        audit = prop.ProposalAudit(st.root)
        context = dom.proposal_context(st)
        context["existing_hypothesis_ids"] = list(st.hypotheses)
        context["sizes"] = st.meta.get("domain_config", {}).get("sizes", [])

        raw_items = []
        try:
            raw_items = self.brain.propose_research(context, k=5)
            if not raw_items:      # provider only speaks the legacy format
                legacy = self.brain.propose_hypotheses(context, k=2)
                raw_items = [self._upgrade_legacy(p) for p in legacy]
        except BrainError as e:
            st.log_event("brain_error",
                         f"proposal request failed ({type(e).__name__}): {e}")
            st.cautions.append(f"LLM proposals unavailable this run: "
                               f"{type(e).__name__}.")
            return
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            audit.rejected(prop.Rejection(
                proposal_id="prop_unparseable", stage="parse",
                reason=f"{type(e).__name__}: {e}", raw={}))
            st.log_event("proposal_rejected",
                         f"provider response could not be parsed: "
                         f"{type(e).__name__}: {e}")
            return

        accepted, rejected = prop.review(
            raw_items, dom, st, provider=self.brain.name,
            model=getattr(self.brain, "model", ""))
        for r in rejected:
            audit.rejected(r)
            st.log_event("proposal_rejected",
                         f"[{r.stage}] {r.proposal_id}: {r.reason[:200]}")
        for p in accepted:
            outcome = self._admit_proposal(p)
            audit.accepted(p, outcome)
        if accepted or rejected:
            st.log_event("proposals_reviewed",
                         f"{len(accepted)} accepted, {len(rejected)} rejected "
                         f"from {self.brain.name}; full audit in "
                         f"logs/proposals.jsonl")

    @staticmethod
    def _upgrade_legacy(p):
        """Map a legacy {statement, rationale, prediction} proposal onto the
        structured schema so both paths meet the same validator.

        Non-dict junk is passed through untouched so the validator rejects it
        with an accurate reason instead of ORIGIN crashing (or, worse, quietly
        inventing a well-formed proposal out of it).
        """
        if not isinstance(p, dict):
            return p
        out = {"proposal_type": prop.HYPOTHESIS,
               "statement": p.get("statement", ""),
               "rationale": p.get("rationale", ""),
               "predicted_measurement": p.get("prediction", {})}
        if "importance" in p:
            out["expected_information_gain"] = p["importance"]
        return out

    def _admit_proposal(self, p: prop.Proposal) -> str:
        st = self.state
        if p.proposal_type == prop.HYPOTHESIS:
            h = Hypothesis(
                id=new_id("hyp"), statement=p.statement,
                rationale=f"[{p.provider} proposal {p.proposal_id}] {p.rationale}",
                predictions=[Prediction(id=new_id("pred"),
                                        text=p.statement[:120], check=p.check)],
                importance=min(0.9, max(0.1, p.expected_information_gain)),
                cost_estimate=max(0.2, p.estimated_cost),
                assumptions=list(p.assumptions),
                tags=["llm_proposed"])
            st.add(h)
            st.log_event("hypothesis",
                         f"{h.id} (llm_proposed, validated): {h.statement}",
                         hypothesis=h.id)
            return f"admitted as {h.id} (PROPOSED)"
        if p.proposal_type == prop.EXPERIMENT:
            designs = st.flags.setdefault("proposed_designs", [])
            designs.append({"proposal_id": p.proposal_id,
                            "statement": p.statement,
                            **p.suggested_experiment})
            st.log_event("experiment_proposal",
                         f"{p.proposal_id}: candidate design accepted "
                         f"(algorithms={p.suggested_experiment.get('algorithms')}, "
                         f"regimes={p.suggested_experiment.get('regimes')}); "
                         f"ORIGIN sets seed, timeout and scope at execution time")
            return "stored as a candidate design"
        if p.proposal_type == prop.COUNTERARGUMENT:
            targets = ", ".join(p.linked_hypotheses)
            st.cautions.append(f"[{p.provider} counterargument, unverified] "
                               f"{p.statement} (targets {targets})")
            for hid in p.linked_hypotheses:
                h = st.hypotheses.get(hid)
                if h is not None and "counterargued" not in h.tags:
                    h.tags.append("counterargued")
            st.log_event("counterargument",
                         f"{p.proposal_id} against {targets}: {p.statement[:140]}")
            return "recorded as a caution"
        st.recommendations.append(f"[{p.provider} knowledge gap] {p.statement}")
        st.log_event("knowledge_gap", f"{p.proposal_id}: {p.statement[:140]}")
        return "recorded as a knowledge gap"

    # --------------------------------------------------------------------- step
    def step(self) -> bool:
        """Execute one research action. Returns False when the mission ends."""
        st, dom = self.state, self.domain
        t_step = time.time()
        try:
            cont = self._step_inner()
        finally:
            st.budget.charge_elapsed(time.time() - t_step)
            self._heartbeat()
        return cont

    def _step_inner(self) -> bool:
        st, dom = self.state, self.domain
        phase = st.meta.get("phase", lc.CREATED)

        # 0. Wall-time budget check (elapsed active runtime).
        reason = st.budget.exhausted_reason()
        if reason and phase in (lc.SELECTING_NEXT_ACTION, lc.FORMING_HYPOTHESES,
                                lc.PLANNING) and "wall-time" in reason:
            self._stop_for_budget(reason)
            phase = st.meta["phase"]

        # 1. Validate the mission spec, then plan.
        if phase == lc.CREATED:
            lc.advance(st, lc.VALIDATING)
            self._set_current("Validating mission specification")
            problems = self._validate_spec()
            if problems:
                lc.advance(st, lc.FAILED, "invalid mission spec: " + "; ".join(problems))
                return False
            lc.advance(st, lc.PLANNING, "mission spec validated")
            return True

        if phase == lc.PLANNING:
            self._set_current("Decomposing research question")
            st.plan = dom.decompose(st.meta["question"], st.meta.get("domain_config", {}))
            for a in dom.initial_assumptions():
                st.assumptions.append(a)
            dom.seed_knowledge(st)
            st.log_event("planned", "Question decomposed into research tree; prior knowledge seeded")
            lc.advance(st, lc.FORMING_HYPOTHESES)
            return True

        # 2. Hypothesize: base pool + validated LLM proposals.
        if phase == lc.FORMING_HYPOTHESES:
            self._set_current("Generating competing hypotheses")
            for h in dom.generate_hypotheses(st):
                st.add(h)
                st.log_event("hypothesis", f"{h.id}: {h.statement}", hypothesis=h.id)
            self._merge_brain_proposals()
            if not st.hypotheses:
                lc.advance(st, lc.FAILED, "domain produced no hypotheses")
                return False
            lc.advance(st, lc.SELECTING_NEXT_ACTION)
            return True

        # 3. Investigate: pick the most valuable pending hypothesis and test it.
        if phase == lc.SELECTING_NEXT_ACTION:
            pending = self._pending()
            if st.flags.get("stagnation", 0) >= STAGNATION_LIMIT and pending:
                for h in pending:
                    h.revise(HypothesisStatus.WEAKENED,
                             "stagnation: repeated investigation produced no new evidence")
                    st.cautions.append(f"{h.id} parked by stagnation guard.")
                st.log_event("stagnation",
                             f"No new evidence for {STAGNATION_LIMIT} consecutive "
                             "investigation steps; moving to criticism")
                pending = []
            if not pending:
                lc.advance(st, lc.CRITICIZING, "no pending hypotheses remain")
                return True
            return self._investigate(pending)

        # 4. Criticism: replication, then falsification, then final review.
        if phase == lc.CRITICIZING:
            budget_stopped = "budget_stop_reason" in st.flags
            if not budget_stopped:
                target = self.critic.replication_target()
                if target is not None:
                    return self._replicate(target)
                target = self.critic.falsification_target()
                if target is not None:
                    return self._falsify(target)
            if not st.flags.get("critic_finalized"):
                self._set_current("Critic: final review of conclusions")
                self.critic.finalize()
                return True
            # 5. Synthesis + terminal.
            self._set_current("Synthesizing research dossier")
            write_reports(st, dom)
            st.log_event("synthesis", "Research dossier and timeline written to reports/")
            stop = st.flags.get("budget_stop_reason") or \
                "no high-value next experiment remained"
            lc.advance(st, lc.COMPLETED, stop)
            self._set_current("Complete")
            return False

        # Unknown/legacy phase: recover safely.
        st.log_event("warning", f"controller found unexpected phase {phase!r}; "
                     "routing to criticism for safe completion")
        lc.advance(st, lc.CRITICIZING, "recovered from unexpected phase")
        return True

    def _llm_candidate_design(self, primary):
        """Turn an accepted ExperimentProposal into a real design.

        Only the already-validated fields (algorithms, regimes, sizes, trials)
        come from the proposal. Seed, timeout, round, kind and hypothesis
        coverage are set by ORIGIN, and the result still faces the sandbox
        policy gate in ExperimentEngine.run().
        """
        st = self.state
        designs = st.flags.get("proposed_designs") or []
        if not designs or "llm_proposed" not in primary.tags:
            return None
        cand = designs.pop(0)
        cfg = st.meta.get("domain_config", {})
        design = {
            "kind": "benchmark", "round": 5,
            "algorithms": list(cand["algorithms"]),
            "regimes": list(cand["regimes"]),
            "sizes": list(cand["sizes"]) or cfg.get("sizes", [256]),
            "trials": int(cand["trials"]),
            "seed": cfg.get("seed", 1234),          # ORIGIN owns determinism
            "timeout_s": cfg.get("timeout_s", 600),  # ORIGIN owns the limit
            "hypothesis_ids": [primary.id],
        }
        st.log_event("experiment_proposal_used",
                     f"candidate design {cand['proposal_id']} instantiated for "
                     f"{primary.id} with ORIGIN-controlled seed/timeout")
        return design

    # ---------------------------------------------------------------- investigate
    def _investigate(self, pending) -> bool:
        st, dom = self.state, self.domain
        scored = []
        for h in pending:
            evid = len(h.supporting_evidence) + len(h.contradicting_evidence)
            score = h.importance / (1 + evid) / max(h.cost_estimate, 0.2)
            scored.append({"label": h.id, "score": round(score, 3),
                           "reason": f"importance {h.importance}, evidence {evid}, "
                                     f"cost {h.cost_estimate}"})
        scored.sort(key=lambda o: o["score"], reverse=True)
        primary = st.hypotheses[scored[0]["label"]]

        lc.advance(st, lc.DESIGNING_EXPERIMENT)
        design = self._llm_candidate_design(primary) or \
            dom.design_experiment(primary, pending, st)
        est = dom.estimate_cost(design)
        if not st.budget.can_run_experiment(est):
            self._stop_for_budget(st.budget.exhausted_reason()
                                  or "next experiment would exceed compute budget")
            return True
        covered = design.get("hypothesis_ids", [primary.id])
        self._decide("select_investigation", scored, primary.id,
                     f"highest expected information gain per unit cost; "
                     f"experiment co-tests {len(covered)} hypothesis(es)")
        self._set_current(f"Testing {', '.join(covered)}")
        for hid in covered:
            st.hypotheses[hid].status = HypothesisStatus.UNDER_TEST

        lc.advance(st, lc.EXECUTING)
        rec = self.experiments.run(design, title=f"Benchmark round {design.get('round')} "
                                                 f"covering {len(covered)} hypothesis(es)")
        result = self.experiments.load_result(rec)
        if result:
            lc.advance(st, lc.ANALYZING)
            summary = dom.analyze(rec, result, st)
            st.log_event("analysis",
                         f"{rec.id} analyzed; regime winners: {summary.get('winners')}",
                         experiment=rec.id)
            st.flags["stagnation"] = 0
            lc.advance(st, lc.UPDATING_KNOWLEDGE)
        else:
            st.flags["stagnation"] = st.flags.get("stagnation", 0) + 1
            lc.advance(st, lc.UPDATING_KNOWLEDGE,
                       "experiment failed; recording failure")
            fails = st.flags.setdefault("exec_failures", {})
            for hid in covered:
                fails[hid] = fails.get(hid, 0) + 1
                h = st.hypotheses[hid]
                if not st.budget.can_retry():
                    h.revise(HypothesisStatus.WEAKENED,
                             "retry budget exhausted; parked without evidence")
                    st.cautions.append(f"{hid} untestable: retry budget exhausted.")
                elif fails[hid] >= 2:   # don't burn budget retrying a broken design
                    h.revise(HypothesisStatus.WEAKENED,
                             f"experiment execution failed {fails[hid]}x; parked")
                    st.cautions.append(
                        f"{hid} untestable: experiment execution failed "
                        f"{fails[hid]}x; parked without evidence.")
                else:
                    st.budget.charge_retry()
                    h.status = HypothesisStatus.PROPOSED
        lc.advance(st, lc.SELECTING_NEXT_ACTION)
        return True

    # ------------------------------------------------------------------ replicate
    def _replicate(self, target) -> bool:
        st, dom = self.state, self.domain
        design = dom.replication_design(target, st)
        if design and st.budget.can_run_experiment(dom.estimate_cost(design)):
            self._decide("critic_replication",
                         [{"label": target.id, "score": 1.0,
                           "reason": "supported by a single experiment only"}],
                         target.id,
                         "critic refuses single-experiment support; independent "
                         "replication with new seeds")
            self._set_current(f"Critic: replicating {target.id}")
            lc.advance(st, lc.REPLICATING)
            rec = self.experiments.run(design, title=f"Replication of {target.id}")
            result = self.experiments.load_result(rec)
            if result:
                dom.analyze(rec, result, st)
            else:
                target.tags = [t for t in target.tags if t != "needs_replication"]
                st.cautions.append(f"{target.id} replication run failed; "
                                   "confidence reduced.")
            lc.advance(st, lc.UPDATING_KNOWLEDGE)
            lc.advance(st, lc.CRITICIZING)
            return True
        target.tags = [t for t in target.tags if t != "needs_replication"]
        st.cautions.append(f"{target.id} could not be replicated within budget; "
                           "confidence reduced.")
        return True

    # -------------------------------------------------------------------- falsify
    def _falsify(self, target) -> bool:
        """Critic attack: try to break a replicated conclusion at boundary
        sizes and on input regimes it has never seen."""
        st, dom = self.state, self.domain
        target.tags.append("falsification_done")
        design = getattr(dom, "falsification_design", lambda *a: None)(target, st)
        att = FalsificationAttempt(id=new_id("fal"), hypothesis_id=target.id,
                                   experiment_id="", probe="")
        if design is None:
            att.outcome, att.detail = "inconclusive", \
                "no probeable predictions for this hypothesis (its prediction " \
                "types cannot be evaluated at boundary/unseen conditions)"
            st.falsifications[att.id] = att
            st.cautions.append(
                f"{target.id} could not be falsification-probed (prediction types "
                f"not probeable); it remains provisionally supported, not accepted.")
            st.log_event("falsification", f"{target.id}: {att.detail}")
            return True
        if not st.budget.can_run_experiment(dom.estimate_cost(design)):
            att.outcome, att.detail = "inconclusive", "insufficient budget for probe"
            st.falsifications[att.id] = att
            st.cautions.append(f"{target.id} accepted without falsification probe "
                               "(budget); treat scope as untested.")
            st.log_event("falsification", f"{target.id}: {att.detail}")
            return True
        att.probe = ", ".join(pc["label"] for pc in design["probe_checks"])
        self._decide("critic_falsification",
                     [{"label": target.id, "score": 1.0,
                       "reason": "replicated conclusion must survive boundary + "
                                 "unseen-regime probes"}],
                     target.id, f"falsification probes: {att.probe}")
        self._set_current(f"Critic: attacking {target.id}")
        lc.advance(st, lc.FALSIFYING)
        rec = self.experiments.run(design, title=f"Falsification probe of {target.id}")
        att.experiment_id = rec.id
        result = self.experiments.load_result(rec)
        if result:
            verdict = dom.evaluate_falsification(rec, result, target)
            att.outcome, att.detail = verdict["outcome"], verdict["detail"]
            old = target.status
            if verdict["outcome"] == "failed":
                target.revise(HypothesisStatus.WEAKENED,
                              f"failed falsification probe {rec.id}")
                target.tags.append("falsification_failed")
                st.failures.append({
                    "experiment": rec.id, "hypothesis": target.id,
                    "prediction": "(falsification probe)",
                    "expected": "conclusion survives boundary conditions",
                    "observed": verdict["detail"][:300],
                    "action": f"{target.id} downgraded to WEAKENED", "ts": time.time()})
            else:
                target.scope = verdict["scope"]
                target.tags.append("falsification_survived")
            if target.status != old:
                st.record_confidence_change("hypothesis", target.id, old.value,
                                            target.status.value,
                                            f"falsification {rec.id}")
        else:
            att.outcome, att.detail = "inconclusive", "probe experiment failed to run"
        st.falsifications[att.id] = att
        st.log_event("falsification",
                     f"{target.id} probe {att.outcome}: {att.detail[:160]}",
                     hypothesis=target.id, experiment=att.experiment_id)
        lc.advance(st, lc.UPDATING_KNOWLEDGE)
        lc.advance(st, lc.CRITICIZING)
        return True

    # -------------------------------------------------------------- validation
    def _validate_spec(self) -> list[str]:
        st = self.state
        probs = []
        if not str(st.meta.get("question", "")).strip():
            probs.append("question is empty")
        from .domains import get_domain
        try:
            get_domain(st.meta.get("domain", ""))
        except Exception as e:  # noqa: BLE001 - report any resolution failure
            probs.append(f"unknown domain: {e}")
        b = st.budget
        if b.experiments_total <= 0:
            probs.append(f"experiments_total must be positive (got {b.experiments_total})")
        if b.compute_seconds_total <= 0:
            probs.append(f"compute_seconds_total must be positive (got {b.compute_seconds_total})")
        if b.elapsed_seconds_total < 0:
            probs.append("elapsed_seconds_total must be >= 0")
        for p in probs:
            st.log_event("validation_error", p)
        return probs

    # ---------------------------------------------------------------------- run
    def run(self, max_steps: int | None = None) -> None:
        # Resuming is engine behaviour, not CLI behaviour: a PAUSED mission
        # must be resumable through the library API too (R-5).
        lc.resume(self.state)
        # A previous process may have been killed between spawning an
        # experiment and the next checkpoint; adopt any orphaned artifacts into
        # the ledger before doing new work, so the history stays accountable.
        adopted = self.state.reconcile_orphans()
        if adopted:
            self.state.cautions.append(
                f"{len(adopted)} experiment(s) were interrupted before being "
                f"checkpointed and are recorded as interrupted: "
                f"{', '.join(adopted)}")
            self.state.save()
        done = 0
        while True:
            if max_steps is not None and done >= max_steps:
                lc.advance(self.state, lc.PAUSED, f"paused after {done} step(s)")
                self.state.save()
                return
            try:
                cont = self.step()
            except KeyboardInterrupt:
                lc.advance(self.state, lc.PAUSED, "interrupted by user")
                self.state.save()
                raise
            self.state.step += 1
            done += 1
            self.state.save()          # checkpoint after every step
            if not cont:
                return
