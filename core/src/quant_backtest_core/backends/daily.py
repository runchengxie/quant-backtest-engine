"""Finite daily product adapter, preserving every original owner table in raw output."""

from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from decimal import Decimal
from importlib import import_module
from typing import Any, cast

from quant_backtest_engine.product import (
    TABLE_NAMES,
    ArtifactRef,
    BackendDescriptor,
    ClockSet,
    EvidenceTable,
    NormalizationReceipt,
    ProductManifest,
    ProductResult,
    manifest_to_json,
    parse_manifest,
    require_capabilities,
    result_to_json,
)
from quant_backtest_engine.product.daily import CONFIG_DECIMALS, DATED_DECIMALS, FEE_DECIMALS

from ..artifacts import json_bytes, load_artifact, output_paths, write_new
from ..errors import BackendUnavailableError
from .protocol import BackendContext

CAPABILITIES = ("daily_replay",)


def _wire(value: Any) -> Any:
    """Original numerical results become exact decimal TEXT, never JSON floats."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): _wire(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(v) for v in value]
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            return None
        return format(Decimal(str(value)), "f")
    if hasattr(value, "item"):
        return _wire(value.item())
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"unsupported daily output scalar: {type(value).__name__}")


def _owner_frame(frame: Any) -> Any:
    if frame is None:
        return None

    def scalar(value: Any) -> Any:
        if isinstance(value, float) and not math.isfinite(value):
            return {"nonfinite": repr(value)}
        return _wire(value)

    return {
        "columns": list(frame.columns),
        "dtypes": [repr(v) for v in frame.dtypes],
        "index_dtype": repr(frame.index.dtype),
        "index_name": frame.index.name,
        "columns_dtype": repr(frame.columns.dtype),
        "columns_name": frame.columns.name,
        "index": [scalar(v) for v in frame.index],
        "data": [[scalar(v) for v in row] for row in frame.itertuples(index=False, name=None)],
    }


class DailyBackend:
    def __init__(self, context: BackendContext) -> None:
        self.context = context

    def descriptor(self) -> BackendDescriptor:
        try:
            import_module("pandas")
            import_module("numpy")
        except ImportError as exc:
            raise BackendUnavailableError(
                "python.daily requires quant-backtest-core[daily]"
            ) from exc
        from ..sessions.checkpoint import provider_identity

        return BackendDescriptor(
            replace(provider_identity(), backend_id="python.daily"),
            ("daily-input.v1",),
            ("backtest-product-result.v1",),
            (),
            CAPABILITIES,
            (("cash", "CNY"),),
            (
                "CNY / Asia-Shanghai explicit daily calendar; chosen long-only targets",
                "No checkpoint/restore, policy, flow, scenario or intraday execution",
                "Capacity supports liquidity/tradability, not price/listing/T+1/lot rules",
                "Legacy audit timestamps are date labels, not observed intraday events",
                "Reports are terminal order summaries, not lifecycle admissions",
            ),
        )

    def _prepare(self, manifest: ProductManifest, context: BackendContext) -> Any:
        if context != self.context:
            raise ValueError("backend context differs from bound context")
        require_capabilities(manifest, self.descriptor())
        if manifest.currency != "CNY" or dict(manifest.units) != {"cash": "CNY"}:
            raise ValueError("daily profile requires CNY and cash=CNY")
        if manifest.timezone != "Asia/Shanghai":
            raise ValueError("daily profile requires Asia/Shanghai")
        if (
            any(
                v is not None
                for v in (manifest.policy, manifest.forecast, manifest.risk, manifest.scenario)
            )
            or manifest.model_versions
        ):
            raise ValueError(
                "daily does not execute policy/model/scenario/forecast/risk transformations"
            )
        wire: dict[str, Any] = manifest_to_json(manifest)
        for name, ref in manifest.inputs:
            wire["inline_inputs"][name] = load_artifact(ref, context.artifact_root)
        wire["inputs"] = {}
        for name, tape in manifest.tapes:
            if isinstance(tape, ArtifactRef):
                wire["tapes"][name] = load_artifact(tape, context.artifact_root)
        parse_manifest(wire)
        pd = import_module("pandas")
        from .._minute.corporate_actions import CorporateAction
        from ..daily.contracts import (
            DailyDecisionTiming,
            DailyInputLayout,
            DailyReplayRequest,
            ExecutionCalendar,
        )
        from ..daily.dated_fees import DatedFeeSchedule, DatedTradeFeeModel, FeeSchedulePeriod
        from ..daily.execution import DetailedTradeFeeModel
        from ..daily.execution_sim.config import build_execution_sim_config
        from ..daily.runner import validate_request

        calendar_data = load_artifact(manifest.calendar, context.artifact_root)
        if (
            not isinstance(calendar_data, dict)
            or set(calendar_data) != {"schema", "timezone", "open_dates"}
            or calendar_data["schema"] != "execution-calendar.v1"
        ):
            raise ValueError("daily requires execution-calendar.v1")
        calendar = ExecutionCalendar.from_dates(
            calendar_data["timezone"], calendar_data["open_dates"]
        )
        if calendar.timezone != manifest.timezone:
            raise ValueError("calendar timezone differs from manifest")
        settings = wire["settings"]
        config = build_execution_sim_config(
            {k: float(v) if k in CONFIG_DECIMALS else v for k, v in settings["config"].items()}
        )
        layout = DailyInputLayout(
            **{
                **settings["layout"],
                "liquidity_units": {
                    v["column"]: v["unit"] for v in settings["layout"]["liquidity_units"]
                },
            }
        )
        numeric = {layout.price_col, *config.liquidity_cols}
        pricing = pd.DataFrame(
            [
                {
                    k: (float(v) if v is not None else float("nan")) if k in numeric else v
                    for k, v in row.items()
                }
                for row in wire["inline_inputs"]["pricing"]
            ]
        )
        positions = pd.DataFrame(
            [{**row, "weight": float(row["weight"])} for row in wire["inline_inputs"]["positions"]]
        )
        fee_config = settings["fee_model"]
        fee: object | None = None
        if fee_config is not None:
            if fee_config["kind"] == "detailed":
                fee = DetailedTradeFeeModel(**{k: float(fee_config[k]) for k in FEE_DECIMALS})
            else:
                fee = DatedTradeFeeModel(
                    DatedFeeSchedule(
                        tuple(
                            FeeSchedulePeriod(
                                **cast(
                                    dict[str, Any],
                                    {
                                        k: float(v) if k in DATED_DECIMALS else v
                                        for k, v in row.items()
                                    },
                                )
                            )
                            for row in fee_config["periods"]
                        )
                    ),
                    fee_config["symbol_markets"],
                )
        actions = tuple(
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
            for row in wire["tapes"]["corporate_actions"]
        )
        request = DailyReplayRequest(
            positions,
            pricing,
            calendar,
            {d: ClockSet(**v) for d, v in settings["decision_clocks"].items()},
            config,
            settings["mode"],
            manifest.share_basis,
            actions,
            fee,
            layout=layout,
            decision_timing={
                d: DailyDecisionTiming(**v) for d, v in settings["decision_timing"].items()
            },
        )
        validate_request(request)
        output_paths(manifest.output_uri, context)
        return request

    def validate(self, manifest: ProductManifest, context: BackendContext) -> None:
        self._prepare(manifest, context)

    def run(self, manifest: ProductManifest, context: BackendContext) -> ProductResult:
        request = self._prepare(manifest, context)
        from ..daily.execution_sim.results import ExecutionAdjustedNavResult
        from ..daily.runner import run_daily

        owned = run_daily(request)
        raw: dict[str, Any] = {"summary": _wire(owned.summary), "tables": {}}
        for name in ("daily", "orders", "fills", "actions", "holdings"):
            frame = getattr(owned, name, None)
            raw["tables"][name] = (
                None
                if frame is None
                else {"columns": list(frame.columns), "rows": _wire(frame.to_dict("records"))}
            )
        ledger = owned.to_unified_ledger(portfolio_value=request.config.portfolio_value)
        raw["unified_ledger"] = {
            name: {
                "columns": list(getattr(ledger, name).columns),
                "rows": _wire(getattr(ledger, name).to_dict("records")),
            }
            for name in ledger.__dataclass_fields__
        }
        raw["owner_tables"] = {
            name: _owner_frame(getattr(owned, name, None))
            for name in ("daily", "orders", "fills", "actions", "holdings")
        }
        raw["owner_unified_ledger"] = {
            name: _owner_frame(getattr(ledger, name)) for name in ledger.__dataclass_fields__
        }
        raw["calendar_semantic_sha256"] = request.calendar.sha256
        raw["decision_clocks"] = cast(dict[str, Any], manifest_to_json(manifest)["settings"])[
            "decision_clocks"
        ]
        raw["schema"] = "daily-owner-result.v1"
        payload = json_bytes(raw)
        raw_hash = hashlib.sha256(payload).hexdigest()
        available = {
            "reports": raw["tables"]["orders"]["rows"],
            "fills": raw["tables"]["fills"]["rows"],
        }
        summary: dict[str, Any] = {"mode": request.mode, "daily_status": "unavailable"}
        if isinstance(owned, ExecutionAdjustedNavResult):
            available["daily"] = raw["tables"]["daily"]["rows"]
            available["fees"] = [
                {
                    k: row[k]
                    for k in (
                        "trade_date",
                        "symbol",
                        "side",
                        "cost_commission",
                        "cost_stamp_tax",
                        "cost_transfer_fee",
                    )
                }
                for row in raw["tables"]["fills"]["rows"]
            ]
            summary.update(raw["summary"]["execution_summary"])
            summary["daily_status"] = "available"
        tables = tuple(
            EvidenceTable(name, "available", tuple(available[name]), None)
            if name in available
            else EvidenceTable(
                name, "unavailable", (), "Daily owner does not supply this economic event ledger"
            )
            for name in TABLE_NAMES
        )
        result = ProductResult(
            "completed",
            hashlib.sha256(json_bytes(manifest_to_json(manifest))).hexdigest(),
            self.descriptor().identity,
            tables,
            summary,
            ArtifactRef(manifest.output_uri + ".native.json", raw_hash, "application/json"),
            NormalizationReceipt(
                "daily-adapter.v1",
                "daily-owner-result.v1",
                raw_hash,
                tuple(n for n in TABLE_NAMES if n not in available),
            ),
            None,
            None,
        )
        result_path, raw_path = output_paths(manifest.output_uri, context)
        write_new(raw_path, payload)
        write_new(result_path, json_bytes(result_to_json(result)))
        return result
