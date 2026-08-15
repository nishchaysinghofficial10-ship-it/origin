"""Experiment confinement policy (v1.0).

Honest scope: this is the strongest *practical* confinement available in a
plain user-space POSIX environment, not a kernel-grade sandbox.

Enforced per experiment subprocess:
  - CPU-seconds hard limit (timeout + grace)      RLIMIT_CPU
  - address-space limit                           RLIMIT_AS
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


def make_preexec(timeout_s: float, policy: dict | None = None):
    if resource is None or os.name != "posix":   # pragma: no cover
        raise RuntimeError(
            "ORIGIN requires POSIX (rlimits + os.setsid) to confine experiment "
            "subprocesses. Windows is not supported; run under WSL2, Linux, or "
            "macOS. See docs/REPRODUCIBILITY.md.")
    p = {**DEFAULT_POLICY, **(policy or {})}

    def _preexec():  # runs in the child just before exec
        os.setsid()
        cpu = int(timeout_s + p["cpu_grace_s"])
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
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


def truncate_output(text: str, policy: dict | None = None) -> str:
    cap = {**DEFAULT_POLICY, **(policy or {})}["output_cap_bytes"]
    raw = text.encode("utf-8", "replace")
    if len(raw) <= cap:
        return text
    return raw[:cap].decode("utf-8", "replace") + f"\n…[truncated at {cap} bytes]"
