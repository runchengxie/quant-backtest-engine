"""Verify regular-wheel ownership and optional simulator dependencies under python -I."""
from __future__ import annotations

import argparse
import importlib.metadata as metadata
import importlib.util
import json
from pathlib import Path
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native", choices=("absent", "present"), required=True)
    args = parser.parse_args()
    assert sys.flags.isolated, "run with python -I"
    for name in ("ticknet", "torch", "quant_platform", "backtest_runtime", "sklearn"):
        assert importlib.util.find_spec(name) is None, name
    assert (importlib.util.find_spec("_microstructure_rs") is not None) == (args.native == "present")
    import quant_backtest_core
    assert "quant_backtest_core.microstructure" not in sys.modules
    from quant_backtest_core.microstructure.matching import MatchingEngine
    from quant_backtest_core.microstructure.ordering import sort_simulator_events
    from quant_backtest_core.microstructure import correctness, pack, replay
    assert all((correctness, pack, replay))
    owners = {"quant-backtest-core": "quant_backtest_core",
              "quant-backtest-engine-client": "quant_backtest_engine"}
    if args.native == "present":
        owners["quant-microstructure-core"] = "_microstructure_rs"
    seen: set[str] = set()
    receipts = {}
    for name, namespace in owners.items():
        dist = metadata.distribution(name)
        direct = dist.read_text("direct_url.json")
        assert not direct or not json.loads(direct).get("dir_info", {}).get("editable", False)
        files = [str(f) for f in dist.files or []]
        owned = [f for f in files if f.endswith((".py", ".pyi", ".so"))]
        assert owned and all(f.startswith(namespace + "/") or f.startswith(namespace + ".") for f in owned), owned
        assert not seen.intersection(owned)
        seen.update(owned)
        if name == "quant-microstructure-core":
            assert any("LICENSE" in f for f in files)
            assert any("THIRD_PARTY_NOTICES" in f for f in files)
        receipts[name] = {"version": dist.version, "root": str(dist.locate_file("")), "files": owned}
    assert Path(quant_backtest_core.__file__).is_relative_to(Path(sys.prefix))
    engine = MatchingEngine(backend="python")
    engine.apply_order("bid", 1, 100, 10)
    assert engine.lob.best_bid() == (100, 10)
    if args.native == "absent":
        for call in (lambda: MatchingEngine(backend="rust"),
                     lambda: sort_simulator_events([], backend="rust")):
            try:
                call()
            except ImportError:
                pass
            else:
                raise AssertionError("missing native silently fell back")
    else:
        assert MatchingEngine(backend="rust").lob.best_bid() is None
    print(json.dumps(receipts, indent=2))


if __name__ == "__main__":
    main()
