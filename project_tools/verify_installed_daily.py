"""Verify installed daily leaf closure without Platform or future runner imports."""
import ast
import importlib
import importlib.metadata
import importlib.util
import inspect
import json
import sys
import typing
from pathlib import Path

def main():
    assert sys.flags.isolated
    forbidden = ("quant_platform", "quant_backtest_runtime", "backtest_runtime",
                 "portfolio_backtester", "research_contracts", "rqdatac", "qlib",
                 "torch", "ticknet", "scipy")
    for name in forbidden:
        assert importlib.util.find_spec(name) is None, name
    package = importlib.import_module("quant_backtest_core.daily")
    importlib.import_module("quant_backtest_core.daily.execution_sim")
    assert not any(name in sys.modules for name in ("numpy", "pandas"))
    config = importlib.import_module("quant_backtest_core.daily.execution_sim.config")
    assert "pandas" not in sys.modules
    assert config.ExecutionSimConfig.__module__ == config.__name__
    origins = {}
    for leaf in ("contracts", "calendar", "summary", "execution_sim.config"):
        module = importlib.import_module("quant_backtest_core.daily." + leaf)
        origin = Path(module.__file__)
        assert origin.is_relative_to(Path(sys.prefix)), origin
        origins[leaf] = str(origin)
        for value in vars(module).values():
            if (inspect.isclass(value) or inspect.isfunction(value)) and value.__module__ == module.__name__:
                typing.get_type_hints(value)
                if inspect.isclass(value):
                    for member in vars(value).values():
                        if isinstance(member, (classmethod, staticmethod)):
                            member = member.__func__
                        if isinstance(member, property):
                            member = member.fget
                        if inspect.isfunction(member):
                            typing.get_type_hints(member)
    for source in Path(package.__file__).parent.rglob("*.py"):
        for node in ast.walk(ast.parse(source.read_text())):
            names = ([node.module or ""] if isinstance(node, ast.ImportFrom) else
                     [item.name for item in node.names] if isinstance(node, ast.Import) else [])
            assert not any(name.split(".")[0] in forbidden for name in names), source
            assert not any("runner" in name or "reporting" in name for name in names), source
    assert not any(name in sys.modules for name in forbidden)
    distributions = {}
    for name in ("quant-backtest-core", "quant-backtest-engine-client"):
        dist = importlib.metadata.distribution(name)
        direct = json.loads(dist.read_text("direct_url.json") or "{}")
        assert direct.get("url", "").endswith(".whl")
        assert not direct.get("dir_info", {}).get("editable", False)
        distributions[name] = {"version": dist.version, "direct_url": direct}
    print(json.dumps({"python": sys.version, "origins": origins, "distributions": distributions}, indent=2))

if __name__ == "__main__":
    main()
