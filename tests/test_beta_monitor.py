import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.monitor_beta import (
    MonitorError,
    _token,
    assess_remote,
    container_evidence,
    worker_lease_errors,
)


class TestBetaMonitor(unittest.TestCase):
    def health(self):
        return (
            {"status": "ok", "accepting_missions": True},
            {
                "database": "ok",
                "accepting_jobs": True,
                "queue": {"completed": 2},
                "failed_missions": 0,
                "oldest_queued_seconds": 0,
                "storage": {"free_bytes": 2_000_000_000,
                            "total_bytes": 4_000_000_000},
            },
        )

    def test_remote_thresholds_pass_and_fail_closed(self):
        public, admin = self.health()
        evidence = assess_remote(
            public, admin, max_queue_age=900, max_failed=0,
            min_free_bytes=1_000_000, require_intake_open=True)
        self.assertEqual(0, evidence["failed_missions"])
        for key, value in (
                ("failed_missions", 1), ("oldest_queued_seconds", 901)):
            broken = dict(admin)
            broken[key] = value
            with self.subTest(key=key), self.assertRaises(MonitorError):
                assess_remote(
                    public, broken, max_queue_age=900, max_failed=0,
                    min_free_bytes=1_000_000, require_intake_open=True)
        missing = dict(admin)
        missing.pop("storage")
        with self.assertRaises(MonitorError):
            assess_remote(public, missing, max_queue_age=900, max_failed=0,
                          min_free_bytes=1, require_intake_open=False)

    def test_container_and_worker_log_checks_are_bounded(self):
        inspection = json.dumps([{
            "RestartCount": 0,
            "State": {"Status": "running", "Health": {"Status": "healthy"}},
        }])

        def runner(args, **_kwargs):
            if args[1] == "inspect":
                return subprocess.CompletedProcess(args, 0, inspection, "")
            return subprocess.CompletedProcess(
                args, 0, "worker lease failed\nnormal line\n", "")

        self.assertEqual(
            {"status": "running", "health": "healthy", "restart_count": 0},
            container_evidence("worker", max_restarts=0, runner=runner))
        self.assertEqual(1, worker_lease_errors("worker", since="15m",
                                               runner=runner))
        with self.assertRaises(MonitorError):
            container_evidence("worker", max_restarts=-1, runner=runner)

    def test_admin_credential_file_requires_private_permissions(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "admin_token.txt"
            path.write_text("monitor-admin-token-with-enough-entropy")
            path.chmod(0o600)
            self.assertGreaterEqual(len(_token(path)), 24)
            path.chmod(0o644)
            with self.assertRaises(MonitorError):
                _token(path)
