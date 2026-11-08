"""Optional public-owner exporter; no dependency of Engine, client or docs builds.

All financial states are exported from pinned, clean public owners. The browser
only replays them. Use a separate locked owner environment for regeneration.
"""

import argparse
import inspect
import json
from pathlib import Path
import subprocess
import sys
from method_fixture_common import PLATFORM, RUNTIME, ENGINE, ROOT, digest


def owner(path, name, revision):
    actual = subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != revision:
        raise ValueError(f"{name} must be at pinned public revision {revision}")
    if subprocess.check_output(
        ["git", "-C", str(path), "diff", "HEAD", "--"], text=True
    ):
        raise ValueError(f"{name} tracked source must be clean")
    return {
        "revision": revision,
        "url": f"https://github.com/runchengxie/quant-{name}/tree/{revision}",
    }


def export(platform, runtime, engine):
    owners = {
        "platform": owner(platform, "platform", PLATFORM),
        "runtime": owner(runtime, "backtest-runtime", RUNTIME),
        "engine": {
            "revision": ENGINE,
            "url": f"https://github.com/runchengxie/quant-backtest-engine/tree/{ENGINE}",
        },
    }
    sys.path[:0] = [
        str(platform / "packages/platform/src"),
        str(platform / "packages/microstructure/src"),
    ]
    from quant_platform.backtest.impact import LinearImpact
    from quant_platform.backtest.minute_session import MinuteSession
    from quant_platform.portfolio.discrete_inventory import solve_discrete_inventory
    from ticknet.simulator.matching import MatchingEngine

    for api in [LinearImpact, MinuteSession, solve_discrete_inventory, MatchingEngine]:
        if not Path(inspect.getfile(api)).resolve().is_relative_to(platform.resolve()):
            raise ValueError("loaded owner source differs from requested checkout")
    from method_market_cases import build_market_cases
    from method_session_cases import build_session_cases

    scenes, shared_case = build_market_cases(engine)
    scenes.update(build_session_cases(shared_case))
    for key, scene in scenes.items():
        scene["supported_controls"] = {
            "scenario_ids": [case["id"] for case in scene["scenarios"]],
            "playback": ["play", "pause", "step", "reset"],
        }
        for case in scene["scenarios"]:
            case["clocks"]["event"] = {
                "book": "elapsed milliseconds",
                "impact": "elapsed seconds",
                "lots": "single decision, clock 0",
                "selection": "trial index",
            }.get(
                key,
                "UTC nanoseconds as decimal strings; risk restore uses event-boundary indices and daily cases use ISO session dates",
            )
            case["units"]["money"] = (
                "USD"
                if key == "flow"
                else ("synthetic currency units" if key == "book" else "CNY")
            )
    source_files = sorted(
        {
            source
            for scene in scenes.values()
            for s in scene["scenarios"]
            for source in s["source"]
            if source.startswith("packages/")
        }
    )
    owners["platform"]["lock_sha256"] = digest((platform / "uv.lock").read_bytes())
    owners["platform"]["source_sha256"] = {
        source: digest((platform / source).read_bytes()) for source in source_files
    }
    owners["runtime"]["source_sha256"] = {
        "docs/financial-sessions.md": digest(
            (runtime / "docs/financial-sessions.md").read_bytes()
        )
    }
    owners["engine"]["source_sha256"] = {
        "fixtures/roundtrip.json": digest(
            (ROOT / "fixtures/roundtrip.json").read_bytes()
        )
    }
    return {
        "schema": "engine-method-replay.v1",
        "owners": owners,
        "exporter_sha256": digest(Path(__file__).read_bytes()),
        "exporter_sources": {
            name: digest((ROOT / name).read_bytes())
            for name in [
                "project_tools/method_fixture_common.py",
                "project_tools/method_market_cases.py",
                "project_tools/method_session_cases.py",
                "project_tools/method_action_case.py",
                "project_tools/method_risk_case.py",
            ]
        },
        "scenes": scenes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ["platform", "runtime", "engine", "output"]:
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    payload = export(
        args.platform.resolve(), args.runtime.resolve(), args.engine.resolve()
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
