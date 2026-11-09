"""Normalize all reported tables without inventing unavailable economic ledgers."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict
from datetime import date
from typing import Any

from quant_backtest_engine.product import (
    TABLE_NAMES,
    ArtifactRef,
    EvidenceTable,
    NormalizationReceipt,
    ProductManifest,
    ProductResult,
    ProviderIdentity,
    result_to_json,
)

from ..artifacts import json_bytes, output_paths, write_new
from ..backends.protocol import BackendContext
from .checkpoint import digest

SOURCES = {
    "reports": "orders",
    "fills": "fills",
    "positions": "holdings",
    "valuations": "valuation_ledger",
    "capital_flows": "capital_flow_ledger",
    "daily": "daily",
}


def transport(value: Any) -> Any:
    # Timestamp.value is an integer nanosecond clock; never pass clocks through floats.
    if hasattr(value, "value") and hasattr(value, "tzinfo"):
        return str(value.value) if value.tzinfo is not None else value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): transport(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [transport(v) for v in value]
    if isinstance(value, float):
        return str(value) if math.isfinite(value) else None
    if type(value) is int:
        return str(value)
    if value is None or isinstance(value, (str, bool)):
        return value
    if hasattr(value, "item"):
        return transport(value.item())
    raise TypeError(f"unsupported native result value: {type(value)}")


def normalize(
    native: Any,
    manifest: ProductManifest,
    provider: ProviderIdentity,
    manifest_hash: str,
    context: BackendContext,
) -> ProductResult:
    from ..backtest._minute_checkpoint import _wire

    raw = {name: transport(getattr(native, name).to_dict("records")) for name in SOURCES.values()}
    raw["summary"] = transport(native.summary)
    # Original tagged owner payload retains nonfinite values and the complete original fields.
    raw["owner_result"] = _wire(asdict(native))
    raw_hash = digest(raw)
    tables = tuple(
        EvidenceTable(name, "available", tuple(raw[SOURCES[name]]), None)
        if name in SOURCES
        else EvidenceTable(
            name, "unavailable", (), "Minute owner does not report this standalone ledger"
        )
        for name in TABLE_NAMES
    )
    result = ProductResult(
        "completed",
        manifest_hash,
        provider,
        tables,
        raw["summary"],
        ArtifactRef(manifest.output_uri + ".native.json", raw_hash, "application/json"),
        NormalizationReceipt(
            "minute-session-adapter.v1",
            "minute-execution-result.v1",
            raw_hash,
            tuple(name for name in TABLE_NAMES if name not in SOURCES),
        ),
        None,
        manifest.scenario,
    )
    output, original = output_paths(manifest.output_uri, context)
    write_new(original, json_bytes(raw))
    write_new(output, json_bytes(result_to_json(result)))
    return result
