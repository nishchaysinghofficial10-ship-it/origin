#!/usr/bin/env python3
"""Run one paid, bounded general-research call without printing the API key."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from origin_web.general_research import (
    AnthropicResearchClient,
    GeneralResearchError,
    read_api_key,
)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument(
        "--topic",
        default="What evidence supports and challenges four-day work weeks?")
    parser.add_argument("--out", type=Path,
                        default=Path("runs/live_general_check"))
    parser.add_argument("--model", default="claude-sonnet-4-6")
    args = parser.parse_args(argv)
    try:
        key = read_api_key(args.key_file)
        client = AnthropicResearchClient(
            key, model=args.model, max_output_tokens=3_200,
            max_searches=3, timeout_s=120, max_continuations=0)
        result = client.research(" ".join(args.topic.split()))
        key = ""
        atomic_write(args.out / "dossier.md", result.dossier)
        atomic_write(
            args.out / "summary.json",
            json.dumps(result.metadata(), indent=2, sort_keys=True) + "\n")
    except (OSError, GeneralResearchError) as exc:
        print(f"LIVE GENERAL RESEARCH CHECK FAILED: {exc}")
        return 2
    print(json.dumps({
        "ok": True,
        "dossier": str((args.out / "dossier.md").resolve()),
        "model": result.model,
        "provider_calls": result.provider_calls,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "web_searches": result.web_searches,
        "sources": len(result.sources),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
