# ORIGIN v1.4.2 — robots.txt Failure Classification Correction

A correctness correction to v1.4.1. No features were added and no retrieval
logic was redesigned: restricted robots retrieval, redirect re-validation,
bounded decompression, provenance, fixture mode and the DNS-rebinding
documentation are all preserved and still covered by their original tests.

---

## The defect

`HttpsProvider.robots_decision()` classified robots retrieval failures like
this:

```python
except RetrievalError:
    cached = (None, ROBOTS_ABSENT)      # every failure became "absent"
```

`RetrievalError` is raised for timeouts, DNS and TLS failures, HTTP 5xx, any
non-200 status, malformed compressed bodies — and for a genuine 404. Collapsing
them lost the only distinction that matters here:

> **"The server told us there are no rules"** is a fact about the site.
> **"We could not find out"** is a fact about our request.

v1.4.1 recorded the second as the first. Reproduced against the pre-fix code:

```
timeout during robots retrieval  -> (True, "absent")     # wrong
HTTP 500 robots response         -> (True, "absent")     # wrong
malformed gzip robots response   -> (True, "absent")     # wrong
```

Each of those wrote `robots_status: absent` into a durable source record — a
provenance claim ORIGIN had no basis for. It also made `require_robots=True`
weaker than intended: it refused, but the recorded reason named the wrong
state.

---

## The fix

Two changes in `origin/retrieval.py`.

**1. A typed HTTP error carrying its status.** `_request()` previously raised a
plain `RetrievalError` for any non-200 response, so the status was only present
in a message string. It now raises:

```python
class HttpStatusError(RetrievalError):
    """An HTTP response ORIGIN will not use, carrying its status code."""
    def __init__(self, status: int, message: str): ...
```

It subclasses `RetrievalError`, so every existing handler behaves as before.

**2. Precise classification in `robots_decision()`**, with a distinct handler
per outcome rather than one catch-all:

| Situation | `robots_status` |
|---|---|
| **HTTP 404 only** | `absent` |
| Retrieved, decoded, parsed; path allowed | `fetched_and_honoured` |
| Retrieved, decoded, parsed; path disallowed | `disallowed_by_policy` |
| `respect_robots=False` | `disabled_by_configuration` |
| Timeout, DNS/connection/TLS failure, HTTP 5xx, any non-404 status, redirect-policy refusal, redirect over the cap, oversized body, malformed or truncated compressed body, unsupported encoding, undecodable content | `unavailable` |

Two supporting details:

- **Decoding is now strict.** v1.4.1 decoded robots bytes with
  `errors="replace"`, so undecodable content silently became mojibake and was
  parsed as if it were rules. It now raises, and the result is `unavailable`.
- **`require_robots=True` refuses both `absent` and `unavailable`**, naming the
  actual state and its detail: the operator asked for rules to have been
  applied, and neither state means they were.

Unchanged by design: when robots is unavailable and `require_robots` is not
set, retrieval proceeds. The correction is to the *recorded provenance*, not to
the permissiveness of the default.

---

## Verification

All commands run on **CPython 3.12.3, Ubuntu 24.04.4 LTS, Linux x86_64**
(single core), at the commit that ships this report.

```
$ python3 -m unittest discover -s tests -p test_retrieval_security.py
Ran 47 tests in 1.081s
OK

$ python3 -m unittest discover -s tests -p test_web_evidence.py
Ran 25 tests in 0.645s
OK

$ python3 tools/web_evidence_demo.py --dir /tmp/origin-evidence-demo --mode fixture
  (4 of 4 claims mapped; 0 did not and are kept as context only)
Summary: /tmp/origin-evidence-demo/logs/evidence_demo_summary.json

$ python3 -m origin verify --dir /tmp/origin-evidence-demo
State verified: counts, references, experiment artifacts and event log are consistent.

$ python3 tools/check_artifacts_portable.py .
PORTABILITY OK: no machine-specific absolute paths in artifacts under .

$ python3 -m unittest discover -s tests
Ran 186 tests in 62.167s
OK
```

