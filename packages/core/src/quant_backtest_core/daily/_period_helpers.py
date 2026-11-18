from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd

from .turnover import turnover_from_trade_weights


def _equal_weights(holdings: list[str]) -> pd.Series:
    if not holdings:
        return pd.Series(dtype=float)
    return pd.Series(np.repeat(1.0 / len(holdings), len(holdings)), index=holdings, dtype=float)


def normalize_position_weights(weights: pd.Series) -> pd.Series:
    if weights is None or weights.empty:
        return pd.Series(dtype=float)
    cleaned = pd.to_numeric(weights, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if cleaned.empty:
        return pd.Series(dtype=float)
    total = float(cleaned.sum())
    if not np.isfinite(total) or total <= 0:
        return _equal_weights(list(cleaned.index))
    return cleaned / total


def clean_position_weights(
    weights: pd.Series,
    *,
    preserve_gross_exposure: bool,
) -> pd.Series:
    """Clean weights while optionally preserving an intentional cash allocation."""

    if not preserve_gross_exposure:
        return normalize_position_weights(weights)
    if weights is None or weights.empty:
        return pd.Series(dtype=float)
    cleaned = pd.to_numeric(weights, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    cleaned = cleaned.loc[cleaned.abs() > 1e-12].astype(float)
    gross = float(cleaned.abs().sum())
    if not np.isfinite(gross) or gross > 1.0 + 1e-12:
        raise ValueError("Preserved target gross exposure must be finite and <= 1.0.")
    return cleaned


def _compute_trade_summary(
    prev_weights: pd.Series | None,
    prev_prices: pd.Series | None,
    prev_date: pd.Timestamp | None,
    target_weights: pd.Series,
    entry_date: pd.Timestamp,
    *,
    price_table: pd.DataFrame,
    preserve_gross_exposure: bool = False,
) -> tuple[float, float, float, pd.Series]:
    target_clean = clean_position_weights(
        target_weights,
        preserve_gross_exposure=preserve_gross_exposure,
    )

    if prev_weights is None:
        if target_clean.empty:
            return 0.0, 0.0, 0.0, pd.Series(dtype=float)
        trade_weights = target_clean.copy()
        turnover = turnover_from_trade_weights(trade_weights, is_initial=True)
        return (
            turnover.one_way_turnover,
            turnover.buy_weight,
            turnover.sell_weight,
            trade_weights,
        )
    if prev_weights.empty:
        if target_clean.empty:
            return 0.0, 0.0, 0.0, pd.Series(dtype=float)
        trade_weights = target_clean.copy()
        turnover = turnover_from_trade_weights(trade_weights)
        return (
            turnover.one_way_turnover,
            turnover.buy_weight,
            turnover.sell_weight,
            trade_weights,
        )

    prev_clean = clean_position_weights(
        prev_weights,
        preserve_gross_exposure=preserve_gross_exposure,
    )
    drift_weights = _drift_previous_weights(
        prev_clean,
        prev_prices,
        prev_date,
        entry_date,
        price_table=price_table,
        preserve_gross_exposure=preserve_gross_exposure,
    )
    all_ids = drift_weights.index.union(target_clean.index)
    drift_aligned = drift_weights.reindex(all_ids).fillna(0.0)
    target_aligned = target_clean.reindex(all_ids).fillna(0.0)
    trade_weights = target_aligned - drift_aligned
    turnover = turnover_from_trade_weights(trade_weights)
    return (
        turnover.one_way_turnover,
        turnover.buy_weight,
        turnover.sell_weight,
        trade_weights,
    )


def _drift_previous_weights(
    prev_clean: pd.Series,
    prev_prices: pd.Series | None,
    prev_date: pd.Timestamp | None,
    entry_date: pd.Timestamp,
    *,
    price_table: pd.DataFrame,
    preserve_gross_exposure: bool,
) -> pd.Series:
    if prev_prices is None or prev_date is None:
        return prev_clean
    prev_prices_valid = prev_prices.reindex(prev_clean.index)
    prev_prices_valid = prev_prices_valid[prev_prices_valid.notna()]
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
    drift_values = prev_clean * (current_prices / prev_prices_valid)
    drift_sum = float(drift_values.sum())
    if drift_sum <= 0:
        return prev_clean
    if not preserve_gross_exposure:
        return clean_position_weights(drift_values, preserve_gross_exposure=False)
    cash_weight = max(0.0, 1.0 - float(prev_clean.sum()))
    nav = cash_weight + drift_sum
    if nav <= 0:
        return prev_clean
    return clean_position_weights(
        drift_values / nav,
        preserve_gross_exposure=True,
    )
