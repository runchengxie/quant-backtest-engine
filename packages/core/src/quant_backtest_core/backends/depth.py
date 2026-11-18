"""Opt-in L2 event product adapter. Nautilus owns every fill and account balance."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from importlib.metadata import version
from typing import Any
from zoneinfo import ZoneInfo

from quant_backtest_engine import EngineClient
from quant_backtest_engine.depth import CAPABILITIES
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
)
from quant_backtest_engine.product.depth import depth_request, validate_depth_input

from ..artifacts import json_bytes, load_artifact, output_paths, write_new
from ..errors import ProductError
from .protocol import BackendContext
from .rust import _clocks, _source_digest, _verify_binary


class DepthBackend:
    def __init__(self, context: BackendContext) -> None:
        self.context = context

    def descriptor(self) -> BackendDescriptor:
        if self.context.rust_executable is not None or self.context.rust_sha256 is not None:
            _verify_binary(self.context)
            assert self.context.rust_executable is not None and self.context.rust_sha256 is not None
            EngineClient(
                self.context.rust_executable, self.context.rust_sha256
            ).depth_capabilities()
        return BackendDescriptor(
            identity=ProviderIdentity(
                backend_id="rust.nautilus.depth",
                distribution="quant-backtest-core",
                version=version("quant-backtest-core"),
                source_revision=None,
                source_sha256=_source_digest(),
                artifact_sha256=self.context.rust_sha256,
                dependencies=(
                    ("required-native-wire", "engine_depth_request.v1"),
                    ("required-nautilus", "0.66.0"),
                ),
            ),
            input_schemas=("rust-depth.v1",),
            result_schemas=("backtest-product-result.v1",),
            checkpoint_schemas=(),
            capabilities=CAPABILITIES,
            units=(("cash", "CNY"),),
            restrictions=(
                "Single raw-price CNY instrument with explicit Asia/Shanghai event-calendar.v1 dates",
                "Normalized aggregate snapshots/deltas and explicit trade aggressors; upstream queue_position=false",
                "One supplied limit/cancel/target-position command per event; target waits for working orders",
                "No T+1, buy-lot enforcement, corporate actions, restore or arbitrary policy callbacks",
                "Available tables: fills, positions, reports; decisions and order receipts retained in raw result",
                "Unified market clocks (ts_ns=available_ns); supplied command latency and real queues require independent evidence",
            ),
        )

    def _prepare(self, manifest: ProductManifest, context: BackendContext) -> dict[str, Any]:
        if context != self.context:
            raise ProductError("depth backend context mismatch")
        require_capabilities(manifest, self.descriptor())
        _verify_binary(context)
        wire: dict[str, Any] = manifest_to_json(manifest)
        for name, reference in manifest.inputs:
            wire["inline_inputs"][name] = load_artifact(reference, context.artifact_root)
        wire["inputs"] = {}
        for name, tape in manifest.tapes:
            if isinstance(tape, ArtifactRef):
                wire["tapes"][name] = load_artifact(tape, context.artifact_root)
        loaded = parse_manifest(wire)
        validate_depth_input(loaded)
        request = depth_request(loaded)
        dates = list(
            dict.fromkeys(
                datetime.fromtimestamp(e["available_ns"] // 1_000_000_000, tz=timezone.utc)
                .astimezone(ZoneInfo(manifest.timezone))
                .date()
                .isoformat()
                for e in request["events"]
            )
        )
        expected = {"schema": "event-calendar.v1", "timezone": manifest.timezone, "sessions": dates}
        if load_artifact(manifest.calendar, context.artifact_root) != expected:
            raise ProductError("event calendar must cover the exact supplied local dates")
        output_paths(manifest.output_uri, context)
        return request

    def validate(self, manifest: ProductManifest, context: BackendContext) -> None:
        request = self._prepare(manifest, context)
        assert context.rust_executable is not None and context.rust_sha256 is not None
        EngineClient(context.rust_executable, context.rust_sha256).validate_depth(request)

    def run(self, manifest: ProductManifest, context: BackendContext) -> ProductResult:
        request = self._prepare(manifest, context)
        assert context.rust_executable is not None and context.rust_sha256 is not None
        native = EngineClient(context.rust_executable, context.rust_sha256).run_depth(request)
        raw = json_bytes(native)
        digest = hashlib.sha256(raw).hexdigest()
        account = native["account"]
        sources = {"fills": "fills", "positions": "positions", "reports": "orders"}
        tables = tuple(
            EvidenceTable(
                name, "available", tuple(_clocks(account[sources[name]], native=False)), None
            )
            if name in sources
            else EvidenceTable(
                name, "unavailable", (), "Native depth result does not provide this economic table"
            )
            for name in TABLE_NAMES
        )
        result = ProductResult(
            status="completed",
            manifest_sha256=hashlib.sha256(json_bytes(manifest_to_json(manifest))).hexdigest(),
            provider=self.descriptor().identity,
            tables=tables,
            summary={
                "initial_cash": request["initial_cash"],
                "final_cash": account["cash"],
                "final_nav": account["equity"],
                "total_commission": account["commission"],
                "decisions": _clocks(native["decisions"], native=False),
                "request_sha256": native["request_sha256"],
            },
            raw_result=ArtifactRef(
                manifest.output_uri + ".native.json", digest, "application/json"
            ),
            normalization=NormalizationReceipt(
                "rust-depth-adapter.v1",
                "engine_depth_result.v1",
                digest,
                tuple(name for name in TABLE_NAMES if name not in sources),
            ),
            failure=None,
            scenario=None,
        )
        result_path, raw_path = output_paths(manifest.output_uri, context)
        write_new(raw_path, raw)
        write_new(result_path, json_bytes(result_to_json(result)))
        return result
