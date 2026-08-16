#!/usr/bin/env python3
"""Privately save an Anthropic API key for the ORIGIN researcher container."""
from __future__ import annotations

import argparse
import getpass
import os
import stat
from pathlib import Path


class KeyConfigurationError(ValueError):
    pass


def validate_key(value: str) -> str:
    key = value.strip()
    if len(key) < 24 or any(character.isspace() for character in key):
        raise KeyConfigurationError("the API key is missing or invalid")
    return key


def save_key(path: Path, key: str) -> Path:
    path = Path(path).resolve()
    key = validate_key(key)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(key + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    path.chmod(0o600)
    if stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise KeyConfigurationError("could not enforce private key-file permissions")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path,
        default=Path("deploy/secrets/anthropic_api_key.txt"))
    args = parser.parse_args(argv)
    try:
        first = getpass.getpass("Paste Anthropic API key (input hidden): ")
        second = getpass.getpass("Paste it again to confirm: ")
        if first != second:
            raise KeyConfigurationError("the two entries did not match")
        path = save_key(args.out, first)
        first = second = ""
    except (EOFError, KeyboardInterrupt, OSError, KeyConfigurationError) as exc:
        print(f"KEY CONFIGURATION FAILED: {exc}")
        return 2
    print(f"Anthropic key stored privately at {path}")
    print("The key value was not printed. This path is excluded from Git.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
