"""Policy-restricted evidence retrieval (v1.4).

ORIGIN fetches documents. It does not browse, crawl, execute, or obey them.

Everything here is deliberately narrow:

  * **https only.** No file://, ftp://, data:, javascript:, gopher:, no plain
    http (a downgrade is a rejection, not a warning).
  * **SSRF defence.** Every hostname is resolved and *every* returned address
    is checked against loopback, private, link-local, multicast, reserved and
    cloud-metadata ranges. A public name that resolves to 169.254.169.254 is
    rejected, and so is one that resolves to two addresses where only one is
    private.
  * **Redirects are re-validated, not followed.** Each hop is treated as a new
    request against the full policy; the chain is capped and recorded.
  * **Budgets and limits.** Request budget per mission, minimum interval
    between requests to the same host, connect/read timeouts, hard response
    byte cap enforced while streaming (not after).
  * **Content types are allow-listed.** text/plain, text/markdown, text/html,
    application/json. Anything else is refused before the body is read.
  * **No JavaScript, no downloaded code, ever executed.** HTML is reduced to
    text by a stdlib parser that drops `<script>` and `<style>` outright.
  * **robots.txt is honoured** by default for the configured user agent.

Nothing in a fetched document can change any of the above: policy lives in
code, not in content.
"""
from __future__ import annotations

import hashlib
import ipaddress
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
import zlib
import http.client
import ssl
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from html.parser import HTMLParser

USER_AGENT = ("ORIGIN-research/1.4 (+https://example.invalid/origin; "
              "automated evidence acquisition; contact: operator)")

ALLOWED_SCHEMES = ("https",)

# Honest states for robots handling. "honoured" is only ever recorded when a
# robots.txt was actually retrieved and parsed.
ROBOTS_FETCHED = "fetched_and_honoured"
ROBOTS_ABSENT = "absent"                  # HTTP 404 ONLY: the site publishes no rules
ROBOTS_UNAVAILABLE = "unavailable"        # any failure to find out: timeout, DNS/TLS,
                                          # 5xx, non-404, policy refusal, oversized,
                                          # malformed body, undecodable content
ROBOTS_DISALLOWED = "disallowed_by_policy"
ROBOTS_DISABLED = "disabled_by_configuration"
ROBOTS_STATES = (ROBOTS_FETCHED, ROBOTS_ABSENT, ROBOTS_UNAVAILABLE,
                 ROBOTS_DISALLOWED, ROBOTS_DISABLED)
ALLOWED_CONTENT_TYPES = ("text/plain", "text/markdown", "text/html",
                         "text/x-markdown", "application/json")
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term",
                   "utm_content", "gclid", "fbclid", "ref", "ref_src"}


class RetrievalError(Exception):
    """Base class: retrieval failed. Never fatal to a mission."""


class HttpStatusError(RetrievalError):
    """An HTTP response ORIGIN will not use, carrying its status code.

    Exists so a caller can distinguish "the server said 404" — robots.txt is
    genuinely absent — from every other failure (timeout, 5xx, malformed body,
    policy refusal), which must never be recorded as absence.
    """

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


class PolicyViolation(RetrievalError):
    """The request was refused before any network activity."""


class RetrievalBudgetExhausted(RetrievalError):
    """The mission's retrieval budget is spent."""


@dataclass
class RetrievalPolicy:
    allowed_schemes: tuple = ALLOWED_SCHEMES
    allowed_content_types: tuple = ALLOWED_CONTENT_TYPES
    max_bytes: int = 400_000
    connect_timeout_s: float = 10.0
    read_timeout_s: float = 20.0
    max_redirects: int = 3
    max_requests: int = 20               # per mission
    min_interval_s: float = 1.0          # per host, politeness
    respect_robots: bool = True
    require_robots: bool = False         # True == refuse when robots is unavailable
    robots_max_bytes: int = 64_000       # robots.txt is small; cap it tightly
    pin_addresses: bool = True           # connect to the address we validated
    allow_hosts: tuple = ()              # empty == any public host allowed
    deny_hosts: tuple = ()
    user_agent: str = USER_AGENT


