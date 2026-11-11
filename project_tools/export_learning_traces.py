"""Exact projection of public evidence; never execute financial calculations.

Producer correspondence below is audited against the retained PR19 exporter
(4820af3). New producer paths require an explicit mapping and mutation tests.
"""

from __future__ import annotations
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

PRESETS = {
    "flow": ["roundtrip"],
    "book": ["depth"],
    "impact": ["small", "large", "nondecaying", "close"],
    "cost": ["once"],
    "lots": ["no-minimum", "minimum", "grid"],
    "paths": ["thin", "deep", "market-up", "feedback"],
    "selection": ["null-search"],
    "risk": ["recovery", "shared", "residual", "actions", "risk-full", "risk-missing"],
}
TABLES = [
    "result",
    "grid",
    "fills",
    "orders",
    "allocation",
    "external_orders",
    "exit_wealth",
    "decision_reports",
    "capital_flow_ledger",
    "valuation_ledger",
    "summary",
    "cohorts",
    "truth",
]
MISSING = "provenance.named_run_binding_not_recorded"
STATIC = "provenance.supplied_metadata"
API_OWNER = {"risk_audit": "platform", "null_scenario": "platform"}


def token(value):
    return str(value).replace("~", "~0").replace("/", "~1")


def pointer(root, path):
    for bit in path.split("/")[1:]:
        bit = bit.replace("~1", "/").replace("~0", "~")
        root = root[int(bit)] if isinstance(root, list) else root[bit]
    return root


def safe(value):
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        raise ValueError("unexpected float in exact owner fixture")
    if isinstance(value, list):
        return [safe(x) for x in value]
    if isinstance(value, dict):
        return {k: safe(v) for k, v in value.items()}
    raise ValueError("unsupported projection value")


