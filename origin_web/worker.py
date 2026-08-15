"""Single-writer mission worker for the controlled interactive beta."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import platform
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

from origin import lifecycle as lc

from .config import WebConfig
from .store import Store


ROOT = Path(__file__).resolve().parents[1]
SAFE_ENV_NAMES = {
    "PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE",
    "PYTHONIOENCODING", "PYTHONUNBUFFERED",
}


class WorkerError(RuntimeError):
    pass


class CancelRequested(WorkerError):
    pass


class WorkerLease:
    """OS-backed single worker lock; released automatically after a crash."""
    def __init__(self, path: Path):
        self.path = path
        self.file = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            self.file.close()
            self.file = None
            raise WorkerError("another ORIGIN beta worker holds the lease") from exc
        os.chmod(self.path, 0o600)
        self.file.seek(0)
        self.file.truncate()
        self.file.write(json.dumps({"pid": os.getpid(), "host": socket.gethostname(),
                                    "acquired_at": time.time()}))
        self.file.flush()
        os.fsync(self.file.fileno())
        return self

    def __exit__(self, *_):
        if self.file is not None:
            fcntl.flock(self.file.fileno(), fcntl.LOCK_UN)
            self.file.close()
            self.file = None


def worker_lease_healthy(path: Path) -> bool:
    """Return true only while a live worker owns the exclusive OS lease."""
    try:
        stream = path.open("r+", encoding="utf-8")
    except OSError:
        return False
    try:
        try:
            record = json.load(stream)
        except (json.JSONDecodeError, OSError, TypeError):
            return False
        try:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pass
        else:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
            return False
        pid = record.get("pid") if isinstance(record, dict) else None
        if (not isinstance(pid, int) or pid <= 0 or
                record.get("host") != socket.gethostname() or
                not isinstance(record.get("acquired_at"), (int, float))):
            return False
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    finally:
        stream.close()


def scrubbed_worker_env() -> dict[str, str]:
    """The research process never receives the API server's credentials."""
    env = {name: value for name, value in os.environ.items()
           if name in SAFE_ENV_NAMES}
    env.update({
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUNBUFFERED": "1",
        "PYTHONHASHSEED": "0",
    })
    return env


