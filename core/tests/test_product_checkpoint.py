"""Expected identity must come from caller inputs."""

import json

import pytest
from quant_backtest_engine.product import manifest_to_json, parse_manifest
from test_product_sessions import setup


def test_missing_session_registry_is_red():
    from pathlib import Path

    from quant_backtest_core import BackendContext
    from quant_backtest_core.backends.registry import get_backend

    assert (
        "checkpoint"
        in get_backend("python.minute", BackendContext(Path("."), Path(".")))
        .descriptor()
        .capabilities
    )


@pytest.mark.parametrize(
    "field",
    [
        "config",
        "delay",
        "impact",
        "bars",
        "targets",
        "locks",
        "actions",
        "valuations",
        "flows",
        "model",
        "policy",
    ],
)
def test_expected_input_drift_is_rejected(tmp_path, field):
    sessions, manifest, context = setup(tmp_path)
    checkpoint = sessions.open_session(manifest, context=context).checkpoint()
    w = manifest_to_json(manifest)
    if field == "config":
        w["settings"]["config"]["buy_fee_bp"] = "4"
    elif field == "delay":
        w["settings"]["report_delay_seconds"] = "0"
    elif field == "impact":
        w["settings"]["impact"]["permanent"] = "0"
    elif field == "bars":
        w["inline_inputs"]["bars"][0]["volume"] = "2000"
    elif field == "targets":
        w["inline_inputs"]["targets"][0]["weight"] = "0.5"
    elif field == "locks":
        w["tapes"]["quantity_locks"] = []
    elif field == "actions":
        w["tapes"]["corporate_actions"] = []
    elif field == "valuations":
        del w["tapes"]["valuation_events"]
    elif field == "flows":
        w["tapes"]["capital_flows"] = []
    elif field == "model":
        w["model_versions"] = {"linear-impact": "different"}
    elif field == "policy":
        w["policy"]["version"] = "v2"
    with pytest.raises(ValueError):
        sessions.restore_session(parse_manifest(w), checkpoint, context=context)


def test_corruption_rejected(tmp_path):
    sessions, manifest, context = setup(tmp_path)
    checkpoint = sessions.open_session(manifest, context=context).checkpoint()
    w = json.loads(checkpoint)
    w["owner_state"]["cursor"] = 100
    with pytest.raises(ValueError):
        sessions.restore_session(manifest, json.dumps(w).encode(), context=context)


@pytest.mark.parametrize("kind", ["source", "dependency", "policy"])
def test_executed_identity_drift_rejects_restore(tmp_path, monkeypatch, kind):
    import quant_backtest_core.sessions.checkpoint as binding

    sessions, manifest, context = setup(tmp_path)
    checkpoint = sessions.open_session(manifest, context=context).checkpoint()
    original = binding.Path.read_bytes

    def changed(path):
        raw = original(path)
        if kind == "source" and path.name == "capital_returns.py":
            return raw + b"# changed helper"
        if kind == "dependency" and path.name == "__init__.py" and path.parent.name == "numpy":
            return raw + b"# changed dependency"
        if kind == "policy" and path.name == "policies.py":
            return raw + b"# changed policy"
        return raw

    monkeypatch.setattr(binding.Path, "read_bytes", changed)
    with pytest.raises(ValueError, match="binding mismatch"):
        sessions.restore_session(manifest, checkpoint, context=context)


def test_calendar_exact_bytes_and_tape_artifact_binding(tmp_path):
    import hashlib

    from quant_backtest_core import BackendContext

    sessions, manifest, context = setup(tmp_path / "out")
    wire = manifest_to_json(manifest)
    calendar = (context.artifact_root / wire["calendar"]["uri"]).read_bytes()
    (tmp_path / wire["calendar"]["uri"]).write_bytes(calendar)
    raw = json.dumps(wire["tapes"]["capital_flows"]).encode()
    (tmp_path / "flows.json").write_bytes(raw)
    wire["tapes"]["capital_flows"] = {
        "uri": "flows.json",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "media_type": "application/json",
    }
    manifest = parse_manifest(wire)
    context = BackendContext(tmp_path, tmp_path / "out")
    checkpoint = sessions.open_session(manifest, context=context).checkpoint()
    (tmp_path / "flows.json").write_bytes(raw + b" ")
    with pytest.raises(ValueError):
        sessions.restore_session(manifest, checkpoint, context=context)
    (tmp_path / "flows.json").write_bytes(raw)
    (tmp_path / wire["calendar"]["uri"]).write_bytes(calendar + b" ")
    with pytest.raises(ValueError):
        sessions.restore_session(manifest, checkpoint, context=context)
