"""ORIGIN critic engine.

The critic's job is to try to prove ORIGIN wrong. In v0.1 it:

1. Refuses to let a provisionally-supported hypothesis rest on a single
   experiment — it demands an independent replication (new random seeds)
   and spends budget to run it. A conclusion that fails replication is
   downgraded and logged as a failure.
2. Attacks replicated conclusions (v1.0): boundary-size and unseen-regime
   falsification probes. Survivors are accepted WITH an explicit scope;
   casualties are downgraded with the breaking condition recorded.
3. Audits assumptions (domain + generic external-validity caveats).
4. Surfaces knowledge-graph contradictions and noise cautions.
5. Converts knowledge gaps into recommended next investigations.

This turns the loop into research -> criticism -> revision -> research,
rather than research -> answer -> stop.
"""
from __future__ import annotations

from .models import HypothesisStatus

GENERIC_CAVEATS = [
    "All timings come from a single machine and interpreter; absolute numbers will not transfer, only rankings might.",
    "Conclusions hold only for the tested input regimes and sizes; extrapolation beyond them is speculation, not inference.",
]


class CriticEngine:
    def __init__(self, state, domain) -> None:
        self.state = state
        self.domain = domain

    # A hypothesis that was supported by exactly one experiment must replicate.
    def replication_target(self):
        for h in self.state.hypotheses.values():
            if (h.status == HypothesisStatus.PROVISIONALLY_SUPPORTED
                    and "needs_replication" in h.tags):
                return h
        return None

    # A replicated conclusion must survive an active falsification attempt.
    def falsification_target(self):
        for h in self.state.hypotheses.values():
            if (h.status == HypothesisStatus.PROVISIONALLY_SUPPORTED
                    and "replicated" in h.tags
                    and "falsification_done" not in h.tags):
                return h
        return None

    def finalize(self) -> None:
        st = self.state
        if st.flags.get("critic_finalized"):
            return
        st.flags["critic_finalized"] = True

        for caveat in self.domain.initial_assumptions() + GENERIC_CAVEATS:
            if caveat not in st.assumptions:
                st.assumptions.append(caveat)

        # Promote conclusions that were replicated AND survived falsification.
        for h in st.hypotheses.values():
            if (h.status == HypothesisStatus.PROVISIONALLY_SUPPORTED
                    and "replicated" in h.tags
                    and "falsification_survived" in h.tags):
                old = h.status
                h.revise(HypothesisStatus.ACCEPTED_WITH_SCOPE,
                         f"replicated + survived falsification; scope: {h.scope}")
                st.record_confidence_change("hypothesis", h.id, old.value,
                                            h.status.value,
                                            "critic promotion after falsification")
                st.log_event("accepted",
                             f"{h.id} ACCEPTED_WITH_SCOPE — {h.scope}",
                             hypothesis=h.id)

        unreplicated = [h.id for h in st.hypotheses.values()
                        if h.status == HypothesisStatus.PROVISIONALLY_SUPPORTED
                        and "replicated" not in h.tags]
        if unreplicated:
            st.cautions.append(
                "Supported but not independently replicated (treat with reduced confidence): "
                + ", ".join(unreplicated))

        for c in st.graph.contradictions:
            st.cautions.append(f"Unresolved contradiction in knowledge graph: {c['description']}")

        for gap in self.domain.knowledge_gaps(st):
            rec = f"Investigate knowledge gap: {gap}"
            if rec not in st.recommendations:
                st.recommendations.append(rec)
        for h in st.hypotheses.values():
            if h.status == HypothesisStatus.WEAKENED:
                st.recommendations.append(
                    f"Revise or split {h.id}: mixed evidence "
                    f"({len(h.supporting_evidence)} for / {len(h.contradicting_evidence)} against).")

        st.log_event("critic_review",
                     f"Critic pass complete: {len(st.assumptions)} assumptions on record, "
                     f"{len(st.cautions)} cautions, {len(st.recommendations)} recommended follow-ups")
