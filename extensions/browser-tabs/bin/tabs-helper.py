#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from everything.atspi_runtime import run_guard  # noqa: E402
from everything.server import JsonLineServer  # noqa: E402


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Keystroke browser-tabs helper (Everything backend)")
    parser.add_argument("--json-lines", action="store_true", help="serve the versioned stdin/stdout protocol")
    parser.add_argument("--atspi-guard", type=int, metavar="PARENT_PID", help=argparse.SUPPRESS)
    parser.add_argument("--test-mode", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = arguments()
    if args.atspi_guard is not None:
        return run_guard(args.atspi_guard)
    if not args.json_lines:
        print("The browser-tabs helper must be started with --json-lines", file=sys.stderr)
        return 2
    test_mode = args.test_mode or os.environ.get("EVERYTHING_TEST_MODE") == "1"
    return asyncio.run(JsonLineServer(str(Path(__file__).resolve()), test_mode=test_mode).run())


if __name__ == "__main__":
    raise SystemExit(main())
