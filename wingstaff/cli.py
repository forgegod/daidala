"""Standalone Wingstaff diagnostics CLI.

The canonical operator surface will be registered under `hermes wingstaff`.
This executable remains useful for package validation and development.
"""

from __future__ import annotations

import argparse
import json

from .packs import PackError, load_pack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="wingstaff")
    sub = parser.add_subparsers(dest="command", required=True)
    packs = sub.add_parser("packs", help="Inspect workflow packs")
    packs_sub = packs.add_subparsers(dest="packs_command", required=True)
    validate = packs_sub.add_parser("validate", help="Validate a bundled pack")
    validate.add_argument("name")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "packs" and args.packs_command == "validate":
        try:
            pack = load_pack(args.name)
        except PackError as exc:
            print(json.dumps({"success": False, "error": str(exc)}))
            return 1
        print(
            json.dumps(
                {
                    "success": True,
                    "pack": pack.name,
                    "lifecycle": list(pack.lifecycle),
                    "human_gate_after": pack.human_gate_after,
                }
            )
        )
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
