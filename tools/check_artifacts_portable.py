#!/usr/bin/env python3
"""Fail if any distributable artifact embeds a machine-specific absolute path.

    python tools/check_artifacts_portable.py .

Scans text artifacts (.json, .jsonl, .md, .html, .py, .toml, .yml) for
absolute filesystem paths that would only resolve on the machine that produced
them. Used by CI and by tests/test_portability.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SUFFIXES = {".json", ".jsonl", ".md", ".html", ".py", ".toml", ".yml", ".yaml"}
SKIP_DIRS = {".git", "__pycache__", ".venv", "node_modules"}
# Absolute paths that identify a particular machine/checkout.
PATTERNS = [
    re.compile(r"/home/[A-Za-z0-9._-]+/"),
    re.compile(r"/Users/[A-Za-z0-9._-]+/"),
    re.compile(r"/root/[A-Za-z0-9._-]+/"),
    re.compile(r"[A-Za-z]:\\\\Users\\\\"),
]
# Hand-written documentation may legitimately quote a machine path (e.g. the
# verification report reproduces the defect it describes). GENERATED markdown
# artifacts — dossiers, timelines, anything under examples/ or a reports/
# directory — are held to the same standard as JSON/HTML state.
DOC_SUFFIXES = {".md"}
DOC_ROOTS = ("docs",)
DOC_STEMS = {"README", "SPECIFICATION", "ROADMAP", "CHANGELOG", "CONTRIBUTING"}
# Source lines that deliberately contain a synthetic foreign path (e.g. a test
# fixture proving such paths are migrated) opt out with this marker.
ALLOW = "portability-allow"


def _is_handwritten_doc(path: Path, base: Path) -> bool:
    try:
        rel = path.resolve().relative_to(base.resolve())
    except ValueError:
        rel = path
    if rel.parts and rel.parts[0] in DOC_ROOTS:
        return True
    return len(rel.parts) == 1 and rel.stem in DOC_STEMS


def scan(base: Path) -> list[str]:
    hits: list[str] = []
    for path in sorted(base.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        if path.suffix.lower() in DOC_SUFFIXES and _is_handwritten_doc(path, base):
            continue
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for pat in PATTERNS:
            for m in pat.finditer(text):
                idx = text[: m.start()].count("\n")
                if ALLOW in lines[idx]:
                    continue
                hits.append(f"{path}:{idx + 1}: {m.group(0)}…")
    return hits


def main(argv: list[str]) -> int:
    base = Path(argv[0] if argv else ".")
    hits = scan(base)
    if hits:
        print(f"PORTABILITY FAIL: {len(hits)} absolute path reference(s) in "
              f"artifacts under {base}:")
        for h in hits[:40]:
            print("  -", h)
        return 1
    print(f"PORTABILITY OK: no machine-specific absolute paths in artifacts "
          f"under {base}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
