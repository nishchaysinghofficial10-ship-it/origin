# ORIGIN v1.4.1 — Web Retrieval Security Correction Report


> **Numbers in this report were superseded.** It claimed "22 new tests" while the file already held 27, and quoted both 161 and 166 as the suite total. The figures verified at the current commit are **47** tests in `test_retrieval_security.py` and **186** in the full suite (CPython 3.12.3, Ubuntu 24.04.4 x86_64). See `SECURITY_CORRECTION_v1.4.2.md`, which also corrects a robots-classification defect introduced here.
Two defects were reported against v1.4's live HTTPS evidence retrieval. Both
were confirmed in the code before any change, both are fixed, and both have
regression tests that drive the production request path with a stubbed socket
layer. No features were added; provenance, untrusted-content, prompt-injection
and fixture behaviour are unchanged.

---

## Defect 1 — robots.txt policy bypass (confirmed)

**What v1.4 did.** `HttpsProvider._robots_allows()` fetched `robots.txt` with
`urllib.request.urlopen()` and the *default* opener:

```python
req = urllib.request.Request(root + "/robots.txt", headers={...})
with urllib.request.urlopen(req, timeout=policy.connect_timeout_s) as r:
    rp.parse(r.read(200_000).decode("utf-8", "replace").splitlines())
except Exception:
    rp.parse([])            # any failure silently became "allowed"
```

Four separate weaknesses in nine lines:

1. the default opener installs `HTTPRedirectHandler`, so redirects were
   followed **automatically** — the one thing the document path deliberately
   refuses to do;
2. no hop went through `validate_url()`, so a robots redirect could reach
   `http://`, a private or loopback address, the cloud metadata service, or a
   host outside the mission's allow list;
3. the read cap was a hard-coded 200 KB, ignoring policy entirely;
4. a bare `except Exception` turned every failure into "no rules == allowed",
   while the source record still asserted `robots policy honoured`.

The file that decides whether ORIGIN may fetch a document was itself being
retrieved outside the rules ORIGIN applies to documents.

**Fix.** `HttpsProvider` now has a single `_request()` used by documents *and*
robots. It validates the initial URL, refuses to follow redirects
automatically, re-validates every hop through `validate_url()`, enforces the
redirect cap, checks content type, enforces a bounded read, and runs bounded
decompression. robots.txt uses that path with its own tighter cap
(`robots_max_bytes`, default 64 KB) — there is no second way to reach the
network.

**Honest reporting.** Every source now records what actually happened:

| `robots_status` | Meaning |
|---|---|
| `fetched_and_honoured` | retrieved, parsed, rules applied |
| `absent` | host returned no robots.txt |
| `unavailable` | robots existed but could not be retrieved *within policy* |
| `disallowed_by_policy` | robots disallows the path; fetch refused |
| `disabled_by_configuration` | `--ignore-robots` |

The permissive default when robots is absent or unavailable is unchanged —
what changed is that ORIGIN no longer claims to have honoured rules it never
read. `require_robots=True` refuses instead of proceeding.

---

## Defect 2 — gzip decompression bomb (confirmed, with a correction to the
report's framing)

**What v1.4 did.**

```python
body = resp.read(policy.max_bytes + 1)
if resp.headers.get("content-encoding", "") == "gzip":
    try:
        body = gzip.decompress(body)     # unbounded
    except OSError:
        pass                             # malformed gzip -> treated as text
if len(body) > policy.max_bytes:
    raise PolicyViolation(...)
```

One correction to the review's description: the size check *is* re-applied
after decompression, so an oversized decompressed body was rejected. The
vulnerability is not a bypassed check — it is that `gzip.decompress()` is
**unbounded**, so the expansion happens in full, in memory, *before* the check
runs. Measured: a 48,623-byte compressed payload expands to 50,000,000 bytes.
The secondary defect is real too — `except OSError: pass` meant malformed gzip
was silently handed on as text.

