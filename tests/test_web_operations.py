import io
import json
import os
import stat
import tarfile
import tempfile
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from origin_web.api import OriginHTTPServer
from origin_web.backup import (
    ARCHIVE_ROOT,
    MANIFEST_NAME,
    BackupError,
    create_backup,
    restore_backup,
    verify_backup,
)
from origin_web.config import WebConfig, token_digest
from origin_web.store import Store
from origin_web.worker import Worker, WorkerLease, worker_lease_healthy
from tools.prepare_beta_deployment import (
    PreparationError,
    main as prepare_main,
    prepare,
    validate_hostname,
    validate_site_origin,
)
from tools.verify_beta_deployment import DeploymentVerifier, VerificationError


ROOT = Path(__file__).resolve().parents[1]
TOKEN = "operations-beta-token-with-enough-entropy"
OTHER_TOKEN = "operations-other-token-with-enough-entropy"
ADMIN_TOKEN = "operations-admin-token-with-enough-entropy"


class TestBetaBackup(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        self.config = WebConfig(data_dir=self.data, token_records={},
                                require_tokens=False)
        self.config.prepare()
        self.store = Store(self.config.db_path)
        self.owner = token_digest(TOKEN)
        self.mission = self.store.create_mission(
            self.owner, "Back up this durable computational mission",
            "algobench", "fast")
        artifact = (self.config.runs_dir / self.mission["id"] /
                    "reports" / "dossier.md")
        artifact.parent.mkdir(parents=True)
        artifact.write_text("# Durable research dossier\n", encoding="utf-8")
        self.archive = self.root / "backup.tar.gz"

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_round_trip_preserves_database_and_mission_artifacts(self):
        created = create_backup(self.data, self.archive)
        verified = verify_backup(self.archive)
        self.assertEqual(created, verified)
        self.assertEqual("2.1.2", verified["research_core"])
        self.assertTrue(verified["worker_quiescence_required"])
        target = self.root / "restored"
        target.mkdir()
        self.root.chmod(0o500)
        try:
            restore_backup(self.archive, target)
        finally:
            self.root.chmod(0o700)
        restored = Store(target / "origin_web.sqlite3")
        try:
            mission = restored.get_mission(self.mission["id"], self.owner)
            self.assertEqual("queued", mission["status"])
        finally:
            restored.close()
        dossier = target / "missions" / self.mission["id"] / "reports" / "dossier.md"
        self.assertEqual("# Durable research dossier\n", dossier.read_text())
        self.assertEqual(0o600, stat.S_IMODE((target / "origin_web.sqlite3").stat().st_mode))

    def test_backup_refuses_output_inside_live_data(self):
        with self.assertRaises(BackupError):
            create_backup(self.data, self.data / "unsafe.tar.gz")

    def test_backup_refuses_mission_symlinks(self):
        target = self.root / "outside.txt"
        target.write_text("outside")
        link = self.config.runs_dir / self.mission["id"] / "link"
        try:
            link.symlink_to(target)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable")
        with self.assertRaises(BackupError):
            create_backup(self.data, self.archive)

    def test_restore_refuses_nonempty_target(self):
        create_backup(self.data, self.archive)
        target = self.root / "occupied"
        target.mkdir()
        (target / "keep.txt").write_text("do not overwrite")
        with self.assertRaises(BackupError):
            restore_backup(self.archive, target)
        self.assertEqual("do not overwrite", (target / "keep.txt").read_text())

    def test_verifier_rejects_traversal_manifest(self):
        manifest = {
            "format": "origin-beta-backup",
            "format_version": 1,
            "database": "origin_web.sqlite3",
            "files": [{"path": "../escape", "size": 1,
                       "sha256": "0" * 64}],
        }
        encoded = json.dumps(manifest).encode()
        with tarfile.open(self.archive, "w:gz") as archive:
            payload = tarfile.TarInfo(f"{ARCHIVE_ROOT}/../escape")
            payload.size = 1
            archive.addfile(payload, io.BytesIO(b"x"))
            info = tarfile.TarInfo(MANIFEST_NAME)
            info.size = len(encoded)
            archive.addfile(info, io.BytesIO(encoded))
        with self.assertRaises(BackupError):
            verify_backup(self.archive)


class TestDeploymentPreparation(unittest.TestCase):
    def test_prepare_is_secret_safe_fail_closed_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            result = prepare(
                "Beta.Example.com.", "https://site.example.com/",
                root / ".env.production", root / "secrets")
            beta = Path(result["beta_token_file"]).read_text().strip()
            admin = Path(result["admin_token_file"]).read_text().strip()
            self.assertGreaterEqual(len(beta), 24)
            self.assertGreaterEqual(len(admin), 24)
            self.assertNotEqual(beta, admin)
            self.assertEqual(
                0, stat.S_IMODE(Path(result["beta_token_file"]).stat().st_mode) & 0o077)
            env = Path(result["env_file"]).read_text()
            self.assertIn("ORIGIN_BETA_HOST=beta.example.com", env)
            self.assertIn("ORIGIN_WEB_ACCEPT_JOBS=0", env)
            self.assertNotIn(beta, env)
            repeated = prepare(
                "beta.example.com", "https://site.example.com",
                root / ".env.production", root / "secrets")
            self.assertEqual(result, repeated)
            prepare("beta.example.com", "https://site.example.com",
                    root / ".env.production", root / "secrets",
                    accept_jobs=True)
            self.assertIn("ORIGIN_WEB_ACCEPT_JOBS=1",
                          (root / ".env.production").read_text())
            with self.assertRaises(PreparationError):
                prepare("other.example.com", "https://site.example.com",
                        root / ".env.production", root / "secrets")

    def test_preparation_cli_never_prints_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = io.StringIO()
            with redirect_stdout(output):
                code = prepare_main([
                    "--host", "beta.example.com",
                    "--site-origin", "https://site.example.com",
                    "--env-file", str(root / ".env.production"),
                    "--secrets-dir", str(root / "secrets"),
                ])
            self.assertEqual(0, code)
            beta = (root / "secrets" / "beta_token.txt").read_text().strip()
            admin = (root / "secrets" / "admin_token.txt").read_text().strip()
            self.assertNotIn(beta, output.getvalue())
            self.assertNotIn(admin, output.getvalue())

    def test_host_and_origin_validation_is_strict(self):
        self.assertEqual("beta.example.com", validate_hostname("Beta.Example.com."))
        self.assertEqual("https://site.example.com",
                         validate_site_origin("https://site.example.com/"))
        for host in ("localhost", "https://beta.example.com", "1.2.3.4",
                     "beta.example.com:443", "bad_host.example.com"):
            with self.subTest(host=host), self.assertRaises(PreparationError):
                validate_hostname(host)
        for origin in ("http://site.example.com", "https://site.example.com/path",
                       "https://user@site.example.com"):
            with self.subTest(origin=origin), self.assertRaises(PreparationError):
                validate_site_origin(origin)


class TestProductionDeploymentArtifacts(unittest.TestCase):
    def test_worker_health_requires_a_live_exclusive_lease(self):
        with tempfile.TemporaryDirectory() as td:
            lease_path = Path(td) / "worker.lock"
            self.assertFalse(worker_lease_healthy(lease_path))
            with WorkerLease(lease_path):
                self.assertTrue(worker_lease_healthy(lease_path))
                self.assertEqual(0o600, stat.S_IMODE(lease_path.stat().st_mode))
            self.assertFalse(worker_lease_healthy(lease_path))

    def test_production_stack_exposes_only_tls_proxy(self):
        compose = (ROOT / "compose.production.yaml").read_text()
        proxy, api = compose.split("\n  api:\n", 1)
        api, worker = api.split("\n  worker:\n", 1)
        worker, researcher = worker.split("\n  researcher:\n", 1)
        researcher, backup = researcher.split("\n  backup:\n", 1)
        self.assertIn('caddy:2.11.4-alpine', proxy)
        self.assertIn('"80:80"', proxy)
        self.assertIn('"443:443"', proxy)
        self.assertNotIn("ports:", api)
        self.assertIn('expose: ["8080"]', api)
        self.assertIn("networks: [edge]", api)
        self.assertIn("network_mode: none", worker)
        self.assertNotIn("BETA_TOKEN", worker)
        self.assertNotIn("ANTHROPIC", worker)
        self.assertIn('origin_web.worker", "--health-check"', worker)
        self.assertNotIn("ports:", researcher)
        self.assertIn("ORIGIN_ANTHROPIC_KEY_FILE", researcher)
        self.assertIn("anthropic_api_key", researcher)
        self.assertIn('origin_web.researcher", "--health-check"', researcher)
        self.assertIn("networks: [research]", researcher)
        self.assertNotIn("networks: [edge]", researcher)
        self.assertIn("origin-beta-data:/data:ro", backup)
        self.assertIn("network_mode: none", backup)
        self.assertIn("disable: true", backup)

        funnel = (ROOT / "compose.funnel.yaml").read_text()
        self.assertIn('"127.0.0.1:${ORIGIN_FUNNEL_LOCAL_PORT:-8080}:8080"',
                      funnel)
        self.assertNotIn("0.0.0.0", funnel)
        self.assertNotIn('"8080:8080"', funnel)
        self.assertNotIn("worker:", funnel)

        dockerfile = (ROOT / "Dockerfile").read_text()
        self.assertIn("--uid 10001", dockerfile)
        self.assertIn("--gid 10001", dockerfile)

    def test_caddy_boundary_has_https_security_and_health_policy(self):
        caddy = (ROOT / "deploy" / "Caddyfile").read_text()
        for expected in (
                "{$ORIGIN_BETA_HOST}", "admin off", "Strict-Transport-Security",
                "X-Frame-Options", "max_size 16KB", "health_uri /api/v1/health",
                "reverse_proxy api:8080"):
            self.assertIn(expected, caddy)
        self.assertNotIn("tls_insecure_skip_verify", caddy)

    def test_example_environment_contains_no_secret(self):
        example = (ROOT / "deploy" / "production.env.example").read_text()
        self.assertNotIn("API_KEY", example)
        self.assertNotIn("sk-ant-", example)
        compose = (ROOT / "compose.production.yaml").read_text()
        self.assertIn("environment: ORIGIN_ANTHROPIC_API_KEY_SECRET", compose)
        self.assertNotIn("file: ./deploy/secrets/anthropic_api_key.txt", compose)
        bridge = (ROOT / "tools" / "compose_beta.py").read_text()
        self.assertNotIn("shell=True", bridge)
        self.assertNotIn("PASSWORD", example)
        self.assertIn("ORIGIN_PUBLIC_SITE_ORIGIN=https://", example)
        self.assertIn("ORIGIN_WEB_GENERAL_RESEARCH=1", example)


class TestRemoteDeploymentVerifier(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = WebConfig(
            data_dir=Path(self.tmp.name),
            token_records={token_digest(TOKEN): "tester",
                           token_digest(OTHER_TOKEN): "other"},
            admin_token_digests=frozenset({token_digest(ADMIN_TOKEN)}),
            host="127.0.0.1", port=0, requests_per_minute=500,
            missions_per_day=5, active_missions_per_principal=1,
            mission_timeout_s=180, step_timeout_s=90,
            general_research_enabled=True)
        self.config.prepare()
        self.store = Store(self.config.db_path)
        self.server = OriginHTTPServer(("127.0.0.1", 0), self.config, self.store)
        self.server_thread = threading.Thread(
            target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        self.stop_worker = threading.Event()

        def run_worker():
            try:
                worker = Worker(self.config, self.store)
                while not self.stop_worker.is_set():
                    mission = self.store.claim_next(worker.worker_id)
                    if mission is None:
                        time.sleep(.05)
                    else:
                        worker.process(mission)
            finally:
                self.store.close()

        self.worker_thread = threading.Thread(target=run_worker, daemon=True)
        self.worker_thread.start()
        self.verifier = DeploymentVerifier(
            f"http://127.0.0.1:{self.server.server_port}", TOKEN, ADMIN_TOKEN,
            other_beta_token=OTHER_TOKEN, allow_http_local=True,
            require_general=True)

    def tearDown(self):
        self.stop_worker.set()
        self.worker_thread.join(timeout=5)
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(timeout=3)
        self.store.close()
        self.tmp.cleanup()

    def test_read_only_and_mutating_acceptance_gates(self):
        evidence = self.verifier.verify_read_only()
        self.assertEqual("bounded", evidence["capabilities"])
        self.assertEqual("bounded", evidence["general_research"])
        self.assertEqual("available", evidence["monitoring"])
        self.assertEqual("closed", self.verifier.set_intake(False))
        self.assertEqual("open", self.verifier.set_intake(True))
        exercised = self.verifier.exercise(timeout=180)
        self.assertRegex(exercised["completed_mission"], r"^msn_[0-9a-f]{16}$")
        self.assertRegex(exercised["cancelled_mission"], r"^msn_[0-9a-f]{16}$")
        self.assertGreater(exercised["experiments"], 0)
        self.assertGreater(exercised["dossier_bytes"], 100)

    def test_verifier_rejects_insecure_remote_origin_and_shared_admin_token(self):
        with self.assertRaises(VerificationError):
            DeploymentVerifier("http://beta.example.com", TOKEN, ADMIN_TOKEN)
        with self.assertRaises(VerificationError):
            DeploymentVerifier("https://beta.example.com", TOKEN, TOKEN)


if __name__ == "__main__":
    unittest.main()