Support matrix, full suite, same commit:

```
CPython 3.10.20   Ran 186 tests in 106.583s  OK
CPython 3.11.15   Ran 186 tests in  72.512s  OK
CPython 3.12.3    Ran 186 tests in  62.167s  OK
CPython 3.13.13   Ran 186 tests in  91.003s  OK
CPython 3.14.4    Ran 186 tests in  71.827s  OK
```

### New regression tests (20, in `tests/test_retrieval_security.py`)

`TestRobotsFailureClassification` drives the real `HttpsProvider` with a
stubbed socket, so URL validation, redirect re-validation, caps and
decompression are the production code:

- HTTP 404 → `absent`
- timeout → `unavailable` (explicitly asserted **not** `absent`)
- HTTP 500 → `unavailable`
- HTTP 401 / 403 / 410 / 429 → `unavailable`
- `URLError`, `SSLError`, `OSError` → `unavailable`
- malformed gzip robots → `unavailable`
- truncated gzip robots → `unavailable`
- undecodable bytes → `unavailable`
- oversized robots (200 KB against a 64 KB cap) → `unavailable`
- robots redirect to `http://`, to a loopback address, to a denied host →
  `unavailable`, and the target is never opened
- redirect chain over the cap → `unavailable`
- parsed allow → `fetched_and_honoured`; parsed disallow → `disallowed_by_policy`
- `respect_robots=False` → `disabled_by_configuration`, robots never requested
- every produced status is a member of `ROBOTS_STATES`, and all five are reachable
- `require_robots=True` refuses both `absent` and `unavailable` with the state named
- `require_robots=True` permits a genuinely parsed allow

`TestRobotsStatusReachesProvenance` checks the status survives into the durable
record: a timeout stores `unavailable` (and the notes never say "honoured"), a
404 stores `absent`, only a parsed allow stores `fetched_and_honoured`, and a
`require_robots` refusal leaves no source, cache, claim or evidence, with
`verify()` clean afterwards.

### Corrected report numbers

The brief flagged inconsistencies in the v1.4.1 documentation, which were real:

| Claim | Was | Now |
|---|---|---|
| New tests in the v1.4.1 correction | "22 new" | **27** were executed in that file at the time; it now holds **47** |
| Full-suite total | both "161" and "166" appeared | **186**, from the command above |
| Web-evidence verification report | "139 tests" in one place, "166" in another | **186** everywhere, with the interpreter and platform stated |

Every number in this document and in the updated reports is the output of a
command executed at this commit, on the environment named above.

---

## Remaining limitations

1. **`unavailable` is still permissive by default.** Retrieval proceeds when
   robots could not be read unless `require_robots=True`. That is a deliberate
   default, now honestly *labelled*; operators who need strictness must set the
   flag.
2. **Robots results are cached per provider instance for the process lifetime.**
   A transient failure is remembered as `unavailable` for the whole run rather
   than retried, and a robots.txt that changes mid-run is not noticed.
3. **`robots_max_bytes` is 64 KB.** A legitimately larger robots.txt is
   `unavailable`, not parsed.
4. **Only `gzip`, `deflate` and identity encodings** are decoded; `br` and
   `zstd` are refused.
5. **Robots parsing is `urllib.robotparser`**, which ignores `Crawl-delay` and
   `Sitemap` and has its own interpretation of wildcards; ORIGIN does not
   implement RFC 9309 itself.
6. **Unchanged from v1.4.1:** unpinned-fallback DNS rebinding race, no TLS
   pinning beyond the system trust store, decompression bounded in memory but
   not in CPU, and general-web breadth still fixture-only for arbitrary hosts.
7. **This is the third defect found in this code path** (robots bypass and the
   gzip bomb in v1.4.1, truncation on re-review, classification here). Treat the
   path as repeatedly reviewed, not as proven correct.
