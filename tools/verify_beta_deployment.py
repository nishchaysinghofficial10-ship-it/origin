#!/usr/bin/env python3
"""Verify a deployed ORIGIN beta without printing or persisting credentials."""
from __future__ import annotations

import argparse
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit


MAX_RESPONSE = 2_100_000
MISSION_RE = re.compile(r"^msn_[0-9a-f]{16}$")


class VerificationError(RuntimeError):
    pass


def _verified_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    if (context.cert_store_stats().get("x509_ca", 0) == 0 and
            Path("/etc/ssl/cert.pem").is_file()):
        context = ssl.create_default_context(cafile="/etc/ssl/cert.pem")
    return context


def _origin(value: str, *, allow_http_local: bool = False,
            allow_path: bool = False) -> str:
    value = value.strip().rstrip("/")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise VerificationError("invalid deployment URL") from exc
    local = parsed.hostname in ("127.0.0.1", "localhost", "::1")
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or
            parsed.fragment or (parsed.path and not allow_path) or
            parsed.scheme not in ({"https", "http"} if allow_http_local else {"https"}) or
            (parsed.scheme == "http" and not local) or
            (port is not None and not 1 <= port <= 65_535)):
        raise VerificationError("deployment URLs must use HTTPS (HTTP is test-loopback only)")
    return value


def _token(path: Path) -> str:
    token = Path(path).read_text(encoding="utf-8").strip()
    if len(token) < 24:
        raise VerificationError(f"credential file is missing or too short: {path}")
    return token


