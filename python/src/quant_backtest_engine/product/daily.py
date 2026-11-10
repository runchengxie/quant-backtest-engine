"""Standard-library daily-input.v1 transport validation; no core import."""

import math
from datetime import date
from decimal import Decimal
from collections.abc import Mapping

from .types import ArtifactRef, ClockSet
from .validation import _array, _decimal, _nonempty, _ns, _shape

CONFIG_DECIMALS = (
    "portfolio_value",
    "participation_rate",
    "liquidity_notional_multiplier",
    "lot_tolerance",
)
CONFIG_BOOLEANS = (
    "enabled",
    "enforce_t1",
    "enforce_price_limits",
    "enforce_listing_status",
)
CONFIG_INTS = (
    "buy_max_days",
    "zero_fill_abort_days_buy",
    "round_lot",
    "sell_round_lot",
)
CONFIG_TEXT = (
    "unfilled_buy_action",
    "unfilled_sell_action",
    "limit_up_col",
    "limit_down_col",
    "listing_status_col",
)
FEE_DECIMALS = (
    "buy_commission_bps",
    "sell_commission_bps",
    "sell_stamp_duty_bps",
    "transfer_fee_bps",
    "min_commission",
    "buy_slippage_bps",
    "sell_slippage_bps",
    "portfolio_value",
)
DATED_DECIMALS = (
    "buy_commission_bps",
    "sell_commission_bps",
    "minimum_commission",
    "sell_stamp_bps",
    "transfer_bps",
    "buy_spread_bps",
    "sell_spread_bps",
)
LAYOUT = (
    "price_col",
    "mark_price_col",
    "tradable_col",
    "buy_tradable_col",
    "sell_tradable_col",
    "currency",
    "quantity_unit",
    "price_unit",
    "liquidity_units",
)
TIMING = (
    "signal_ns",
    "earliest_order_ns",
    "execution_window_start_ns",
    "execution_window_end_ns",
    "timing_policy_id",
    "trading_calendar_ref",
)


def _number(value, key):
    _decimal(value, key)
    number = float(value)
    if not math.isfinite(number) or (number == 0 and Decimal(value) != 0):
        raise ValueError(f"{key} is outside the daily owner's finite numerical range")