@dataclass
class FetchResult:
    requested_url: str
    canonical_url: str
    final_url: str
    status: int
    content_type: str
    charset: str
    body: bytes
    text: str
    content_hash: str
    elapsed_s: float
    redirect_chain: list = field(default_factory=list)
    headers: dict = field(default_factory=dict)   # allow-listed subset only
    provider: str = "https"
    truncated: bool = False
    robots_status: str = "not_checked"   # see ROBOTS_STATES
    pinned_address: str = ""             # the validated IP actually connected to

    def summary(self) -> dict:
        return {"requested_url": self.requested_url,
                "canonical_url": self.canonical_url,
                "final_url": self.final_url, "status": self.status,
                "content_type": self.content_type, "bytes": len(self.body),
                "content_hash": self.content_hash,
                "elapsed_s": round(self.elapsed_s, 3),
                "redirects": self.redirect_chain, "provider": self.provider,
                "truncated": self.truncated, "robots_status": self.robots_status,
                "pinned_address": self.pinned_address}


# ------------------------------------------------------------------ URL policy
def canonical_url(url: str) -> str:
    """Stable address form for dedupe: lowercase scheme/host, default port
    dropped, fragment removed, tracking parameters stripped, empty path -> '/'.

    Query parameter ORDER is preserved: reordering can change what a server
    returns, so it is not ORIGIN's to normalise.
    """
    parts = urllib.parse.urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower()
    if not host:
        raise PolicyViolation(f"no host in URL {url!r}")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as e:
        raise PolicyViolation(f"invalid international hostname in {url!r}: {e}")
    netloc = host
    if parts.port and not ((scheme == "https" and parts.port == 443) or
                           (scheme == "http" and parts.port == 80)):
        netloc = f"{host}:{parts.port}"
    query = urllib.parse.urlencode(
        [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
         if k.lower() not in TRACKING_PARAMS])
    return urllib.parse.urlunsplit((scheme, netloc, parts.path or "/", query, ""))


def _addresses(host: str) -> list[str]:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise PolicyViolation(f"hostname {host!r} does not resolve: {e}")
    return sorted({i[4][0] for i in infos})


def _reject_non_public(addr: str, host: str) -> None:
    ip = ipaddress.ip_address(addr)
    if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
            or ip.is_reserved or ip.is_unspecified):
        raise PolicyViolation(
            f"{host} resolves to non-public address {addr}; refusing "
            f"(loopback/private/link-local/metadata addresses are never fetched)")


def validate_url(url: str, policy: RetrievalPolicy, *,
                 resolve: bool = True) -> str:
    """Full pre-flight check. Returns the canonical URL or raises."""
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme.lower() not in policy.allowed_schemes:
        raise PolicyViolation(
            f"scheme {parts.scheme!r} is not allowed (permitted: "
            f"{', '.join(policy.allowed_schemes)}); refusing {url!r}")
    canon = canonical_url(url)
    host = urllib.parse.urlsplit(canon).hostname or ""
    if policy.deny_hosts and any(host == d or host.endswith("." + d)
                                 for d in policy.deny_hosts):
        raise PolicyViolation(f"host {host!r} is on the deny list")
    if policy.allow_hosts and not any(host == a or host.endswith("." + a)
                                      for a in policy.allow_hosts):
        raise PolicyViolation(
            f"host {host!r} is not on this mission's allow list "
            f"({', '.join(policy.allow_hosts)})")
    # A literal IP is checked directly; a name is checked on every address it
    # resolves to, so DNS cannot smuggle us onto a private network.
    try:
        _reject_non_public(str(ipaddress.ip_address(host)), host)
    except ValueError:
        if resolve:
            for addr in _addresses(host):
                _reject_non_public(addr, host)
    return canon