class DeploymentVerifier:
    def __init__(self, api_origin: str, beta_token: str, admin_token: str, *,
                 site_url: str = "", other_beta_token: str = "",
                 allow_http_local: bool = False,
                 require_general: bool = False):
        self.api = _origin(api_origin, allow_http_local=allow_http_local)
        self.site = (_origin(site_url, allow_http_local=allow_http_local,
                             allow_path=True) if site_url else "")
        self.site_origin = ""
        if self.site:
            parsed = urlsplit(self.site)
            self.site_origin = f"{parsed.scheme}://{parsed.netloc}"
        self.beta_token = beta_token
        self.admin_token = admin_token
        self.other_beta_token = other_beta_token
        self.require_general = require_general
        if len(beta_token) < 24 or len(admin_token) < 24:
            raise VerificationError("tester and administrator tokens must be at least 24 characters")
        if beta_token == admin_token:
            raise VerificationError("tester and administrator tokens must be different")
        self.context = _verified_ssl_context()

    def request(self, method: str, path: str, *, token: str = "",
                body: dict | None = None, origin: str = "") -> tuple[int, bytes, dict]:
        data = None if body is None else json.dumps(body).encode()
        headers = {"User-Agent": "ORIGIN-deployment-verifier/1"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            headers["Content-Type"] = "application/json"
        if origin:
            headers["Origin"] = origin
        request = urllib.request.Request(self.api + path, data=data,
                                         headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=15,
                                              context=self.context)
        except urllib.error.HTTPError as exc:
            response = exc
        try:
            content_length = int(response.headers.get("Content-Length", "0") or 0)
            if content_length > MAX_RESPONSE:
                raise VerificationError("deployment response exceeds the verifier limit")
            payload = response.read(MAX_RESPONSE + 1)
            if len(payload) > MAX_RESPONSE:
                raise VerificationError("deployment response exceeds the verifier limit")
            return response.status, payload, dict(response.headers.items())
        finally:
            response.close()

    @staticmethod
    def decoded(payload: bytes) -> dict:
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VerificationError("deployment returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise VerificationError("deployment JSON response is not an object")
        return value

    def verify_read_only(self) -> dict:
        evidence: dict[str, object] = {}
        status, payload, headers = self.request("GET", "/api/v1/health")
        health = self.decoded(payload)
        if status != 200 or health.get("status") != "ok":
            raise VerificationError("public health endpoint is not healthy")
        if any(name in health for name in ("queue", "database", "audit")):
            raise VerificationError("public health endpoint leaks private operational state")
        if headers.get("X-Content-Type-Options") != "nosniff":
            raise VerificationError("API security headers are missing")
        evidence["health"] = "ok"

        status, payload, _ = self.request("GET", "/api/v1/capabilities")
        capabilities = self.decoded(payload)
        provider_calls = capabilities.get("provider_calls")
        retrievals = capabilities.get("network_retrievals")
        if self.require_general:
            general = capabilities.get("general_research")
            if (status != 200 or not isinstance(provider_calls, int) or
                    not 1 <= provider_calls <= 2 or
                    not isinstance(retrievals, int) or not 1 <= retrievals <= 5 or
                    not isinstance(general, dict) or not general.get("enabled") or
                    "general" not in capabilities.get("domains", {})):
                raise VerificationError(
                    "deployed general research capability is missing or unbounded")
            evidence["general_research"] = "bounded"
        elif (status != 200 or provider_calls != 0 or retrievals != 0):
            raise VerificationError("deployed capabilities exceed the beta contract")
        evidence["capabilities"] = "bounded"

        status, _, _ = self.request("GET", "/api/v1/missions")
        if status != 401:
            raise VerificationError("unauthenticated mission listing was not rejected")
        status, _, _ = self.request("GET", "/api/v1/admin/health",
                                    token=self.beta_token)
        if status != 403:
            raise VerificationError("ordinary tester credential reached administrator state")
        status, payload, _ = self.request("GET", "/api/v1/admin/health",
                                          token=self.admin_token)
        admin = self.decoded(payload)
        if status != 200 or admin.get("database") != "ok" or "queue" not in admin:
            raise VerificationError("administrator health endpoint failed")
        storage = admin.get("storage", {})
        monitoring_values = (
            admin.get("failed_missions"),
            admin.get("oldest_queued_seconds"),
            storage.get("free_bytes") if isinstance(storage, dict) else None,
            storage.get("total_bytes") if isinstance(storage, dict) else None,
        )
        if not all(isinstance(value, int) and value >= 0
                   for value in monitoring_values):
            raise VerificationError(
                "administrator health endpoint lacks operating metrics")
        evidence["monitoring"] = "available"
        status, payload, _ = self.request("GET", "/api/v1/missions",
                                          token=self.beta_token)
        missions = self.decoded(payload)
        if status != 200 or not isinstance(missions.get("missions"), list):
            raise VerificationError("tester mission listing failed")
        evidence["authentication"] = "isolated"

        if self.site_origin:
            status, _, cors = self.request("GET", "/api/v1/health",
                                           origin=self.site_origin)
            if status != 200 or cors.get("Access-Control-Allow-Origin") != self.site_origin:
                raise VerificationError("configured public-site CORS origin is not allowed")
            _, _, rejected = self.request("GET", "/api/v1/health",
                                          origin="https://untrusted.invalid")
            if rejected.get("Access-Control-Allow-Origin"):
                raise VerificationError("API reflects an untrusted CORS origin")
            site_request = urllib.request.Request(
                self.site + "/runtime-config.js",
                headers={"User-Agent": "ORIGIN-deployment-verifier/1"})
            with urllib.request.urlopen(site_request, timeout=15,
                                        context=self.context) as response:
                runtime = response.read(100_000).decode("utf-8")
            if json.dumps(self.api) not in runtime or "Bearer " in runtime:
                raise VerificationError("public site is not safely connected to this API")
            evidence["site_connection"] = "exact-origin"
        return evidence

    def _mission(self, mission_id: str) -> dict:
        status, payload, _ = self.request(
            "GET", f"/api/v1/missions/{mission_id}", token=self.beta_token)
        value = self.decoded(payload)
        if status != 200:
            raise VerificationError(f"mission status failed with HTTP {status}")
        return value["mission"]

    def _wait(self, mission_id: str, wanted: set[str], timeout: float) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            mission = self._mission(mission_id)
            if mission["status"] in wanted:
                return mission
            if mission["status"] in {"failed", "cancelled"} - wanted:
                raise VerificationError(
                    f"mission {mission_id} entered {mission['status']}: {mission.get('error', '')}")
            time.sleep(1)
        raise VerificationError(f"mission {mission_id} did not reach {sorted(wanted)}")

    def exercise(self, timeout: float = 240) -> dict:
        status, payload, _ = self.request(
            "POST", "/api/v1/missions", token=self.beta_token,
            body={"question": "Which sorting strategy wins at small sizes?",
                  "domain": "algobench", "profile": "fast"})
        created = self.decoded(payload)
        if status != 202:
            raise VerificationError(f"mission creation failed with HTTP {status}")
        mission_id = created.get("mission", {}).get("id", "")
        if not MISSION_RE.fullmatch(mission_id):
            raise VerificationError("mission creation returned an invalid identifier")
        status, payload, _ = self.request(
            "POST", f"/api/v1/missions/{mission_id}/pause",
            token=self.beta_token, body={})
        if status != 202:
            raise VerificationError("pause request failed")
        paused = self._wait(mission_id, {"paused"}, 60)
        if paused["status"] != "paused":
            raise VerificationError("mission did not pause durably")
        status, _, _ = self.request(
            "POST", f"/api/v1/missions/{mission_id}/resume",
            token=self.beta_token, body={})
        if status != 202:
            raise VerificationError("resume request failed")
        completed = self._wait(mission_id, {"completed"}, timeout)
        status, dossier, _ = self.request(
            "GET", f"/api/v1/missions/{mission_id}/dossier",
            token=self.beta_token)
        if status != 200 or len(dossier) < 100 or b"Research Dossier" not in dossier:
            raise VerificationError("completed mission produced no valid dossier")
        if self.other_beta_token:
            status, _, _ = self.request(
                "GET", f"/api/v1/missions/{mission_id}",
                token=self.other_beta_token)
            if status != 404:
                raise VerificationError("a second tester could read the first tester's mission")

        status, payload, _ = self.request(
            "POST", "/api/v1/missions", token=self.beta_token,
            body={"question": "Cancel this bounded deployment acceptance mission",
                  "domain": "algobench", "profile": "fast"})
        cancellation = self.decoded(payload)
        if status != 202:
            raise VerificationError("cancellation acceptance mission could not be created")
        cancel_id = cancellation["mission"]["id"]
        status, _, _ = self.request(
            "POST", f"/api/v1/missions/{cancel_id}/cancel",
            token=self.beta_token, body={})
        if status != 202:
            raise VerificationError("cancel request failed")
        self._wait(cancel_id, {"cancelled"}, 60)
        return {
            "completed_mission": mission_id,
            "cancelled_mission": cancel_id,
            "experiments": completed.get("experiments_used", 0),
            "dossier_bytes": len(dossier),
        }

    def set_intake(self, accepting: bool) -> str:
        status, payload, _ = self.request(
            "POST", "/api/v1/admin/intake", token=self.admin_token,
            body={"accepting": accepting})
        value = self.decoded(payload)
        if status != 200 or value.get("accepting") is not accepting:
            raise VerificationError("administrator intake control failed")
        return "open" if accepting else "closed"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-origin", required=True)
    parser.add_argument("--site-url", default="")
    parser.add_argument("--beta-token-file", type=Path, required=True)
    parser.add_argument("--admin-token-file", type=Path, required=True)
    parser.add_argument("--other-beta-token-file", type=Path)
    parser.add_argument("--exercise", action="store_true",
                        help="create, pause/resume, complete, and cancel real missions")
    parser.add_argument("--intake", choices=("open", "closed"),
                        help="set durable intake using the administrator credential")
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--allow-http-local", action="store_true",
                        help=argparse.SUPPRESS)
    parser.add_argument("--require-general", action="store_true",
                        help="require bounded, enabled general public-web research")
    args = parser.parse_args(argv)
    try:
        verifier = DeploymentVerifier(
            args.api_origin, _token(args.beta_token_file),
            _token(args.admin_token_file), site_url=args.site_url,
            other_beta_token=(_token(args.other_beta_token_file)
                              if args.other_beta_token_file else ""),
            allow_http_local=args.allow_http_local,
            require_general=args.require_general)
        evidence = verifier.verify_read_only()
        if args.intake:
            evidence["intake"] = verifier.set_intake(args.intake == "open")
        if args.exercise:
            evidence["exercise"] = verifier.exercise(args.timeout)
    except (OSError, urllib.error.URLError, VerificationError) as exc:
        print(f"DEPLOYMENT VERIFICATION FAILED: {exc}")
        return 2
    print(json.dumps({"ok": True, "evidence": evidence}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