def leaves(value, path=""):
    if isinstance(value, dict):
        for k, v in value.items():
            yield from leaves(v, path + "/" + token(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from leaves(v, path + "/" + str(i))
    else:
        yield path, value


def source_record(path, names, reason=None):
    return {
        "source_pointer": path,
        "run_names": sorted(names),
        "run_binding_status": "available"
        if names
        else (
            "unavailable"
            if reason in {MISSING, "provenance.owner_value_pending"}
            else "not_applicable"
        ),
        "reason_key": None if names else (reason or STATIC),
    }


def producers(scene, preset, case, section, path):
    """Return actual contributing calls; constants do not acquire false producers."""
    bits = path.strip("/").split("/")
    field = bits[-1]
    i = int(bits[0]) if bits and bits[0].isdigit() else 0
    if scene == "flow":
        return (
            ([], STATIC)
            if section == "states" and (i == 0 or field in {"phase", "clock"})
            else ([], MISSING)
        )
    if section == "states":
        if field in {"phase", "clock", "trial"}:
            return [], STATIC
        if scene == "book":
            return (
                ([], STATIC)
                if i == 0 or (field == "reported" and i < 3)
                else (["matcher"], None)
            )
        if scene == "impact":
            return (
                ([], STATIC)
                if field in {"quantity", "unaffected"}
                else (["model"], None)
            )
        if scene == "cost" or (scene == "risk" and preset == "shared"):
            return ([], STATIC) if i == 0 else (["execution"], None)
        if scene == "lots":
            return ["planning"], None
        if scene == "paths":
            return ([], STATIC) if field == "price" else (["execution"], None)
        if scene == "selection":
            return ["generator"], None
        if preset == "recovery":
            return ["session"], None
        if preset == "residual":
            if field == "cash_realized_wealth" and i < len(case["states"]) - 1:
                return [], "provenance.owner_value_pending"
            return (
                (["session", "wealth"], None)
                if field in {"wealth", "cash_realized_wealth"}
                and i == len(case["states"]) - 1
                else (["session"], None)
            )
        if preset == "actions":
            if field == "capital_flow" or (
                i == 3 and field in {"cash_right", "stock_right"}
            ):
                return [], STATIC
            return ["baseline" if i < 3 else "continuation"], None
        if preset.startswith("risk-"):
            return ["audit"], None
    if section == "grid":
        if field == "shares":
            return [], STATIC
        return ["grid-" + case["grid"][i]["shares"].replace(",", "-")], None
    if section == "external_orders":
        return ["netting"], None
    if section == "allocation":
        if bits[0] == "deltas":
            if field in {"sleeve", "symbol", "internal_quantity"}:
                return ["allocation", "netting"], None
            return ["allocation", "execution", "netting"], None
        if bits[0] == "fills" and field in {"fill_id", "symbol", "side"}:
            return [], STATIC
        if bits[0] == "pooled_quantities" and field == "0":
            return ["allocation"], None
        return ["allocation", "execution"], None
    if section == "exit_wealth":
        return ["session", "wealth"], None
    if section in {"capital_flow_ledger", "valuation_ledger"}:
        return ["continuation"], None
    if section == "decision_reports":
        return ["session"], None
    if section in {"summary", "cohorts"}:
        return ["audit"], None
    if section == "truth":
        return ["generator"], None
    if section in {"fills", "orders"}:
        return ["session" if preset == "residual" else "execution"], None
    raise ValueError(f"unmapped producer: {scene}/{preset}/{section}{path}")


def clock_for(scene, preset, row):
    value = str(row["clock"])
    tz = None
    if scene == "book":
        kind = "elapsed_ms"
    elif scene == "impact":
        kind = "elapsed_s"
    elif scene == "lots" or preset == "recovery":
        kind = "event_index"
    elif scene == "selection":
        kind = "trial_index"
    elif "T" in value or (" " in value and ":" in value):
        kind = "iso_datetime"
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("absolute clock requires timezone")
        value = parsed.astimezone(timezone.utc).isoformat()
        tz = "UTC"
    elif "-" in value:
        kind = "session_date"
    else:
        kind = "utc_ns"
        tz = "UTC"
    return {"kind": kind, "value": value, "timezone": tz}


def project_method_trace(fixture, scene_id, preset_id):
    if fixture["schema"] != "engine-method-replay.v1" or preset_id not in PRESETS.get(
        scene_id, []
    ):
        raise ValueError("unknown schema or preset")
    cases = fixture["scenes"][scene_id]["scenarios"]
    index = next(i for i, c in enumerate(cases) if c["id"] == preset_id)
    case = cases[index]
    base = f"/scenes/{scene_id}/scenarios/{index}"
    runs = case["run_sha256"]
    if not isinstance(runs, dict) or set(runs) != set(case["inputs"].get("runs", {})):
        raise ValueError("exact named calls required")
    calls = {}
    for name, digest in runs.items():
        api = case["inputs"]["runs"][name]["api"]
        owner = API_OWNER.get(
            api, "core" if "core" in fixture["owners"] else "platform"
        )
        calls[name] = {
            "input_pointer": base + "/inputs/runs/" + token(name),
            "digest_pointer": base + "/run_sha256/" + token(name),
            "owner_id": owner,
            "source_ids": ["owner-" + owner, "exporter"],
        }
    events = []
    for i, row in enumerate(case["states"]):
        values = safe(row)
        event_id = f"{scene_id}.{preset_id}.{i}"
        sources = {
            k: source_record(
                base + "/states/" + str(i) + "/" + token(k),
                *producers(scene_id, preset_id, case, "states", f"/{i}/{k}"),
            )
            for k in row
        }
        events.append(
            {
                "event_id": event_id,
                "ordinal": i,
                "clock": clock_for(scene_id, preset_id, row),
                "stage": row["phase"],
                "depends_on": [],
                "values": values,
                "source_pointers": sources,
            }
        )
    tables = []
    for section in TABLES:
        if section not in case:
            continue
        rows = safe(case[section])
        sources = {}
        for path, value in leaves(rows):
            sources["/rows" + path] = source_record(
                base + "/" + section + path,
                *producers(scene_id, preset_id, case, section, path),
            )
        union = sorted({n for s in sources.values() for n in s["run_names"]})
        tables.append(
            {
                "id": section,
                "rows": rows,
                "value_sources": sources,
                **source_record(
                    base + "/" + section,
                    union,
                    MISSING if scene_id == "flow" else STATIC,
                ),
            }
        )
    owner = case["owner"]
    provider = fixture["owners"][owner]
    result = {
        "schema": "engine-learning-trace.v1",
        "scene_id": scene_id,
        "preset_id": preset_id,
        "provider": {
            "id": owner,
            "backend_id": "rust-nautilus" if owner == "engine" else "python",
            **provider,
        },
        "bindings": {
            "input_sha256": case["input_sha256"],
            "config_sha256": case["config_sha256"],
            "run_sha256": dict(runs),
            "run_bindings_pointer": base + "/run_sha256",
            "run_bindings_status": "available" if runs else "unavailable",
            "run_bindings_reason_key": None if runs else MISSING,
            "calls": calls,
        },
        "units": case["units"],
        "currency": case.get("currency", case["units"].get("money"))
        if case.get("currency", case["units"].get("money")) in {"USD", "CNY"}
        else "unknown",
        "clock_semantics": case["clocks"],
        "calibration": "synthetic_only",
        "evidence_boundary": case["evidence_boundary"],
        "source_ids": ["owner-" + owner, "exporter"],
        "seed": str(case["inputs"]["runs"]["generator"]["arguments"]["seed"])
        if scene_id == "selection"
        else None,
        "policy_mode": "supplied_orders"
        if scene_id == "flow"
        else (
            "declared_feedback"
            if scene_id == "paths" and preset_id == "feedback"
            else ("fixed_forecast" if scene_id == "paths" else "not_applicable")
        ),
        "events": events,
        "tables": tables,
        "exporter_sources": fixture["exporter_sources"],
    }
    for key in ["forecast_sha256", "market_sha256"]:
        if key in case:
            result["bindings"][key] = case[key]
    if scene_id == "paths":
        points = []
        for event in events:
            matches = {}
            for other in cases:
                ids = [
                    f"paths.{other['id']}.{j}"
                    for j, row in enumerate(other["states"])
                    if row["phase"] == event["stage"]
                    and str(row["clock"]) == event["values"]["clock"]
                ]
                if len(ids) > 1:
                    raise ValueError("ambiguous comparison point")
                matches[other["id"]] = ids[0] if ids else None
            points.append(
                {
                    "id": event["event_id"],
                    "label_key": "phase." + event["stage"],
                    "events": matches,
                }
            )
        result["comparison"] = {"axis": "utc_ns_stage", "points": points}
    return result


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
        + "\n",
        encoding="utf-8",
    )


def digest_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path, url):
    return {"url": url, "sha256": digest_file(path)}


