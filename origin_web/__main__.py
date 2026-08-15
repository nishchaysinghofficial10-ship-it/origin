"""Command line entry point for the ORIGIN beta service."""
from __future__ import annotations

import argparse

from .api import serve
from .worker import main as worker_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m origin_web")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("api", help="run the authenticated queue API")
    worker = sub.add_parser("worker", help="run the exclusive research worker")
    worker.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "api":
        serve()
        return 0
    return worker_main(["--once"] if args.once else [])


if __name__ == "__main__":
    raise SystemExit(main())
