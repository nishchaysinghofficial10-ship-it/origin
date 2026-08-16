#!/usr/bin/env python3
"""Build the dependency-free ORIGIN public evidence site.

The source site deliberately contains no generated research claims. This build
copies the exact, versioned flagship artifacts into the deployable directory so
the browser renders the same evidence that ships with the repository.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
DEFAULT_OUT = ROOT / "build" / "web"
SITE_URL = "https://nishchaysinghofficial10-ship-it.github.io/origin"

EVIDENCE_FILES = {
    ROOT / "examples/final_flagship_mission/EVALUATION_RESULTS.json":
        "data/EVALUATION_RESULTS.json",
    ROOT / "examples/final_flagship_mission/PREREGISTRATION.json":
        "data/PREREGISTRATION.json",
    ROOT / "examples/final_flagship_mission/origin_full/state.json":
        "data/flagship-state.json",
    ROOT / "examples/final_flagship_mission/origin_full/logs/events.jsonl":
        "data/flagship-events.jsonl",
    ROOT / "examples/final_flagship_mission/origin_full/reports/dossier.md":
        "data/flagship-dossier.md",
    ROOT / "examples/final_flagship_mission/origin_full/reports/timeline.md":
        "data/flagship-timeline.md",
}


def git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def safe_output(path: Path) -> Path:
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError("output must be a child of the repository")
    return resolved


def api_origin(api_base: str) -> str:
    value = api_base.strip().rstrip("/")
    if not value:
        return ""
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.netloc or parsed.path or
            parsed.query or parsed.fragment or parsed.username or parsed.password or
            not re.fullmatch(r"[A-Za-z0-9.-]+(?::[0-9]{1,5})?", parsed.netloc)):
        raise ValueError("beta API base must be an HTTPS origin with no path")
    return value


def build(output: Path, api_base: str = "", *, same_origin_api: bool = False) -> Path:
    output = safe_output(output)
    api_base = api_origin(api_base)
    if api_base and same_origin_api:
        raise ValueError("choose either an API origin or same-origin API mode")
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(WEB, output)
    (output / "data").mkdir(parents=True, exist_ok=True)
    for source, relative in EVIDENCE_FILES.items():
        if not source.is_file():
            raise FileNotFoundError(f"required evidence is missing: {source}")
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    runtime = ("'use strict';\n\n"
               "// Public endpoint configuration only. No token belongs here.\n"
               "window.ORIGIN_BETA = Object.freeze({apiBase: "
               + json.dumps(api_base) + ", sameOrigin: "
               + json.dumps(same_origin_api) + "});\n")
    (output / "runtime-config.js").write_text(runtime, encoding="utf-8")
    if api_base:
        index = output / "index.html"
        html = index.read_text(encoding="utf-8")
        html = html.replace("connect-src 'self'", f"connect-src 'self' {api_base}")
        index.write_text(html, encoding="utf-8")

    (output / ".nojekyll").write_text("", encoding="utf-8")
    (output / "404.html").write_text(
        (output / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
    (output / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{SITE_URL}/</loc></url>\n'
        '</urlset>\n', encoding="utf-8")
    meta = {
        "site": "ORIGIN public evidence site",
        "release": "2.1.2",
        "source_commit": git_commit(),
        "evidence_files": sorted(EVIDENCE_FILES.values()),
        "claims_source": "versioned repository artifacts",
        "interactive_beta_connected": bool(api_base or same_origin_api),
        "interactive_beta_origin": "same-origin" if same_origin_api else api_base,
    }
    (output / "build-meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--api-base", default="",
                        help="optional public HTTPS origin for the controlled beta API")
    parser.add_argument("--same-origin-api", action="store_true",
                        help="connect the site to an API served from the same origin")
    args = parser.parse_args(argv)
    built = build(args.out, args.api_base, same_origin_api=args.same_origin_api)
    print(f"Built ORIGIN website: {built}")
    print(f"Evidence files: {len(EVIDENCE_FILES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
