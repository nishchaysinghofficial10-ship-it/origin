"""ORIGIN knowledge graph.

Knowledge is stored as entities and relations, each with provenance,
confidence, and evidence links. Functional relations (e.g. "fastest_on")
are automatically checked for contradictions: if two different subjects
claim the same functional slot, the contradiction itself becomes a
research target.
"""
from __future__ import annotations

from .models import new_id, now

# Predicates where (predicate, object) should map to a single subject.
FUNCTIONAL_PREDICATES = {"fastest_on", "slowest_on"}


class KnowledgeGraph:
    def __init__(self) -> None:
        self.entities: dict[str, dict] = {}     # id -> {id, name, kind}
        self.relations: dict[str, dict] = {}    # id -> {id, subj, pred, obj, confidence, evidence_ids, created_at}
        self.contradictions: list[dict] = []

    # ---------------------------------------------------------------- entities
    def entity(self, name: str, kind: str) -> str:
        for e in self.entities.values():
            if e["name"] == name and e["kind"] == kind:
                return e["id"]
        eid = new_id("ent")
        self.entities[eid] = {"id": eid, "name": name, "kind": kind}
        return eid

    def entity_name(self, eid: str) -> str:
        return self.entities.get(eid, {}).get("name", eid)

    # --------------------------------------------------------------- relations
    def add_relation(self, subj: str, pred: str, obj: str, confidence: float,
                     evidence_ids: list | None = None) -> dict:
        """Add or merge a relation. Returns the relation dict.

        Merging: identical (subj, pred, obj) accumulates evidence and keeps the
        max confidence. Conflict: a functional predicate already bound to a
        different subject raises a contradiction record instead of silently
        overwriting knowledge.
        """
        evidence_ids = evidence_ids or []
        for r in self.relations.values():
            if r["subj"] == subj and r["pred"] == pred and r["obj"] == obj:
                r["evidence_ids"] = list(dict.fromkeys(r["evidence_ids"] + evidence_ids))
                r["confidence"] = max(r["confidence"], confidence)
                return r

        if pred in FUNCTIONAL_PREDICATES:
            for r in self.relations.values():
                if r["pred"] == pred and r["obj"] == obj and r["subj"] != subj:
                    self.contradictions.append({
                        "id": new_id("contra"),
                        "description": (
                            f"'{self.entity_name(r['subj'])}' and '{self.entity_name(subj)}' "
                            f"both claimed as {pred} '{self.entity_name(obj)}'"
                        ),
                        "relation_ids": [r["id"]],
                        "created_at": now(),
                    })

        rid = new_id("rel")
        rel = {"id": rid, "subj": subj, "pred": pred, "obj": obj,
               "confidence": round(confidence, 3), "evidence_ids": evidence_ids,
               "created_at": now()}
        self.relations[rid] = rel
        return rel

    def relations_readable(self) -> list[str]:
        out = []
        for r in sorted(self.relations.values(), key=lambda x: x["created_at"]):
            out.append(
                f"{self.entity_name(r['subj'])} —{r['pred']}→ {self.entity_name(r['obj'])} "
                f"(confidence {r['confidence']:.2f}, evidence: {len(r['evidence_ids'])})"
            )
        return out

    # ------------------------------------------------------------ serialization
    def to_dict(self) -> dict:
        return {"entities": self.entities, "relations": self.relations,
                "contradictions": self.contradictions}

    @classmethod
    def from_dict(cls, d: dict) -> "KnowledgeGraph":
        g = cls()
        g.entities = d.get("entities", {})
        g.relations = d.get("relations", {})
        g.contradictions = d.get("contradictions", [])
        return g
