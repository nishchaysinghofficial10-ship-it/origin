#!/usr/bin/env python3
"""Rewrite absolute experiment-artifact references in a stored ORIGIN project
to root-relative form (portability migration for projects written by
ORIGIN <= v1.0).

    python tools/normalize_paths.py examples/flagship_run [more projects...]

Only the `dir` fields of experiment records are touched; nothing else in the
snapshot is modified, so archived missions keep their original research
content (including legacy lifecycle phase strings used by migration tests).
Idempotent: running it twice changes nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TARGETS = ("state.json", "state.json.bak", "research_state/experiments.json")


def _rel(value: str, rec_id: str, root: Path) -> str:
    if not value:
        return f"experiments/{rec_id}"
    p = Path(value)
    if not p.is_absolute():
        return p.as_posix()
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return f"experiments/{rec_id}"


def normalize(root: Path) -> int:
    changed = 0
    for name in TARGETS:
        path = root / name
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        records = data.get("experiments", data) if isinstance(data, dict) else {}
        if not isinstance(records, dict):
            continue
        touched = False
        for rec_id, rec in records.items():
            if not isinstance(rec, dict) or "dir" not in rec:
                continue
            new = _rel(rec["dir"], rec.get("id", rec_id), root)
            if new != rec["dir"]:
                rec["dir"] = new
                touched = True
                changed += 1
        if touched:
            path.write_text(json.dumps(data, indent=2, default=str))
            print(f"  rewrote {path}")
    return changed


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    total = 0
    for arg in argv:
        root = Path(arg)
        n = normalize(root)
        total += n
        print(f"{root}: {n} artifact reference(s) made root-relative")
    return 0 if total >= 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
