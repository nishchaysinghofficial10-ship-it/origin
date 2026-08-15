# ORIGIN — Web Evidence Baseline Audit (before v1.4)

Method: inspection of `origin/evidence.py` (86 lines), `models.Source`,
`models.Claim`, `origin/graph.py`, `origin/proposals.py`, `origin/brain.py`,
the ingestion tests in `tests/test_evidence_redteam.py`, and the security docs;
plus a live probe of what this environment can actually reach.

## Environment facts (probed, not assumed)

```
$ python3 - <<'PY'  # urllib GET, 12s timeout
https://raw.githubusercontent.com/python/cpython/main/Objects/listsort.txt
  → 200 text/plain
https://pypi.org/simple/            → 200 text/html
https://en.wikipedia.org/wiki/Timsort → HTTPError 403 (blocked by egress proxy)
PY
```

Egress is **allow-listed** to package registries, GitHub and
`api.anthropic.com`. So: real HTTPS retrieval is testable here against
allow-listed hosts, but **general web retrieval is not reachable and must be
labelled unverified**.

## What exists today

| Component | State | Classification | Notes |
|---|---|---|---|
| `evidence.ingest_file()` | Local files only: 200 KB cap, sha256, dedupe by hash, cached copy under `sources/`, claims via `brain.extract_claims` | IMPLEMENTED_AND_VERIFIED | The pipeline shape to preserve: source → extraction → validated claim |
| Untrusted-by-default handling | Documents wrapped in `<untrusted_document>` with an ignore-instructions directive; claims forced to `SPECULATION`, confidence capped 0.4 | IMPLEMENTED_AND_VERIFIED | `test_ingested_content_is_untrusted_speculation_with_provenance` |
| Dedupe | Content hash only (`sha256[:16]` embedded in `locator`) | PARTIALLY_IMPLEMENTED | No URL canonicalization; nothing to dedupe *by address* |
| `Source` model | `id, kind, title, locator, reliability, added_at` | **PARTIALLY_IMPLEMENTED** | No canonical/requested URL, author, publication date, retrieval time, content type, HTTP status, content hash field, cache reference, extraction method, provider, or licence note. `reliability` is a bare float with **no stored explanation** |
| `Claim` model | `id, text, status, confidence, source_ids, notes` | **PARTIALLY_IMPLEMENTED** | **No supporting passage, no offset, no extraction method/timestamp, no claim type, no limitations.** A claim cannot currently be audited back to the text it came from |
| Claim schema validation | `CLAIM_PROPOSAL_SCHEMA` (text 10–300, confidence ≤ 0.5) | PARTIALLY_IMPLEMENTED | Does not require provenance fields |
| Knowledge graph | Relations + automatic contradiction detection for functional predicates | IMPLEMENTED_AND_VERIFIED | Web claims never touch it today; that property must be kept |
| Provenance to conclusions | Claims are never promoted to FACT; experiments produce the findings | IMPLEMENTED_AND_VERIFIED | Preserve |
| Network retrieval | **None.** No HTTP client, no URL policy, no SSRF defence, no redirect handling, no size/time limits, no request budget, no robots handling | **MISSING** | The whole of this phase |
| Retrieval failure handling | n/a | MISSING | |
| Retrieval logging/redaction | n/a | MISSING | `redact()` exists and must cover retrieval logs too |
| Conflicting external claims | Not detected | MISSING | Requirement: conflicting sources must stay visible |

## Gaps this phase must close

1. No retrieval layer at all — no provider interface, no policy, no budgets.
2. `Source` cannot carry provenance (URLs, status, content type, hash,
   extraction method, provider, licence).
3. `Claim` cannot carry the passage it came from, so extraction is unauditable.
4. Reliability is an opaque number with no recorded basis.
5. No URL canonicalization, so address-level duplicates are invisible.
6. No conflict detection between external claims.
7. Injection tests cover *ingested local documents* and *provider responses*,
   but not *retrieved web content* travelling the full path.

## What must be preserved (regression floor)

- `ingest_file()` behaviour and its tests (local ingestion keeps working).
- Untrusted-by-default: SPECULATION status, confidence cap, no FACT promotion.
- No path from a claim to the knowledge graph or to a conclusion.
- Zero third-party dependencies (stdlib `urllib`, `html.parser`, `ipaddress`,
  `socket`, `urllib.robotparser`).
