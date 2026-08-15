"""Regression tests for the v1.4.1 security corrections.

Defect 1 — robots.txt policy bypass. `HttpsProvider._robots_allows()` fetched
robots.txt with a default opener: automatic redirects, no `validate_url()` on
any hop, no host/scheme/address checks, and a bare `except Exception` that
turned every failure into "no rules == allowed" while the source record still
said robots was honoured.

Defect 2 — gzip decompression bomb. The byte cap was applied to the compressed
body and re-checked after decompression, but `gzip.decompress()` itself was
unbounded: a ~50 KB compressed payload expanded fully in memory before any
check ran.

Every test here drives the REAL `HttpsProvider` request path with a stubbed
socket layer, so the validation, redirect, cap and decompression logic under
test is the production code, not a mock of it.
"""
import gzip
import ssl
import zlib
import io
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from origin import retrieval as R                             # noqa: E402
from origin import web_evidence as W                          # noqa: E402
from origin.budget import Budget                              # noqa: E402
from origin.cli import PROFILES                               # noqa: E402
from origin.state import ResearchState                        # noqa: E402


class _FakeResponse:
    def __init__(self, body: bytes):
        self._buf = io.BytesIO(body)

    def read(self, n=-1):
        return self._buf.read(n)

    def close(self):
        pass


class StubHttps(R.HttpsProvider):
    """Real provider, stubbed transport.

    `routes` maps an absolute URL to (status, headers, body). Everything else
    — URL validation, redirect re-validation, caps, decompression, robots
    handling — is the production implementation.
    """

    def __init__(self, routes):
        super().__init__()
        self.routes = routes
        self.opened: list[str] = []

    def _open(self, url, policy, accept):
        self.opened.append(url)
        if url not in self.routes:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        status, headers, body = self.routes[url]
        if isinstance(body, str):
            body = body.encode()
        resp = _FakeResponse(body)
        return resp, dict(headers), status, "93.184.216.34", resp


class _RaisingStub(StubHttps):
    """StubHttps that raises a chosen transport exception for given URLs."""

    def __init__(self, routes, failures):
        super().__init__(routes)
        self.failures = failures

    def _open(self, url, policy, accept):
        if url in self.failures:
            self.opened.append(url)
            raise self.failures[url]
        return super()._open(url, policy, accept)


DOC = ("Sorting Notes\n\nMerge sort is a stable comparison sort with "
       "guaranteed n log n behaviour on every input distribution.\n")
DOC_HEADERS = {"Content-Type": "text/plain; charset=utf-8"}


def policy(**kw):
    kw.setdefault("min_interval_s", 0.0)
    kw.setdefault("pin_addresses", False)      # the stub replaces the socket
    return R.RetrievalPolicy(**kw)


def _no_dns(monkey_hosts=("target.test", "evil.test", "other.test")):
    """Skip real DNS for synthetic hostnames; policy logic is what's under test."""
    original = R._addresses
    R._addresses = lambda host: (["93.184.216.34"] if host in monkey_hosts
                                 else original(host))
    return original


