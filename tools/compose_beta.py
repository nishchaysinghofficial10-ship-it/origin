#!/usr/bin/env python3
"""Run ORIGIN's Compose stack while bridging private files into runtime secrets.

The three values exist in this wrapper's environment only for the lifetime of
the Docker Compose client. Compose mounts them as service-scoped files; it does
not add them to a service environment or the rendered configuration.
"""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
from pathlib import Path


class SecretBridgeError(RuntimeError):
    pass


def read_private_secret(path: Path) -> str:
    path = Path(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise SecretBridgeError(f"private secret file is unavailable: {path}") from exc
    try:
        details = os.fstat(descriptor)
        chunks: list[bytes] = []
        remaining = 4_097
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    finally:
        os.close(descriptor)
    if not stat.S_ISREG(details.st_mode):
        raise SecretBridgeError(f"private secret path is not a regular file: {path}")
    if len(raw) > 4_096:
        raise SecretBridgeError(f"private secret file is too large: {path}")
    if os.name == "posix" and stat.S_IMODE(details.st_mode) & 0o077:
        raise SecretBridgeError(f"private secret file must have mode 0600: {path}")
    try:
        value = raw.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise SecretBridgeError(f"private secret file is not UTF-8: {path}") from exc
    if not 24 <= len(value) <= 4_096 or any(character.isspace() for character in value):
        raise SecretBridgeError(f"private secret file has an invalid value: {path}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    parser.add_argument("--funnel", action="store_true",
                        help="include the loopback-only Tailscale Funnel overlay")
    parser.add_argument("--beta-token-file", type=Path,
                        default=Path("deploy/secrets/beta_token.txt"))
    parser.add_argument("--admin-token-file", type=Path,
                        default=Path("deploy/secrets/admin_token.txt"))
    parser.add_argument("--anthropic-key-file", type=Path,
                        default=Path("deploy/secrets/anthropic_api_key.txt"))
    parser.add_argument("compose_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    compose_args = args.compose_args[1:] if args.compose_args[:1] == ["--"] else args.compose_args
    if not compose_args:
        parser.error("provide Docker Compose arguments after --")
    try:
        secrets = {
            "ORIGIN_BETA_TOKEN_SECRET": read_private_secret(args.beta_token_file),
            "ORIGIN_ADMIN_TOKEN_SECRET": read_private_secret(args.admin_token_file),
            "ORIGIN_ANTHROPIC_API_KEY_SECRET": read_private_secret(args.anthropic_key_file),
        }
        command = [
            "docker", "compose", "--env-file", str(args.env_file),
            "--file", "compose.production.yaml",
        ]
        if args.funnel:
            command.extend(("--file", "compose.funnel.yaml"))
        environment = os.environ.copy()
        environment.update(secrets)
        completed = subprocess.run(command + compose_args, env=environment, check=False)
        return completed.returncode
    except (OSError, SecretBridgeError) as exc:
        print(f"COMPOSE SECRET BRIDGE FAILED: {exc}")
        return 2
    finally:
        if "secrets" in locals():
            for name in secrets:
                secrets[name] = ""


if __name__ == "__main__":
    raise SystemExit(main())
