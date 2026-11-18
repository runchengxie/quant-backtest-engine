"""Regenerate synthetic teaching evidence from exact ordinary installed wheels.

No owner checkout enters sys.path. Runtime is a historical public reference only.
Financial arithmetic remains in the preserved exporters and installed owners.
"""

import argparse
import importlib.metadata as metadata
import inspect
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile
from method_fixture_common import PLATFORM, RUNTIME, ENGINE, ROOT, digest

HELPERS = [
    "method_fixture_common",
    "method_owner_calls",
    "method_market_cases",
    "method_session_cases",
    "method_action_case",
    "method_risk_case",
]


def verify_installed(engine):
    lock = json.loads((ROOT / "docs/assets/method/owner-lock.json").read_text())
    expected = {
        "quant-backtest-core": "0.3.0",
        "quant-backtest-engine-client": "0.3.0",
        "quant-platform": "0.3.0",
        "research-contracts": "0.1.0",
        "quant-microstructure-core": "0.1.0",
        **lock["dependencies"],
    }
    records = {}
    for name, version in expected.items():
        distribution = metadata.distribution(name)
        if distribution.version != version:
            raise ValueError(f"stale provider/dependency: {name}")
        direct = distribution.read_text("direct_url.json")
        if name.startswith(("quant-", "research-")):
            if not direct:
                raise ValueError("ordinary exact-wheel install required")
            direct = json.loads(direct)
            if direct.get("dir_info"):
                raise ValueError("editable/directory owner forbidden")
            wheel = direct["url"].rsplit("/", 1)[-1]
            location = Path(unquote(urlsplit(direct["url"]).path))
            sha = digest(location.read_bytes())
            with ZipFile(location) as archive:
                for member in archive.namelist():
                    if member.endswith("/") or member.endswith("/RECORD"):
                        continue
                    installed = Path(distribution.locate_file(member))
                    if (
                        not installed.is_file()
                        or installed.read_bytes() != archive.read(member)
                    ):
                        raise ValueError(
                            "installed owner differs from registered wheel"
                        )
            if lock["wheels"].get(wheel) != sha:
                raise ValueError(f"unregistered wheel bytes: {name}")
            records[name] = {"version": version, "wheel": wheel, "sha256": sha}
        else:
            records[name] = {
                "version": version,
                "record_sha256": digest(distribution.read_text("RECORD").encode()),
            }
    if digest(engine.read_bytes()) != lock["rust_sha256"]:
        raise ValueError("unregistered Rust executable")
    return records


def export(engine, receipt=None):
    dependencies = verify_installed(engine)
    executed = set()

    def profile(frame, event, arg):
        if event == "call" and frame.f_code.co_filename.startswith(
            str(ROOT / "project_tools") + "/"
        ):
            executed.add((Path(frame.f_code.co_filename).name, frame.f_code.co_name))

    from method_market_cases import build_market_cases
    from method_session_cases import build_session_cases

    sys.setprofile(profile)
    try:
        scenes, shared = build_market_cases(engine)
        scenes.update(build_session_cases(shared))
    finally:
        sys.setprofile(None)
    for key, scene in scenes.items():
        scene["supported_controls"] = {
            "scenario_ids": [c["id"] for c in scene["scenarios"]],
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
    owners = {}
    for name, revision, repository in [
        ("engine", ENGINE, "quant-backtest-engine"),
        ("core", ENGINE, "quant-backtest-engine"),
        ("platform", PLATFORM, "quant-platform"),
        ("runtime", RUNTIME, "quant-backtest-runtime"),
    ]:
        owners[name] = {
            "revision": revision,
            "url": f"https://github.com/runchengxie/{repository}/tree/{revision}",
        }
    loaded = {}
    for name, module in list(sys.modules.items()):
        if not name.startswith(
            ("quant_backtest_core", "quant_backtest_engine", "quant_platform")
        ):
            continue
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        path = Path(filename).resolve()
        if not path.is_relative_to(Path(sys.prefix).resolve()):
            raise ValueError("owner source not from isolated installed environment")
        owner = (
            "core"
            if name.startswith("quant_backtest_core")
            else ("platform" if name.startswith("quant_platform") else "engine")
        )
        owners[owner].setdefault("source_sha256", {})[name] = digest(path.read_bytes())
        loaded[name] = {"path": str(path), "sha256": digest(path.read_bytes())}
    owners["engine"]["source_sha256"] = {
        "fixtures/roundtrip.json": digest(
            (ROOT / "fixtures/roundtrip.json").read_bytes()
        )
    }
    owners["core"]["version"] = "0.3.0"
    owners["platform"]["version"] = "0.3.0"
    owners["engine"]["version"] = "0.2.0"
    for name in ["engine", "core", "platform"]:
        owners[name]["dependency_sha256"] = digest(dependencies)
    exporter_sources = {
        "project_tools/" + name + ".py": digest(
            (ROOT / "project_tools" / (name + ".py")).read_bytes()
        )
        for name in HELPERS
    }
    result = {
        "schema": "engine-method-replay.v1",
        "owners": owners,
        "exporter_sha256": digest(Path(__file__).read_bytes()),
        "exporter_sources": exporter_sources,
        "scenes": scenes,
        "execution": {
            "dependencies": dependencies,
            "rust_sha256": digest(engine.read_bytes()),
            "executed_helpers": [
                {"file": f, "function": n} for f, n in sorted(executed)
            ],
        },
    }
    if receipt:
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps(
                {
                    "python": {
                        "path": sys.executable,
                        "sha256": digest(Path(sys.executable).resolve().read_bytes()),
                    },
                    "loaded_sources": loaded,
                    "loaded_dependency_sources": {
                        name: {
                            "path": str(Path(module.__file__).resolve()),
                            "sha256": digest(
                                Path(module.__file__).resolve().read_bytes()
                            ),
                        }
                        for name, module in list(sys.modules.items())
                        if getattr(module, "__file__", None)
                        and Path(module.__file__).is_file()
                        and Path(module.__file__)
                        .resolve()
                        .is_relative_to(Path(sys.prefix).resolve())
                    },
                    "execution": result["execution"],
                    "provider_revisions": {k: v["revision"] for k, v in owners.items()},
                },
                indent=2,
            )
            + "\n"
        )
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--engine", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--receipt", type=Path)
    a = p.parse_args()
    payload = export(a.engine.resolve(), a.receipt)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(
        json.dumps(
            payload, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
