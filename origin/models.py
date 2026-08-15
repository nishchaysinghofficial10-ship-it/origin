"""ORIGIN core data model.

Every piece of knowledge carries an explicit epistemic status, so the system
never confuses what it has verified with what it has merely generated.
This implements the "evidence hierarchy" — the most important architectural
principle in the ORIGIN specification.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now() -> float:
    return time.time()


class EpistemicStatus(str, Enum):
    FACT = "fact"                                # directly supported by reliable sources
    INFERENCE = "inference"                      # derived from multiple pieces of evidence
    HYPOTHESIS = "hypothesis"                    # proposed, insufficiently tested
    EXPERIMENTAL_RESULT = "experimental_result"  # produced by ORIGIN's own experiments
    SPECULATION = "speculation"                  # lacks sufficient evidence
    CONTRADICTED = "contradicted"                # significant evidence against


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    UNDER_TEST = "under_test"
    PROVISIONALLY_SUPPORTED = "provisionally_supported"
    ACCEPTED_WITH_SCOPE = "accepted_with_scope"   # replicated + survived falsification; scope recorded
    WEAKENED = "weakened"
    REJECTED = "rejected"


@dataclass
class Source:
    id: str
    kind: str                 # "internet" | "dataset" | "user" | "prior_knowledge" | "internal_experiment"
    title: str
    locator: str = ""         # url / path / doi
    reliability: float = 0.6
    added_at: float = field(default_factory=now)
    # ---- v1.4 provenance (all optional; absent on pre-v1.4 sources) -------
    canonical_url: str = ""
    requested_url: str = ""
    final_url: str = ""
    author: str = ""
    published: str = ""            # as stated by the source, unparsed
    retrieved_at: float = 0.0
    content_type: str = ""
    http_status: int = 0
    content_hash: str = ""         # sha256 of the retrieved bytes
    cache_ref: str = ""            # path, relative to the project root
    extraction_method: str = ""
    provider: str = ""
    redirect_chain: list = field(default_factory=list)
    reliability_basis: list = field(default_factory=list)  # explainable reasons
    license_note: str = ""
    retrieval_notes: str = ""
    robots_status: str = ""        # fetched_and_honoured | absent | unavailable
                                   # | disallowed_by_policy | disabled_by_configuration
    pinned_address: str = ""       # the validated IP the connection was pinned to

    @classmethod
    def from_dict(cls, d: dict) -> "Source":
        d = dict(d)
        for key, default in (("canonical_url", ""), ("requested_url", ""),
                             ("final_url", ""), ("author", ""), ("published", ""),
                             ("retrieved_at", 0.0), ("content_type", ""),
                             ("http_status", 0), ("content_hash", ""),
                             ("cache_ref", ""), ("extraction_method", ""),
                             ("provider", ""), ("redirect_chain", []),
                             ("reliability_basis", []), ("license_note", ""),
                             ("retrieval_notes", ""), ("robots_status", ""),
                             ("pinned_address", "")):
            d.setdefault(key, default)
        return cls(**d)


@dataclass
class Claim:
    id: str
    text: str
    status: EpistemicStatus
    confidence: float
    source_ids: list = field(default_factory=list)
    notes: str = ""
    created_at: float = field(default_factory=now)
    # ---- v1.4 extraction provenance --------------------------------------
    passage: str = ""              # the exact text the claim was drawn from
    passage_offset: int = -1       # character offset into the extracted text
    extraction_method: str = ""
    extracted_at: float = 0.0
    claim_type: str = ""           # descriptive | comparative | conditional | definitional
    limitations: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Claim":
        d = dict(d)
        d["status"] = EpistemicStatus(d["status"])
        for key, default in (("passage", ""), ("passage_offset", -1),
                             ("extraction_method", ""), ("extracted_at", 0.0),
                             ("claim_type", ""), ("limitations", "")):
            d.setdefault(key, default)
        return cls(**d)


@dataclass
class Evidence:
    id: str
    target_id: str            # hypothesis or claim id this evidence bears on
    direction: str            # "supports" | "contradicts"
    strength: float           # 0..1
    kind: str                 # "experiment" | "source" | "analysis"
    summary: str
    experiment_id: str = ""
    source_id: str = ""
    payload: dict = field(default_factory=dict)
    created_at: float = field(default_factory=now)

    @classmethod
    def from_dict(cls, d: dict) -> "Evidence":
        return cls(**d)


@dataclass
class Prediction:
    id: str
    text: str
    check: dict               # machine-checkable spec, interpreted by the research domain
    outcome: str = "untested" # "untested" | "confirmed" | "refuted" | "unstable" | "inconclusive"
    detail: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Prediction":
        return cls(**d)


@dataclass
class Hypothesis:
    id: str
    statement: str
    rationale: str
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    predictions: list = field(default_factory=list)          # list[Prediction]
    supporting_evidence: list = field(default_factory=list)  # evidence ids
    contradicting_evidence: list = field(default_factory=list)
    importance: float = 1.0
    cost_estimate: float = 1.0
    tags: list = field(default_factory=list)
    tested_in: list = field(default_factory=list)            # experiment ids
    assumptions: list = field(default_factory=list)          # stated preconditions
    scope: str = ""                                          # conditions under which it holds
    revisions: list = field(default_factory=list)            # append-only status/scope history
    created_at: float = field(default_factory=now)
    updated_at: float = field(default_factory=now)

    def revise(self, new_status: "HypothesisStatus", reason: str) -> None:
        self.revisions.append({"ts": now(), "from": self.status.value,
                               "to": new_status.value, "reason": reason})
        self.status = new_status
        self.updated_at = now()

    def ledger(self) -> dict:
        return {
            "supporting": len(self.supporting_evidence),
            "contradicting": len(self.contradicting_evidence),
            "experiments": len(self.tested_in),
            "predictions_confirmed": sum(1 for p in self.predictions if p.outcome == "confirmed"),
            "predictions_refuted": sum(1 for p in self.predictions if p.outcome == "refuted"),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Hypothesis":
        d = dict(d)
        d["status"] = HypothesisStatus(d["status"])
        d["predictions"] = [Prediction.from_dict(p) for p in d.get("predictions", [])]
        d.setdefault("scope", "")
        d.setdefault("revisions", [])
        d.setdefault("assumptions", [])
        return cls(**d)


@dataclass
class Invalidity:
    """A candidate is NOT VALID under a stated condition.

    v2.1 (gap 8). Domains previously each invented their own convention for
    "this candidate returned a wrong answer here, keep it out of the rankings",
    which meant every new domain re-implemented the exclusion — and the core
    had no way to check that a report never crowned an invalid candidate.
    """
    id: str
    candidate: str                 # algorithm / method / configuration name
    condition: str                 # regime, topology, input class, "*" for all
    reason: str
    experiment_id: str = ""
    detected_at: float = field(default_factory=now)

    @classmethod
    def from_dict(cls, d: dict) -> "Invalidity":
        return cls(**d)


@dataclass
class FalsificationAttempt:
    """A critic-designed attack on a surviving conclusion."""
    id: str
    hypothesis_id: str
    experiment_id: str
    probe: str                      # what was attacked (boundary/unseen conditions)
    outcome: str = "pending"        # survived | failed | inconclusive
    detail: str = ""
    ts: float = field(default_factory=now)

    @classmethod
    def from_dict(cls, d: dict) -> "FalsificationAttempt":
        return cls(**d)


@dataclass
class ExperimentRecord:
    id: str
    title: str
    hypothesis_ids: list
    design: dict
    status: str = "planned"    # planned | running | completed | failed
    dir: str = ""              # ROOT-RELATIVE, e.g. "experiments/exp_ab12cd34ef"
    duration_s: float = 0.0
    summary: dict = field(default_factory=dict)
    error: str = ""
    created_at: float = field(default_factory=now)
    finished_at: float = 0.0

    def path(self, root) -> Path:
        """Resolve this experiment's artifact directory against a project root.

        `dir` is stored root-relative so a project can be copied, archived, or
        unpacked anywhere. Absolute values written by ORIGIN <= v1.0 are still
        honoured here; `ResearchState.load` normalizes them on read.
        """
        d = Path(self.dir) if self.dir else Path("experiments") / self.id
        return d if d.is_absolute() else Path(root) / d

    @classmethod
    def from_dict(cls, d: dict) -> "ExperimentRecord":
        return cls(**d)


def to_jsonable(obj):
    """Dataclass -> plain dict (str enums serialize as their values)."""
    if hasattr(obj, "__dataclass_fields__"):
        return asdict(obj)
    return obj
