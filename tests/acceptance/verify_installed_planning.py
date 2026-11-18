"""Installed bounded-planning closure; run with -I from outside the repository."""

import argparse
import importlib
import importlib.metadata
import importlib.util
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", action="store_true")
    args = parser.parse_args()
    assert sys.flags.isolated
    for name in ("quant_platform", "backtest_runtime", "quant_backtest_runtime", "torch", "osqp", "qlib", "ticknet"):
        assert importlib.util.find_spec(name) is None, name
    import quant_backtest_core.planning
    assert not any(name in sys.modules for name in ("pandas", "numpy", "scipy"))
    modules = ["discrete_inventory", "discrete_oracle", "sleeve_allocation"]
    if args.base:
        for name in ("pandas", "numpy", "scipy"):
            assert importlib.util.find_spec(name) is None, name
    else:
        modules += ["impact_planning", "multiperiod"]
        for name, version in {"numpy": "2.2.6", "pandas": "3.0.6", "scipy": "1.18.1"}.items():
            assert importlib.metadata.version(name) == version
    origins = {}
    for leaf in modules:
        module = importlib.import_module("quant_backtest_core.planning." + leaf)
        assert Path(module.__file__).is_relative_to(Path(sys.prefix))
        origins[leaf] = module.__file__
    from quant_backtest_core.planning.discrete_oracle import enumerate_lot_portfolios
    result = enumerate_lot_portfolios(prices=[6, 4], target_quantities=[1.5, 1.5],
        max_lots=[3, 3], lot_sizes=[1, 1], cash_budget=14, minimum_commission=1)
    assert (result.quantities, result.spent, result.objective) == ((1, 1), 12, 0.5)
    distributions = {}
    for name in ("quant-backtest-core", "quant-backtest-engine-client"):
        dist = importlib.metadata.distribution(name)
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        assert direct.get("url", "").endswith(".whl")
        assert not direct.get("dir_info", {}).get("editable", False)
        distributions[name] = {"version": dist.version, "direct_url": direct}
    assert not any(name in sys.modules for name in ("quant_platform", "backtest_runtime", "torch", "osqp"))
    print(json.dumps({"python": sys.version, "origins": origins, "distributions": distributions}, indent=2))


if __name__ == "__main__":
    main()