# ------------------------------------------------------------ text extraction
class _TextExtractor(HTMLParser):
    """HTML -> text. Script and style content is discarded, never returned."""
    SKIP = {"script", "style", "noscript", "template", "svg"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self.title = ""
        self._in_title = False
        self.meta: dict = {}

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            a = {k.lower(): (v or "") for k, v in attrs}
            name = (a.get("name") or a.get("property") or "").lower()
            if name in ("author", "article:author", "citation_author"):
                self.meta.setdefault("author", a.get("content", ""))
            if name in ("date", "article:published_time", "citation_date",
                        "citation_publication_date"):
                self.meta.setdefault("published", a.get("content", ""))
        elif tag in ("p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip_depth:
            self._skip_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in ("p", "div", "li", "tr", "h1", "h2", "h3", "h4"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._in_title:
            self.title += data.strip()
        else:
            self.parts.append(data)


def extract_text(body: bytes, content_type: str, charset: str = "utf-8") -> dict:
    """Return {text, title, method, author, published}. Never executes anything."""
    raw = body.decode(charset or "utf-8", "replace")
    ctype = (content_type or "").split(";")[0].strip().lower()
    if ctype in ("text/html", "application/xhtml+xml"):
        parser = _TextExtractor()
        try:
            parser.feed(raw)
        except Exception:                       # noqa: BLE001 - malformed HTML
            pass
        lines = [ln.strip() for ln in "".join(parser.parts).splitlines()]
        text = "\n".join(ln for ln in lines if ln)
        return {"text": text, "title": parser.title[:200],
                "method": "html.parser text extraction (script/style dropped)",
                "author": parser.meta.get("author", ""),
                "published": parser.meta.get("published", "")}
    if ctype == "application/json":
        return {"text": raw, "title": "", "method": "raw json text",
                "author": "", "published": ""}
    first = next((ln.strip() for ln in raw.splitlines() if ln.strip()), "")
    return {"text": raw, "title": first[:200], "method": "plain text passthrough",
            "author": "", "published": ""}


def bounded_decompress(data: bytes, encoding: str, limit: int) -> bytes:
    """Decompress at most `limit` bytes, then stop.

    `gzip.decompress()` is unbounded: a small compressed body can expand to
    gigabytes in memory before any size check runs. This feeds the stream
    through a decompressor in chunks and aborts the moment the OUTPUT exceeds
    the policy limit, so a decompression bomb costs `limit` bytes, not the
    attacker's chosen expansion.
    """
    enc = (encoding or "").strip().lower()
    if enc in ("", "identity"):
        return data
    if enc == "gzip":
        wbits = 16 + zlib.MAX_WBITS
    elif enc == "deflate":
        wbits = zlib.MAX_WBITS
    else:
        raise PolicyViolation(f"content-encoding {enc!r} is not supported")
    dec = zlib.decompressobj(wbits)
    out = bytearray()
    step = 16_384
    try:
        for i in range(0, len(data), step):
            out.extend(dec.decompress(data[i:i + step], limit + 1 - len(out)))
            if len(out) > limit:
                raise PolicyViolation(
                    f"{enc} content expanded past the {limit}-byte limit; "
                    f"aborted mid-decompression and discarded")
            if dec.unconsumed_tail and len(out) > limit:
                break
        out.extend(dec.flush(limit + 1 - len(out)))
    except zlib.error as e:
        raise RetrievalError(f"malformed {enc} content: {e}")
    if len(out) > limit:
        raise PolicyViolation(
            f"{enc} content expanded past the {limit}-byte limit; discarded")
    if not dec.eof:
        # A stream that never reached its end marker was cut short in transit
        # (or truncated by the compressed-size cap). Returning what decoded so
        # far would record a source whose stored content hash does not
        # correspond to the text ORIGIN kept, so it is an error instead.
        raise RetrievalError(
            f"truncated {enc} response: the compressed stream ended before its "
            f"end marker; {len(out)} byte(s) decoded and discarded")
    return bytes(out)


# ---------------------------------------------------------------- providers
class EvidenceProvider(ABC):
    """Provider-neutral retrieval interface. The controller never imports a
    specific website, search engine, or vendor client."""
    name = "abstract"

    @abstractmethod
    def fetch(self, url: str, policy: RetrievalPolicy) -> FetchResult:
        ...


class FixtureProvider(EvidenceProvider):
    """Deterministic offline provider: serves canned documents by URL.

    Used by every test and by `--fixtures` mode, so the whole evidence
    pipeline is exercisable with no network at all.
    """
    name = "fixture"

    def __init__(self, documents: dict, latency_s: float = 0.0):
        # documents: canonical_url -> dict(body=bytes|str, content_type=..,
        #                                  status=200, redirects=[...], raise=Exc)
        self.documents = documents
        self.latency_s = latency_s
        self.calls: list[str] = []

    def fetch(self, url: str, policy: RetrievalPolicy) -> FetchResult:
        canon = validate_url(url, policy, resolve=False)
        self.calls.append(canon)
        doc = self.documents.get(canon) or self.documents.get(url)
        if doc is None:
            raise RetrievalError(f"fixture provider has no document for {canon}")
        if isinstance(doc, Exception) or isinstance(doc.get("raise"), Exception):
            raise doc if isinstance(doc, Exception) else doc["raise"]
        chain = list(doc.get("redirects", []))
        for hop in chain:                       # each hop faces the full policy
            validate_url(hop, policy, resolve=False)
        if len(chain) > policy.max_redirects:
            raise PolicyViolation(f"redirect chain of {len(chain)} exceeds the "
                                  f"limit of {policy.max_redirects}")
        ctype = doc.get("content_type", "text/plain; charset=utf-8")
        base = ctype.split(";")[0].strip().lower()
        if base not in policy.allowed_content_types:
            raise PolicyViolation(f"content type {base!r} is not allowed "
                                  f"(permitted: {', '.join(policy.allowed_content_types)})")
        body = doc["body"]
        if isinstance(body, str):
            body = body.encode()
        truncated = len(body) > policy.max_bytes
        if truncated and doc.get("hard_limit", True):
            raise PolicyViolation(
                f"response of {len(body)} bytes exceeds the "
                f"{policy.max_bytes}-byte limit; refusing")
        time.sleep(self.latency_s)
        extracted = extract_text(body, ctype)
        return FetchResult(
            requested_url=url, canonical_url=canon,
            final_url=chain[-1] if chain else canon,
            status=int(doc.get("status", 200)), content_type=ctype,
            charset="utf-8", body=body, text=extracted["text"],
            content_hash=hashlib.sha256(body).hexdigest(),
            elapsed_s=self.latency_s, redirect_chain=chain,
            headers={"content-type": ctype}, provider=self.name)


class HttpsProvider(EvidenceProvider):
    """stdlib HTTPS retrieval. One policy-enforcing request path, used for
    documents AND for robots.txt — there is no second, looser way out."""
    name = "https"

    def __init__(self):
        self._last_request: dict[str, float] = {}
        self._robots: dict[str, tuple] = {}      # root -> (parser|None, status)

    # ---------------------------------------------------------- transport
    def _throttle(self, host: str, policy: RetrievalPolicy) -> None:
        last = self._last_request.get(host)
        if last is not None:
            wait = policy.min_interval_s - (time.time() - last)
            if wait > 0:
                time.sleep(wait)
        self._last_request[host] = time.time()

    def _open(self, url: str, policy: RetrievalPolicy, accept: str):
        """Open one hop. Connects to the address that was validated, when the
        interpreter allows it (see `pin_addresses` / DNS-rebinding notes)."""
        parts = urllib.parse.urlsplit(url)
        host, port = parts.hostname or "", parts.port or 443
        pinned = ""
        headers = {"user-agent": policy.user_agent, "accept": accept,
                   "accept-encoding": "gzip, identity", "host": parts.netloc}
        if policy.pin_addresses:
            try:
                addr = _addresses(host)[0]
                for candidate in _addresses(host):
                    _reject_non_public(candidate, host)
                conn = http.client.HTTPSConnection(
                    host, port, timeout=policy.read_timeout_s,
                    context=ssl.create_default_context())
                # Connect to the validated IP while keeping SNI and certificate
                # verification bound to the real hostname.
                conn._create_connection = (            # noqa: SLF001
                    lambda address, timeout, source_address, _ip=addr:
                    socket.create_connection((_ip, address[1]), timeout,
                                             source_address))
                path = parts.path or "/"
                if parts.query:
                    path += "?" + parts.query
                conn.request("GET", path, headers=headers)
                resp = conn.getresponse()
                pinned = addr
                return resp, dict(resp.getheaders()), resp.status, pinned, conn
            except (PolicyViolation, RetrievalError):
                raise
            except Exception:                          # noqa: BLE001
                pinned = ""                            # fall through, unpinned
        req = urllib.request.Request(url, method="GET", headers=headers)
        opener = urllib.request.build_opener(_NoRedirect())
        resp = opener.open(req, timeout=policy.read_timeout_s)
        return resp, dict(resp.headers), resp.status, pinned, resp

    def _request(self, url: str, policy: RetrievalPolicy, *, max_bytes: int,
                 allowed_types: tuple, accept: str) -> dict:
        """Validated, redirect-capped, size-bounded GET.

        Every hop — including the first — goes through `validate_url`, so a
        redirect can never reach http, a private address, or a host outside the
        mission's allow list. Used for documents and robots.txt alike.
        """
        canon = validate_url(url, policy)
        current, chain = canon, []
        for hop in range(policy.max_redirects + 1):
            self._throttle(urllib.parse.urlsplit(current).hostname or "", policy)
            closer = None
            try:
                resp, headers, status, pinned, closer = self._open(
                    current, policy, accept)
            except urllib.error.HTTPError as e:
                status, headers, resp = e.code, dict(e.headers), e
            except (urllib.error.URLError, TimeoutError, socket.timeout,
                    ssl.SSLError, OSError) as e:
                raise RetrievalError(f"{type(e).__name__} fetching {current}: {e}")
            try:
                if status in (301, 302, 303, 307, 308):
                    location = headers.get("Location") or headers.get("location", "")
                    if not location:
                        raise HttpStatusError(
                            status, f"HTTP {status} from {current} without a "
                                    f"Location header")
                    if hop >= policy.max_redirects:
                        raise PolicyViolation(
                            f"more than {policy.max_redirects} redirects from "
                            f"{canon}; refusing")
                    current = validate_url(
                        urllib.parse.urljoin(current, location), policy)
                    chain.append(current)
                    continue
                if status != 200:
                    raise HttpStatusError(status, f"HTTP {status} for {current}")
                ctype_full = headers.get("Content-Type") or headers.get("content-type", "")
                base = ctype_full.split(";")[0].strip().lower()
                if base not in allowed_types:
                    raise PolicyViolation(
                        f"content type {base or 'unknown'!r} from {current} is "
                        f"not allowed (permitted: {', '.join(allowed_types)})")
                declared = headers.get("Content-Length") or headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise PolicyViolation(
                        f"declared size {declared} exceeds the {max_bytes}-byte "
                        f"limit; refusing before download")
                # Bounded read: covers chunked and length-less responses too.
                raw = resp.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise PolicyViolation(
                        f"response from {current} exceeded the {max_bytes}-byte "
                        f"limit mid-download; discarded")
                encoding = (headers.get("Content-Encoding")
                            or headers.get("content-encoding", ""))
                body = bounded_decompress(raw, encoding, max_bytes)
                charset = "utf-8"
                if "charset=" in ctype_full:
                    charset = ctype_full.split("charset=")[-1].split(";")[0].strip()
                return {"final_url": current, "status": status, "body": body,
                        "content_type": ctype_full, "charset": charset,
                        "headers": headers, "redirects": chain,
                        "pinned": pinned}
            finally:
                try:
                    closer.close()
                except Exception:                      # noqa: BLE001
                    pass
        raise PolicyViolation(f"redirect limit reached for {canon}")

    # ------------------------------------------------------------- robots
    def robots_decision(self, canon: str, policy: RetrievalPolicy) -> tuple:
        """Return (allowed, status). `status` is one of ROBOTS_STATES and is
        recorded on the source, so a mission never claims robots was honoured
        when it was merely unavailable — nor claims it was *absent* when the
        request actually failed.

        Classification (v1.4.2):
            HTTP 404 ................................. absent
            parsed successfully, path allowed ........ fetched_and_honoured
            parsed successfully, path disallowed ..... disallowed_by_policy
            respect_robots=False ..................... disabled_by_configuration
            anything else — timeout, DNS/TLS/connection failure, 5xx, any
            non-404 status, redirect-policy refusal, oversized body, malformed
            or undecodable content, unsupported encoding ..... unavailable

        A failed request is never absence: "the server told us there are no
        rules" and "we could not find out" are different facts, and only the
        first is a statement about the site.
        """
        if not policy.respect_robots:
            return True, ROBOTS_DISABLED
        parts = urllib.parse.urlsplit(canon)
        root = f"{parts.scheme}://{parts.netloc}"
        cached = self._robots.get(root)
        if cached is None:
            detail = ""
            try:
                got = self._request(
                    root + "/robots.txt", policy,
                    max_bytes=policy.robots_max_bytes,
                    allowed_types=("text/plain", "text/html", "text/markdown",
                                   "application/json"),
                    accept="text/plain")
                try:
                    text = got["body"].decode(got["charset"] or "utf-8",
                                              "strict")
                except (UnicodeDecodeError, LookupError) as e:
                    # Undecodable bytes are not rules and are not absence.
                    raise RetrievalError(
                        f"robots.txt at {root} could not be decoded: {e}")
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(text.splitlines())
                cached = (parser, ROBOTS_FETCHED, "")
            except HttpStatusError as e:
                if e.status == 404:
                    # The one case that genuinely means "this site publishes no
                    # rules". Every other status is a failure to find out.
                    cached = (None, ROBOTS_ABSENT, f"HTTP 404 from {root}/robots.txt")
                else:
                    cached = (None, ROBOTS_UNAVAILABLE,
                              f"HTTP {e.status} from {root}/robots.txt")
            except PolicyViolation as e:
                # robots.txt that cannot be fetched WITHIN POLICY (redirect to
                # http, to a private address, to a denied host, oversized) is
                # not "no rules": it is unavailable, and it is recorded as such.
                cached = (None, ROBOTS_UNAVAILABLE, str(e)[:160])
            except RetrievalError as e:
                # Timeout, DNS/TLS/connection failure, malformed compressed
                # body, undecodable content — all unavailable, never absent.
                cached = (None, ROBOTS_UNAVAILABLE,
                          f"{type(e).__name__}: {str(e)[:140]}")
            self._robots[root] = cached
        parser, status, detail = cached
        if parser is None:
            if policy.require_robots:
                # require_robots refuses BOTH absent and unavailable: the
                # operator asked for rules to have been applied, and neither
                # state means they were.
                raise PolicyViolation(
                    f"robots.txt for {root} is '{status}'"
                    + (f" ({detail})" if detail else "")
                    + " and require_robots is set, so no rules could be applied")
            return True, status
        if not parser.can_fetch(policy.user_agent, canon):
            return False, ROBOTS_DISALLOWED
        return True, status

    # ------------------------------------------------------------- fetch
    def fetch(self, url: str, policy: RetrievalPolicy) -> FetchResult:
        t0 = time.time()
        canon = validate_url(url, policy)
        allowed, robots_status = self.robots_decision(canon, policy)
        if not allowed:
            raise PolicyViolation(
                f"robots.txt at {urllib.parse.urlsplit(canon).netloc} disallows "
                f"this path for {policy.user_agent.split('/')[0]}")
        got = self._request(canon, policy, max_bytes=policy.max_bytes,
                            allowed_types=policy.allowed_content_types,
                            accept=", ".join(policy.allowed_content_types))
        extracted = extract_text(got["body"], got["content_type"], got["charset"])
        return FetchResult(
            requested_url=url, canonical_url=canon, final_url=got["final_url"],
            status=got["status"], content_type=got["content_type"],
            charset=got["charset"], body=got["body"], text=extracted["text"],
            content_hash=hashlib.sha256(got["body"]).hexdigest(),
            elapsed_s=time.time() - t0, redirect_chain=got["redirects"],
            headers={k: v for k, v in got["headers"].items()
                     if k.lower() in ("content-type", "last-modified", "etag",
                                      "date")},
            provider=self.name, robots_status=robots_status,
            pinned_address=got["pinned"])


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Turn redirects into HTTPError so the caller re-validates each hop."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_provider(name: str, documents: dict | None = None) -> EvidenceProvider:
    name = (name or "fixture").lower()
    if name == "fixture":
        return FixtureProvider(documents or {})
    if name == "https":
        return HttpsProvider()
    raise PolicyViolation(f"unknown evidence provider {name!r} "
                          f"(choose fixture | https)")
