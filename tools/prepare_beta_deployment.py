#!/usr/bin/env python3
"""Prepare non-secret production configuration and strong local secret files."""
from __future__ import annotations

import argparse
import os
import re
import secrets
import stat
from pathlib import Path
from urllib.parse import urlsplit


HOST_RE = re.compile(
    r"(?=.{4,253}\Z)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?\Z")


class PreparationError(ValueError):
    pass


def validate_hostname(value: str) -> str:
    host = value.strip().lower().rstrip(".")
    if not HOST_RE.fullmatch(host):
        raise PreparationError(
            "beta host must be a public DNS hostname without a scheme, path, or port")
    return host


def validate_site_origin(value: str) -> str:
    origin = value.strip().rstrip("/")
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as exc:
        raise PreparationError("site origin is not a valid HTTPS origin") from exc
    if (parsed.scheme != "https" or not parsed.hostname or parsed.path or
            parsed.query or parsed.fragment or parsed.username or parsed.password or
            origin != f"https://{parsed.netloc}" or
            (port is not None and not 1 <= port <= 65_535)):
        raise PreparationError("site origin must be a bare HTTPS origin")
    return origin


def _read_secret(path: Path) -> str:
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PreparationError(f"could not read existing secret: {path}") from exc
    if len(token) < 24:
        raise PreparationError(f"existing secret is too short: {path}")
    return token


def _create_secret(path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    token = secrets.token_urlsafe(32)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return _read_secret(path)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        stream.write(token + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return token


def _secure_permissions(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise PreparationError(f"secret must not be group/world accessible: {path}")


def _atomic_configuration(path: Path, encoded: str) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prepare(host: str, site_origin: str, env_file: Path,
            secrets_dir: Path, *, accept_jobs: bool = False) -> dict[str, Path | str]:
    host = validate_hostname(host)
    site_origin = validate_site_origin(site_origin)
    env_file = Path(env_file).resolve()
    secrets_dir = Path(secrets_dir).resolve()
    beta_path = secrets_dir / "beta_token.txt"
    admin_path = secrets_dir / "admin_token.txt"
    beta = _create_secret(beta_path)
    admin = _create_secret(admin_path)
    _secure_permissions(beta_path)
    _secure_permissions(admin_path)
    if secrets.compare_digest(beta, admin):
        raise PreparationError("beta and administrator credentials must be different")

    values = {
        "ORIGIN_BETA_HOST": host,
        "ORIGIN_PUBLIC_SITE_ORIGIN": site_origin,
        "ORIGIN_WEB_ACCEPT_JOBS": "1" if accept_jobs else "0",
        "ORIGIN_DATA_VOLUME": "origin-beta-data",
        "ORIGIN_BACKUP_VOLUME": "origin-beta-backups",
        "ORIGIN_CADDY_DATA_VOLUME": "origin-beta-caddy-data",
        "ORIGIN_CADDY_CONFIG_VOLUME": "origin-beta-caddy-config",
    }
    encoded = "".join(f"{name}={value}\n" for name, value in values.items())
    if env_file.exists():
        existing = env_file.read_text(encoding="utf-8")
        if existing != encoded:
            existing_lines = dict(
                line.split("=", 1) for line in existing.splitlines()
                if line and not line.startswith("#") and "=" in line)
            expected_without_intake = {
                name: value for name, value in values.items()
                if name != "ORIGIN_WEB_ACCEPT_JOBS"}
            existing_without_intake = {
                name: value for name, value in existing_lines.items()
                if name != "ORIGIN_WEB_ACCEPT_JOBS"}
            if (existing_without_intake != expected_without_intake or
                    existing_lines.get("ORIGIN_WEB_ACCEPT_JOBS") not in ("0", "1") or
                    set(existing_lines) != set(values)):
                raise PreparationError(
                    f"refusing to overwrite different deployment configuration: {env_file}")
            _atomic_configuration(env_file, encoded)
    else:
        env_file.parent.mkdir(parents=True, exist_ok=True)
        _atomic_configuration(env_file, encoded)
    return {
        "host": host,
        "site_origin": site_origin,
        "env_file": env_file,
        "beta_token_file": beta_path,
        "admin_token_file": admin_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True,
                        help="public API hostname, for example beta.example.com")
    parser.add_argument("--site-origin", required=True,
                        help="exact browser origin allowed by CORS")
    parser.add_argument("--env-file", type=Path, default=Path(".env.production"))
    parser.add_argument("--secrets-dir", type=Path,
                        default=Path("deploy/secrets"))
    parser.add_argument(
        "--accept-jobs", action="store_true",
        help="open environment intake; use only after the live acceptance gate passes")
    args = parser.parse_args(argv)
    try:
        result = prepare(args.host, args.site_origin,
                         args.env_file, args.secrets_dir,
                         accept_jobs=args.accept_jobs)
    except PreparationError as exc:
        print(f"PREPARATION ERROR: {exc}")
        return 2
    print(f"Prepared fail-closed deployment configuration: {result['env_file']}")
    print(f"Created or verified tester secret: {result['beta_token_file']}")
    print(f"Created or verified administrator secret: {result['admin_token_file']}")
    print("Mission intake is " + ("enabled." if args.accept_jobs else
                                  "disabled until the post-deployment gate passes."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
