"""Experiment confinement policy (v1.1).

Honest scope: this is the strongest *practical* confinement available in a
plain user-space POSIX environment, not a kernel-grade sandbox.

Enforced per experiment subprocess:
  - CPU-seconds hard limit (timeout + grace)      RLIMIT_CPU
  - memory limit                                  RLIMIT_AS (Linux) or a
                                                  fail-closed process-group
                                                  RSS watchdog (macOS)
  - max file size it may create                   RLIMIT_FSIZE
  - process/thread count                          RLIMIT_NPROC
  - core dumps disabled                           RLIMIT_CORE = 0
  - own session (killable as a group)             os.setsid
  - scrubbed environment: no secrets, no proxy vars, deterministic hash seed
  - working directory jailed to the experiment dir
  - stdout/stderr captured and truncated to a byte cap
  - wall-clock timeout (subprocess timeout=...)

NOT enforced (documented residual risk — see docs/security/SECURITY_REVIEW.md):
kernel-level network isolation and filesystem namespacing require privileges
this environment does not have. Mitigation: ORIGIN only ever executes code
generated from its own audited domain templates — never LLM-produced or
web-derived code — and the scrubbed environment carries no credentials.

Designs that exceed policy caps are REJECTED with a logged reason before any
process is spawned.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

try:
    import resource            # POSIX only
except ImportError:            # pragma: no cover - not reachable on Linux/macOS
    resource = None

DEFAULT_POLICY = {
    "max_timeout_s": 900,        # designs may not ask for more
    "cpu_grace_s": 10,
    "mem_mb": 768,
    "fsize_mb": 32,
    "nproc": 64,
    "output_cap_bytes": 256_000,
    "max_input_size": 200_000,   # domain: largest single benchmark input
    "max_trials": 25,
}


@dataclass(frozen=True)
class ConfinedProcessResult:
    """The observable result of one confined child process."""

    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    termination_reason: str = ""
    peak_rss_bytes: int = 0


def validate_design(design: dict, policy: dict | None = None) -> list[str]:
    """Return a list of policy violations ([] == safe to run)."""
    p = {**DEFAULT_POLICY, **(policy or {})}
    probs: list[str] = []
    t = design.get("timeout_s", 600)
    if not isinstance(t, (int, float)) or t <= 0:
        probs.append(f"invalid timeout_s {t!r}")
    elif t > p["max_timeout_s"]:
        probs.append(f"timeout_s {t} exceeds policy max {p['max_timeout_s']}")
    for n in design.get("sizes", []):
        if not isinstance(n, int) or n <= 0:
            probs.append(f"invalid input size {n!r}")
        elif n > p["max_input_size"]:
            probs.append(f"input size {n} exceeds policy max {p['max_input_size']}")
    tr = design.get("trials", 1)
    if not isinstance(tr, int) or tr <= 0 or tr > p["max_trials"]:
        probs.append(f"trials {tr!r} outside 1..{p['max_trials']}")
    return probs


def scrubbed_env(exp_dir: str) -> dict:
    """Minimal deterministic environment; never inherits secrets or proxies."""
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": exp_dir,
        "TMPDIR": exp_dir,
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
    }


def _platform_name(platform_name: str | None = None) -> str:
    return platform_name or sys.platform


def confinement_profile(timeout_s: float, policy: dict | None = None,
                        platform_name: str | None = None) -> dict:
    """Return the exact confinement contract used for an experiment.

    macOS exposes ``RLIMIT_AS`` as an alias of ``RLIMIT_RSS`` and rejects the
    finite hard limit ORIGIN uses on Linux.  Running without a memory boundary
    would silently weaken the threat model, so Darwin uses a parent-side RSS
    watchdog over the child's entire process group.  If that watchdog cannot
    sample the group, the child is killed (fail closed).
    """
    p = {**DEFAULT_POLICY, **(policy or {})}
    target = _platform_name(platform_name)
    memory = ({
        "mechanism": "process_group_rss_watchdog",
        "scope": "sampled resident memory for the complete child process group",
        "fail_closed": True,
    } if target == "darwin" else {
        "mechanism": "RLIMIT_AS",
        "scope": "per-process virtual address space",
        "fail_closed": True,
    })
    memory["limit_bytes"] = p["mem_mb"] * 1024 * 1024
    return {
        "policy_version": "1.1",
        "platform": target,
        "cpu_limit_seconds": int(timeout_s + p["cpu_grace_s"]),
        "wall_timeout_seconds": timeout_s,
        "memory": memory,
        "file_size_limit_bytes": p["fsize_mb"] * 1024 * 1024,
        "process_limit": p["nproc"],
        "core_dumps": False,
        "new_session": True,
        "isolated_python": True,
        "scrubbed_environment": True,
        "network_namespace": False,
        "filesystem_namespace": False,
    }


def make_preexec(timeout_s: float, policy: dict | None = None,
                 platform_name: str | None = None):
    if resource is None or os.name != "posix":   # pragma: no cover
        raise RuntimeError(
            "ORIGIN requires POSIX (rlimits + os.setsid) to confine experiment "
            "subprocesses. Windows is not supported; run under WSL2, Linux, or "
            "macOS. See docs/REPRODUCIBILITY.md.")
    p = {**DEFAULT_POLICY, **(policy or {})}
    target = _platform_name(platform_name)

    def _preexec():  # runs in the child just before exec
        cpu = int(timeout_s + p["cpu_grace_s"])
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        if target != "darwin":
            mem = p["mem_mb"] * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        fsz = p["fsize_mb"] * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_FSIZE, (fsz, fsz))
        try:
            resource.setrlimit(resource.RLIMIT_NPROC, (p["nproc"], p["nproc"]))
        except (ValueError, OSError):
            pass  # some environments forbid lowering NPROC; documented
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    return _preexec


def _darwin_process_group_rss_bytes(process_group: int) -> int | None:
    """Return total RSS for a Darwin process group, or None on monitor failure.

    ``/bin/ps`` is an OS component and is addressed by absolute path so the
    experiment's scrubbed PATH cannot redirect the monitor.  The caller treats
    every unavailable or malformed sample as a fail-closed condition.
    """
    try:
        sampled = subprocess.run(
            ["/bin/ps", "-axo", "pgid=,rss="],
            capture_output=True, text=True, timeout=2, check=False,
            env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if sampled.returncode != 0:
        return None
    total_kib = 0
    matched = False
    try:
        for line in sampled.stdout.splitlines():
            pgid_text, rss_text = line.split()
            if int(pgid_text) == process_group:
                total_kib += int(rss_text)
                matched = True
    except (TypeError, ValueError):
        return None
    return total_kib * 1024 if matched else None


def _kill_process_group(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _run_darwin_confined(args: list[str], *, cwd: str, timeout_s: float,
                          env: dict, policy: dict | None) -> ConfinedProcessResult:
    p = {**DEFAULT_POLICY, **(policy or {})}
    memory_limit = p["mem_mb"] * 1024 * 1024
    proc = subprocess.Popen(
        args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env, start_new_session=True,
        preexec_fn=make_preexec(timeout_s, policy, "darwin"),
    )
    deadline = time.monotonic() + timeout_s
    peak_rss = 0
    termination_reason = ""
    stdout = ""
    stderr = ""

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _kill_process_group(proc)
            stdout, stderr = proc.communicate()
            raise subprocess.TimeoutExpired(
                args, timeout_s, output=stdout, stderr=stderr)
        try:
            # communicate() drains both pipes while the short timeout lets the
            # parent enforce memory without risking an output-pipe deadlock.
            stdout, stderr = proc.communicate(timeout=min(0.05, remaining))
            break
        except subprocess.TimeoutExpired:
            rss = _darwin_process_group_rss_bytes(proc.pid)
            if rss is None:
                if proc.poll() is not None:
                    stdout, stderr = proc.communicate()
                    break
                termination_reason = "rss_monitor_unavailable"
                _kill_process_group(proc)
                stdout, stderr = proc.communicate()
                stderr += ("\nORIGIN confinement failed closed: unable to "
                           "sample the child process group RSS.\n")
                break
            peak_rss = max(peak_rss, rss)
            if rss > memory_limit:
                termination_reason = "memory_limit_exceeded"
                _kill_process_group(proc)
                stdout, stderr = proc.communicate()
                stderr += (
                    "\nORIGIN confinement: child process-group RSS exceeded "
                    f"{memory_limit} bytes (observed {rss} bytes).\n")
                break

    return ConfinedProcessResult(
        args=args, returncode=proc.returncode, stdout=stdout, stderr=stderr,
        termination_reason=termination_reason, peak_rss_bytes=peak_rss)


def run_confined(args: list[str], *, cwd: str, timeout_s: float, env: dict,
                  policy: dict | None = None) -> ConfinedProcessResult:
    """Run an experiment under the platform's declared confinement profile."""
    if sys.platform == "darwin":
        return _run_darwin_confined(
            args, cwd=cwd, timeout_s=timeout_s, env=env, policy=policy)

    proc = subprocess.run(
        args, cwd=cwd, capture_output=True, text=True, timeout=timeout_s,
        env=env, start_new_session=True,
        preexec_fn=make_preexec(timeout_s, policy),
    )
    return ConfinedProcessResult(
        args=args, returncode=proc.returncode, stdout=proc.stdout,
        stderr=proc.stderr)


def truncate_output(text: str, policy: dict | None = None) -> str:
    cap = {**DEFAULT_POLICY, **(policy or {})}["output_cap_bytes"]
    raw = text.encode("utf-8", "replace")
    if len(raw) <= cap:
        return text
    return raw[:cap].decode("utf-8", "replace") + f"\n…[truncated at {cap} bytes]"
