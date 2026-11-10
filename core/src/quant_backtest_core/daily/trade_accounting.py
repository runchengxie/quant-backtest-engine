"""Pure portfolio drift, turnover, and transaction-cost accounting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import numpy as np
import pandas as pd

from ._period_helpers import normalize_position_weights


@dataclass(frozen=True)
class TradeCostConfig:
    """Rates applied to executed portfolio notional, expressed as decimals."""

    commission_rate: float = 0.0
    stamp_tax_rate: float = 0.0
    slippage_rate: float = 0.0


@dataclass(frozen=True)
class TradeAccounting:
    turnover: float
    commission: float
    stamp_tax: float
    slippage: float
    total_cost: float
    executed_weights: pd.Series
    pending_weights: pd.Series


def _clean_weights(weights: pd.Series | Mapping[str, float] | None) -> pd.Series:
    if weights is None:
        return pd.Series(dtype=float)
    values = pd.Series(weights, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    values = values[values > 0]
    total = float(values.sum())
    if total <= 0:
        return pd.Series(dtype=float)
    return values / total


def drift_weights(
    previous_weights: pd.Series | Mapping[str, float] | None,
    previous_prices: pd.Series | Mapping[str, float] | None,
    current_prices: pd.Series | Mapping[str, float] | None,
) -> pd.Series:
    """Mark prior weights to current prices and renormalize the available holdings."""

    weights = _clean_weights(previous_weights)
    if weights.empty or previous_prices is None or current_prices is None:
        return weights
    previous = pd.Series(previous_prices, dtype=float).reindex(weights.index)
    current = pd.Series(current_prices, dtype=float).reindex(weights.index)
    valid = previous.gt(0) & current.gt(0) & previous.notna() & current.notna()
    if not valid.any():
        return weights
    drifted = weights[valid] * current[valid] / previous[valid]
    return _clean_weights(drifted)


def compute_trade_accounting(
    previous_weights: pd.Series | Mapping[str, float] | None,
    target_weights: pd.Series | Mapping[str, float],
    previous_prices: pd.Series | Mapping[str, float] | None,
    current_prices: pd.Series | Mapping[str, float] | None,
    tradable: pd.Series | Mapping[str, bool],
    costs: TradeCostConfig | None = None,
) -> TradeAccounting:
    """Compute executable trades, pending trades, turnover, and transaction costs."""

    costs = costs or TradeCostConfig()
    target = _clean_weights(target_weights)
    drifted = drift_weights(previous_weights, previous_prices, current_prices)
    symbols = drifted.index.union(target.index)
    trade = target.reindex(symbols, fill_value=0.0) - drifted.reindex(symbols, fill_value=0.0)
    can_trade = pd.Series(tradable, dtype=bool).reindex(symbols, fill_value=False)
    executed = trade[can_trade & trade.ne(0)]
    pending = trade[~can_trade & trade.ne(0)]

    sells = -executed.clip(upper=0.0)
    turnover = 0.5 * float(executed.abs().sum())
    commission = float(executed.abs().sum()) * costs.commission_rate
    stamp_tax = float(sells.sum()) * costs.stamp_tax_rate
    slippage = float(executed.abs().sum()) * costs.slippage_rate
    total_cost = commission + stamp_tax + slippage
    return TradeAccounting(
        turnover=turnover,
        commission=commission,
        stamp_tax=stamp_tax,
        slippage=slippage,
        total_cost=total_cost,
        executed_weights=executed,
        pending_weights=pending,
    )


def compute_trade_accounting_frame(
    frame: pd.DataFrame, costs: TradeCostConfig | None = None
) -> TradeAccounting:
    """Evaluate one content-addressed table of portfolio weights and marks."""
    required = {
        "symbol",
        "previous_weight",
        "target_weight",
        "previous_price",
        "current_price",
        "tradable",
    }
    if set(frame.columns) != required:
        raise ValueError("trade accounting input has invalid columns")
    if frame.symbol.isna().any() or frame.symbol.duplicated().any():
        raise ValueError("trade accounting symbols must be unique and non-null")
    if (
        frame.tradable.isna().any()
        or not frame.tradable.map(lambda value: isinstance(value, bool)).all()
    ):
        raise ValueError("tradable must contain booleans")
    indexed = frame.set_index("symbol")
    for name in ("previous_weight", "target_weight", "previous_price", "current_price"):
        values = pd.to_numeric(indexed[name], errors="coerce")
        if values.isna().ne(indexed[name].isna()).any():
            raise ValueError(f"{name} must contain numeric values or null")
        indexed[name] = values
    return compute_trade_accounting(
        indexed.previous_weight.dropna(),
        indexed.target_weight.dropna(),
        indexed.previous_price.dropna(),
        indexed.current_price.dropna(),
        indexed.tradable,
        costs,
    )


__all__ = [
    "TradeAccounting",
    "TradeCostConfig",
    "compute_trade_accounting",
    "compute_trade_accounting_frame",
    "drift_weights",
]


def compute_trade_summary(
    prev_weights: pd.Series | None,
    prev_prices: pd.Series | None,
    prev_date: pd.Timestamp | None,
    target_weights: pd.Series,
    entry_date: pd.Timestamp,
    *,
    price_table: pd.DataFrame,
) -> tuple[float, float, float, pd.Series]:
    """Return total, entry and exit turnover plus signed trade weights."""

    if target_weights is None or target_weights.empty:
        return 0.0, 0.0, 0.0, pd.Series(dtype=float)

    target_clean = normalize_position_weights(target_weights)
    if target_clean.empty:
        return 0.0, 0.0, 0.0, pd.Series(dtype=float)

    if prev_weights is None or prev_weights.empty:
        trade_weights = target_clean.copy()
        traded = float(trade_weights.abs().sum())
        return traded, traded, 0.0, trade_weights

    prev_clean = normalize_position_weights(prev_weights)
    drift_weights = drift_previous_weights(
        prev_clean,
        prev_prices,
        prev_date,
        entry_date,
        price_table=price_table,
    )
    all_ids = drift_weights.index.union(target_clean.index)
    drift_aligned = drift_weights.reindex(all_ids).fillna(0.0)
    target_aligned = target_clean.reindex(all_ids).fillna(0.0)
    trade_weights = target_aligned - drift_aligned
    entry_turnover = float(trade_weights.clip(lower=0.0).sum())
    exit_turnover = float((-trade_weights.clip(upper=0.0)).sum())
    turnover = 0.5 * float(np.abs(trade_weights).sum())
    return turnover, entry_turnover, exit_turnover, trade_weights


def drift_previous_weights(
    prev_clean: pd.Series,
    prev_prices: pd.Series | None,
    prev_date: pd.Timestamp | None,
    entry_date: pd.Timestamp,
    *,
    price_table: pd.DataFrame,
) -> pd.Series:
    """Drift normalized prior weights to entry-date prices when prices are available."""

    if prev_prices is None or prev_date is None:
        return prev_clean
    prev_prices_valid = prev_prices.reindex(prev_clean.index)
    prev_prices_valid = cast(pd.Series, prev_prices_valid[prev_prices_valid.notna()])
    if prev_prices_valid.empty or entry_date not in price_table.index:
        return prev_clean
    prev_clean = prev_clean.reindex(prev_prices_valid.index).dropna()
    current_prices = cast(pd.Series, price_table.loc[entry_date, prev_prices_valid.index])
    valid_prev = current_prices.notna()
    prev_prices_valid = cast(pd.Series, prev_prices_valid[valid_prev])
    current_prices = current_prices[valid_prev]
    prev_clean = prev_clean.reindex(prev_prices_valid.index).dropna()
    if prev_prices_valid.empty or prev_clean.empty:
        return prev_clean
    drift = prev_clean * (current_prices / prev_prices_valid)
    if float(drift.sum()) <= 0:
        return prev_clean
    return normalize_position_weights(drift)


# Compatibility aliases retain the separate legacy normalization and initial semantics.
_compute_trade_summary = compute_trade_summary
_drift_previous_weights = drift_previous_weights

__all__.extend(
    [
        "_compute_trade_summary",
        "_drift_previous_weights",
        "compute_trade_summary",
        "drift_previous_weights",
    ]
)
