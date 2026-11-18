"""Explicit normalized-L2 product profile; execution belongs to the selected native owner."""

from __future__ import annotations

from ..depth import validate_request
from . import types as t
from .validation import _decimal, _ns, _ordered, _shape
from .validation import _to_json as _thaw


def depth_request(manifest: t.ProductManifest) -> dict:
    """Build native input only after artifact-backed values have been resolved."""
    events = _thaw(dict(manifest.tapes)["events"])
    commands = _thaw(dict(manifest.tapes)["commands"])
    settings = _thaw(manifest.settings)

    def clocks(value):
        if isinstance(value, dict):
            return {
                k: int(v) if k.endswith("_ns") else clocks(v) for k, v in value.items()
            }
        if isinstance(value, list):
            return [clocks(v) for v in value]
        return value

    return {
        "schema_version": "engine_depth_request.v1",
        "currency": manifest.currency,
        "initial_cash": manifest.initial_account["cash"],
        "fee_bps": settings["fee_bps"],
        "instrument": _thaw(manifest.inline_inputs["instrument"]),
        "insert_latency_ns": int(settings["insert_latency_ns"]),
        "cancel_latency_ns": int(settings["cancel_latency_ns"]),
        "end_ns": int(settings["end_ns"]),
        "events": clocks(events),
        "commands": clocks(commands),
        "required_capabilities": list(manifest.required_capabilities),
    }


def validate_depth_input(manifest: t.ProductManifest) -> None:
    if (
        manifest.backend_id != "rust.nautilus.depth"
        or manifest.currency != "CNY"
        or manifest.share_basis != "raw"
        or manifest.timezone != "Asia/Shanghai"
    ):
        raise ValueError(
            "depth product profile requires explicit CNY/raw/Asia-Shanghai backend"
        )
    if dict(manifest.units) != {"cash": "CNY"}:
        raise ValueError("depth cash unit must be CNY")
    if (
        manifest.policy is not None
        or manifest.forecast is not None
        or manifest.risk is not None
        or manifest.model_versions
        or manifest.scenario is not None
    ):
        raise ValueError(
            "depth profile executes supplied commands, not policy/model/scenario references"
        )
    _shape(manifest.initial_account, ("cash",))
    _decimal(manifest.initial_account["cash"], "cash")
    _shape(
        manifest.settings,
        ("fee_bps", "insert_latency_ns", "cancel_latency_ns", "end_ns"),
    )
    _decimal(manifest.settings["fee_bps"], "fee_bps")
    for name in ("insert_latency_ns", "cancel_latency_ns", "end_ns"):
        _ns(manifest.settings[name], name)
    for name in ("information_ns", "decision_ns", "entry_ns"):
        if getattr(manifest.clocks, name) is None:
            raise ValueError("depth admission clocks must be explicit")
    _ordered(
        manifest.clocks.information_ns,
        manifest.clocks.decision_ns,
        "information/decision",
    )
    _ordered(manifest.clocks.decision_ns, manifest.clocks.entry_ns, "decision/entry")
    _ordered(
        manifest.clocks.available_ns, manifest.clocks.decision_ns, "available/decision"
    )
    if manifest.clocks.valuation_ns != manifest.settings["end_ns"]:
        raise ValueError("valuation clock must match observation horizon")
    if set(dict(manifest.inputs)) | set(manifest.inline_inputs) != {
        "instrument"
    } or set(dict(manifest.tapes)) != {"events", "commands"}:
        raise ValueError(
            "depth profile requires instrument input and events/commands tapes"
        )
    if manifest.inputs or any(isinstance(v, t.ArtifactRef) for _, v in manifest.tapes):
        return
    request = depth_request(manifest)
    validate_request(request)
    if int(manifest.clocks.entry_ns) > request["events"][0]["available_ns"]:
        raise ValueError("events precede run admission")
