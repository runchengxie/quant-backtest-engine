"""Fail closed on byte identities, source projection, producer maps and schemas."""

import argparse
import hashlib
import json
import re
from pathlib import Path

try:
    from .export_learning_traces import (
        PRESETS,
        project_source_registry,
        project_method_trace,
        pointer,
        safe,
        leaves,
    )
except ImportError:
    from export_learning_traces import (
        PRESETS,
        project_source_registry,
        project_method_trace,
        pointer,
        safe,
        leaves,
    )


def validate_fixture(fixture, root):
    lock = json.loads((root / "docs/assets/method/owner-lock.json").read_text())
    if fixture.get("schema") != "engine-method-replay.v1":
        raise ValueError("unknown fixture schema")
    if {n: o["revision"] for n, o in fixture["owners"].items()} != lock[
        "provider_revisions"
    ]:
        raise ValueError("stale provider")
    execution = fixture["execution"]
    if execution["rust_sha256"] != lock["rust_sha256"]:
        raise ValueError("execution binary identity mismatch")
    wheels = {
        entry["wheel"]: entry["sha256"]
        for entry in execution["dependencies"].values()
        if "wheel" in entry
    }
    if wheels != lock["wheels"]:
        raise ValueError("installed owner wheel identity mismatch")
    for name, version in lock["dependencies"].items():
        if execution["dependencies"][name]["version"] != version:
            raise ValueError("installed dependency version mismatch")
    sources = {
        **fixture["exporter_sources"],
        "project_tools/export_method_fixtures.py": fixture["exporter_sha256"],
    }
    for name, sha in sources.items():
        if not name.startswith("project_tools/") or ".." in name.split("/"):
            raise ValueError("invalid exporter source")
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != sha:
            raise ValueError("stale exporter helper")
    for scene in fixture["scenes"].values():
        for case in scene["scenarios"]:
            canonical = lambda v: hashlib.sha256(
                json.dumps(v, sort_keys=True, allow_nan=False).encode()
            ).hexdigest()
            if (
                case["input_sha256"] != canonical(case["inputs"])
                or case["config_sha256"] != case["input_sha256"]
            ):
                raise ValueError("input/config digest mismatch")
            runs = case["inputs"].get("runs", {})
            if case["run_sha256"] != {n: canonical(call) for n, call in runs.items()}:
                raise ValueError("call-definition hash mismatch")
    return True


def validate_trace(trace, fixture):
    if trace.get("schema") != "engine-learning-trace.v1":
        raise ValueError("unknown trace schema")
    expected = project_method_trace(fixture, trace["scene_id"], trace["preset_id"])
    if trace != expected:
        raise ValueError(
            "trace differs from exact source and audited contributor projection"
        )
    for event in trace["events"]:
        for name, source in event["source_pointers"].items():
            if event["values"][name] != safe(
                pointer(fixture, source["source_pointer"])
            ):
                raise ValueError("event source mismatch")
    for table in trace["tables"]:
        for path, value in leaves(table["rows"]):
            if value != safe(
                pointer(
                    fixture, table["value_sources"]["/rows" + path]["source_pointer"]
                )
            ):
                raise ValueError("table source mismatch")
    return True


def validate_learning_assets(manifest_path):
    directory = manifest_path.parent
    docs = directory.parents[1]
    from jsonschema import Draft202012Validator

    def read(ref):
        url = ref["url"]
        if (
            not isinstance(url, str)
            or not url.startswith("assets/")
            or ".." in url.split("/")
            or "?" in url
            or "#" in url
            or "\\" in url
        ):
            raise ValueError("invalid public URL")
        path = docs / url
        if path.is_symlink() or not path.resolve().is_relative_to(docs.resolve()):
            raise ValueError("unsafe artifact")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise ValueError("byte hash mismatch")
        return json.loads(raw)

    def schema(name, value):
        definition = json.loads(
            (directory / "schemas" / (name + ".schema.json")).read_text()
        )
        Draft202012Validator.check_schema(definition)
        Draft202012Validator(definition).validate(value)

    manifest = json.loads(manifest_path.read_text())
    schema("manifest", manifest)
    fixture = read(manifest["fixture"])
    validate_fixture(fixture, docs.parent)
    sources = read(manifest["sources"])
    grid = read(manifest["preset_grid"])
    schema("sources", sources)
    schema("preset-grid", grid)
    if manifest["provider_revisions"] != {
        n: o["revision"] for n, o in fixture["owners"].items()
    }:
        raise ValueError("provider revision mismatch")
    if manifest["exporter_sources"] != fixture["exporter_sources"]:
        raise ValueError("manifest exporter sources differ from fixture")
    source_ids = [source["id"] for source in sources["records"]]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("duplicate source identifier")
    if sources != project_source_registry(fixture, docs / manifest["fixture"]["url"]):
        raise ValueError("source registry differs from exact owner evidence")
    for source in sources["records"]:
        if (
            source["class"] == "real_market_calibration"
            or source.get("availability") != "available"
        ):
            raise ValueError("empirical evidence not registered")
    expected = [(s, p) for s, ps in PRESETS.items() for p in ps]
    if [(t["scene_id"], t["preset_id"]) for t in manifest["traces"]] != expected:
        raise ValueError("preset coverage mismatch")
    if [(t["scene_id"], t["preset_id"]) for t in grid["presets"]] != expected:
        raise ValueError("grid coverage mismatch")
    for ref, entry in zip(manifest["traces"], grid["presets"], strict=True):
        trace = read(ref)
        schema("trace", trace)
        validate_trace(trace, fixture)
        for record in [trace, *trace["bindings"]["calls"].values()]:
            if not set(record["source_ids"]).issubset(source_ids):
                raise ValueError("unresolved trace/call source reference")
        case = next(
            c
            for c in fixture["scenes"][trace["scene_id"]]["scenarios"]
            if c["id"] == trace["preset_id"]
        )
        if (
            entry["seed"] != trace["seed"]
            or entry["capabilities"] != ["recorded_events"]
            or entry["inputs"] != safe(case["inputs"])
            or entry["trace_sha256"] != ref["sha256"]
            or entry["owner_calls"] != trace["bindings"]["calls"]
        ):
            raise ValueError("grid input/binding mismatch")
    catalogs = {locale: read(ref) for locale, ref in manifest["catalogs"].items()}
    for locale, catalog in catalogs.items():
        original = json.loads((docs / "assets/method" / (locale + ".json")).read_text())
        if catalog != original:
            raise ValueError("catalog differs from authoritative projection")
    if set(catalogs["en"]) != set(catalogs["zh-CN"]):
        raise ValueError("catalog keys differ")
    for path in directory.rglob("*.json"):
        if "/schemas/" in path.as_posix():
            continue
        text = path.read_text()
        if any(
            x in text for x in ["/home/", "/run/media/", "quant-research", "account_id"]
        ):
            raise ValueError("private content in public artifacts")
    return {
        "schema": "engine-learning-validation.v1",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "traces": len(expected),
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(validate_learning_assets(a.manifest)))
