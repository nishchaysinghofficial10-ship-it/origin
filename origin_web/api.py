"""Minimal authenticated HTTP API for the controlled ORIGIN beta.

The API never imports the research controller and never runs a mission. It
validates a small fixed request schema and writes to the durable queue. A
separate worker owns all interaction with the core engine.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from . import __version__
from .config import WebConfig
from .general_research import TopicRejected, assess_topic
from .store import Conflict, IntakeClosed, NotFound, QuotaExceeded, Store


MISSION_RE = re.compile(r"^msn_[0-9a-f]{16}$")
MISSION_ROUTE_RE = re.compile(
    r"^/api/v1/missions/(?P<id>msn_[0-9a-f]{16})"
    r"(?:/(?P<action>dossier|pause|resume|cancel))?$")
ALLOWED_PROFILES = {
    "algobench": ("fast",),
    "graphbench": ("graph_fast",),
    "general": ("web_research",),
}
DEFAULT_PROFILES = {
    "algobench": "fast",
    "graphbench": "graph_fast",
    "general": "web_research",
}


class OriginHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, config: WebConfig, store: Store):
        self.config = config
        self.store = store
        super().__init__(address, OriginHandler)


class OriginHandler(BaseHTTPRequestHandler):
    server: OriginHTTPServer
    protocol_version = "HTTP/1.1"
    server_version = "ORIGIN-Beta"
    sys_version = ""

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            # ThreadingHTTPServer uses a short-lived thread per connection.
            # Close its thread-local SQLite handle rather than relying on GC.
            self.server.store.close()

    def log_message(self, fmt: str, *args) -> None:
        # Authorization and bodies are never interpolated here.
        request_id = getattr(self, "request_id", "-")
        sys.stderr.write(f"origin-web {request_id} {self.client_address[0]} "
                         f"{fmt % args}\n")

    def _origin(self) -> str:
        return self.headers.get("Origin", "").rstrip("/")

    def _common_headers(self, content_type: str, length: int) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Request-ID", self.request_id)
        origin = self._origin()
        if origin and origin in self.server.config.allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_bytes(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self._common_headers(content_type, len(body))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = (json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
                + "\n").encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8")

    def _error(self, status: int, code: str, message: str) -> None:
        self._json(status, {"error": {"code": code, "message": message},
                            "request_id": self.request_id})

    def _read_json(self) -> dict[str, Any] | None:
        if self.headers.get("Transfer-Encoding"):
            self._error(HTTPStatus.BAD_REQUEST, "unsupported_transfer_encoding",
                        "chunked request bodies are not accepted")
            return None
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            self._error(HTTPStatus.LENGTH_REQUIRED, "content_length_required",
                        "Content-Length is required")
            return None
        try:
            length = int(raw_length)
        except ValueError:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_content_length",
                        "Content-Length must be an integer")
            return None
        if length < 0 or length > self.server.config.max_body_bytes:
            self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_too_large",
                        "request body exceeds the configured limit")
            return None
        content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip()
        if content_type != "application/json":
            self._error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "json_required",
                        "Content-Type must be application/json")
            return None
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._error(HTTPStatus.BAD_REQUEST, "invalid_json",
                        "request body must be valid UTF-8 JSON")
            return None
        if not isinstance(payload, dict):
            self._error(HTTPStatus.BAD_REQUEST, "object_required",
                        "request JSON must be an object")
            return None
        return payload

    def _authenticate(self) -> tuple[str, str, bool] | None:
        config = self.server.config
        if not config.token_records and config.allow_insecure_local:
            return "local-development", "local-development", True
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            self.server.store.audit("anonymous", "authenticate", "missing")
            self._error(HTTPStatus.UNAUTHORIZED, "authentication_required",
                        "send a beta access token as a Bearer token")
            return None
        token = header[7:].strip()
        if len(token) > 512:
            token = "invalid"
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        label = None
        for expected, candidate_label in config.token_records.items():
            if hmac.compare_digest(digest, expected):
                label = candidate_label
        is_admin = any(hmac.compare_digest(digest, expected)
                       for expected in config.admin_token_digests)
        if label is None and not is_admin:
            self.server.store.audit(digest[:16], "authenticate", "invalid")
            self._error(HTTPStatus.UNAUTHORIZED, "invalid_token",
                        "the beta access token is invalid")
            return None
        allowed, remaining = self.server.store.rate_allowed(
            digest, config.requests_per_minute)
        if not allowed:
            self.server.store.audit(digest, "rate_limit", "rejected")
            self._error(HTTPStatus.TOO_MANY_REQUESTS, "rate_limited",
                        "request limit reached; retry after the next minute")
            return None
        self.rate_remaining = remaining
        return digest, label or "administrator", is_admin

    def _request_parts(self) -> tuple[str, str]:
        parsed = urlsplit(self.path)
        return parsed.path.rstrip("/") or "/", parsed.query

    def _public_health(self) -> None:
        accepting = (self.server.config.environment_accepts_jobs and
                     self.server.store.accepting_jobs())
        self._json(HTTPStatus.OK, {
            "service": "origin-interactive-beta",
            "version": __version__,
            "status": "ok",
            "accepting_missions": accepting,
            "general_research_enabled": self.server.config.general_research_enabled,
            "research_core": "2.1.2",
        })

    def _capabilities(self) -> None:
        self._json(HTTPStatus.OK, {
            "mode": "controlled-general-research-beta",
            "domains": {
                "algobench": {"profiles": ["fast"]},
                "graphbench": {"profiles": ["graph_fast"]},
                **({"general": {"profiles": ["web_research"]}}
                   if self.server.config.general_research_enabled else {}),
            },
            "provider_calls": (self.server.config.provider_calls_per_mission
                               if self.server.config.general_research_enabled else 0),
            "network_retrievals": (self.server.config.web_searches_per_mission
                                   if self.server.config.general_research_enabled else 0),
            "max_question_chars": self.server.config.max_question_chars,
            "authentication_required": True,
            "general_research": {
                "enabled": self.server.config.general_research_enabled,
                "profile": "web_research",
                "model": self.server.config.research_model,
                "missions_per_tester_per_day": self.server.config.general_missions_per_day,
                "global_paid_missions_per_day": self.server.config.provider_missions_per_day,
                "requested_max_output_tokens": (
                    self.server.config.research_max_output_tokens),
            },
            "limitations": [
                "general mode is a cited public-web synthesis, not experimental proof",
                "user-space experiment confinement inside a required container boundary",
                "no dangerous operational assistance or personalized professional advice",
                "no physical, wet-lab, human-subject, or real-world experiment execution",
            ],
        })

    def _create_mission(self, principal: str) -> None:
        config = self.server.config
        store = self.server.store
        if not config.environment_accepts_jobs or not store.accepting_jobs():
            store.audit(principal, "create_mission", "intake_closed")
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "intake_closed",
                        "new mission intake is temporarily disabled")
            return
        payload = self._read_json()
        if payload is None:
            return
        unknown = set(payload) - {"question", "domain", "profile"}
        if unknown:
            self._error(HTTPStatus.BAD_REQUEST, "unknown_fields",
                        "unsupported request fields: " + ", ".join(sorted(unknown)))
            return
        question = payload.get("question")
        domain = payload.get("domain")
        if not isinstance(question, str) or not isinstance(domain, str):
            self._error(HTTPStatus.BAD_REQUEST, "invalid_mission",
                        "question and domain are required strings")
            return
        question = " ".join(question.split())
        if not 12 <= len(question) <= config.max_question_chars:
            self._error(HTTPStatus.BAD_REQUEST, "invalid_question",
                        f"question must contain 12–{config.max_question_chars} characters")
            return
        if domain not in ALLOWED_PROFILES:
            self._error(HTTPStatus.BAD_REQUEST, "unsupported_domain",
                        "domain must be general, algobench, or graphbench")
            return
        if domain == "general" and not config.general_research_enabled:
            self._error(HTTPStatus.SERVICE_UNAVAILABLE,
                        "general_research_unavailable",
                        "general-topic research is not enabled on this deployment")
            return
        profile = payload.get("profile", DEFAULT_PROFILES[domain])
        if profile not in ALLOWED_PROFILES[domain]:
            self._error(HTTPStatus.BAD_REQUEST, "unsupported_profile",
                        f"profile must be one of: {', '.join(ALLOWED_PROFILES[domain])}")
            return
        if domain == "general":
            try:
                assess_topic(question)
            except TopicRejected as exc:
                store.audit(principal, "create_mission", "topic_rejected",
                            detail=f"category={exc.category}")
                self._error(HTTPStatus.UNPROCESSABLE_ENTITY,
                            "topic_not_supported", str(exc))
                return
        try:
            mission = store.create_mission_limited(
                principal, question, domain, profile,
                active_limit=config.active_missions_per_principal,
                daily_limit=(config.general_missions_per_day if domain == "general"
                             else config.missions_per_day),
                daily_domain=("general" if domain == "general" else None))
        except IntakeClosed as exc:
            store.audit(principal, "create_mission", "intake_closed")
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "intake_closed", str(exc))
            return
        except QuotaExceeded as exc:
            store.audit(principal, "create_mission", "quota_rejected", detail=str(exc))
            self._error(HTTPStatus.TOO_MANY_REQUESTS,
                        "mission_quota_reached", str(exc))
            return
        store.audit(principal, "create_mission", "queued", mission["id"],
                    f"domain={domain};profile={profile}")
        self._json(HTTPStatus.ACCEPTED, {"mission": mission})

    def _mission_action(self, principal: str, mission_id: str,
                        action: str | None) -> None:
        store = self.server.store
        if not MISSION_RE.fullmatch(mission_id):
            self._error(HTTPStatus.NOT_FOUND, "not_found", "mission not found")
            return
        try:
            if not action and self.command in ("GET", "HEAD"):
                self._json(HTTPStatus.OK,
                           {"mission": store.get_mission(mission_id, principal)})
                return
            if action == "dossier" and self.command in ("GET", "HEAD"):
                store.get_mission(mission_id, principal)
                dossier = (self.server.config.runs_dir / mission_id /
                           "reports" / "dossier.md")
                if not dossier.is_file():
                    self._error(HTTPStatus.NOT_FOUND, "dossier_not_ready",
                                "the mission dossier is not available yet")
                    return
                body = dossier.read_bytes()
                if len(body) > 2_000_000:
                    self._error(HTTPStatus.INTERNAL_SERVER_ERROR,
                                "artifact_limit_exceeded",
                                "the dossier exceeds the public artifact limit")
                    return
                self._send_bytes(HTTPStatus.OK, body,
                                 "text/markdown; charset=utf-8")
                store.audit(principal, "read_dossier", "ok", mission_id)
                return
            if self.command != "POST" or action not in ("pause", "resume", "cancel"):
                self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed",
                            "this mission operation is not supported")
                return
            payload = self._read_json()
            if payload is None:
                return
            if payload:
                self._error(HTTPStatus.BAD_REQUEST, "empty_object_required",
                            "this operation accepts an empty JSON object")
                return
            if action == "pause":
                mission = store.request_pause(mission_id, principal)
            elif action == "resume":
                if not self.server.config.environment_accepts_jobs or not store.accepting_jobs():
                    self._error(HTTPStatus.SERVICE_UNAVAILABLE, "intake_closed",
                                "mission execution is temporarily disabled")
                    return
                mission = store.request_resume(
                    mission_id, principal,
                    active_limit=self.server.config.active_missions_per_principal)
            else:
                mission = store.request_cancel(mission_id, principal)
            store.audit(principal, action, mission["status"], mission_id)
            self._json(HTTPStatus.ACCEPTED, {"mission": mission})
        except NotFound:
            self._error(HTTPStatus.NOT_FOUND, "not_found", "mission not found")
        except Conflict as exc:
            self._error(HTTPStatus.CONFLICT, "invalid_transition", str(exc))
        except QuotaExceeded as exc:
            self._error(HTTPStatus.TOO_MANY_REQUESTS,
                        "mission_quota_reached", str(exc))

    def _authenticated_get(self, principal: str, path: str,
                           is_admin: bool) -> None:
        if path == "/api/v1/missions":
            self._json(HTTPStatus.OK, {
                "missions": self.server.store.list_missions(principal)})
            return
        if path == "/api/v1/admin/health":
            if not is_admin:
                self._error(HTTPStatus.FORBIDDEN, "admin_required",
                            "a separate administrator credential is required")
                return
            self._json(HTTPStatus.OK, self.server.store.dump_health())
            return
        match = MISSION_ROUTE_RE.fullmatch(path)
        if match:
            self._mission_action(principal, match["id"], match["action"])
            return
        self._error(HTTPStatus.NOT_FOUND, "not_found", "endpoint not found")

    def _authenticated_post(self, principal: str, path: str,
                            is_admin: bool) -> None:
        if path == "/api/v1/missions":
            self._create_mission(principal)
            return
        if path == "/api/v1/admin/intake":
            if not is_admin:
                self._error(HTTPStatus.FORBIDDEN, "admin_required",
                            "a separate administrator credential is required")
                return
            payload = self._read_json()
            if payload is None:
                return
            if set(payload) != {"accepting"} or not isinstance(payload["accepting"], bool):
                self._error(HTTPStatus.BAD_REQUEST, "invalid_intake_setting",
                            "body must be {\"accepting\": true|false}")
                return
            self.server.store.set_accepting_jobs(payload["accepting"])
            self.server.store.audit(principal, "set_intake", "open" if
                                    payload["accepting"] else "closed")
            self._json(HTTPStatus.OK, {"accepting": payload["accepting"]})
            return
        match = MISSION_ROUTE_RE.fullmatch(path)
        if match:
            self._mission_action(principal, match["id"], match["action"])
            return
        self._error(HTTPStatus.NOT_FOUND, "not_found", "endpoint not found")

    def _dispatch(self) -> None:
        self.request_id = "req_" + secrets.token_hex(6)
        path, query = self._request_parts()
        if query:
            self._error(HTTPStatus.BAD_REQUEST, "query_not_supported",
                        "query parameters are not accepted")
            return
        if path == "/api/v1/health" and self.command in ("GET", "HEAD"):
            self._public_health()
            return
        if path == "/api/v1/capabilities" and self.command in ("GET", "HEAD"):
            self._capabilities()
            return
        authenticated = self._authenticate()
        if authenticated is None:
            return
        principal, _label, is_admin = authenticated
        if self.command in ("GET", "HEAD"):
            self._authenticated_get(principal, path, is_admin)
        elif self.command == "POST":
            self._authenticated_post(principal, path, is_admin)
        else:
            self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed",
                        "only GET, HEAD, POST and OPTIONS are supported")

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch()

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch()

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch()

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch()

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch()

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.request_id = "req_" + secrets.token_hex(6)
        origin = self._origin()
        if not origin or origin not in self.server.config.allowed_origins:
            self._error(HTTPStatus.FORBIDDEN, "origin_not_allowed",
                        "browser origin is not allowed")
            return
        self.send_response(HTTPStatus.NO_CONTENT)
        self._common_headers("text/plain; charset=utf-8", 0)
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        self.end_headers()


def serve(config: WebConfig | None = None, store: Store | None = None) -> None:
    config = config or WebConfig.from_env()
    config.prepare()
    store = store or Store(config.db_path)
    server = OriginHTTPServer((config.host, config.port), config, store)
    print(f"ORIGIN beta API listening on http://{config.host}:{server.server_port}")
    print("Mission execution is handled by a separate `python -m origin_web worker` process.")
    try:
        server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        store.close()
