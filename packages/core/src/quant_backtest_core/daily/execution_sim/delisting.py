"""Reconcile simulated fill quantities before an exchange delisting date."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


def _quantity_trades(
    fills: pd.DataFrame, marks: pd.DataFrame, price_col: str, symbols: set[str]
) -> pd.DataFrame:
    trades = fills[["trade_date", "symbol", "side", "filled_notional"]].copy()
    trades["trade_date"] = pd.to_datetime(trades.trade_date).dt.strftime("%Y%m%d")
    trades["symbol"] = trades.symbol.astype(str)
    trades = trades.loc[trades.symbol.isin(symbols)].merge(
        marks, on=["trade_date", "symbol"], how="left", validate="many_to_one"
    )
    if trades.empty:
        trades["quantity"] = pd.Series(dtype=float)
        return trades
    trades[price_col] = pd.to_numeric(trades[price_col], errors="coerce")
    trades["filled_notional"] = pd.to_numeric(trades.filled_notional, errors="coerce")
    bad_values = (
        trades[[price_col, "filled_notional"]].isna().any().any()
        or trades[price_col].le(0).any()
        or trades.filled_notional.le(0).any()
    )
    if bad_values:
        raise ValueError("delisting fill has no valid execution mark or notional")
    if not trades.side.isin(["buy", "sell"]).all():
        raise ValueError("delisting fill has unsupported side")
    quantity = trades.filled_notional.div(trades[price_col])
    trades["quantity"] = quantity.where(trades.side.eq("buy"), -quantity)
    return trades


def audit_delisting_exits(
    fills: pd.DataFrame,
    pricing: pd.DataFrame,
    delist_dates: Mapping[str, str],
    *,
    price_col: str,
    tolerance: float = 1e-8,
) -> pd.DataFrame:
    """Require zero simulated shares before delisting and no later fill.

    This reconstructs shares from ``filled_notional / execution mark``. It does
    not establish real settlement or resolve unmodeled corporate actions.
    """
    required_prices = {"trade_date", "symbol", price_col}
    required_fills = {"trade_date", "symbol", "side", "filled_notional"}
    if missing := required_prices - set(pricing):
        raise ValueError(f"pricing is missing {sorted(missing)}")
    if missing := required_fills - set(fills):
        raise ValueError(f"fills are missing {sorted(missing)}")
    if tolerance < 0:
        raise ValueError("tolerance must be nonnegative")
    marks = pricing[["trade_date", "symbol", price_col]].copy()
    marks["trade_date"] = pd.to_datetime(marks.trade_date).dt.strftime("%Y%m%d")
    marks["symbol"] = marks.symbol.astype(str)
    if marks.duplicated(["trade_date", "symbol"]).any():
        raise ValueError("pricing has duplicate symbol/date keys")
    if marks.empty:
        raise ValueError("pricing has no trading dates")
    last_day = str(marks.trade_date.max())
    relevant = {
        str(symbol): str(day) for symbol, day in delist_dates.items() if str(day) <= last_day
    }
    if not relevant:
        return pd.DataFrame(columns=["symbol", "delist_date", "residual_quantity", "status"])
    trades = _quantity_trades(fills, marks, price_col, set(relevant))
    rows = []
    for symbol, day in sorted(relevant.items()):
        matching = trades.loc[trades.symbol.eq(symbol)]
        late = matching.loc[matching.trade_date.ge(day)]
        residual = float(matching.loc[matching.trade_date.lt(day), "quantity"].sum())
        status = "passed" if late.empty and abs(residual) <= tolerance else "failed"
        rows.append(
            {"symbol": symbol, "delist_date": day, "residual_quantity": residual, "status": status}
        )
    result = pd.DataFrame(rows)
    failed = result.loc[result.status.eq("failed")]
    if not failed.empty:
        symbols = failed.symbol.tolist()
        raise ValueError(f"unsettled simulated delisting exposure: {symbols}")
    return result
