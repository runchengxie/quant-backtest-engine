"""Run with an isolated Python (-I); never adds a checkout to sys.path."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("sdk", "base", "rust", "minute"), required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--rust-executable", type=Path)
    parser.add_argument("--rust-sha256")
    args = parser.parse_args()
    assert sys.flags.isolated, "use python -I for installed acceptance"
    forbidden = (
        "pandas",
        "numpy",
        "scipy",
        "torch",
        "qlib",
        "osqp",
        "quant_platform",
        "backtest_runtime",
    )
    if args.mode == "minute":
        forbidden = tuple(name for name in forbidden if name not in {"pandas", "numpy"})
    for module in forbidden:
        assert importlib.util.find_spec(module) is None, f"unexpected optional dependency: {module}"
    import quant_backtest_engine
    import quant_backtest_engine.product

    assert not any(name.startswith("quant_backtest_core") for name in sys.modules)
    packages = ["quant-backtest-engine-client"]
    if args.mode != "sdk":
        import quant_backtest_core

        packages.append("quant-backtest-core")
        assert Path(quant_backtest_core.__file__).is_relative_to(Path(sys.prefix))
    else:
        assert importlib.util.find_spec("quant_backtest_core") is None
    assert Path(quant_backtest_engine.__file__).is_relative_to(Path(sys.prefix))
    for package in packages:
        distribution = importlib.metadata.distribution(package)
        direct = json.loads(distribution.read_text("direct_url.json") or "{}")
        assert not direct.get("dir_info", {}).get("editable", False)
        assert direct.get("url", "").endswith(".whl"), "acceptance requires independent wheels"
    if args.mode != "sdk":
        import quant_backtest_core.sessions
        import quant_backtest_core.scenarios
        assert "pandas" not in sys.modules, "session protocol must stay lazy"
        sdk_files = {str(f) for f in importlib.metadata.files(packages[0]) or ()}
        core_files = {str(f) for f in importlib.metadata.files(packages[1]) or ()}
        assert not sdk_files.intersection(core_files), "wheel namespaces overlap"
    if args.mode == "minute":
        assert args.manifest and args.artifact_root and args.output_root
        from quant_backtest_engine.product import loads_manifest, result_to_json
        from quant_backtest_core import BackendContext
        from quant_backtest_core.sessions import open_session, restore_session
        manifest = loads_manifest(args.manifest.read_text())
        def context(name):
            return BackendContext(args.artifact_root, args.output_root / name)
        expected = result_to_json(open_session(manifest, context=context("reference")).finish())
        session = open_session(manifest, context=context("boundaries"))
        checkpoints = [session.checkpoint()]
        while session.step() is not None:
            checkpoints.append(session.checkpoint())
        assert len(checkpoints) > 10
        for index, checkpoint in enumerate(checkpoints):
            restored = restore_session(manifest, checkpoint, context=context(str(index)))
            assert restored.checkpoint() == checkpoint
            result = restored.finish()
            assert result_to_json(result) == expected
            assert restored.finish() is result
        print(json.dumps({"every_boundary_restore":len(checkpoints), "complete_payload":"equal"}))
    if args.mode == "rust":
        assert all(
            (
                args.manifest,
                args.artifact_root,
                args.output_root,
                args.rust_executable,
                args.rust_sha256,
            )
        )
        from quant_backtest_engine.product import loads_manifest

        from quant_backtest_core import BackendContext, run_manifest

        result = run_manifest(
            loads_manifest(args.manifest.read_text()),
            context=BackendContext(
                args.artifact_root, args.output_root, args.rust_executable, args.rust_sha256
            ),
        )
        assert result.summary["final_cash"] == result.summary["final_nav"] == "10197.8"
        assert result.raw_result is not None
        raw = (args.output_root / result.raw_result.uri).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == result.normalization.source_sha256
    print(
        json.dumps(
            {
                "mode": args.mode,
                "python": sys.version.split()[0],
                "distributions": {p: importlib.metadata.version(p) for p in packages},
                "optional_dependencies": "minute only" if args.mode == "minute" else "absent",
                "result": "passed",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