class TestRobotsFollowsRetrievalPolicy(unittest.TestCase):
    """Defect 1: robots.txt must obey the same network policy as documents."""

    def setUp(self):
        self._orig = _no_dns()

    def tearDown(self):
        R._addresses = self._orig

    def _fetch(self, routes, pol=None):
        provider = StubHttps(routes)
        return provider, provider.fetch("https://target.test/doc", pol or policy())

    def test_robots_redirect_to_http_is_refused_not_followed(self):
        routes = {
            "https://target.test/robots.txt":
                (301, {"Location": "http://target.test/robots.txt"}, b""),
            "https://target.test/doc": (200, DOC_HEADERS, DOC),
        }
        provider, result = self._fetch(routes)
        # The downgrade is refused; robots is recorded as UNAVAILABLE, never
        # as "honoured", and the insecure URL is never opened.
        self.assertEqual(result.robots_status, R.ROBOTS_UNAVAILABLE)
        self.assertNotIn("http://target.test/robots.txt", provider.opened)

    def test_robots_redirect_to_private_address_is_refused(self):
        routes = {
            "https://target.test/robots.txt":
                (302, {"Location": "https://10.0.0.7/robots.txt"}, b""),
            "https://target.test/doc": (200, DOC_HEADERS, DOC),
        }
        provider, result = self._fetch(routes)
        self.assertEqual(result.robots_status, R.ROBOTS_UNAVAILABLE)
        self.assertNotIn("https://10.0.0.7/robots.txt", provider.opened)

    def test_robots_redirect_to_metadata_service_is_refused(self):
        routes = {
            "https://target.test/robots.txt":
                (302, {"Location": "https://169.254.169.254/latest/meta-data/"}, b""),
            "https://target.test/doc": (200, DOC_HEADERS, DOC),
        }
        provider, result = self._fetch(routes)
        self.assertEqual(result.robots_status, R.ROBOTS_UNAVAILABLE)
        self.assertFalse([u for u in provider.opened if "169.254" in u])

    def test_robots_redirect_to_denied_host_is_refused(self):
        pol = policy(allow_hosts=("target.test",))
        routes = {
            "https://target.test/robots.txt":
                (302, {"Location": "https://evil.test/robots.txt"}, b""),
            "https://target.test/doc": (200, DOC_HEADERS, DOC),
        }
        provider, result = self._fetch(routes, pol)
        self.assertEqual(result.robots_status, R.ROBOTS_UNAVAILABLE)
        self.assertNotIn("https://evil.test/robots.txt", provider.opened)

    def test_robots_redirect_chain_over_the_cap_is_refused(self):
        routes = {
            "https://target.test/robots.txt":
                (302, {"Location": "https://target.test/r1"}, b""),
            "https://target.test/r1": (302, {"Location": "https://target.test/r2"}, b""),
            "https://target.test/r2": (302, {"Location": "https://target.test/r3"}, b""),
            "https://target.test/r3": (302, {"Location": "https://target.test/r4"}, b""),
            "https://target.test/r4": (200, {"Content-Type": "text/plain"}, "User-agent: *\nDisallow: /\n"),
            "https://target.test/doc": (200, DOC_HEADERS, DOC),
        }
        provider, result = self._fetch(routes, policy(max_redirects=2))
        self.assertEqual(result.robots_status, R.ROBOTS_UNAVAILABLE)
        # the rules behind the over-long chain are NOT applied
        self.assertNotIn("https://target.test/r4", provider.opened)

    def test_oversized_robots_is_refused_and_recorded_unavailable(self):
        routes = {
            "https://target.test/robots.txt":
                (200, {"Content-Type": "text/plain"}, b"#" * 200_000),
            "https://target.test/doc": (200, DOC_HEADERS, DOC),
        }
        provider, result = self._fetch(routes, policy(robots_max_bytes=64_000))
        self.assertEqual(result.robots_status, R.ROBOTS_UNAVAILABLE)

    def test_absent_robots_is_recorded_as_absent_not_honoured(self):
        routes = {"https://target.test/doc": (200, DOC_HEADERS, DOC)}
        _, result = self._fetch(routes)       # robots.txt 404s
        self.assertEqual(result.robots_status, R.ROBOTS_ABSENT)
        self.assertNotEqual(result.robots_status, R.ROBOTS_FETCHED)

    def test_valid_robots_rule_disallowing_the_path_blocks_retrieval(self):
        routes = {
            "https://target.test/robots.txt":
                (200, {"Content-Type": "text/plain"},
                 "User-agent: *\nDisallow: /private/\n"),
            "https://target.test/private/doc": (200, DOC_HEADERS, DOC),
        }
        provider = StubHttps(routes)
        with self.assertRaises(R.PolicyViolation) as cm:
            provider.fetch("https://target.test/private/doc", policy())
        self.assertIn("disallows", str(cm.exception))
        self.assertNotIn("https://target.test/private/doc", provider.opened)

    def test_valid_robots_allowing_the_path_is_recorded_as_honoured(self):
        routes = {
            "https://target.test/robots.txt":
                (200, {"Content-Type": "text/plain"},
                 "User-agent: *\nDisallow: /private/\n"),
            "https://target.test/doc": (200, DOC_HEADERS, DOC),
        }
        _, result = self._fetch(routes)
        self.assertEqual(result.robots_status, R.ROBOTS_FETCHED)

    def test_require_robots_refuses_when_rules_are_unavailable(self):
        routes = {"https://target.test/doc": (200, DOC_HEADERS, DOC)}
        provider = StubHttps(routes)
        with self.assertRaises(R.PolicyViolation) as cm:
            provider.fetch("https://target.test/doc",
                           policy(require_robots=True))
        self.assertIn("require_robots", str(cm.exception))

    def test_robots_disabled_by_configuration_is_recorded_as_such(self):
        routes = {"https://target.test/doc": (200, DOC_HEADERS, DOC)}
        provider = StubHttps(routes)
        result = provider.fetch("https://target.test/doc",
                                policy(respect_robots=False))
        self.assertEqual(result.robots_status, R.ROBOTS_DISABLED)
        self.assertNotIn("https://target.test/robots.txt", provider.opened)


