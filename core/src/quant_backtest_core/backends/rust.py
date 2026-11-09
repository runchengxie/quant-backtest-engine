"""Native v2 session adapter: NautilusTrader remains the sole financial owner."""

from __future__ import annotations

import hashlib
import re
from dataclasses import fields
from importlib.metadata import version
from pathlib import Path
from typing import Any

from quant_backtest_engine import EngineClient
from quant_backtest_engine.product import (
    TABLE_NAMES,
    ArtifactRef,
    BackendDescriptor,
    EvidenceTable,
    NormalizationReceipt,
    ProductManifest,
    ProductResult,
    ProviderIdentity,
    manifest_to_json,
    parse_manifest,
    require_capabilities,
    result_to_json,
    validate_rust_session,
)

from ..artifacts import json_bytes, load_artifact, output_paths, write_new
from ..errors import BackendUnavailableError, ProductError
from .native_validation import validate_native
from .protocol import BackendContext

CAPABILITIES = (
    "session_ledger",
    "configured_t_plus_one",
    "buy_lots",
    "quote_trade_permissions",
    "quote_liquidity",
)
# Only directly reported native tables are available. Orders are terminal reports,
# not admission or cancellation events; daily cash observations are not a cash ledger.
TABLE_SOURCES = {
    "fills": "fills",
    "positions": "daily_positions",
    "reports": "orders",
    "daily": "daily_ledger",
}


def _source_digest() -> str:
    root = Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes() + b"\0")
    return digest.hexdigest()


def _verify_binary(context: BackendContext) -> None:
    if context.rust_executable is None or context.rust_sha256 is None:
        raise BackendUnavailableError("Rust requires a trusted executable and its SHA256")
    if not context.rust_executable.is_absolute() or not re.fullmatch(
        r"[0-9a-f]{64}", context.rust_sha256
    ):
        raise ProductError("select an absolute Rust executable and lowercase SHA256")
    if hashlib.sha256(context.rust_executable.read_bytes()).hexdigest() != context.rust_sha256:
        raise ProductError("Rust executable digest mismatch")


def _clocks(value: Any, *, native: bool) -> Any:
    if isinstance(value, dict):
        return {
            key: (int(item) if native else str(item))
            if key.endswith("_ns")
            else _clocks(item, native=native)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_clocks(item, native=native) for item in value]
    return value


def descriptor_json(descriptor: BackendDescriptor) -> dict[str, Any]:
    identity = {
        field.name: getattr(descriptor.identity, field.name)
        for field in fields(descriptor.identity)
    }
    identity["dependencies"] = dict(descriptor.identity.dependencies)
    return {
        "identity": identity,
        "input_schemas": descriptor.input_schemas,
        "result_schemas": descriptor.result_schemas,
        "checkpoint_schemas": descriptor.checkpoint_schemas,
        "capabilities": descriptor.capabilities,
        "units": dict(descriptor.units),
        "restrictions": descriptor.restrictions,
    }


