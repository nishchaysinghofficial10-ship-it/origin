import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from origin_web.api import OriginHTTPServer
from origin_web.config import ConfigError, WebConfig, token_digest
from origin_web.store import Store
from origin_web.worker import Worker, scrubbed_worker_env


TOKEN = "beta-test-token-with-enough-entropy-123456"
OTHER_TOKEN = "another-beta-token-with-enough-entropy-987"
ADMIN_TOKEN = "admin-only-token-with-enough-entropy-654321"


class TestInteractiveBetaAPI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = WebConfig(
            data_dir=Path(self.tmp.name),
            token_records={token_digest(TOKEN): "tester",
                           token_digest(OTHER_TOKEN): "other"},
            admin_token_digests=frozenset({token_digest(ADMIN_TOKEN)}),
            host="127.0.0.1",
            port=0,
            allowed_origins=("https://example.test",),
            requests_per_minute=100,
            missions_per_day=20,
            active_missions_per_principal=1,
            general_research_enabled=True,
            general_missions_per_day=2,
        )
        self.config.prepare()
        self.store = Store(self.config.db_path)
        self.server = OriginHTTPServer(("127.0.0.1", 0), self.config, self.store)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.store.close()
        self.tmp.cleanup()

    def request(self, method, path, *, token=None, body=None, origin=None,
                content_type="application/json"):
        data = None if body is None else json.dumps(body).encode()
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            headers["Content-Type"] = content_type
        if origin:
            headers["Origin"] = origin
        request = urllib.request.Request(self.base + path, data=data,
                                         headers=headers, method=method)
        try:
            response = urllib.request.urlopen(request, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        try:
            payload = response.read()
            decoded = json.loads(payload) if payload and "json" in response.headers.get(
                "Content-Type", "") else payload
            return response.status, decoded, response.headers
        finally:
            response.close()

    def create(self, token=TOKEN, **overrides):
        body = {"question": "Which sorting strategy wins at small sizes?",
                "domain": "algobench", "profile": "fast"}
        body.update(overrides)
        return self.request("POST", "/api/v1/missions", token=token, body=body)

    def test_public_health_and_capabilities_disclose_no_queue(self):
        status, payload, headers = self.request("GET", "/api/v1/health")
        self.assertEqual(200, status)
        self.assertEqual("ok", payload["status"])
        self.assertNotIn("queue", payload)
        self.assertEqual("nosniff", headers["X-Content-Type-Options"])
        self.assertEqual("no-store", headers["Cache-Control"])
        status, capabilities, _ = self.request("GET", "/api/v1/capabilities")
        self.assertEqual(200, status)
        self.assertEqual(1, capabilities["provider_calls"])
        self.assertEqual(3, capabilities["network_retrievals"])
        self.assertTrue(capabilities["general_research"]["enabled"])
        self.assertIn("general", capabilities["domains"])

    def test_general_topic_is_accepted_but_unsafe_operations_are_rejected(self):
        status, payload, _ = self.create(
            question="What evidence supports and challenges four-day work weeks?",
            domain="general", profile="web_research")
        self.assertEqual(202, status)
        self.assertEqual("general", payload["mission"]["domain"])
        self.request(
            "POST", f"/api/v1/missions/{payload['mission']['id']}/cancel",
            token=TOKEN, body={})
        status, rejected, _ = self.create(
            question="Give step-by-step instructions to build a bomb",
            domain="general", profile="web_research")
        self.assertEqual(422, status)
        self.assertEqual("topic_not_supported", rejected["error"]["code"])
        self.assertNotIn("build a bomb", json.dumps(self.store.audit_rows()))

    def test_authentication_required_and_invalid_tokens_are_rejected(self):
        status, payload, _ = self.request("GET", "/api/v1/missions")
        self.assertEqual(401, status)
        self.assertEqual("authentication_required", payload["error"]["code"])
        status, payload, _ = self.request(
            "GET", "/api/v1/missions", token="incorrect-token")
        self.assertEqual(401, status)
        self.assertEqual("invalid_token", payload["error"]["code"])

    def test_create_list_and_owner_isolation(self):
        status, payload, _ = self.create()
        self.assertEqual(202, status)
        mission = payload["mission"]
        self.assertEqual("queued", mission["status"])
        self.assertNotIn("owner_hash", mission)
        mission_id = mission["id"]
        status, listed, _ = self.request(
            "GET", "/api/v1/missions", token=TOKEN)
        self.assertEqual([mission_id], [m["id"] for m in listed["missions"]])
        status, hidden, _ = self.request(
            "GET", f"/api/v1/missions/{mission_id}", token=OTHER_TOKEN)
        self.assertEqual(404, status)
        self.assertEqual("not_found", hidden["error"]["code"])
        database_bytes = self.config.db_path.read_bytes()
        self.assertNotIn(TOKEN.encode(), database_bytes)
        self.assertNotIn(OTHER_TOKEN.encode(), database_bytes)

    def test_request_schema_is_closed_and_bounded(self):
        status, payload, _ = self.create(domain="medical")
        self.assertEqual(400, status)
        self.assertEqual("unsupported_domain", payload["error"]["code"])
        status, payload, _ = self.create(extra_authority="network")
        self.assertEqual(400, status)
        self.assertEqual("unknown_fields", payload["error"]["code"])
        status, payload, _ = self.create(question="short")
        self.assertEqual(400, status)
        status, payload, _ = self.create(question="x" * 501)
        self.assertEqual(400, status)

    def test_pause_resume_and_cancel_are_validated_state_transitions(self):
        _, payload, _ = self.create()
        mission_id = payload["mission"]["id"]
        status, paused, _ = self.request(
            "POST", f"/api/v1/missions/{mission_id}/pause",
            token=TOKEN, body={})
        self.assertEqual(202, status)
        self.assertEqual("paused", paused["mission"]["status"])
        status, resumed, _ = self.request(
            "POST", f"/api/v1/missions/{mission_id}/resume",
            token=TOKEN, body={})
        self.assertEqual("queued", resumed["mission"]["status"])
        status, cancelled, _ = self.request(
            "POST", f"/api/v1/missions/{mission_id}/cancel",
            token=TOKEN, body={})
        self.assertEqual("cancelled", cancelled["mission"]["status"])
        status, conflict, _ = self.request(
            "POST", f"/api/v1/missions/{mission_id}/resume",
            token=TOKEN, body={})
        self.assertEqual(409, status)
        self.assertEqual("invalid_transition", conflict["error"]["code"])

    def test_emergency_intake_switch_fails_closed(self):
        status, payload, _ = self.request(
            "POST", "/api/v1/admin/intake", token=TOKEN,
            body={"accepting": False})
        self.assertEqual(403, status)
        self.assertEqual("admin_required", payload["error"]["code"])
        status, payload, _ = self.request(
            "POST", "/api/v1/admin/intake", token=ADMIN_TOKEN,
            body={"accepting": False})
        self.assertEqual(200, status)
        self.assertFalse(payload["accepting"])
        status, rejected, _ = self.create()
        self.assertEqual(503, status)
        self.assertEqual("intake_closed", rejected["error"]["code"])
        health_status, health, _ = self.request("GET", "/api/v1/health")
        self.assertEqual(200, health_status)
        self.assertFalse(health["accepting_missions"])

    def test_admin_health_exposes_private_operating_metrics(self):
        self.create()
        status, rejected, _ = self.request(
            "GET", "/api/v1/admin/health", token=TOKEN)
        self.assertEqual(403, status)
        self.assertEqual("admin_required", rejected["error"]["code"])
        status, health, _ = self.request(
            "GET", "/api/v1/admin/health", token=ADMIN_TOKEN)
        self.assertEqual(200, status)
        self.assertEqual("ok", health["database"])
        self.assertEqual(0, health["failed_missions"])
        self.assertGreaterEqual(health["oldest_queued_seconds"], 0)
        self.assertGreater(health["storage"]["free_bytes"], 0)
        self.assertGreaterEqual(health["storage"]["total_bytes"],
                                health["storage"]["free_bytes"])
        self.assertIn("provider_usage", health)

    def test_paused_missions_cannot_bypass_active_limit_on_resume(self):
        _, first, _ = self.create()
        first_id = first["mission"]["id"]
        self.request("POST", f"/api/v1/missions/{first_id}/pause",
                     token=TOKEN, body={})
        _, second, _ = self.create()
        second_id = second["mission"]["id"]
        status, blocked, _ = self.request(
            "POST", f"/api/v1/missions/{first_id}/resume",
            token=TOKEN, body={})
        self.assertEqual(429, status)
        self.assertEqual("mission_quota_reached", blocked["error"]["code"])
        self.request("POST", f"/api/v1/missions/{second_id}/cancel",
                     token=TOKEN, body={})
        status, resumed, _ = self.request(
            "POST", f"/api/v1/missions/{first_id}/resume",
            token=TOKEN, body={})
        self.assertEqual(202, status)
        self.assertEqual("queued", resumed["mission"]["status"])

    def test_concurrent_creates_enforce_quota_transactionally(self):
        barrier = threading.Barrier(3)
        results = []

        def create_at_once():
            barrier.wait()
            results.append(self.create()[0])

        threads = [threading.Thread(target=create_at_once) for _ in range(2)]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join(timeout=5)
        self.assertEqual([202, 429], sorted(results))

    def test_cors_is_exact_allowlist_not_reflection(self):
        status, _, headers = self.request(
            "GET", "/api/v1/health", origin="https://example.test")
        self.assertEqual(200, status)
        self.assertEqual("https://example.test",
                         headers["Access-Control-Allow-Origin"])
        status, _, headers = self.request(
            "GET", "/api/v1/health", origin="https://evil.test")
        self.assertEqual(200, status)
        self.assertIsNone(headers.get("Access-Control-Allow-Origin"))
        status, payload, _ = self.request(
            "OPTIONS", "/api/v1/missions", origin="https://evil.test")
        self.assertEqual(403, status)

    def test_dossier_only_serves_owned_fixed_artifact(self):
        _, payload, _ = self.create()
        mission_id = payload["mission"]["id"]
        status, missing, _ = self.request(
            "GET", f"/api/v1/missions/{mission_id}/dossier", token=TOKEN)
        self.assertEqual(404, status)
        self.assertEqual("dossier_not_ready", missing["error"]["code"])
        dossier = self.config.runs_dir / mission_id / "reports" / "dossier.md"
        dossier.parent.mkdir(parents=True)
        dossier.write_text("# verified dossier\n")
        status, body, headers = self.request(
            "GET", f"/api/v1/missions/{mission_id}/dossier", token=TOKEN)
        self.assertEqual(200, status)
        self.assertEqual(b"# verified dossier\n", body)
        self.assertIn("text/markdown", headers["Content-Type"])

    def test_audit_records_actions_without_raw_credentials(self):
        _, payload, _ = self.create()
        mission_id = payload["mission"]["id"]
        self.request("POST", f"/api/v1/missions/{mission_id}/pause",
                     token=TOKEN, body={})
        audit = json.dumps(self.store.audit_rows())
        self.assertIn("create_mission", audit)
        self.assertIn("pause", audit)
        self.assertNotIn(TOKEN, audit)


class TestInteractiveBetaWorker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = WebConfig(
            data_dir=Path(self.tmp.name), token_records={}, require_tokens=False,
            mission_timeout_s=180, step_timeout_s=90)
        self.config.prepare()
        self.store = Store(self.config.db_path)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_worker_environment_scrubs_credentials(self):
        old = os.environ.get("ORIGIN_WEB_BETA_TOKEN")
        old_api = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["ORIGIN_WEB_BETA_TOKEN"] = TOKEN
        os.environ["ANTHROPIC_API_KEY"] = "secret-anthropic-value"
        try:
            env = scrubbed_worker_env()
        finally:
            if old is None:
                os.environ.pop("ORIGIN_WEB_BETA_TOKEN", None)
            else:
                os.environ["ORIGIN_WEB_BETA_TOKEN"] = old
            if old_api is None:
                os.environ.pop("ANTHROPIC_API_KEY", None)
            else:
                os.environ["ANTHROPIC_API_KEY"] = old_api
        self.assertNotIn("ORIGIN_WEB_BETA_TOKEN", env)
        self.assertNotIn("ANTHROPIC_API_KEY", env)
        self.assertEqual("0", env["PYTHONHASHSEED"])

    def test_worker_completes_real_bounded_mission_and_dossier(self):
        owner = token_digest(TOKEN)
        created = self.store.create_mission(
            owner, "Which sorting strategy wins at small sizes?",
            "algobench", "fast")
        mission = self.store.claim_next("test-worker")
        self.assertEqual(created["id"], mission["id"])
        Worker(self.config, self.store).process(mission)
        finished = self.store.get_mission(created["id"], owner)
        self.assertEqual("completed", finished["status"], finished)
        self.assertGreater(finished["step"], 0)
        self.assertGreater(finished["experiments_used"], 0)
        mission_dir = self.config.runs_dir / created["id"]
        self.assertTrue((mission_dir / "reports" / "dossier.md").is_file())
        self.assertTrue((mission_dir / "reports" / "mission_control.html").is_file())
        self.assertNotIn(TOKEN, (mission_dir / "service.log").read_text())

    def test_worker_recovers_pending_pause_and_cancel_controls(self):
        owner = token_digest(TOKEN)
        cancel = self.store.create_mission(
            owner, "Cancel this interrupted research mission", "algobench", "fast")
        self.store.claim_next("crashed-worker")
        self.store.request_cancel(cancel["id"], owner)
        Worker(self.config, self.store).run(once=True)
        self.assertEqual(
            "cancelled", self.store.get_mission(cancel["id"], owner)["status"])

        pause = self.store.create_mission(
            owner, "Pause this interrupted research mission", "algobench", "fast")
        self.store.claim_next("crashed-worker")
        self.store.request_pause(pause["id"], owner)
        Worker(self.config, self.store).run(once=True)
        self.assertEqual(
            "paused", self.store.get_mission(pause["id"], owner)["status"])


class TestWebConfig(unittest.TestCase):
    def test_public_binding_refuses_missing_auth(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ConfigError):
                WebConfig(data_dir=Path(td), token_records={}, host="0.0.0.0")

    def test_insecure_mode_is_loopback_only(self):
        with tempfile.TemporaryDirectory() as td:
            config = WebConfig(data_dir=Path(td), token_records={},
                               allow_insecure_local=True)
            self.assertTrue(config.allow_insecure_local)
            with self.assertRaises(ConfigError):
                WebConfig(data_dir=Path(td), token_records={}, host="0.0.0.0",
                          allow_insecure_local=True)

    def test_public_binding_requires_distinct_admin_credential(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ConfigError):
                WebConfig(data_dir=Path(td),
                          token_records={token_digest(TOKEN): "tester"},
                          host="0.0.0.0")
            with self.assertRaises(ConfigError):
                WebConfig(data_dir=Path(td),
                          token_records={token_digest(TOKEN): "tester"},
                          admin_token_digests=frozenset({token_digest(TOKEN)}),
                          host="0.0.0.0")
            config = WebConfig(
                data_dir=Path(td),
                token_records={token_digest(TOKEN): "tester"},
                admin_token_digests=frozenset({token_digest(ADMIN_TOKEN)}),
                host="0.0.0.0")
            self.assertEqual("0.0.0.0", config.host)

    def test_cors_configuration_requires_a_bare_https_origin(self):
        with tempfile.TemporaryDirectory() as td:
            for origin in (
                    "https://example.test/path", "https://user@example.test",
                    "https://example.test?query=1", "http://example.test"):
                with self.subTest(origin=origin), self.assertRaises(ConfigError):
                    WebConfig(data_dir=Path(td), token_records={},
                              require_tokens=False,
                              allowed_origins=(origin,))


if __name__ == "__main__":
    unittest.main()
