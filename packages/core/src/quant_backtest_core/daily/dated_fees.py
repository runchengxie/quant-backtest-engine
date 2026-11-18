"""Immutable, date-aware execution fee schedules and pure quotations.

The module deliberately contains no broker or exchange defaults. Callers must
provide every rate, the schedule dates, and an explicit symbol-to-market map.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from itertools import pairwise
from types import MappingProxyType
from typing import Any, Literal

Side = Literal["buy", "sell"]


def _as_date(value: date | datetime | str, *, field: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be an ISO date") from exc
    raise TypeError(f"{field} must be a date, datetime, or ISO date string")


def _non_negative_finite(value: float, *, field: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{field} must be finite and non-negative")
    return number


@dataclass(frozen=True, init=False)
class FeeSchedulePeriod:
    """Fee rates active for one market on ``[start_date, end_date)``."""

    start_date: date
    end_date: date
    market: str
    buy_commission_bps: float
    sell_commission_bps: float
    minimum_commission: float
    sell_stamp_bps: float
    transfer_bps: float
    buy_spread_bps: float
    sell_spread_bps: float

    def __init__(
        self,
        start_date: date | datetime | str,
        end_date: date | datetime | str,
        market: str,
        buy_commission_bps: float,
        sell_commission_bps: float,
        minimum_commission: float,
        sell_stamp_bps: float,
        transfer_bps: float,
        buy_spread_bps: float,
        sell_spread_bps: float,
    ) -> None:
        start = _as_date(start_date, field="start_date")
        end = _as_date(end_date, field="end_date")
        if start >= end:
            raise ValueError("start_date must be before end_date")
        market = str(market)
        if not market or market != market.strip():
            raise ValueError("market must be a non-empty, canonical identifier")
        object.__setattr__(self, "start_date", start)
        object.__setattr__(self, "end_date", end)
        object.__setattr__(self, "market", market)
        rates = {
            "buy_commission_bps": buy_commission_bps,
            "sell_commission_bps": sell_commission_bps,
            "minimum_commission": minimum_commission,
            "sell_stamp_bps": sell_stamp_bps,
            "transfer_bps": transfer_bps,
            "buy_spread_bps": buy_spread_bps,
            "sell_spread_bps": sell_spread_bps,
        }
        for field, value in rates.items():
            object.__setattr__(
                self,
                field,
                _non_negative_finite(value, field=field),
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "market": self.market,
            "buy_commission_bps": self.buy_commission_bps,
            "sell_commission_bps": self.sell_commission_bps,
            "minimum_commission": self.minimum_commission,
            "sell_stamp_bps": self.sell_stamp_bps,
            "transfer_bps": self.transfer_bps,
            "buy_spread_bps": self.buy_spread_bps,
            "sell_spread_bps": self.sell_spread_bps,
        }


@dataclass(frozen=True)
class DatedFeeSchedule:
    """Validated collection of non-overlapping market fee periods."""

    periods: tuple[FeeSchedulePeriod, ...]

    def __post_init__(self) -> None:
        periods = tuple(self.periods)
        if not periods:
            raise ValueError("periods must contain at least one fee period")
        if not all(isinstance(period, FeeSchedulePeriod) for period in periods):
            raise TypeError("periods must contain only FeeSchedulePeriod values")
        object.__setattr__(self, "periods", periods)
        by_market: dict[str, list[FeeSchedulePeriod]] = {}
        for period in periods:
            by_market.setdefault(period.market, []).append(period)
        for market, market_periods in by_market.items():
            ordered = sorted(market_periods, key=lambda item: item.start_date)
            for previous, current in pairwise(ordered):
                if current.start_date < previous.end_date:
                    raise ValueError(f"overlapping fee periods for market {market!r}")

    def resolve(self, trade_date: date | datetime | str, *, market: str) -> FeeSchedulePeriod:
        when = _as_date(trade_date, field="trade_date")
        matches = [
            period
            for period in self.periods
            if period.market == market and period.start_date <= when < period.end_date
        ]
        if not matches:
            raise ValueError(f"no fee period for market {market!r} on {when.isoformat()}")
        if len(matches) != 1:
            raise ValueError(f"ambiguous fee periods for market {market!r} on {when.isoformat()}")
        return matches[0]


@dataclass(frozen=True, init=False)
class FeeQuoteContext:
    """Complete context needed to quote one incremental actual or preview fill."""

    trade_date: date
    side: Side
    symbol: str
    market: str
    executed_notional: float
    cumulative_group_notional: float = 0.0

    def __init__(
        self,
        trade_date: date | datetime | str,
        side: str,
        symbol: str,
        market: str,
        executed_notional: float,
        cumulative_group_notional: float = 0.0,
    ) -> None:
        object.__setattr__(self, "trade_date", _as_date(trade_date, field="trade_date"))
        if side not in ("buy", "sell"):
            raise ValueError("side must be exactly 'buy' or 'sell'")
        if not symbol or symbol != symbol.strip():
            raise ValueError("symbol must be a non-empty, canonical identifier")
        if not market or market != market.strip():
            raise ValueError("market must be a non-empty, canonical identifier")
        object.__setattr__(self, "side", side)
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "market", market)
        object.__setattr__(
            self,
            "executed_notional",
            _non_negative_finite(executed_notional, field="executed_notional"),
        )
        object.__setattr__(
            self,
            "cumulative_group_notional",
            _non_negative_finite(
                cumulative_group_notional,
                field="cumulative_group_notional",
            ),
        )


@dataclass(frozen=True)
class DatedFeeQuote:
    """Auditable component quote for an incremental fill."""

    commission: float
    stamp_tax: float
    transfer_fee: float
    spread_cost: float
    market: str
    period_start: date
    period_end: date
    cumulative_group_notional_before: float
    cumulative_group_notional_after: float

    @property
    def total_cost(self) -> float:
        return float(self.commission + self.stamp_tax + self.transfer_fee + self.spread_cost)


@dataclass(frozen=True)
class DatedTradeFeeModel:
    """Reusable dated schedule with immutable symbol market identities."""

    schedule: DatedFeeSchedule
    symbol_markets: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.schedule, DatedFeeSchedule):
            raise TypeError("schedule must be a DatedFeeSchedule")
        symbol_markets: dict[str, str] = {}
        for symbol, market in self.symbol_markets.items():
            if not symbol or symbol != symbol.strip():
                raise ValueError("symbol market mapping keys must be canonical identifiers")
            if not market or market != market.strip():
                raise ValueError("symbol market mapping values must be canonical identifiers")
            symbol_markets[str(symbol)] = str(market)
        object.__setattr__(self, "symbol_markets", MappingProxyType(symbol_markets))

    def market_for(self, symbol: str) -> str:
        try:
            return self.symbol_markets[symbol]
        except KeyError as exc:
            raise ValueError(f"missing market mapping for symbol {symbol!r}") from exc

    def quote(self, context: FeeQuoteContext) -> DatedFeeQuote:
        if not isinstance(context, FeeQuoteContext):
            raise TypeError("context must be a FeeQuoteContext")
        mapped_market = self.market_for(context.symbol)
        if context.market != mapped_market:
            raise ValueError(
                f"market mismatch for symbol {context.symbol!r}: "
                f"context={context.market!r}, mapping={mapped_market!r}"
            )
        period = self.schedule.resolve(context.trade_date, market=context.market)
        amount = context.executed_notional
        before = context.cumulative_group_notional
        after = before + amount
        commission_bps = (
            period.buy_commission_bps if context.side == "buy" else period.sell_commission_bps
        )
        accrued_before = (
            0.0
            if before == 0.0
            else max(before * commission_bps / 10_000.0, period.minimum_commission)
        )
        accrued_after = (
            0.0
            if after == 0.0
            else max(after * commission_bps / 10_000.0, period.minimum_commission)
        )
        return DatedFeeQuote(
            commission=max(accrued_after - accrued_before, 0.0),
            stamp_tax=(
                amount * period.sell_stamp_bps / 10_000.0 if context.side == "sell" else 0.0
            ),
            transfer_fee=amount * period.transfer_bps / 10_000.0,
            spread_cost=(
                amount
                * (period.buy_spread_bps if context.side == "buy" else period.sell_spread_bps)
                / 10_000.0
            ),
            market=context.market,
            period_start=period.start_date,
            period_end=period.end_date,
            cumulative_group_notional_before=before,
            cumulative_group_notional_after=after,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "name": "dated",
            "periods": [period.as_dict() for period in self.schedule.periods],
            "symbol_markets": dict(sorted(self.symbol_markets.items())),
        }


__all__ = [
    "DatedFeeQuote",
    "DatedFeeSchedule",
    "DatedTradeFeeModel",
    "FeeQuoteContext",
    "FeeSchedulePeriod",
    "Side",
]