class RustBackend:
    def __init__(self, context: BackendContext) -> None:
        self.context = context

    def descriptor(self) -> BackendDescriptor:
        if self.context.rust_executable is not None or self.context.rust_sha256 is not None:
            _verify_binary(self.context)
        return BackendDescriptor(
            identity=ProviderIdentity(
                backend_id="rust.nautilus.sessions",
                distribution="quant-backtest-core",
                version=version("quant-backtest-core"),
                source_revision=None,
                source_sha256=_source_digest(),
                dependencies=(
                    ("quant-backtest-engine-client", version("quant-backtest-engine-client")),
                    ("required-nautilus", "0.66.0"),
                    ("required-native-input", "engine_request.v2"),
                    ("required-native-result", "engine_result.v2"),
                ),
                artifact_sha256=self.context.rust_sha256,
            ),
            input_schemas=("rust-session.v1",),
            result_schemas=("backtest-product-result.v1",),
            checkpoint_schemas=(),
            capabilities=CAPABILITIES,
            units=(("cash", "CNY"),),
            restrictions=(
                "CNY/raw/Asia-Shanghai product profile; cash unit must be CNY",
                "Explicit synthetic-calendar.v1 session-date list; no calendar generation",
                "No policy, model, scenario transformation, forecast, risk or restore",
                "Available tables: fills, positions, reports, daily",
                "All other evidence tables are unavailable, not empty ledgers",
            ),
        )

    def _prepare(self, manifest: ProductManifest, context: BackendContext) -> dict[str, Any]:
        if context != self.context:
            raise ProductError("backend context differs from its bound trusted context")
        require_capabilities(manifest, self.descriptor())
        _verify_binary(context)
        if (
            manifest.policy is not None
            or manifest.forecast is not None
            or manifest.risk is not None
            or manifest.model_versions
            or manifest.scenario is not None
        ):
            raise ProductError(
                "Rust adapter does not execute policies, models, scenarios, forecast or risk"
            )
        if manifest.currency != "CNY" or dict(manifest.units) != {"cash": "CNY"}:
            raise ProductError("this product profile requires CNY and explicit cash=CNY units")
        wire: dict[str, Any] = manifest_to_json(manifest)
        for name, reference in manifest.inputs:
            wire["inline_inputs"][name] = load_artifact(reference, context.artifact_root)
        wire["inputs"] = {}
        for name, tape in manifest.tapes:
            if isinstance(tape, ArtifactRef):
                wire["tapes"][name] = load_artifact(tape, context.artifact_root)
        loaded = parse_manifest(wire)
        validate_rust_session(loaded)
        calendar = load_artifact(manifest.calendar, context.artifact_root)
        dates = [session["session_date"] for session in wire["tapes"]["sessions"]]
        if calendar != {
            "schema": "synthetic-calendar.v1",
            "timezone": manifest.timezone,
            "sessions": dates,
        }:
            raise ProductError("calendar must match the explicit session dates and timezone")
        request = {
            "schema_version": "engine_request.v2",
            "currency": manifest.currency,
            "price_basis": manifest.share_basis,
            "initial_cash": wire["initial_account"]["cash"],
            "fee_bps": wire["settings"]["fee_bps"],
            "enforce_t1": wire["settings"]["enforce_t1"],
            "instruments": wire["inline_inputs"]["instruments"],
            "required_capabilities": list(manifest.required_capabilities),
            "sessions": _clocks(wire["tapes"]["sessions"], native=True),
        }
        validate_native(request, manifest.timezone)
        output_paths(manifest.output_uri, context)
        return request

    def validate(self, manifest: ProductManifest, context: BackendContext) -> None:
        self._prepare(manifest, context)

    def run(self, manifest: ProductManifest, context: BackendContext) -> ProductResult:
        request = self._prepare(manifest, context)
        # EngineClient independently verifies and snapshots the binary before executing.
        assert context.rust_executable is not None and context.rust_sha256 is not None
        native = EngineClient(context.rust_executable, context.rust_sha256).run_sessions(request)
        raw_bytes = json_bytes(native)
        raw_hash = hashlib.sha256(raw_bytes).hexdigest()
        tables = tuple(
            EvidenceTable(
                name, "available", tuple(_clocks(native[TABLE_SOURCES[name]], native=False)), None
            )
            if name in TABLE_SOURCES
            else EvidenceTable(
                name,
                "unavailable",
                (),
                "Native engine_result.v2 does not report this evidence table",
            )
            for name in TABLE_NAMES
        )
        result = ProductResult(
            status="completed",
            manifest_sha256=hashlib.sha256(json_bytes(manifest_to_json(manifest))).hexdigest(),
            provider=self.descriptor().identity,
            tables=tables,
            summary={
                key: native[key]
                for key in ("initial_cash", "final_cash", "final_nav", "total_commission")
            },
            raw_result=ArtifactRef(
                manifest.output_uri + ".native.json", raw_hash, "application/json"
            ),
            normalization=NormalizationReceipt(
                "rust-session-adapter.v1",
                "engine_result.v2",
                raw_hash,
                tuple(name for name in TABLE_NAMES if name not in TABLE_SOURCES),
            ),
            failure=None,
            scenario=manifest.scenario,
        )
        result_path, raw_path = output_paths(manifest.output_uri, context)
        write_new(raw_path, raw_bytes)
        write_new(result_path, json_bytes(result_to_json(result)))
        return result
