"""Exercise the opt-in L2 provider through regular installed SDK/Core packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--engine", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    assert sys.flags.isolated, "use python -I for installed-package acceptance"
    import quant_backtest_core
    import quant_backtest_engine
    from quant_backtest_core import BackendContext, run_manifest
    from quant_backtest_engine import EngineClient
    from quant_backtest_engine.product import loads_manifest

    for module in (quant_backtest_core, quant_backtest_engine):
        assert Path(module.__file__).is_relative_to(Path(sys.prefix))
    root = Path(__file__).resolve().parents[1]
    binary = a.engine.resolve()
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    request = json.loads((root / "fixtures/depth.json").read_text())
    client = EngineClient(binary, digest)
    validation = client.validate_depth(request)
    assert validation["schema_version"] == "engine_depth_validation.v1"
    manifest = loads_manifest((root / "fixtures/product/rust-depth.json").read_text())
    a.output.mkdir(parents=True, exist_ok=False)
    result = run_manifest(
        manifest,
        context=BackendContext(root / "fixtures/product", a.output, binary, digest),
    )
    assert result.status == "completed" and result.summary["final_cash"] == "9949.65"
    assert result.summary["total_commission"] == "0.05"
    native = json.loads((a.output / result.raw_result.uri).read_text())
    assert [f["price"] for f in native["account"]["fills"]] == ["10", "10.1"]
    assert (
        len({r["trade_id"] for r in native["receipts"] if r["kind"] == "filled"}) == 2
    )
    receipt = {
        "kind": "installed-native-depth-acceptance",
        "engine_sha256": digest,
        "request_sha256": validation["request_sha256"],
        "raw_sha256": result.raw_result.sha256,
        "cash": result.summary["final_cash"],
        "commission": result.summary["total_commission"],
    }
    (a.output / "acceptance.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt))


if __name__ == "__main__":
    main()
