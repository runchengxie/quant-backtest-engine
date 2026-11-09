"""Explicit minute profile, exact transport conversion only at the native boundary."""

from __future__ import annotations

import hashlib
import zoneinfo
from importlib import import_module
from pathlib import Path
from typing import Any, cast

from quant_backtest_engine.product import (
    ArtifactRef,
    BackendDescriptor,
    ProductManifest,
    ProductResult,
    ProviderIdentity,
    manifest_to_json,
    parse_manifest,
    require_capabilities,
)

from ..artifacts import load_artifact, output_paths
from ..errors import BackendUnavailableError
from .protocol import BackendContext

CAPABILITIES = (
    "session_ledger",
    "checkpoint",
    "restore",
    "corporate_actions",
    "capital_flows",
    "valuation_events",
    "quantity_locks",
    "delayed_reports",
    "linear_impact",
)


def prepare(
    manifest: ProductManifest, context: BackendContext
) -> tuple[dict[str, Any], dict[str, Any], ProviderIdentity]:
    backend = MinuteBackend(context)
    descriptor = backend.descriptor()
    require_capabilities(manifest, descriptor)
    if (
        manifest.currency != "CNY"
        or manifest.share_basis != "raw"
        or dict(manifest.units) != {"cash": "CNY"}
    ):
        raise ValueError("minute profile requires raw shares and cash=CNY")
    if manifest.scenario is not None or manifest.forecast is not None or manifest.risk is not None:
        raise ValueError("minute does not execute scenario/forecast/risk transformations")
    if manifest.model_versions not in ((), (("linear-impact", "v1"),)):
        raise ValueError("only explicit linear-impact v1 is supported")
    wire: dict[str, Any] = manifest_to_json(manifest)
    for name, ref in manifest.inputs:
        wire["inline_inputs"][name] = load_artifact(ref, context.artifact_root)
    wire["inputs"] = {}
    for name, tape in manifest.tapes:
        if isinstance(tape, ArtifactRef):
            wire["tapes"][name] = load_artifact(tape, context.artifact_root)
    parse_manifest(wire)
    calendar = load_artifact(manifest.calendar, context.artifact_root)
    pd = import_module("pandas")
    from ..backtest.impact import LinearImpact
    from ..backtest.minute import (
        CapitalFlow,
        CorporateAction,
        MinuteExecutionConfig,
        ValuationEvent,
    )
    from ..backtest.quantity_locks import QuantityLock

    def clock(value: str) -> Any:
        return pd.Timestamp(int(value), tz="UTC").tz_convert(manifest.timezone)

    def frame(rows: list[dict[str, Any]], clocks: set[str], numbers: set[str]) -> Any:
        return pd.DataFrame(
            [
                {
                    k: clock(v) if k in clocks else float(v) if k in numbers else v
                    for k, v in row.items()
                }
                for row in rows
            ]
        )

    targets = frame(
        wire["inline_inputs"]["targets"],
        {"decision_time", "entry_time", "information_time"},
        {"weight"},
    )
    bars = frame(
        wire["inline_inputs"]["bars"],
        {"time", "interval_start", "mark_source_time"},
        {"open", "high", "low", "close", "volume", "amount", "up_limit", "down_limit"},
    )
    dates = sorted(
        {t.date().isoformat() for t in bars.time}
        | {t.date().isoformat() for t in targets.entry_time}
    )
    if calendar != {
        "schema": "synthetic-calendar.v1",
        "timezone": manifest.timezone,
        "sessions": dates,
    }:
        raise ValueError("calendar must match explicit minute session dates and timezone")
    settings, tapes = wire["settings"], wire["tapes"]
    from quant_backtest_engine.product.minute import CONFIG_DECIMALS

    config = MinuteExecutionConfig(
        initial_cash=float(wire["initial_account"]["cash"]),
        **cast(
            dict[str, Any],
            {k: float(v) if k in CONFIG_DECIMALS else v for k, v in settings["config"].items()},
        ),
    )
    kwargs = {
        "targets": targets,
        "bars": bars,
        "config": config,
        "report_delay_seconds": float(settings["report_delay_seconds"]),
        "impact": LinearImpact(**{k: float(v) for k, v in settings["impact"].items()})
        if settings["impact"] is not None
        else None,
        "quantity_locks": tuple(
            QuantityLock(
                **cast(
                    dict[str, Any],
                    {
                        k: int(v) if k.endswith("_ns") else tuple(v) if k == "symbols" else v
                        for k, v in row.items()
                    },
                )
            )
            for row in tapes["quantity_locks"]
        ),
        "corporate_actions": tuple(
            CorporateAction(
                **cast(
                    dict[str, Any],
                    {
                        k: float(v)
                        if k in {"cash_per_share", "stock_per_share", "withholding_rate"}
                        else v
                        for k, v in row.items()
                    },
                )
            )
            for row in tapes["corporate_actions"]
        ),
        "valuation_events": tuple(
            ValuationEvent(
                **cast(
                    dict[str, Any],
                    {
                        k: clock(v)
                        if k.endswith("_time")
                        else float(v)
                        if k == "value_per_share"
                        else v
                        for k, v in row.items()
                    },
                )
            )
            for row in tapes["valuation_events"]
        ),
        "capital_flows": tuple(
            CapitalFlow(
                **cast(
                    dict[str, Any],
                    {
                        k: clock(v) if k.endswith("_time") else float(v) if k == "amount" else v
                        for k, v in row.items()
                    },
                )
            )
            for row in tapes["capital_flows"]
        ),
    }
    output_paths(manifest.output_uri, context)
    zone_files = [Path(root) / manifest.timezone for root in zoneinfo.TZPATH]
    zone_file = next((p for p in zone_files if p.is_file()), None)
    if zone_file is not None:
        zone_bytes = zone_file.read_bytes()
    else:
        from importlib.resources import files

        zone_bytes = files("tzdata.zoneinfo").joinpath(manifest.timezone).read_bytes()
    return (
        kwargs,
        {
            "loaded": wire,
            "calendar": calendar,
            "timezone_sha256": hashlib.sha256(zone_bytes).hexdigest(),
        },
        descriptor.identity,
    )


class MinuteBackend:
    def __init__(self, context: BackendContext) -> None:
        self.context = context

    def descriptor(self) -> BackendDescriptor:
        try:
            import_module("pandas")
        except ImportError as exc:
            raise BackendUnavailableError(
                "python.minute execution requires quant-backtest-core[minute]"
            ) from exc
        from ..sessions.checkpoint import provider_identity

        return BackendDescriptor(
            provider_identity(),
            ("minute-input.v1",),
            ("backtest-product-result.v1",),
            ("engine-financial-checkpoint.v1",),
            CAPABILITIES,
            (("cash", "CNY"),),
            (
                "Raw CNY explicit synthetic calendar; no inferred external data",
                "Fixed target-weights.v1 or trusted LocalPolicy object",
                "Checkpoint restore requires exact installed source and dependency identities",
            ),
        )

    def validate(self, manifest: ProductManifest, context: BackendContext) -> None:
        prepare(manifest, context)

    def run(self, manifest: ProductManifest, context: BackendContext) -> ProductResult:
        from ..sessions import open_session

        return open_session(manifest, context=context).finish()