class TestCompressedResponseLimits(unittest.TestCase):
    """Defect 2: the byte cap must bound the DECOMPRESSED body, and the
    decompression itself must be bounded, not checked after the fact."""

    def setUp(self):
        self._orig = _no_dns()

    def tearDown(self):
        R._addresses = self._orig

    def test_bounded_decompress_refuses_a_bomb(self):
        bomb = gzip.compress(b"A" * 50_000_000)
        self.assertLess(len(bomb), 400_000, "the bomb must look small compressed")
        with self.assertRaises(R.PolicyViolation) as cm:
            R.bounded_decompress(bomb, "gzip", 400_000)
        self.assertIn("expanded past", str(cm.exception))

    def test_decompressed_content_exactly_at_the_cap_is_accepted(self):
        payload = b"B" * 1000
        out = R.bounded_decompress(gzip.compress(payload), "gzip", 1000)
        self.assertEqual(out, payload)
        with self.assertRaises(R.PolicyViolation):
            R.bounded_decompress(gzip.compress(payload + b"C"), "gzip", 1000)

    def test_normal_small_gzip_response_round_trips(self):
        self.assertEqual(R.bounded_decompress(gzip.compress(b"hello"), "gzip",
                                              400_000), b"hello")
        self.assertEqual(R.bounded_decompress(b"plain", "", 400_000), b"plain")
        self.assertEqual(R.bounded_decompress(b"plain", "identity", 400_000),
                         b"plain")

    def test_malformed_gzip_is_an_error_not_silent_passthrough(self):
        with self.assertRaises(R.RetrievalError):
            R.bounded_decompress(b"this is not gzip", "gzip", 400_000)

    def test_unknown_content_encoding_is_refused(self):
        with self.assertRaises(R.PolicyViolation):
            R.bounded_decompress(b"\x00", "br", 400_000)

    def test_gzip_bomb_over_the_wire_is_refused(self):
        bomb = gzip.compress(b"A" * 50_000_000)
        routes = {"https://target.test/bomb": (
            200, {"Content-Type": "text/plain", "Content-Encoding": "gzip"}, bomb)}
        provider = StubHttps(routes)
        with self.assertRaises(R.PolicyViolation) as cm:
            provider.fetch("https://target.test/bomb", policy())
        self.assertIn("expanded past", str(cm.exception))

    def test_malformed_gzip_over_the_wire_fails_cleanly(self):
        routes = {"https://target.test/broken": (
            200, {"Content-Type": "text/plain", "Content-Encoding": "gzip"},
            b"definitely not gzip")}
        provider = StubHttps(routes)
        with self.assertRaises(R.RetrievalError):
            provider.fetch("https://target.test/broken", policy())

    def test_normal_gzip_over_the_wire_is_extracted(self):
        routes = {"https://target.test/ok": (
            200, {"Content-Type": "text/plain; charset=utf-8",
                  "Content-Encoding": "gzip"}, gzip.compress(DOC.encode()))}
        provider = StubHttps(routes)
        result = provider.fetch("https://target.test/ok", policy())
        self.assertIn("Merge sort is a stable", result.text)
        self.assertEqual(len(result.body), len(DOC.encode()))


