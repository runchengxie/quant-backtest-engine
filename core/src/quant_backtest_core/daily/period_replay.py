"""Calendar-bound diagnostic period replay of caller-chosen positions."""

from collections.abc import Mapping
from typing import Any, cast

import pandas as pd
from quant_backtest_engine.product.types import JsonValue

from ._position_backtest_config import (
    PositionBacktestConfig,
    PositionBacktestResult,
    _date_series,
    normalize_position_backtest_periods,
    normalize_position_backtest_pricing,
)
from ._position_backtest_engine import run_position_backtest
from .contracts import ExecutionCalendar


def run_period_replay(
    *,
    positions: pd.DataFrame,
    pricing: pd.DataFrame,
    periods: pd.DataFrame,
    calendar: ExecutionCalendar,
    config: Mapping[str, JsonValue],
) -> PositionBacktestResult:
    settings = PositionBacktestConfig(**cast(dict[str, Any], dict(config)))
    selected = normalize_position_backtest_periods(periods)
    prices = normalize_position_backtest_pricing(
        pricing,
        price_col=settings.price_col,
        entry_price_col=settings.entry_price_col,
        exit_price_col=settings.exit_price_col,
        tradable_col=settings.tradable_col,
        terminal_exit_price_col=settings.terminal_exit_price_col,
    )
    sessions = set(calendar.open_dates)
    price_dates = set(prices.trade_date.dt.strftime("%Y-%m-%d"))
    required = set(selected.entry_date_ts.dt.strftime("%Y-%m-%d")) | set(
        selected.exit_date_ts.dt.strftime("%Y-%m-%d")
    )
    if "planned_exit_date" in selected:
        required |= set(_date_series(selected.planned_exit_date).dropna().dt.strftime("%Y-%m-%d"))
    if not required <= sessions or not required <= price_dates or not price_dates <= sessions:
        raise ValueError(
            "explicit period boundaries and pricing require supplied calendar coverage"
        )
    if price_dates:
        expected = {d for d in sessions if min(price_dates) <= d <= max(price_dates)}
        if price_dates != expected:
            raise ValueError("diagnostic pricing omits supplied calendar sessions")
    return run_position_backtest(
        positions=positions, pricing=pricing, periods=periods, config=settings
    )
