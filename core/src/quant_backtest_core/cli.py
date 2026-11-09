"""Explicit product CLI; executable configuration belongs to the trusted caller."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from quant_backtest_engine.product import loads_manifest, result_to_json

from .backends.protocol import BackendContext
from .backends.registry import get_backend
from .backends.rust import descriptor_json
from .runner import run_manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quant-backtest")
    sub = parser.add_subparsers(dest="command", required=True)
    capabilities = sub.add_parser("capabilities")
    capabilities.add_argument("backend")
    run = sub.add_parser("run-manifest")
    run.add_argument("manifest", type=Path)
    run.add_argument("--artifact-root", required=True, type=Path)
    run.add_argument("--output-root", required=True, type=Path)
    run.add_argument("--rust-executable", type=Path)
    run.add_argument("--rust-sha256")
    args = parser.parse_args(argv)
    try:
        if args.command == "capabilities":
            context = BackendContext(Path.cwd(), Path.cwd())
            print(
                json.dumps(
                    descriptor_json(get_backend(args.backend, context).descriptor()), sort_keys=True
                )
            )
        else:
            manifest = loads_manifest(args.manifest.read_text(encoding="utf-8"))
            context = BackendContext(
                args.artifact_root, args.output_root, args.rust_executable, args.rust_sha256
            )
            result = run_manifest(manifest, context=context)
            print(json.dumps(result_to_json(result), sort_keys=True))
    except (ValueError, OSError) as exc:
        print(f"quant-backtest: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
