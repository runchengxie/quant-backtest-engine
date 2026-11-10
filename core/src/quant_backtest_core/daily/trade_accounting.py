"""Pure portfolio drift, turnover, and transaction-cost accounting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd


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