class TestRejectionLeavesNoState(unittest.TestCase):
    """A refused response must leave no source, cache, claim or evidence."""

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.st = ResearchState.create(self.tmp / "m", "q", "algobench",
                                       PROFILES["fast"], Budget(), "fast")
        self._orig = _no_dns()

    def tearDown(self):
        R._addresses = self._orig
        self._td.cleanup()

    def test_no_partial_state_after_a_gzip_bomb(self):
        bomb = gzip.compress(b"A" * 50_000_000)
        provider = StubHttps({"https://target.test/bomb": (
            200, {"Content-Type": "text/plain", "Content-Encoding": "gzip"}, bomb)})
        with self.assertRaises(R.PolicyViolation):
            W.ingest_url(self.st, "https://target.test/bomb", provider, None,
                         policy())
        self.assertEqual([s for s in self.st.sources.values()
                          if s.kind == "web_document"], [])
        self.assertEqual(self.st.claims, {})
        self.assertEqual(self.st.evidence, {})
        cache = Path(self.st.root) / "sources"
        self.assertFalse(cache.exists() and any(cache.iterdir()))
        # the refusal is recorded, and the state stays loadable and consistent
        self.st.save()
        reloaded = ResearchState.load(self.st.root)
        self.assertEqual(reloaded.verify(), [])
        self.assertTrue(any(e["kind"] == "retrieval_refused"
                            for e in reloaded.read_events()))

    def test_no_partial_state_after_a_robots_disallow(self):
        provider = StubHttps({
            "https://target.test/robots.txt":
                (200, {"Content-Type": "text/plain"},
                 "User-agent: *\nDisallow: /\n"),
            "https://target.test/doc": (200, DOC_HEADERS, DOC)})
        with self.assertRaises(R.PolicyViolation):
            W.ingest_url(self.st, "https://target.test/doc", provider, None,
                         policy())
        self.assertEqual([s for s in self.st.sources.values()
                          if s.kind == "web_document"], [])
        self.st.save()
        self.assertEqual(ResearchState.load(self.st.root).verify(), [])

    def test_source_records_the_robots_and_pinning_outcome(self):
        provider = StubHttps({
            "https://target.test/robots.txt":
                (200, {"Content-Type": "text/plain"}, "User-agent: *\nAllow: /\n"),
            "https://target.test/doc": (200, DOC_HEADERS, DOC)})
        out = W.ingest_url(self.st, "https://target.test/doc", provider, None,
                           policy())
        src = self.st.sources[out["source"]]
        self.assertEqual(src.robots_status, R.ROBOTS_FETCHED)
        self.assertIn(src.robots_status, R.ROBOTS_STATES)
        self.assertIn("robots:", src.retrieval_notes)


