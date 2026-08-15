"""Structured research proposals (v1.3).

This module is the *stable internal interface* between any language model and
ORIGIN's research engine. The engine never sees a provider response; it sees
validated `Proposal` objects, or it sees a rejection with a reason.

    provider response text
      -> parse (strict JSON, no repair)
      -> schema validation      (shape, types, bounds, no unknown fields)
      -> policy validation      (domain vocabulary, sandbox limits)
      -> audit log              (accepted AND rejected, append-only)
      -> ORIGIN decides

Four proposal types are supported. Each carries enough structure for ORIGIN to
evaluate it *without reading the prose*:

    HypothesisProposal     a testable claim + the measurement that would test it
    ExperimentProposal     a benchmark design, bounded by domain + sandbox policy
    CounterargumentProposal an attack on an existing hypothesis
    KnowledgeGapProposal   something the mission has not measured

Hard rules enforced here:
  * Unknown `proposal_type` -> rejected.
  * Missing required field -> rejected. Never defaulted into existence.
  * Unknown field -> rejected (a model inventing `auto_accept: true` must not
    be quietly ignored; it must be visible in the audit log).
  * Nothing here executes, imports, or evaluates any string from a provider.
  * A proposal is *never* evidence. Accepted proposals enter the pipeline as
    PROPOSED hypotheses / recommendations / cautions only.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .schema import validate

HYPOTHESIS = "hypothesis"
EXPERIMENT = "experiment"
COUNTERARGUMENT = "counterargument"
KNOWLEDGE_GAP = "knowledge_gap"
PROPOSAL_TYPES = (HYPOTHESIS, EXPERIMENT, COUNTERARGUMENT, KNOWLEDGE_GAP)

MAX_PROPOSALS_PER_CALL = 8          # hard cap regardless of what arrives

_COMMON = {
    "proposal_type": {"type": "string", "enum": list(PROPOSAL_TYPES)},
    "statement": {"type": "string", "minLength": 15, "maxLength": 400},
    "rationale": {"type": "string", "minLength": 10, "maxLength": 800},
    "assumptions": {"type": "array", "maxItems": 6,
                    "items": {"type": "string", "minLength": 3,
                              "maxLength": 200}},
    "limitations": {"type": "string", "maxLength": 400},
    "confidence": {"type": "number", "minimum": 0.0, "maximum": 0.9},
    "expected_information_gain": {"type": "number", "minimum": 0.0,
                                  "maximum": 1.0},
    "estimated_cost": {"type": "number", "minimum": 0.0, "maximum": 10.0},
    "linked_hypotheses": {"type": "array", "maxItems": 6,
                          "items": {"type": "string", "maxLength": 40}},
}

# `predicted_measurement` is the only bridge from prose to something ORIGIN can
# check. `kind` and `params` are validated against the DOMAIN's vocabulary in
# validate_policy() — the schema only guarantees the shape.
_MEASUREMENT = {
    "type": "object", "additionalProperties": False,
    "required": ["kind", "params"],
    "properties": {"kind": {"type": "string", "minLength": 3, "maxLength": 40},
                   "params": {"type": "object"}},
}

_SUGGESTED_EXPERIMENT = {
    "type": "object", "additionalProperties": False,
    "required": ["algorithms", "regimes", "sizes", "trials"],
    "properties": {
        "algorithms": {"type": "array", "maxItems": 8,
                       "items": {"type": "string", "maxLength": 40}},
        "regimes": {"type": "array", "maxItems": 8,
                    "items": {"type": "string", "maxLength": 40}},
        "sizes": {"type": "array", "maxItems": 6, "items": {"type": "integer"}},
        "trials": {"type": "integer", "minimum": 1, "maximum": 25},
    },
}

SCHEMAS = {
    HYPOTHESIS: {
        "type": "object", "additionalProperties": False,
        "required": ["proposal_type", "statement", "rationale",
                     "predicted_measurement"],
        "properties": {**_COMMON, "predicted_measurement": _MEASUREMENT},
    },
    EXPERIMENT: {
        "type": "object", "additionalProperties": False,
        "required": ["proposal_type", "statement", "rationale",
                     "suggested_experiment"],
        "properties": {**_COMMON, "suggested_experiment": _SUGGESTED_EXPERIMENT,
                       "predicted_measurement": _MEASUREMENT},
    },
    COUNTERARGUMENT: {
        "type": "object", "additionalProperties": False,
        "required": ["proposal_type", "statement", "rationale",
                     "linked_hypotheses"],
        "properties": {**_COMMON, "predicted_measurement": _MEASUREMENT},
    },
    KNOWLEDGE_GAP: {
        "type": "object", "additionalProperties": False,
        "required": ["proposal_type", "statement", "rationale"],
        "properties": {**_COMMON, "predicted_measurement": _MEASUREMENT},
    },
}


@dataclass
class Proposal:
    """A validated proposal. Construction does not imply acceptance."""
    proposal_id: str
    proposal_type: str
    statement: str
    rationale: str
    provider: str = "unknown"
    model: str = ""
    assumptions: list = field(default_factory=list)
    linked_hypotheses: list = field(default_factory=list)
    predicted_measurement: dict = field(default_factory=dict)
    suggested_experiment: dict = field(default_factory=dict)
    expected_information_gain: float = 0.5
    estimated_cost: float = 1.0
    confidence: float = 0.3
    limitations: str = ""
    check: dict = field(default_factory=dict)      # domain-mapped, machine-checkable
    received_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Rejection:
    proposal_id: str
    reason: str
    stage: str                    # parse | schema | policy | duplicate | cap
    raw: dict = field(default_factory=dict)
    received_at: float = field(default_factory=time.time)


def proposal_id(payload) -> str:
    """Deterministic id from the proposal content (stable across runs)."""
    blob = json.dumps(payload, sort_keys=True, default=str)[:4000]
    return "prop_" + hashlib.sha256(blob.encode()).hexdigest()[:10]


def parse_provider_json(text: str) -> list:
    """Strict parse of a provider response into a list of raw proposals.

    Tolerates only a surrounding ```json fence — a formatting artifact, not a
    meaning change. Anything else that is not valid JSON is rejected; ORIGIN
    never repairs a malformed proposal, because a repaired proposal is a
    proposal ORIGIN wrote.
    """
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        lines = [ln for ln in cleaned.splitlines() if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    if not cleaned:
        raise ValueError("provider returned an empty response")
    got = json.loads(cleaned)          # JSONDecodeError propagates to the caller
    if isinstance(got, dict):
        got = got.get("proposals", got)
        if isinstance(got, dict):
            got = [got]
    if not isinstance(got, list):
        raise ValueError(f"expected a JSON array of proposals, got "
                         f"{type(got).__name__}")
    return got


def validate_schema(raw) -> tuple[str, list[str]]:
    """Returns (proposal_type, problems). Problems empty == schema-valid."""
    if not isinstance(raw, dict):
        return "", [f"proposal is {type(raw).__name__}, expected an object"]
    ptype = raw.get("proposal_type")
    if ptype not in PROPOSAL_TYPES:
        return "", [f"unsupported proposal_type {ptype!r} "
                    f"(supported: {', '.join(PROPOSAL_TYPES)})"]
    return ptype, validate(raw, SCHEMAS[ptype], path="proposal")


def validate_policy(raw: dict, ptype: str, domain, state,
                    sandbox_policy=None) -> tuple[dict, list[str]]:
    """Domain and safety validation. Returns (extras, problems).

    `extras` carries anything the policy layer derived, e.g. the internal
    machine-checkable `check` built from `predicted_measurement`.
    """
    from . import sandbox as sandbox_mod
    problems: list[str] = []
    extras: dict = {}

    measurement = raw.get("predicted_measurement")
    if ptype == HYPOTHESIS and not measurement:
        problems.append("hypothesis proposals must carry a "
                        "predicted_measurement ORIGIN can check")
    if measurement:
        if not hasattr(domain, "build_check"):
            problems.append(f"domain {getattr(domain, 'name', '?')} accepts no "
                            f"machine-checkable predictions")
        else:
            try:
                extras["check"] = domain.build_check(
                    measurement["kind"], measurement.get("params", {}), state)
            except (ValueError, KeyError, TypeError) as e:
                problems.append(f"predicted_measurement outside the domain "
                                f"vocabulary: {e}")

    design = raw.get("suggested_experiment")
    if ptype == EXPERIMENT and not design:
        problems.append("experiment proposals must carry a suggested_experiment")
    if design:
        ctx = domain.proposal_context(state) if hasattr(domain, "proposal_context") else {}
        known_algs = set(ctx.get("algorithms", []))
        known_regimes = set(ctx.get("regimes", []))
        for alg in design.get("algorithms", []):
            if alg not in known_algs:
                problems.append(f"unsupported algorithm {alg!r} "
                                f"(known: {sorted(known_algs)})")
        for regime in design.get("regimes", []):
            if regime not in known_regimes:
                problems.append(f"unsupported input regime {regime!r} "
                                f"(known: {sorted(known_regimes)})")
        if not design.get("algorithms") or not design.get("regimes"):
            problems.append("suggested_experiment must name at least one "
                            "algorithm and one regime")
        # The same policy gate that guards ORIGIN's own designs.
        probe = {"timeout_s": ctx.get("timeout_s", 600),
                 "sizes": design.get("sizes", []),
                 "trials": design.get("trials", 1)}
        problems.extend(sandbox_mod.validate_design(probe, sandbox_policy))

    if ptype == COUNTERARGUMENT:
        linked = raw.get("linked_hypotheses") or []
        unknown = [h for h in linked if h not in state.hypotheses]
        if not linked:
            problems.append("counterargument proposals must link at least one "
                            "existing hypothesis")
        elif unknown:
            problems.append(f"counterargument links unknown hypotheses: {unknown}")

    return extras, problems


def build(raw: dict, ptype: str, extras: dict, provider: str,
          model: str = "") -> Proposal:
    return Proposal(
        proposal_id=proposal_id(raw), proposal_type=ptype,
        statement=raw["statement"], rationale=raw["rationale"],
        provider=provider, model=model,
        assumptions=list(raw.get("assumptions", [])),
        linked_hypotheses=list(raw.get("linked_hypotheses", [])),
        predicted_measurement=dict(raw.get("predicted_measurement", {})),
        suggested_experiment=dict(raw.get("suggested_experiment", {})),
        expected_information_gain=float(raw.get("expected_information_gain", 0.5)),
        estimated_cost=float(raw.get("estimated_cost", 1.0)),
        confidence=float(raw.get("confidence", 0.3)),
        limitations=str(raw.get("limitations", "")),
        check=extras.get("check", {}))


def review(raw_items: list, domain, state, provider: str, model: str = "",
           sandbox_policy=None) -> tuple[list[Proposal], list[Rejection]]:
    """Run the full validation pipeline over raw provider proposals."""
    accepted: list[Proposal] = []
    rejected: list[Rejection] = []
    seen_statements = {h.statement for h in state.hypotheses.values()}

    for i, raw in enumerate(raw_items):
        if len(accepted) + len(rejected) >= MAX_PROPOSALS_PER_CALL:
            rejected.append(Rejection(
                proposal_id=f"prop_over_cap_{i}", stage="cap",
                reason=f"more than {MAX_PROPOSALS_PER_CALL} proposals in one "
                       f"response; the remainder were discarded unread",
                raw={}))
            break
        pid = proposal_id(raw)
        ptype, problems = validate_schema(raw)
        if problems:
            rejected.append(Rejection(proposal_id=pid, stage="schema",
                                      reason="; ".join(problems),
                                      raw=raw if isinstance(raw, dict) else {"raw": str(raw)[:500]}))
            continue
        extras, problems = validate_policy(raw, ptype, domain, state,
                                           sandbox_policy)
        if problems:
            rejected.append(Rejection(proposal_id=pid, stage="policy",
                                      reason="; ".join(problems), raw=raw))
            continue
        if raw["statement"] in seen_statements:
            rejected.append(Rejection(proposal_id=pid, stage="duplicate",
                                      reason="statement duplicates an existing "
                                             "hypothesis", raw=raw))
            continue
        seen_statements.add(raw["statement"])
        accepted.append(build(raw, ptype, extras, provider, model))
    return accepted, rejected


# ------------------------------------------------------------ audit log
class ProposalAudit:
    """Append-only audit of every proposal ORIGIN was offered.

    Accepted and rejected alike, with the reason and the proposal body, so a
    reviewer can reconstruct what the model asked for and why ORIGIN refused.
    Proposal bodies are model output, not private prompts: storing them is the
    point. They are still passed through the secret redactor.
    """

    def __init__(self, root: Path):
        self.path = Path(root) / "logs" / "proposals.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, record: dict) -> None:
        from .brain import redact
        blob = json.dumps(record, default=str)
        with open(self.path, "a") as f:
            f.write(redact(blob) + "\n")

    def accepted(self, p: Proposal, outcome: str = "admitted") -> None:
        self._write({"ts": time.time(), "verdict": "accepted",
                     "outcome": outcome, **p.to_dict()})

    def rejected(self, r: Rejection) -> None:
        self._write({"ts": time.time(), "verdict": "rejected",
                     "stage": r.stage, "reason": r.reason,
                     "proposal_id": r.proposal_id, "proposal": r.raw})

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out
