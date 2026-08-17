"""Local verification and Cloud worker commands."""

from __future__ import annotations

import argparse


def main() -> int:
    parser = argparse.ArgumentParser(prog="khalinos")
    parser.add_argument("command", choices=["serve", "worker"])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    args = parser.parse_args()
    if args.command == "worker":
        from khalinos.worker import main as worker_main
        return worker_main()
    import uvicorn
    uvicorn.run("khalinos.api:app", host=args.host, port=args.port)
    return 0

