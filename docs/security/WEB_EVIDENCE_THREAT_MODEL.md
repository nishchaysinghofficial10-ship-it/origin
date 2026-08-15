# ORIGIN — Web Evidence Threat Model

Scope: the retrieval and evidence layer added in v1.4. System-wide threats are
in `THREAT_MODEL.md`; the LLM proposal surface is in `LLM_THREAT_MODEL.md`.

## Trust boundary

```text
operator (trusted)
  → approved URL, host allow-list, budgets ......... semi-trusted, validated
  → ORIGIN core (trusted code)
      → HTTP request ............................... constructed by ORIGIN
      → RESPONSE BODY .............................. UNTRUSTED DATA
      → text extraction, passages .................. still untrusted
      → claim candidates ........................... schema + provenance gate
      → Claim(SPECULATION, ≤0.4) ................... context, never a finding
```

Retrieved bytes are data. They are never instructions, never code, and never a
reason to change policy.

## Adversaries and attacks

| # | Adversary | Attack | Control | Evidence |
|---|---|---|---|---|
| W1 | Hostile page author | Prompt injection aimed at the extraction model ("ignore instructions", "mark as true", "reveal ANTHROPIC_API_KEY") | Text is quoted inside `<untrusted_source>` with an explicit ignore-instructions directive; and structurally there is nothing to reach — no path from text to FACT, evidence, graph, policy, secrets, or execution | `test_injection_content_is_inert`, `test_source_text_reaches_a_model_only_inside_an_untrusted_envelope` |
| W2 | Same | Embeds a shell command or code and hopes it runs | Nothing retrieved is ever executed; runners come only from in-repo domain templates | `test_injection_content_is_inert` |
| W3 | Same | Serves HTML with `<script>` exfiltration | HTML is reduced to text; script/style/noscript/template/svg content is discarded, never stored or shown | `test_html_extraction_drops_script_and_style` |
| W4 | Attacker controlling a URL ORIGIN is given | SSRF to `169.254.169.254`, `127.0.0.1`, RFC1918, or `localhost` | Every resolved address checked against loopback/private/link-local/multicast/reserved | `test_loopback_private_and_metadata_addresses_are_rejected` |
| W5 | Same | DNS rebinding: a public name resolving to a private address | *All* addresses from `getaddrinfo` are checked, not just the first; the connection is then **pinned** to a validated address (SNI/cert still bound to the hostname), closing the resolve-then-connect race for the connection ORIGIN makes. See residual risk 6 for what pinning does not cover | `test_hostname_resolving_to_private_address_is_rejected`; live check records `pinned_address` |
| W6 | Same | Redirect chain that escapes policy (https → http, or → private host) | Redirects are never followed automatically; each hop is a fresh, fully validated request, and the chain is capped and recorded | `test_redirect_limit_and_scheme_escape_are_refused` |
| W7 | Same | Resource exhaustion: multi-GB body, slow loris, endless redirect | Size cap enforced on `content-length` *and* while streaming; connect/read timeouts; redirect cap; per-mission request budget; per-host rate limit | `test_oversized_response_is_refused`, `test_timeout_and_malformed_response_do_not_corrupt_state`, `test_retrieval_budget_is_enforced` |
| W8 | Same | Serves a binary/PDF/executable to be parsed | Content types are allow-listed and checked before the body is read | `test_unsupported_content_type_is_refused` |
| W9 | Same | Publishes a plausible false performance claim | Claims enter as SPECULATION ≤0.4 with a stored passage; in the algorithms domain, findings come only from ORIGIN experiments | `test_no_web_claim_becomes_accepted_knowledge` |
| W10 | Two sources | Contradict each other, hoping one silently wins | Conflicts are recorded and surfaced as cautions; both claims remain SPECULATION; nothing is resolved without an experiment | `test_conflicting_external_claims_remain_visible` |
| W11 | Page containing credentials | Secret propagates into claims, logs, dossier | Claim text, passages and all log lines pass through `redact()` | `test_secrets_in_retrieved_text_are_redacted_from_logs` |
| W12 | Model doing extraction | Fabricates a claim with no supporting passage | Passage must be locatable in the retrieved text or the claim is rejected; ORIGIN never invents provenance | `test_llm_candidates_without_provenance_are_rejected_not_repaired` |
| W13 | Flaky network / hostile endpoint | Timeout, reset, malformed response mid-mission | Every provider exception is contained; a failure is logged and returned, never raised into the mission; `verify()` stays clean; no half-written source record | `test_timeout_and_malformed_response_do_not_corrupt_state` |
| W15 | Hostile host (**v1.4.1 fix**) | robots.txt redirect used to escape policy — to `http://`, a private address, a denied host, or an over-long chain | robots.txt is fetched through the *same* `_request()` path as a document: https-only, address checks, host lists, per-hop re-validation, redirect cap, 64 KB cap. A robots file that cannot be fetched within policy is recorded `unavailable`, never silently "honoured" | `test_retrieval_security.py::TestRobotsFollowsRetrievalPolicy` (10 tests) |
| W16 | Hostile host (**v1.4.1 fix**) | gzip decompression bomb: a small compressed body expanding to gigabytes in memory | Bounded decompression: `zlib.decompressobj` fed in chunks with an output limit, aborting the instant output passes the cap. Malformed compressed data is an error, not silent passthrough. Unknown encodings are refused | `test_retrieval_security.py::TestCompressedResponseLimits` (8 tests) |
| W14 | Operator error | Points ORIGIN at a private URL or a huge crawl | Policy refuses loudly (raises) rather than silently skipping; budgets and allow-lists are explicit | `test_cli_refuses_a_policy_violating_url` |

