"""Evidence acquisition & ingestion (v1.0 — local documents).

Pipeline:  file -> EvidenceSource (hashed, timestamped, cached)
                -> passages -> proposed claims (brain, schema-validated)
                -> Claim(status=SPECULATION, capped confidence, provenance)

Hard rules enforced here:
  * External/ingested content is UNTRUSTED DATA. It is never executed, and it
    can never enter the state as FACT or as Evidence — only as SPECULATION
    claims that experiments may later support or contradict.
  * Every claim carries provenance (source id -> file hash + retrieval time).
  * Confidence is capped at 0.4 regardless of what any provider proposes.

Live web acquisition is deferred (see ROADMAP): this module is its landing
zone — a URL fetcher would produce the same Source/passage inputs.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from .brain import Brain, BrainError, CLAIM_PROPOSAL_SCHEMA, validate_proposals
from .models import Claim, EpistemicStatus, Source, new_id

MAX_DOC_BYTES = 200_000
CONFIDENCE_CAP = 0.4


def ingest_file(state, path: str | Path, brain: Brain) -> dict:
    """Ingest one local text document. Returns a summary dict."""
    p = Path(path)
    raw = p.read_bytes()[:MAX_DOC_BYTES]
    text = raw.decode("utf-8", "replace")
    digest = hashlib.sha256(raw).hexdigest()

    # Deduplicate by content hash.
    for s in state.sources.values():
        if s.locator.endswith(digest[:16]):
            state.log_event("ingest_skipped", f"{p.name} already ingested "
                            f"(sha256 {digest[:16]})")
            return {"source": s.id, "claims": 0, "skipped": True}

    cache = state.root / "sources" / f"{digest[:16]}_{p.name}"
    cache.write_bytes(raw)
    src = Source(id=new_id("src"), kind="local_document", title=p.name,
                 locator=f"file:{p.name} sha256:{digest[:16]}",
                 reliability=0.3)
    state.add(src)
    state.log_event("source_ingested",
                    f"{p.name} ({len(raw)} bytes, sha256 {digest[:16]}) — "
                    "content treated as UNTRUSTED", source=src.id)

    try:
        proposals = brain.extract_claims(text, p.name)
    except BrainError as e:
        state.log_event("ingest_error", f"claim extraction failed: {e}")
        state.save()
        return {"source": src.id, "claims": 0, "error": str(e)}

    accepted, rejected = validate_proposals(proposals, CLAIM_PROPOSAL_SCHEMA)
    for reason in rejected:
        state.log_event("proposal_rejected", f"claim proposal rejected: {reason}")
    made = 0
    for prop in accepted:
        c = Claim(id=new_id("clm"), text=prop["text"],
                  status=EpistemicStatus.SPECULATION,
                  confidence=min(float(prop.get("confidence", 0.3)), CONFIDENCE_CAP),
                  source_ids=[src.id])
        state.add(c)
        state.record_confidence_change("claim", c.id, None, c.confidence,
                                       f"ingested from untrusted source {src.id}")
        state.log_event("claim_extracted", f"{c.id} (SPECULATION, "
                        f"conf {c.confidence}): {c.text[:90]}",
                        claim=c.id, source=src.id)
        made += 1
    state.save()
    return {"source": src.id, "claims": made,
            "rejected": len(rejected), "sha256": digest[:16],
            "retrieved_at": time.time()}