class Worker:
    def __init__(self, config: WebConfig, store: Store | None = None):
        self.config = config
        self.store = store or Store(config.db_path)
        self.worker_id = (f"{platform.node()}:{os.getpid()}:"
                          f"{int(time.time())}")

    def _mission_dir(self, mission_id: str) -> Path:
        # The store creates IDs; this assertion prevents future callers from
        # turning a queue value into a filesystem escape.
        if not (mission_id.startswith("msn_") and len(mission_id) == 20 and
                all(c in "0123456789abcdef" for c in mission_id[4:])):
            raise WorkerError("invalid mission identifier in durable queue")
        path = (self.config.runs_dir / mission_id).resolve()
        if self.config.runs_dir.resolve() not in path.parents:
            raise WorkerError("mission path escaped the configured run directory")
        return path

    @staticmethod
    def _state(path: Path) -> dict | None:
        state_path = path / "state.json"
        if not state_path.is_file():
            return None
        return json.loads(state_path.read_text(encoding="utf-8"))

    def _kill_group(self, process: subprocess.Popen) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)

    def _run_command(self, mission: dict, args: list[str], *,
                     timeout_s: float, monitor_cancel: bool = True) -> tuple[int, str]:
        mission_id = mission["id"]
        mission_dir = self._mission_dir(mission_id)
        mission_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        log_path = mission_dir / "service.log"
        started = time.monotonic()
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                args, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log,
                stderr=subprocess.STDOUT, env=scrubbed_worker_env(),
                start_new_session=True)
            while process.poll() is None:
                if time.monotonic() - started > timeout_s:
                    self._kill_group(process)
                    return 124, "service step timeout reached"
                if monitor_cancel and self.store.worker_control(mission_id) == "cancel_requested":
                    self._kill_group(process)
                    return 130, "cancel requested by beta operator"
                time.sleep(.25)
        return int(process.returncode or 0), ""

    def _init(self, mission: dict) -> None:
        mission_dir = self._mission_dir(mission["id"])
        if (mission_dir / "state.json").is_file():
            return
        command = [
            sys.executable, "-m", "origin", "init", mission["question"],
            "--dir", str(mission_dir), "--domain", mission["domain"],
            "--profile", mission["profile"], "--max-experiments", "12",
            "--compute-minutes", "10", "--max-minutes", "15",
            "--provider-calls", "0", "--brain", "none",
        ]
        code, detail = self._run_command(
            mission, command, timeout_s=30, monitor_cancel=True)
        if code == 130:
            raise CancelRequested(detail)
        if code:
            raise WorkerError(detail or f"mission initialization exited {code}")

    def _durable_cancel(self, mission: dict, reason: str) -> None:
        mission_dir = self._mission_dir(mission["id"])
        if (mission_dir / "state.json").is_file():
            self._run_command(
                mission, [sys.executable, "-m", "origin", "cancel", "--dir",
                          str(mission_dir)], timeout_s=30, monitor_cancel=False)
            state = self._state(mission_dir)
            if state:
                self.store.update_progress(mission["id"], state)
        self.store.finish(mission["id"], "cancelled", stop_reason=reason)
        self.store.audit(mission["owner_hash"], "worker_cancel", "cancelled",
                         mission["id"], reason)

    def _finalize_reports(self, mission: dict) -> None:
        mission_dir = self._mission_dir(mission["id"])
        for command_name in ("report", "html", "verify"):
            code, detail = self._run_command(
                mission, [sys.executable, "-m", "origin", command_name,
                          "--dir", str(mission_dir)],
                timeout_s=60, monitor_cancel=False)
            if code:
                raise WorkerError(detail or f"{command_name} exited {code}")

    def process(self, mission: dict) -> None:
        mission_id = mission["id"]
        mission_dir = self._mission_dir(mission_id)
        started_at = float(mission.get("started_at") or time.time())
        try:
            self._init(mission)
            while True:
                control = self.store.worker_control(mission_id)
                if control == "cancel_requested":
                    self._durable_cancel(mission, "cancelled by beta operator")
                    return
                if control == "pause_requested":
                    self.store.worker_pause(mission_id)
                    self.store.audit(mission["owner_hash"], "worker_pause",
                                     "paused", mission_id,
                                     "paused between durable controller steps")
                    return
                if time.time() - started_at > self.config.mission_timeout_s:
                    self._durable_cancel(mission,
                                         "service mission wall-time limit reached")
                    return

                command = [sys.executable, "-m", "origin", "run", "--dir",
                           str(mission_dir), "--steps", "1"]
                code, detail = self._run_command(
                    mission, command, timeout_s=self.config.step_timeout_s)
                if code == 130:
                    self._durable_cancel(mission, detail)
                    return
                if code:
                    raise WorkerError(detail or f"research step exited {code}")
                state = self._state(mission_dir)
                if state is None:
                    raise WorkerError("research step produced no durable state")
                self.store.update_progress(mission_id, state)
                phase = state.get("meta", {}).get("phase")
                if phase in lc.TERMINAL:
                    if phase == lc.COMPLETED:
                        self._finalize_reports(mission)
                        self.store.finish(
                            mission_id, "completed",
                            stop_reason=state.get("meta", {}).get("stop_reason", ""))
                        outcome = "completed"
                    elif phase == lc.CANCELLED:
                        self.store.finish(
                            mission_id, "cancelled",
                            stop_reason=state.get("meta", {}).get("stop_reason", ""))
                        outcome = "cancelled"
                    else:
                        self.store.finish(
                            mission_id, "failed",
                            error=f"research core entered terminal phase {phase}",
                            stop_reason=state.get("meta", {}).get("stop_reason", ""))
                        outcome = "failed"
                    self.store.audit(mission["owner_hash"], "worker_finish",
                                     outcome, mission_id,
                                     f"core_phase={phase}")
                    return
        except CancelRequested as exc:
            self._durable_cancel(mission, str(exc) or "cancelled by beta operator")
        except Exception as exc:  # the durable error is intentionally bounded
            detail = f"{type(exc).__name__}: {exc}"[:500]
            self.store.finish(mission_id, "failed", error=detail,
                              stop_reason="interactive worker failure")
            self.store.audit(mission["owner_hash"], "worker_finish", "failed",
                             mission_id, detail)

    def run(self, *, once: bool = False) -> int:
        # Complete controls that survived a previous worker process before
        # returning ordinary interrupted work to the queue.
        for mission in self.store.pending_control("cancel_requested"):
            self._durable_cancel(mission, "cancel request recovered after worker restart")
        for mission in self.store.pending_control("pause_requested"):
            self.store.worker_pause(mission["id"])
            self.store.audit(mission["owner_hash"], "worker_pause", "paused",
                             mission["id"], "pause recovered after worker restart")
        recovered = self.store.recover_running("exclusive worker restarted")
        if recovered:
            print(f"Recovered {recovered} interrupted mission(s) into the queue.")
        while True:
            mission = self.store.claim_next(self.worker_id)
            if mission is None:
                if once:
                    return 0
                time.sleep(self.config.worker_poll_s)
                continue
            print(f"Processing {mission['id']} ({mission['domain']}/{mission['profile']})")
            self.process(mission)
            if once:
                return 0


def run_worker(config: WebConfig | None = None, *, once: bool = False) -> int:
    config = config or WebConfig.from_env(require_tokens=False)
    config.prepare()
    store = Store(config.db_path)
    worker = Worker(config, store)
    try:
        with WorkerLease(config.data_dir / "worker.lock"):
            return worker.run(once=once)
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true",
                        help="process at most one queued mission and exit")
    parser.add_argument("--health-check", action="store_true",
                        help="exit successfully only while the worker lease is active")
    args = parser.parse_args(argv)
    if args.once and args.health_check:
        parser.error("--once and --health-check are mutually exclusive")
    if args.health_check:
        config = WebConfig.from_env(require_tokens=False)
        return 0 if worker_lease_healthy(config.data_dir / "worker.lock") else 1
    try:
        return run_worker(once=args.once)
    except WorkerError as exc:
        print(f"WORKER ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