class TestStreamAndLengthLimits(unittest.TestCase):
    """Gaps found while re-reviewing the v1.4.1 fix: truncation and the
    limits that apply to bodies with no usable declared length."""

    def setUp(self):
        self.original = _no_dns()

    def tearDown(self):
        R._addresses = self.original

    def test_truncated_compressed_stream_is_an_error_not_partial_content(self):
        full = gzip.compress(b"D" * 10_000)
        with self.assertRaises(R.RetrievalError) as cm:
            R.bounded_decompress(full[:len(full) // 2], "gzip", 400_000)
        self.assertIn("truncated", str(cm.exception))
        # deflate behaves the same way
        with self.assertRaises(R.RetrievalError):
            R.bounded_decompress(zlib.compress(b"E" * 10_000)[:20], "deflate",
                                 400_000)
        # and an intact stream still round-trips
        self.assertEqual(len(R.bounded_decompress(full, "gzip", 400_000)), 10_000)

    def test_truncated_gzip_over_the_wire_leaves_no_state(self):
        full = gzip.compress(b"F" * 50_000)
        routes = {"https://target.test/robots.txt":
                      (200, {"Content-Type": "text/plain"},
                       "User-agent: *\nAllow: /\n"),
                  "https://target.test/cut":
                      (200, {"Content-Type": "text/plain",
                             "Content-Encoding": "gzip"},
                       full[:len(full) // 3])}
        provider = StubHttps(routes)
        with self.assertRaises(R.RetrievalError):
            provider.fetch("https://target.test/cut", policy())

    def test_body_with_no_declared_length_is_still_capped(self):
        routes = {"https://target.test/robots.txt":
                      (200, {"Content-Type": "text/plain"},
                       "User-agent: *\nAllow: /\n"),
                  "https://target.test/big":
                      (200, {"Content-Type": "text/plain"}, b"G" * 500_000)}
        provider = StubHttps(routes)
        with self.assertRaises(R.PolicyViolation) as cm:
            provider.fetch("https://target.test/big", policy(max_bytes=100_000))
        self.assertIn("limit", str(cm.exception).lower())

    def test_declared_length_over_the_cap_is_refused_before_download(self):
        routes = {"https://target.test/robots.txt":
                      (200, {"Content-Type": "text/plain"},
                       "User-agent: *\nAllow: /\n"),
                  "https://target.test/huge":
                      (200, {"Content-Type": "text/plain",
                             "Content-Length": str(10 ** 9)}, b"H" * 10)}
        provider = StubHttps(routes)
        with self.assertRaises(R.PolicyViolation) as cm:
            provider.fetch("https://target.test/huge", policy(max_bytes=100_000))
        self.assertIn("declared", str(cm.exception).lower())

    def test_deflate_bomb_over_the_wire_is_refused(self):
        routes = {"https://target.test/robots.txt":
                      (200, {"Content-Type": "text/plain"},
                       "User-agent: *\nAllow: /\n"),
                  "https://target.test/bomb":
                      (200, {"Content-Type": "text/plain",
                             "Content-Encoding": "deflate"},
                       zlib.compress(b"I" * 50_000_000))}
        provider = StubHttps(routes)
        with self.assertRaises(R.PolicyViolation) as cm:
            provider.fetch("https://target.test/bomb", policy(max_bytes=100_000))
        self.assertIn("expanded past", str(cm.exception))


class TestRobotsFailureClassification(unittest.TestCase):
    """v1.4.2: a failed robots request is never recorded as absence.

    v1.4.1 caught every `RetrievalError` during robots retrieval and stored
    `absent`, so a timeout produced `(True, "absent")` — a claim about the
    site, made from a failure to reach it. Only an HTTP 404 may say absent.
    """

    ROBOTS = "https://target.test/robots.txt"
    DOC_URL = "https://target.test/doc"

    def setUp(self):
        self.original = _no_dns()

    def tearDown(self):
        R._addresses = self.original

    def _decide(self, routes=None, raises=None, **policy_kw):
        provider = StubHttps(routes or {})
        if raises is not None:
            provider = _RaisingStub(routes or {}, {self.ROBOTS: raises})
        return provider, provider.robots_decision(self.DOC_URL,
                                                  policy(**policy_kw))

    # ---- the one case that means "no rules" ---------------------------
    def test_http_404_is_absent(self):
        _, (allowed, status) = self._decide({})          # stub 404s by default
        self.assertTrue(allowed)
        self.assertEqual(status, R.ROBOTS_ABSENT)

    # ---- everything else is a failure to find out ---------------------
    def test_timeout_is_unavailable_not_absent(self):
        _, (allowed, status) = self._decide(raises=TimeoutError("read timed out"))
        self.assertTrue(allowed)                          # default stays permissive
        self.assertEqual(status, R.ROBOTS_UNAVAILABLE)
        self.assertNotEqual(status, R.ROBOTS_ABSENT)

    def test_http_500_is_unavailable(self):
        err = urllib.error.HTTPError(self.ROBOTS, 500, "Server Error", {}, None)
        _, (_, status) = self._decide(raises=err)
        self.assertEqual(status, R.ROBOTS_UNAVAILABLE)

    def test_non_404_client_error_is_unavailable(self):
        for code in (401, 403, 410, 429):
            err = urllib.error.HTTPError(self.ROBOTS, code, "no", {}, None)
            _, (_, status) = self._decide(raises=err)
            self.assertEqual(status, R.ROBOTS_UNAVAILABLE, f"HTTP {code}")

    def test_connection_and_tls_failures_are_unavailable(self):
        for err in (urllib.error.URLError("connection refused"),
                    ssl.SSLError("handshake failed"),
                    OSError("network unreachable")):
            _, (_, status) = self._decide(raises=err)
            self.assertEqual(status, R.ROBOTS_UNAVAILABLE, repr(err))

    def test_malformed_gzip_robots_is_unavailable(self):
        routes = {self.ROBOTS: (200, {"Content-Type": "text/plain",
                                      "Content-Encoding": "gzip"},
                                b"\x1f\x8b\x08\x00 not really gzip")}
        _, (_, status) = self._decide(routes)
        self.assertEqual(status, R.ROBOTS_UNAVAILABLE)

    def test_truncated_gzip_robots_is_unavailable(self):
        full = gzip.compress(b"User-agent: *\nDisallow: /secret\n")
        routes = {self.ROBOTS: (200, {"Content-Type": "text/plain",
                                      "Content-Encoding": "gzip"},
                                full[:len(full) // 2])}
        _, (_, status) = self._decide(routes)
        self.assertEqual(status, R.ROBOTS_UNAVAILABLE)

    def test_undecodable_robots_content_is_unavailable(self):
        routes = {self.ROBOTS: (200, {"Content-Type": "text/plain; charset=utf-8"},
                                b"\xff\xfe\x00\x80 not valid utf-8")}
        _, (_, status) = self._decide(routes)
        self.assertEqual(status, R.ROBOTS_UNAVAILABLE)

    def test_oversized_robots_is_unavailable(self):
        routes = {self.ROBOTS: (200, {"Content-Type": "text/plain"}, b"#" * 200_000)}
        _, (_, status) = self._decide(routes, robots_max_bytes=64_000)
        self.assertEqual(status, R.ROBOTS_UNAVAILABLE)

    def test_policy_violating_robots_redirect_is_unavailable(self):
        for target in ("http://target.test/robots.txt",
                       "https://127.0.0.1/robots.txt",
                       "https://evil.test/robots.txt"):
            routes = {self.ROBOTS: (302, {"Location": target}, b"")}
            provider = StubHttps(routes)
            allowed, status = provider.robots_decision(
                self.DOC_URL, policy(allow_hosts=("target.test",)))
            self.assertEqual(status, R.ROBOTS_UNAVAILABLE, target)
            self.assertNotIn(target, provider.opened)

    def test_redirect_chain_over_the_cap_is_unavailable(self):
        routes = {self.ROBOTS: (302, {"Location": "https://target.test/r1"}, b"")}
        for i in range(1, 8):
            routes[f"https://target.test/r{i}"] = (
                302, {"Location": f"https://target.test/r{i + 1}"}, b"")
        _, (_, status) = self._decide(routes, max_redirects=2)
        self.assertEqual(status, R.ROBOTS_UNAVAILABLE)

    # ---- the states that are genuinely about the rules ----------------
    def test_parsed_rules_are_fetched_and_honoured_or_disallowed(self):
        allow = {self.ROBOTS: (200, {"Content-Type": "text/plain"},
                               "User-agent: *\nAllow: /\n")}
        _, (allowed, status) = self._decide(allow)
        self.assertTrue(allowed)
        self.assertEqual(status, R.ROBOTS_FETCHED)

        deny = {self.ROBOTS: (200, {"Content-Type": "text/plain"},
                              "User-agent: *\nDisallow: /doc\n")}
        _, (allowed2, status2) = self._decide(deny)
        self.assertFalse(allowed2)
        self.assertEqual(status2, R.ROBOTS_DISALLOWED)

    def test_disabled_by_configuration(self):
        provider, (allowed, status) = self._decide({}, respect_robots=False)
        self.assertTrue(allowed)
        self.assertEqual(status, R.ROBOTS_DISABLED)
        self.assertEqual(provider.opened, [])

    def test_every_status_is_a_declared_state(self):
        seen = set()
        for routes, raises, kw in (
                ({}, None, {}),
                ({}, TimeoutError("t"), {}),
                ({self.ROBOTS: (200, {"Content-Type": "text/plain"},
                                "User-agent: *\nAllow: /\n")}, None, {}),
                ({self.ROBOTS: (200, {"Content-Type": "text/plain"},
                                "User-agent: *\nDisallow: /doc\n")}, None, {}),
                ({}, None, {"respect_robots": False})):
            _, (_, status) = self._decide(routes, raises=raises, **kw)
            seen.add(status)
        self.assertTrue(seen <= set(R.ROBOTS_STATES), seen)
        self.assertEqual(seen, {R.ROBOTS_ABSENT, R.ROBOTS_UNAVAILABLE,
                                R.ROBOTS_FETCHED, R.ROBOTS_DISALLOWED,
                                R.ROBOTS_DISABLED})

    # ---- require_robots refuses BOTH non-rule states -------------------
    def test_require_robots_refuses_absent_and_unavailable(self):
        with self.assertRaises(R.PolicyViolation) as absent:
            self._decide({}, require_robots=True)
        self.assertIn("absent", str(absent.exception))
        self.assertIn("require_robots", str(absent.exception))

        with self.assertRaises(R.PolicyViolation) as unavailable:
            self._decide(raises=TimeoutError("read timed out"),
                         require_robots=True)
        self.assertIn("unavailable", str(unavailable.exception))
        self.assertIn("require_robots", str(unavailable.exception))

    def test_require_robots_permits_a_genuinely_parsed_allow(self):
        routes = {self.ROBOTS: (200, {"Content-Type": "text/plain"},
                                "User-agent: *\nAllow: /\n")}
        _, (allowed, status) = self._decide(routes, require_robots=True)
        self.assertTrue(allowed)
        self.assertEqual(status, R.ROBOTS_FETCHED)


class TestRobotsStatusReachesProvenance(unittest.TestCase):
    """The corrected status must survive into the stored source record."""

    ROBOTS = "https://target.test/robots.txt"
    DOC_URL = "https://target.test/doc"

    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.tmp = Path(self._td.name)
        self.original = _no_dns()

    def tearDown(self):
        R._addresses = self.original
        self._td.cleanup()

    def _mission(self, name="m"):
        return ResearchState.create(self.tmp / name, "q", "algobench",
                                    PROFILES["fast"], Budget(), "fast")

    def test_retrieval_after_a_robots_timeout_records_unavailable(self):
        st = self._mission()
        provider = _RaisingStub({self.DOC_URL: (200, DOC_HEADERS, DOC)},
                                {self.ROBOTS: TimeoutError("read timed out")})
        out = W.ingest_url(st, self.DOC_URL, provider, None, policy())
        self.assertTrue(out["ok"])
        src = st.sources[out["source"]]
        self.assertEqual(src.robots_status, R.ROBOTS_UNAVAILABLE)
        self.assertNotEqual(src.robots_status, R.ROBOTS_ABSENT)
        self.assertIn("unavailable", src.retrieval_notes)
        self.assertNotIn("honoured", src.retrieval_notes)

    def test_retrieval_after_a_404_records_absent(self):
        st = self._mission("m2")
        provider = StubHttps({self.DOC_URL: (200, DOC_HEADERS, DOC)})
        out = W.ingest_url(st, self.DOC_URL, provider, None, policy())
        src = st.sources[out["source"]]
        self.assertEqual(src.robots_status, R.ROBOTS_ABSENT)
        self.assertNotIn("honoured", src.retrieval_notes)

    def test_only_a_parsed_allow_records_honoured(self):
        st = self._mission("m3")
        provider = StubHttps({
            self.ROBOTS: (200, {"Content-Type": "text/plain"},
                          "User-agent: *\nAllow: /\n"),
            self.DOC_URL: (200, DOC_HEADERS, DOC)})
        out = W.ingest_url(st, self.DOC_URL, provider, None, policy())
        src = st.sources[out["source"]]
        self.assertEqual(src.robots_status, R.ROBOTS_FETCHED)
        self.assertIn("fetched_and_honoured", src.retrieval_notes)

    def test_require_robots_refusal_leaves_no_partial_state(self):
        st = self._mission("m4")
        provider = _RaisingStub({self.DOC_URL: (200, DOC_HEADERS, DOC)},
                                {self.ROBOTS: TimeoutError("read timed out")})
        with self.assertRaises(R.PolicyViolation):
            W.ingest_url(st, self.DOC_URL, provider, None,
                         policy(require_robots=True))
        self.assertEqual([s for s in st.sources.values()
                          if s.kind == "web_document"], [])
        self.assertEqual(st.claims, {})
        self.assertEqual(st.evidence, {})
        cache = Path(st.root) / "sources"
        self.assertFalse(cache.exists() and any(cache.iterdir()))
        st.save()
        self.assertEqual(ResearchState.load(st.root).verify(), [])


if __name__ == "__main__":
    unittest.main()
