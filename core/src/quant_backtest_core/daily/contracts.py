"""Neutral daily metadata, independent of any daily execution runner."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from types import MappingProxyType
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from quant_backtest_engine.product.types import ClockSet

from quant_backtest_core._minute.corporate_actions import (
    CorporateAction,
    normalize_corporate_actions,
)

from .execution_sim.config import ExecutionSimConfig

_NS = re.compile(r"-?(0|[1-9][0-9]*)\Z")


def strict_date(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("date must be a strict YYYY-MM-DD string")
    date.fromisoformat(value)
    return value


def _text(value: str, name: str) -> None:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{name} must be explicit normalized text")


def _ns(value: str | None) -> None:
    if value is not None and (not isinstance(value, str) or not _NS.fullmatch(value)):
        raise ValueError("clock must be an exact UTC-ns decimal string or None")


def _ordered(left: str | None, right: str | None, label: str) -> None:
    if left is not None and right is not None and int(left) > int(right):
        raise ValueError(f"reversed {label}")


def utc_ns(value: datetime | pd.Timestamp) -> str:
    """Convert aware source time exactly, without floating-point epoch seconds."""
    timestamp = pd.Timestamp(value)
    if timestamp is pd.NaT or timestamp.tzinfo is None:
        raise ValueError("source time must be timezone-aware")
    return str(timestamp.as_unit("ns").value)


def _calendar_bytes(timezone: str, open_dates: tuple[str, ...]) -> bytes:
    return (
        json.dumps(
            {"schema": "execution-calendar.v1", "timezone": timezone, "open_dates": open_dates},
            ensure_ascii=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")


@dataclass(frozen=True)
class ExecutionCalendar:
    timezone: str
    open_dates: tuple[str, ...]
    sha256: str

    def __post_init__(self) -> None:
        _text(self.timezone, "timezone")
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must identify an installed IANA zone") from exc
        dates = tuple(sorted({strict_date(day) for day in self.open_dates}))
        object.__setattr__(self, "open_dates", dates)
        if self.sha256 != hashlib.sha256(self.semantic_bytes()).hexdigest():
            raise ValueError("execution calendar semantic digest mismatch")

    def semantic_bytes(self) -> bytes:
        return _calendar_bytes(self.timezone, self.open_dates)

    @classmethod
    def from_dates(cls, timezone: str, open_dates: Sequence[str]) -> ExecutionCalendar:
        dates = tuple(sorted({strict_date(day) for day in open_dates}))
        digest = hashlib.sha256(_calendar_bytes(timezone, dates)).hexdigest()
        return cls(timezone, dates, digest)


@dataclass(frozen=True)
class DailyInputLayout:
    price_col: str
    mark_price_col: str
    tradable_col: str | None
    buy_tradable_col: str | None
    sell_tradable_col: str | None
    currency: str
    quantity_unit: str
    price_unit: str
    liquidity_units: Mapping[str, str]

    def __post_init__(self) -> None:
        for name in ("price_col", "mark_price_col", "currency", "quantity_unit", "price_unit"):
            _text(getattr(self, name), name)
        for name in ("tradable_col", "buy_tradable_col", "sell_tradable_col"):
            if getattr(self, name) is not None:
                _text(getattr(self, name), name)
        if self.mark_price_col != self.price_col:
            raise ValueError("this daily owner requires mark_price_col == price_col")
        units = dict(self.liquidity_units)
        for key, value in units.items():
            _text(key, "liquidity column")
            _text(value, "liquidity unit")
        object.__setattr__(self, "liquidity_units", MappingProxyType(units))


@dataclass(frozen=True)
class DailyDecisionTiming:
    signal_ns: str | None
    earliest_order_ns: str | None
    execution_window_start_ns: str | None
    execution_window_end_ns: str | None
    timing_policy_id: str | None
    trading_calendar_ref: str | None

    def __post_init__(self) -> None:
        for value in (
            self.signal_ns,
            self.earliest_order_ns,
            self.execution_window_start_ns,
            self.execution_window_end_ns,
        ):
            _ns(value)
        for name in ("timing_policy_id", "trading_calendar_ref"):
            if getattr(self, name) is not None:
                _text(getattr(self, name), name)
        start, end = self.execution_window_start_ns, self.execution_window_end_ns
        if (start is None) != (end is None):
            raise ValueError("execution window bounds must be supplied together")
        _ordered(start, end, "execution window")
        _ordered(self.earliest_order_ns, end, "earliest order/window end")

    @property
    def entry_ns(self) -> str | None:
        bounds = [
            v for v in (self.earliest_order_ns, self.execution_window_start_ns) if v is not None
        ]
        return max(bounds, key=int) if bounds else None

    def validate_clocks(self, clocks: ClockSet) -> None:
        _ordered(clocks.information_ns, self.signal_ns, "information/signal")
        _ordered(self.signal_ns, clocks.decision_ns, "signal/decision")
        _ordered(clocks.decision_ns, clocks.valuation_ns, "decision/valuation")
        _ordered(clocks.decision_ns, self.earliest_order_ns, "decision/earliest order")
        _ordered(clocks.decision_ns, self.execution_window_start_ns, "decision/window start")
        _ordered(self.execution_window_end_ns, clocks.valuation_ns, "window end/valuation")
        if self.entry_ns is not None and clocks.entry_ns != self.entry_ns:
            raise ValueError("entry must equal the earliest eligible source bound")


@dataclass(frozen=True)
class DailyReplayRequest:
    positions: pd.DataFrame
    pricing: pd.DataFrame
    calendar: ExecutionCalendar
    decision_clocks: Mapping[str, ClockSet]
    config: ExecutionSimConfig
    mode: Literal["ideal", "capacity", "adjusted", "sequenced"]
    price_basis: Literal["raw", "adjusted"]
    corporate_actions: tuple[CorporateAction, ...]
    fee_model: object | None = None
    layout: DailyInputLayout = field(kw_only=True)
    decision_timing: Mapping[str, DailyDecisionTiming] = field(kw_only=True)

    def __post_init__(self) -> None:
        if self.mode not in ("ideal", "capacity", "adjusted", "sequenced"):
            raise ValueError("unsupported daily mode")
        if self.price_basis not in ("raw", "adjusted"):
            raise ValueError("unsupported price basis")
        if not isinstance(self.config, ExecutionSimConfig):
            raise TypeError("config must be the owned ExecutionSimConfig")
        if "rebalance_date" not in self.positions:
            raise ValueError("positions require rebalance_date")
        dates = {strict_date(value) for value in self.positions["rebalance_date"]}
        clocks = dict(self.decision_clocks)
        timing = dict(self.decision_timing)
        for day in set(clocks) | set(timing):
            strict_date(day)
        if set(clocks) != dates or not set(timing) <= dates:
            raise ValueError(
                "decision clocks must exactly cover rebalance dates; timing keys must match targets"
            )
        for day, clock in clocks.items():
            if not isinstance(clock, ClockSet):
                raise TypeError("decision clocks must contain ClockSet values")
            if any(v is None for v in (clock.information_ns, clock.decision_ns, clock.entry_ns)):
                raise ValueError(
                    "executable targets require information, decision and entry evidence"
                )
            _ordered(clock.information_ns, clock.decision_ns, "information/decision")
            _ordered(clock.decision_ns, clock.entry_ns, "decision/entry")
            _ordered(clock.available_ns, clock.decision_ns, "available/decision")
            if day in timing:
                timing[day].validate_clocks(clock)
        object.__setattr__(self, "decision_clocks", MappingProxyType(clocks))
        object.__setattr__(self, "decision_timing", MappingProxyType(timing))
        actions = tuple(self.corporate_actions)
        object.__setattr__(self, "corporate_actions", actions)
        self.legacy_corporate_actions()
        self._validate_layout()

    def _validate_layout(self) -> None:
        layout, config = self.layout, self.config
        quantity = f"{self.price_basis}_share"
        if layout.quantity_unit != quantity or layout.price_unit != f"{layout.currency}/{quantity}":
            raise ValueError("price and quantity units must agree with currency and share basis")
        selected = {layout.price_col}
        selected.update(
            v
            for v in (layout.tradable_col, layout.buy_tradable_col, layout.sell_tradable_col)
            if v is not None
        )
        if config.enabled:
            selected.update(config.liquidity_cols)
            unit = (
                layout.currency
                if config.liquidity_notional_multiplier == 1
                else f"{config.liquidity_notional_multiplier:g} {layout.currency}"
            )
            if any(layout.liquidity_units.get(col) != unit for col in config.liquidity_cols):
                raise ValueError(
                    "every selected liquidity unit must agree with currency and multiplier"
                )
            if config.enforce_price_limits:
                if config.limit_up_col is None or config.limit_down_col is None:
                    raise ValueError("enabled price limits require explicit selectors")
                selected.update((config.limit_up_col, config.limit_down_col))
            if config.enforce_listing_status:
                if config.listing_status_col is None:
                    raise ValueError("enabled listing status requires an explicit selector")
                selected.add(config.listing_status_col)
        if missing := selected - set(self.pricing.columns):
            raise ValueError(f"missing selected pricing columns: {sorted(missing)}")

    def legacy_corporate_actions(self) -> tuple[CorporateAction, ...] | None:
        """Neutral empty means no request; direct legacy empty retains its opt-in."""
        return normalize_corporate_actions(self.corporate_actions or None, self.price_basis)


@dataclass(frozen=True)
class DailySummaryEvidence:
    daily_status: Literal["available", "unavailable"]
    fills_status: Literal["available", "unavailable"]
    valuation_complete_by_row: tuple[bool | None, ...]
    external_flow_zero_by_row: tuple[bool | None, ...]
    schema: Literal["daily-summary-evidence.v1"] = field(
        default="daily-summary-evidence.v1", kw_only=True
    )

    def __post_init__(self) -> None:
        if self.schema != "daily-summary-evidence.v1":
            raise ValueError("unsupported daily summary evidence schema")
        if self.daily_status not in ("available", "unavailable") or self.fills_status not in (
            "available",
            "unavailable",
        ):
            raise ValueError("invalid evidence status")
        for name in ("valuation_complete_by_row", "external_flow_zero_by_row"):
            values = tuple(getattr(self, name))
            if any(value is not None and type(value) is not bool for value in values):
                raise ValueError("row evidence must contain bool or None")
            if self.daily_status == "unavailable" and any(v is not None for v in values):
                raise ValueError("unavailable daily evidence cannot assert row support")
            object.__setattr__(self, name, values)


@dataclass(frozen=True)
class ExecutionSummary:
    daily_return: tuple[float | None, ...]
    cumulative_return: float | None
    turnover: float | None
    total_fees: float | None
    valuation_complete: bool
