"""Check each independently installed extra without source-tree import tricks."""

import argparse
import importlib.util
import json
import sys
from importlib import metadata
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        choices=(
            "base",
            "minute",
            "scenario",
            "planning",
            "cost",
            "microstructure",
            "daily",
            "all",
        ),
        required=True,
    )
    args = parser.parse_args()
    assert sys.flags.isolated
    for name in (
        "quant_platform",
        "quant_backtest_runtime",
        "backtest_runtime",
        "ticknet",
        "torch",
        "qlib",
        "osqp",
    ):
        assert importlib.util.find_spec(name) is None, name

    assert not any(k.startswith("quant_backtest_core") for k in sys.modules)

    assert not any(k in sys.modules for k in ("pandas", "numpy", "scipy"))
    expected = set() if args.profile == "base" else {"numpy", "pandas"}
    if args.profile in ("planning", "cost", "all"):
        expected.add("scipy")
    for name in ("numpy", "pandas", "scipy"):
        assert (importlib.util.find_spec(name) is not None) == (name in expected), (
            args.profile,
            name,
        )
    assert metadata.version("quant-backtest-core") == "0.3.0"
    distributions = {}
    for name in ("quant-backtest-core", "quant-backtest-engine-client"):
        dist = metadata.distribution(name)
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        assert direct.get("url", "").endswith(".whl") and not direct.get(
            "dir_info", {}
        ).get("editable", False)
        assert all(
            Path(str(dist.locate_file(p))).is_relative_to(Path(sys.prefix))
            for p in dist.files or ()
            if str(p).endswith(".py")
        )
        distributions[name] = {"version": dist.version, "direct_url": direct}
    if args.profile == "daily":
        from quant_backtest_core import BackendContext
        from quant_backtest_core.backends.registry import get_backend
        backend = get_backend("python.daily", BackendContext(Path("."), Path(".")))
        assert backend.descriptor().input_schemas == ("daily-input.v1",)
    print(
        json.dumps(
            {
                "profile": args.profile,
                "python": sys.version,
                "distributions": distributions,
                "numerical_packages": {n: metadata.version(n) for n in expected},
            },
            sort_keys=True,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