def _day(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("daily dates require YYYY-MM-DD")


def validate_daily_input(manifest):
    _shape(manifest.initial_account, ("cash",))
    _number(manifest.initial_account["cash"], "cash")
    if Decimal(manifest.initial_account["cash"]) <= 0:
        raise ValueError("daily cash must be positive")
    _shape(
        manifest.settings,
        ("mode", "config", "layout", "decision_clocks", "decision_timing", "fee_model"),
    )
    settings = manifest.settings
    if settings["mode"] not in ("ideal", "capacity", "adjusted", "sequenced"):
        raise ValueError("unsupported daily mode")
    config = settings["config"]
    _shape(
        config,
        CONFIG_DECIMALS
        + CONFIG_BOOLEANS
        + CONFIG_INTS
        + CONFIG_TEXT
        + ("liquidity_cols", "sell_max_days"),
    )
    for key in CONFIG_DECIMALS:
        _number(config[key], key)
    for key in CONFIG_BOOLEANS:
        if type(config[key]) is not bool:
            raise ValueError(f"{key} must be boolean")
    for key in CONFIG_INTS:
        if config[key] is not None and (
            type(config[key]) is not int or config[key] <= 0
        ):
            raise ValueError(f"{key} must be positive integer or null")
    if settings["mode"] == "capacity":
        for name, supported in (
            ("unfilled_buy_action", "keep_cash"),
            ("unfilled_sell_action", "keep_position"),
        ):
            if config[name] != supported:
                raise ValueError(f"capacity mode requires {name}={supported}")
        unsupported = [
            key
            for key in ("enforce_price_limits", "enforce_listing_status", "enforce_t1")
            if config[key]
        ]
        unsupported.extend(
            key for key in ("round_lot", "sell_round_lot") if config[key] is not None
        )
        if unsupported:
            raise ValueError(
                "capacity mode does not support "
                + ", ".join(unsupported)
                + "; use adjusted or sequenced mode"
            )
    if type(config["buy_max_days"]) is not int:
        raise ValueError("buy_max_days must be integer")
    if config["sell_max_days"] != "until_next_rebalance" and (
        type(config["sell_max_days"]) is not int or config["sell_max_days"] <= 0
    ):
        raise ValueError("invalid sell_max_days")
    for key in CONFIG_TEXT:
        if config[key] is not None:
            _nonempty(config[key], key)
    for column in _array(config["liquidity_cols"], "liquidity_cols"):
        _nonempty(column, "liquidity column")
    if Decimal(config["portfolio_value"]) != Decimal(manifest.initial_account["cash"]):
        raise ValueError("portfolio_value must equal initial cash")
    layout = settings["layout"]
    _shape(layout, LAYOUT)
    if layout["currency"] != manifest.currency:
        raise ValueError("layout currency differs from manifest")
    for key in LAYOUT[:-1]:
        if layout[key] is not None:
            _nonempty(layout[key], key)
    unit_columns = set()
    for item in _array(layout["liquidity_units"], "liquidity_units"):
        _shape(item, ("column", "unit"))
        _nonempty(item["column"], "column")
        _nonempty(item["unit"], "unit")
        if item["column"] in unit_columns:
            raise ValueError("duplicate liquidity unit column")
        unit_columns.add(item["column"])
    if unit_columns != set(config["liquidity_cols"]):
        raise ValueError("liquidity units must exactly cover selected columns")
    multiplier = float(config["liquidity_notional_multiplier"])
    unit = (
        layout["currency"]
        if multiplier == 1
        else f"{multiplier:g} {layout['currency']}"
    )
    if any(item["unit"] != unit for item in layout["liquidity_units"]):
        raise ValueError("liquidity unit disagrees with currency and multiplier")
    for mapping, timing in (
        (settings["decision_clocks"], False),
        (settings["decision_timing"], True),
    ):
        if not isinstance(mapping, Mapping):
            raise ValueError("decision metadata must be objects")
        for day, value in mapping.items():
            _day(day)
            _shape(value, TIMING if timing else tuple(ClockSet.__dataclass_fields__))
            for key, entry in value.items():
                if key.endswith("_ns") and entry is not None:
                    _ns(entry, key)
    if set(dict(manifest.inputs)) | set(manifest.inline_inputs) != {
        "positions",
        "pricing",
    }:
        raise ValueError("daily requires exactly positions and pricing")
    for row in manifest.inline_inputs.get("positions", ()):
        _shape(row, ("rebalance_date", "entry_date", "symbol", "weight"), ("side",))
        _day(row["rebalance_date"])
        _day(row["entry_date"])
        _nonempty(row["symbol"], "symbol")
        _number(row["weight"], "weight")
    controls = {
        layout[k]
        for k in ("tradable_col", "buy_tradable_col", "sell_tradable_col")
        if layout[k] is not None
    }
    if config["enforce_price_limits"]:
        controls.update((config["limit_up_col"], config["limit_down_col"]))
    numbers = {layout["price_col"], *config["liquidity_cols"]}
    columns = {"trade_date", "symbol"} | numbers | controls
    if config["enforce_listing_status"]:
        columns.add(config["listing_status_col"])
    for row in manifest.inline_inputs.get("pricing", ()):
        _shape(row, tuple(columns))
        _day(row["trade_date"])
        _nonempty(row["symbol"], "symbol")
        for key in numbers:
            if row[key] is not None:
                _number(row[key], key)
        for key in controls:
            if row[key] is not None and type(row[key]) is not bool:
                raise ValueError(f"{key} must be boolean or null")
    tapes = dict(manifest.tapes)
    if set(tapes) != {"corporate_actions"}:
        raise ValueError("daily requires explicit corporate_actions tape only")
    actions = tapes["corporate_actions"]
    if not isinstance(actions, ArtifactRef):
        for row in actions:
            _shape(
                row,
                (
                    "event_id",
                    "symbol",
                    "available_date",
                    "record_date",
                    "ex_date",
                    "cash_per_share",
                    "cash_pay_date",
                    "stock_per_share",
                    "stock_tradable_date",
                    "withholding_rate",
                ),
            )
            for key in ("cash_per_share", "stock_per_share", "withholding_rate"):
                _number(row[key], key)
            for key in (
                "available_date",
                "record_date",
                "ex_date",
                "cash_pay_date",
                "stock_tradable_date",
            ):
                if row[key] is not None:
                    _day(row[key])
    fee = settings["fee_model"]
    if fee is not None:
        if not isinstance(fee, Mapping):
            raise ValueError("fee_model must be an object or null")
        if fee.get("kind") == "detailed":
            _shape(fee, ("kind",) + FEE_DECIMALS)
            for key in FEE_DECIMALS:
                _number(fee[key], key)
        elif fee.get("kind") == "dated":
            _shape(fee, ("kind", "periods", "symbol_markets"))
            if not isinstance(fee["symbol_markets"], Mapping):
                raise ValueError("symbol_markets must be object")
            for row in _array(fee["periods"], "periods"):
                _shape(row, ("start_date", "end_date", "market") + DATED_DECIMALS)
                _day(row["start_date"])
                _day(row["end_date"])
                for key in DATED_DECIMALS:
                    _number(row[key], key)
        else:
            raise ValueError("unsupported fee model registry key")