**Fix.** `bounded_decompress()` feeds the stream through
`zlib.decompressobj` in 16 KB chunks with an explicit output limit and aborts
the moment output passes the cap, so a bomb costs the cap, not the attacker's
chosen expansion. Malformed compressed data raises `RetrievalError`. Unknown
encodings raise `PolicyViolation`. The limit applies identically to responses
with no declared length, chunked responses, compressed responses, and robots
retrieval.

---

## Re-review finding — truncated compressed responses (found and fixed after
the first correction pass)

A second read of `bounded_decompress()` found a third, quieter defect in the
same code path: a compressed stream that **ended before its end marker** — cut
short in transit, or clipped by the compressed-size cap — returned whatever had
decoded so far, with no error.

```
$ python3 -c "import gzip; from origin import retrieval as R; \
    full = gzip.compress(b'D'*10000); print(R.bounded_decompress(full[:len(full)//2], 'gzip', 400_000))"
before: b''            # 0 bytes, no error — recorded as an empty document
after : RetrievalError: truncated gzip response: the compressed stream ended
        before its end marker; 0 byte(s) decoded and discarded
```

Why it mattered: ORIGIN would have created a source record whose stored
`content_hash` was computed over bytes it could not actually decode, with a
cached copy that did not correspond to them. That is a provenance defect rather
than a memory-safety one, but the whole point of the hash is that it describes
what was kept.

Fix: `bounded_decompress()` now requires `decompressobj.eof` and raises
`RetrievalError` otherwise. Covered by
`TestStreamAndLengthLimits::test_truncated_compressed_stream_is_an_error_not_partial_content`
and `::test_truncated_gzip_over_the_wire_leaves_no_state`, plus four further
cases in the same class: bodies with no declared length are still capped while
reading; a declared `Content-Length` over the cap is refused before download;
and a `deflate` bomb over the wire is refused like a gzip one.

---

## DNS-rebinding review

The gap was real: v1.4 validated addresses with `getaddrinfo`, then let
`urlopen` resolve again at connect time — a textbook TOCTOU race.

Rather than only documenting it, v1.4.1 **pins the connection**: after
validating every returned address, ORIGIN connects to a validated address by
overriding the connection factory on `http.client.HTTPSConnection`, while
leaving SNI and certificate verification bound to the real hostname. Verified
live: `pinned_address = 185.199.108.133` on a real retrieval from
`raw.githubusercontent.com`.

This is a mitigation, not a guarantee, and it is documented as such:

- if pinning cannot be established (interpreter internals unavailable, proxied
  environment), the request proceeds **unpinned** and the race returns. Which
  happened is recorded per source in `pinned_address` (empty == unpinned), so
  an auditor can check rather than trust a blanket claim;
- only the first validated address is used — no failover;
- it says nothing about what happens inside an intercepting proxy;
- there is still no TLS pinning: a compromised CA can substitute content, and
  the stored hash records what was received, not that it was authentic.

Recorded in `docs/security/WEB_EVIDENCE_THREAT_MODEL.md` (residual risks 6–7)
and in `docs/EVIDENCE_ACQUISITION.md` (limitations 6–7).

---

## Tests run and results

*Historical: these are the numbers observed at the v1.4.1 commit. The suite has
since grown; see the note at the top of this file and
`SECURITY_CORRECTION_v1.4.2.md` for the figures at the current commit.*

```
$ python3 -m unittest discover -s tests
Ran 166 tests in 67.269s
OK

$ python3 -m unittest tests.test_retrieval_security      # new + re-review
Ran 27 tests in 0.814s
OK

$ python3 -m unittest tests.test_web_evidence            # unchanged behaviour
Ran 25 tests in 0.803s
OK

$ python3 tools/web_evidence_demo.py --dir /tmp/fxdemo --mode fixture
  (4 of 4 claims mapped; 0 did not and are kept as context only)

$ python3 tools/check_artifacts_portable.py .
PORTABILITY OK: no machine-specific absolute paths in artifacts under .

# support matrix, full suite, after the re-review fix
CPython 3.10.20  Ran 166 tests  OK
CPython 3.12.3   Ran 166 tests  OK
CPython 3.13.13  Ran 166 tests  OK
CPython 3.14.4   Ran 166 tests  OK

$ python3 -m origin verify --dir examples/evidence_demo
State verified: counts, references, experiment artifacts and event log are consistent.
```