def project_source_registry(fixture, fixture_path):
    sources = {
        "schema": "engine-learning-sources.v1",
        "records": [
            {
                "id": "owner-" + name,
                "class": "documented_discussion"
                if name == "runtime"
                else "synthetic_execution_evidence",
                "title": name,
                "url": owner["url"],
                "locator": owner["revision"],
                "claim": "Historical Runtime documentation; no process execution in this tutorial"
                if name == "runtime"
                else "Pinned public synthetic owner evidence",
                "limitations": "No empirical calibration",
                "availability": "available",
                "revision": owner["revision"],
                "sha256": fixture.get("execution", {}).get(
                    "rust_sha256", digest_file(fixture_path)
                )
                if name == "engine"
                else fixture.get("execution", {})
                .get("dependencies", {})
                .get(
                    {"core": "quant-backtest-core", "platform": "quant-platform"}.get(
                        name, ""
                    ),
                    {},
                )
                .get("sha256", digest_file(fixture_path)),
            }
            for name, owner in fixture["owners"].items()
        ],
    }
    sources["records"].append(
        {
            "id": "exporter",
            "class": "project_interpretation",
            "title": "Preserved tutorial exporter",
            "url": "https://github.com/runchengxie/quant-backtest-engine/pull/19",
            "locator": "4820af3b82940e7697cb8c92154315b1d59ee23d",
            "claim": "Recorded synthetic teaching transformations",
            "limitations": "Not independent market observations",
            "availability": "available",
        }
    )
    return sources


def export_learning_traces(
    fixture_path, output_dir, source_registry=None, preset_grid=None
):
    fixture = json.loads(fixture_path.read_text())
    output_dir.mkdir(parents=True, exist_ok=True)
    sources = project_source_registry(fixture, fixture_path)
    if source_registry is not None:
        if json.loads(source_registry.read_text()) != sources:
            raise ValueError("source registry differs from exact owner evidence")
    write_json(output_dir / "sources.json", sources)
    traces = []
    tuples = []
    for scene, presets in PRESETS.items():
        for preset in presets:
            trace = project_method_trace(fixture, scene, preset)
            path = output_dir / "traces" / scene / (preset + ".json")
            write_json(path, trace)
            reference = {
                "scene_id": scene,
                "preset_id": preset,
                **ref(path, f"assets/learning/traces/{scene}/{preset}.json"),
            }
            traces.append(reference)
            case = next(
                c for c in fixture["scenes"][scene]["scenarios"] if c["id"] == preset
            )
            tuples.append(
                {
                    "scene_id": scene,
                    "preset_id": preset,
                    "inputs": safe(case["inputs"]),
                    "seed": trace["seed"],
                    "capabilities": ["recorded_events"],
                    "owner_calls": trace["bindings"]["calls"],
                    "trace_sha256": reference["sha256"],
                }
            )
    grid = {"schema": "engine-learning-grid.v1", "presets": tuples}
    if preset_grid is not None:
        if json.loads(preset_grid.read_text()) != grid:
            raise ValueError("preset grid differs from exact fixed owner tuples")
    write_json(output_dir / "preset-grid.json", grid)
    catalogs = {}
    for locale in ["en", "zh-CN"]:
        source = fixture_path.parent / (locale + ".json")
        path = output_dir / "catalogs" / (locale + ".json")
        write_json(path, json.loads(source.read_text()))
        catalogs[locale] = ref(path, f"assets/learning/catalogs/{locale}.json")
    manifest = {
        "schema": "engine-learning-manifest.v1",
        "provider_revisions": {n: o["revision"] for n, o in fixture["owners"].items()},
        "exporter_sources": fixture["exporter_sources"],
        "fixture": ref(fixture_path, "assets/method/fixtures.json"),
        "sources": ref(output_dir / "sources.json", "assets/learning/sources.json"),
        "catalogs": catalogs,
        "preset_grid": ref(
            output_dir / "preset-grid.json", "assets/learning/preset-grid.json"
        ),
        "traces": traces,
    }
    path = output_dir / "manifest.json"
    write_json(path, manifest)
    return path


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--source-registry", type=Path)
    p.add_argument("--preset-grid", type=Path)
    a = p.parse_args()
    print(export_learning_traces(a.fixture, a.output, a.source_registry, a.preset_grid))
