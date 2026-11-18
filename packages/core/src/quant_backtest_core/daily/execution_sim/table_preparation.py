"""Preparation of shared execution tables and target positions."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .config import ExecutionSimConfig, required_execution_sim_columns
from .models import _ExecutionTables


def _prepare_long_only_execution_positions(
    positions: pd.DataFrame,
) -> tuple[pd.DataFrame | None, str | None, dict[str, Any] | None]:
    work_positions = positions.copy()
    if "side" in work_positions.columns:
        unsupported_side = work_positions["side"].astype(str).str.lower().eq("short").any()
        if unsupported_side:
            return None, "skipped_long_short_not_supported", None
    work_positions["weight"] = pd.to_numeric(work_positions["weight"], errors="coerce")
    if (work_positions["weight"] < 0).any():
        return None, "skipped_negative_weights_not_supported", None
    work_positions["rebalance_date"] = pd.to_datetime(
        work_positions["rebalance_date"], errors="coerce"
    )
    work_positions["entry_date"] = pd.to_datetime(work_positions["entry_date"], errors="coerce")
    work_positions = work_positions.dropna(subset=["rebalance_date", "entry_date", "symbol"])
    work_positions = work_positions[work_positions["weight"].notna()].copy()
    if work_positions.empty:
        return None, "no_usable_positions", None
    return work_positions, None, None


def _prepare_execution_tables(
    pricing_data: pd.DataFrame,
    config: ExecutionSimConfig,
    *,
    price_col: str,
    tradable_col: str | None,
    buy_tradable_col: str | None,
    sell_tradable_col: str | None,
    limit_up_col: str | None = None,
    limit_down_col: str | None = None,
    listing_status_col: str | None = None,
) -> tuple[_ExecutionTables | None, str | None, dict[str, Any] | None]:
    pricing = pricing_data.drop_duplicates(subset=["trade_date", "symbol"]).copy()
    pricing["trade_date"] = pd.to_datetime(pricing["trade_date"], errors="coerce")
    pricing = pricing.dropna(subset=["trade_date", "symbol"])
    required_cols = required_execution_sim_columns(
        config,
        price_col=price_col,
        tradable_col=tradable_col if tradable_col in pricing.columns else None,
    )
    # An explicitly requested control must not silently become unrestricted.
    required_cols.update(
        col for col in (tradable_col, buy_tradable_col, sell_tradable_col) if col is not None
    )
    # Phase 4: 市场规则依赖列缺失时, 若规则已开启则终止 (约束 #7).
    market_rule_cols = {
        col
        for col in (limit_up_col, limit_down_col, listing_status_col)
        if col and col not in pricing.columns
    }
    if (config.enforce_price_limits or config.enforce_listing_status) and market_rule_cols:
        return (
            None,
            "missing_pricing_columns",
            {"missing_pricing_columns": sorted(market_rule_cols)},
        )
    missing_cols = sorted(col for col in required_cols if col not in pricing.columns)
    if missing_cols:
        return None, "missing_pricing_columns", {"missing_pricing_columns": missing_cols}

    tables = _build_execution_tables(
        pricing,
        config,
        price_col=price_col,
        tradable_col=tradable_col,
        buy_tradable_col=buy_tradable_col,
        sell_tradable_col=sell_tradable_col,
        limit_up_col=limit_up_col,
        limit_down_col=limit_down_col,
        listing_status_col=listing_status_col,
    )
    if not tables.trade_dates:
        return None, "no_trade_dates", None
    return tables, None, None


def prepare_execution_tables(
    pricing_data: pd.DataFrame,
    config: ExecutionSimConfig,
    *,
    price_col: str,
    tradable_col: str | None = None,
    buy_tradable_col: str | None = None,
    sell_tradable_col: str | None = None,
    limit_up_col: str | None = None,
    limit_down_col: str | None = None,
    listing_status_col: str | None = None,
) -> _ExecutionTables:
    """Prepare pivoted execution inputs for reuse across ledger simulations."""
    tables, status, extra = _prepare_execution_tables(
        pricing_data,
        config,
        price_col=price_col,
        tradable_col=tradable_col,
        buy_tradable_col=buy_tradable_col,
        sell_tradable_col=sell_tradable_col,
        limit_up_col=limit_up_col,
        limit_down_col=limit_down_col,
        listing_status_col=listing_status_col,
    )
    if tables is None:
        detail = f" ({extra})" if extra else ""
        raise ValueError(f"could not prepare execution tables: {status}{detail}")
    return tables


def _build_execution_tables(
    pricing: pd.DataFrame,
    config: ExecutionSimConfig,
    *,
    price_col: str,
    tradable_col: str | None,
    buy_tradable_col: str | None,
    sell_tradable_col: str | None,
    limit_up_col: str | None = None,
    limit_down_col: str | None = None,
    listing_status_col: str | None = None,
) -> _ExecutionTables:
    trade_dates = sorted(pd.to_datetime(pricing["trade_date"].unique()))
    date_to_idx = {date: idx for idx, date in enumerate(trade_dates)}
    price_table = pricing.pivot(index="trade_date", columns="symbol", values=price_col)
    tradable_table = _build_tradable_table(pricing, tradable_col)
    buy_tradable_table = _build_tradable_table(pricing, buy_tradable_col)
    sell_tradable_table = _build_tradable_table(pricing, sell_tradable_col)
    if buy_tradable_table is None:
        buy_tradable_table = tradable_table
    if sell_tradable_table is None:
        sell_tradable_table = tradable_table
    liquidity_tables = {
        col: pricing.pivot(index="trade_date", columns="symbol", values=col)
        for col in config.liquidity_cols
    }
    # Phase 4 market-rule tables (None when the column is absent).
    limit_up_table = _build_tradable_table(pricing, limit_up_col)
    limit_down_table = _build_tradable_table(pricing, limit_down_col)
    listing_status_table = (
        pricing.pivot(index="trade_date", columns="symbol", values=listing_status_col)
        if listing_status_col and listing_status_col in pricing.columns
        else None
    )
    return _ExecutionTables(
        trade_dates=trade_dates,
        date_to_idx=date_to_idx,
        price_table=price_table,
        buy_tradable_table=buy_tradable_table,
        sell_tradable_table=sell_tradable_table,
        liquidity_tables=liquidity_tables,
        limit_up_table=limit_up_table,
        limit_down_table=limit_down_table,
        listing_status_table=listing_status_table,
    )


def _build_tradable_table(
    pricing: pd.DataFrame,
    tradable_col: str | None,
) -> pd.DataFrame | None:
    if not tradable_col or tradable_col not in pricing.columns:
        return None
    table = pricing.pivot(index="trade_date", columns="symbol", values=tradable_col)
    return table.mask(table.isna(), False).astype(bool)