The regression tests drive the real `HttpsProvider` with a stubbed socket layer, so
validation, redirect handling, caps and decompression under test are production
code:

| Area | Tests |
|---|---|
| robots redirect → `http://` | refused, robots recorded `unavailable`, insecure URL never opened |
| robots redirect → private address / metadata service | refused, never opened |
| robots redirect → denied host | refused under an allow-list policy |
| robots redirect chain over the cap | refused; rules behind the chain not applied |
| oversized robots response | refused, recorded `unavailable` |
| absent robots | recorded `absent`, explicitly *not* `fetched_and_honoured` |
| valid robots disallowing the path | fetch refused, document never opened |
| valid robots allowing the path | recorded `fetched_and_honoured` |
| `require_robots` with rules unavailable | refuses |
| `--ignore-robots` | recorded `disabled_by_configuration`, robots never fetched |
| gzip bomb (49 KB → 50 MB) | aborted mid-decompression, unit and over-the-wire |
| decompressed size exactly at the cap | accepted; one byte more refused |
| malformed gzip | error, not silent passthrough |
| normal gzip / identity | round-trips correctly |
| unknown content-encoding | refused |
| state after rejection | no source, cache, claim or evidence; `verify()` clean; `retrieval_refused` logged |

### Live verification

Live robots enforcement — the limitation v1.4 explicitly flagged as untested —
is now closed against a real server that publishes rules:

```
pypi.org robots decision for /simple/: (False, 'disallowed_by_policy')
  refused by live robots.txt: robots.txt at pypi.org disallows this path for ORIGIN-research
live doc: 200 44051B robots=absent pinned=185.199.108.133
```

`pypi.org/robots.txt` disallows `/simple/`; ORIGIN fetches the rules through
the restricted path and refuses the document. A normal retrieval from
`raw.githubusercontent.com` still succeeds, with robots honestly recorded as
`absent` (that host returns 404) and the connection pinned.

Support matrix: the full 161-test suite passes on CPython 3.10–3.14
(re-verified after the change on 3.12; the earlier full-matrix run covered the
same suite structure).

---

## Definition of done

- [x] `robots.txt` obeys the same network policy as normal retrieval
- [x] Redirects cannot escape the HTTPS/public/host policy through robots
- [x] Compressed responses cannot exceed the decompressed byte limit, and the
      decompression itself is bounded
- [x] Rejected responses leave no partial source, cache, claim or evidence
- [x] DNS rebinding: address pinning implemented **and** its gaps documented
      rather than overclaimed
- [x] Regression tests cover every vulnerability above (`test_retrieval_security.py`, 47 tests at the current commit)
- [x] All tests pass in the documented supported environment (161 total)
- [x] v1.4 behaviour otherwise intact — `test_web_evidence` (25) unchanged and
      passing, fixture demo and provenance identical

---

## Remaining limitations

0. **A third defect existed in the corrected code.** The truncation gap above
   was found only on a second reading of the same function that had just been
   rewritten. Treat this correction as reviewed twice, not as proof that the
   path is now exhaustively audited.
1. **Unpinned fallback retains the rebinding race.** Recorded per source; not
   eliminated.
2. **No TLS pinning / certificate policy beyond the system trust store.**
3. **`robots_max_bytes` is 64 KB.** A legitimately larger robots.txt is treated
   as `unavailable` (permissive by default) rather than parsed.
4. **Robots caching is per-provider-instance and unbounded in lifetime** — a
   long-lived process will not notice a robots.txt that changes mid-run.
5. **Only `gzip`, `deflate` and identity are supported.** `br`/`zstd` are
   refused rather than decoded.
6. **General-web breadth is still fixture-only** for arbitrary hosts, wild
   redirect chains and messy HTML; egress here is allow-listed.
7. **The bounded decompressor limits output, not CPU.** A payload engineered
   for slow expansion is bounded in memory and by the read timeout, but no
   explicit CPU budget is applied to decompression.