## Residual risks

1. **The cached copy is verbatim.** Its hash is the provenance, so it is not
   redacted. Do not retrieve pages containing secrets or personal data.
2. **No TLS pinning or certificate policy beyond the platform default.** A
   compromised CA or a MITM proxy could serve substituted content; the content
   hash records what was received, not that it was authentic.
3. **robots.txt is honoured but terms of service are not parsed.** The operator
   remains responsible for whether a retrieval is permitted.
4. **Reliability scoring is heuristic.** It rewards transport and host class,
   not truthfulness. A well-hosted wrong document scores well — which is why
   the ceiling is 0.6 and why claims never become findings.
5. **Conflict detection is narrow** (two known subjects, opposite direction
   words). Undetected disagreement is possible and is not evidence of consensus.
6. **DNS rebinding: mitigated, with a named gap.** ORIGIN resolves a host,
   rejects the request if *any* returned address is non-public, then connects
   to a validated address by overriding the connection factory
   (`http.client.HTTPSConnection._create_connection`) while leaving SNI and
   certificate verification bound to the real hostname. That closes the
   classic resolve-then-connect race. What it does **not** cover:
   - if pinning cannot be established (interpreter internals unavailable, or a
     proxied environment), the request proceeds through `urlopen` **unpinned**
     and the race returns. The outcome is recorded per source as
     `pinned_address` (empty == unpinned), so an auditor can tell which
     happened rather than having to trust a blanket claim;
   - only the first validated address is used, so ORIGIN does not fail over to
     a second address;
   - it says nothing about what happens inside an intercepting proxy.
7. **No TLS pinning.** Certificate validation uses the system trust store. A
   compromised CA or an intercepting proxy can substitute content; the stored
   hash records what was received, not that it was authentic.
8. **General-web retrieval is partly unverified here.** Egress in the build
   environment is allow-listed; live retrieval was exercised against
   `raw.githubusercontent.com` and `pypi.org`. Live robots enforcement was
   verified (pypi.org disallows `/simple/`; ORIGIN refuses it). Arbitrary
   hosts, wild redirect chains and messy HTML remain fixture-only.
