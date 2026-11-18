"""Adjusted and ideal NAV execution simulation paths."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..dated_fees import DatedTradeFeeModel
from ..execution import DetailedTradeFeeModel
from ..types import CostBreakdown
from .capacity import _positions_value, _refresh_last_prices
from .config import ExecutionSimConfig
from .models import (
    SupportedTradeFeeModel,
    _ExecutionTables,
)
from .orders import (
    _build_targets_by_rebalance,
    _rebalance_ideal_target,
)
from .reporting import (
    _empty_adjusted_nav_result,
    _executed_daily_columns,
    _format_date,
    _nav_fill_columns,
    _nav_order_columns,
    _summarize_adjusted_nav,
)
from .results import ExecutionAdjustedNavResult
from .table_preparation import (
    _build_execution_tables,
    _prepare_long_only_execution_positions,
)

TradeFeeModel = SupportedTradeFeeModel


def simulate_ideal_daily_nav(
    positions: pd.DataFrame | None,
    pricing_data: pd.DataFrame | None,
    *,
    price_col: str,
    limit_up_col: str | None = None,
    limit_down_col: str | None = None,
    listing_status_col: str | None = None,
    transaction_cost_bps: float = 0.0,
    trading_days_per_year: int = 252,
    portfolio_value: float = 1_000_000.0,
    trade_fee_model: DetailedTradeFeeModel | None = None,
) -> ExecutionAdjustedNavResult:
    """Daily NAV for immediate, fully liquid rebalances to target weights.

    Phase 4 market-rule columns are accepted but the ideal path keeps rules
    disabled (it models a frictionless rebalance), so only the audit
    timestamps are populated when the caller supplies the columns.
    """
    if isinstance(trade_fee_model, DatedTradeFeeModel):
        raise TypeError(
            "DatedTradeFeeModel is not supported by simulate_ideal_daily_nav; "
            "use simulate_execution_adjusted_nav so fill date and group context are preserved"
        )
    if trade_fee_model is not None and not isinstance(trade_fee_model, DetailedTradeFeeModel):
        raise TypeError(f"unsupported trade_fee_model type: {type(trade_fee_model).__name__}")
    config = ExecutionSimConfig(
        enabled=True,
        portfolio_value=float(portfolio_value),
        participation_rate=1.0,
        liquidity_cols=(),
        buy_max_days=1,
        sell_max_days=1,
        zero_fill_abort_days_buy=None,
    )
    if positions is None or positions.empty:
        return _empty_adjusted_nav_result(config, status="no_positions")
    if pricing_data is None or pricing_data.empty:
        return _empty_adjusted_nav_result(config, status="no_pricing_data")

    work_positions, status, extra = _prepare_long_only_execution_positions(positions)
    if status is not None or work_positions is None:
        return _empty_adjusted_nav_result(config, status=status, extra=extra)
    tables, targets_by_entry, status, extra = _prepare_ideal_nav_targets(
        work_positions,
        pricing_data,
        config=config,
        price_col=price_col,
        limit_up_col=limit_up_col,
        limit_down_col=limit_down_col,
        listing_status_col=listing_status_col,
    )
    if status is not None:
        return _empty_adjusted_nav_result(config, status=status, extra=extra)

    daily, orders, fills = _run_ideal_daily_nav_ledger(
        config=config,
        tables=tables,
        targets_by_entry=targets_by_entry,
        cost_rate=max(float(transaction_cost_bps), 0.0) / 10_000.0,
        trade_fee_model=trade_fee_model,
    )
    summary = _summarize_adjusted_nav(
        config,
        daily=daily,
        orders=orders,
        transaction_cost_bps=transaction_cost_bps,
        trading_days_per_year=trading_days_per_year,
        status="ok",
        trade_fee_model=trade_fee_model,
    )
    summary["mode"] = "ideal_daily_nav"
    return ExecutionAdjustedNavResult(summary=summary, daily=daily, orders=orders, fills=fills)


def _prepare_ideal_nav_targets(
    work_positions: pd.DataFrame | None,
    pricing_data: pd.DataFrame,
    *,
    config: ExecutionSimConfig,
    price_col: str,
    limit_up_col: str | None = None,
    limit_down_col: str | None = None,
    listing_status_col: str | None = None,
) -> tuple[
    _ExecutionTables | None,
    dict[pd.Timestamp, tuple[pd.Timestamp, dict[str, float]]],
    str | None,
    dict[str, Any] | None,
]:
    if work_positions is None:
        return None, {}, "no_usable_positions", None
    required_columns = {"trade_date", "symbol", price_col}
    missing_columns = sorted(col for col in required_columns if col not in pricing_data.columns)
    if missing_columns:
        return None, {}, "missing_pricing_columns", {"missing_pricing_columns": missing_columns}

    pricing = pricing_data.drop_duplicates(subset=["trade_date", "symbol"]).copy()
    pricing["trade_date"] = pd.to_datetime(pricing["trade_date"], errors="coerce")
    pricing = pricing.dropna(subset=["trade_date", "symbol"])
    tables = _build_execution_tables(
        pricing,
        config,
        price_col=price_col,
        tradable_col=None,
        buy_tradable_col=None,
        sell_tradable_col=None,
        limit_up_col=limit_up_col,
        limit_down_col=limit_down_col,
        listing_status_col=listing_status_col,
    )
    if not tables.trade_dates:
        return None, {}, "no_trade_dates", None

    targets_by_rebalance = _build_targets_by_rebalance(work_positions)
    targets_by_entry = {
        info["entry_date"]: (rebalance_date, info["weights"])
        for rebalance_date, info in targets_by_rebalance
        if info["entry_date"] in tables.date_to_idx
    }
    if not targets_by_entry:
        return None, {}, "no_executable_entry_dates", None
    return tables, targets_by_entry, None, None


def _run_ideal_daily_nav_ledger(
    *,
    config: ExecutionSimConfig,
    tables: _ExecutionTables | None,
    targets_by_entry: dict[pd.Timestamp, tuple[pd.Timestamp, dict[str, float]]],
    cost_rate: float,
    trade_fee_model: DetailedTradeFeeModel | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if tables is None:
        return (
            pd.DataFrame(columns=_executed_daily_columns()),
            pd.DataFrame(columns=_nav_order_columns()),
            pd.DataFrame(columns=_nav_fill_columns()),
        )
    first_entry = sorted(targets_by_entry)[0]
    start_idx = tables.date_to_idx[first_entry]

    cash = float(config.portfolio_value)
    shares: dict[str, float] = {}
    last_prices: dict[str, float] = {}
    order_rows: list[dict[str, Any]] = []
    fill_rows: list[dict[str, Any]] = []
    daily_rows: list[dict[str, Any]] = []
    previous_nav = float(config.portfolio_value)

    for trade_idx in range(start_idx, len(tables.trade_dates)):
        trade_date = tables.trade_dates[trade_idx]
        _refresh_last_prices(last_prices, shares, trade_date, tables.price_table)
        nav_before_orders = cash + _positions_value(
            shares,
            trade_date,
            tables.price_table,
            last_prices,
        )
        traded_notional = 0.0
        transaction_cost = CostBreakdown()

        if trade_date in targets_by_entry:
            rebalance_date, target_weights = targets_by_entry[trade_date]
            cash_ref = {"cash": cash}
            traded_notional, transaction_cost = _rebalance_ideal_target(
                rebalance_date=rebalance_date,
                entry_date=trade_date,
                target_weights=target_weights,
                shares=shares,
                cash_ref=cash_ref,
                nav=nav_before_orders,
                trade_idx=trade_idx,
                tables=tables,
                config=config,
                last_prices=last_prices,
                cost_rate=cost_rate,
                trade_fee_model=trade_fee_model,
                order_rows=order_rows,
                fill_rows=fill_rows,
            )
            cash = float(cash_ref["cash"])

        current_value = _positions_value(shares, trade_date, tables.price_table, last_prices)
        nav_after_orders = cash + current_value
        daily_return = nav_after_orders / previous_nav - 1.0 if previous_nav > 0 else np.nan
        previous_nav = nav_after_orders
        daily_rows.append(
            _ideal_daily_nav_row(
                trade_date=trade_date,
                daily_return=daily_return,
                nav_after_orders=nav_after_orders,
                current_value=current_value,
                cash=cash,
                traded_notional=traded_notional,
                transaction_cost=transaction_cost,
                portfolio_value=config.portfolio_value,
            )
        )

    daily = pd.DataFrame(daily_rows, columns=_executed_daily_columns())
    orders = pd.DataFrame(order_rows, columns=_nav_order_columns())
    fills = pd.DataFrame(fill_rows, columns=_nav_fill_columns())
    return daily, orders, fills


def _ideal_daily_nav_row(
    *,
    trade_date: pd.Timestamp,
    daily_return: float,
    nav_after_orders: float,
    current_value: float,
    cash: float,
    traded_notional: float,
    transaction_cost: CostBreakdown,
    portfolio_value: float,
) -> dict[str, Any]:
    cash_weight = float(cash / nav_after_orders) if nav_after_orders > 0 else np.nan
    return {
        "trade_date": _format_date(trade_date),
        "executed_return": float(daily_return),
        "executed_nav": float(nav_after_orders / float(portfolio_value)),
        "portfolio_value": float(nav_after_orders),
        "cash": float(cash),
        "invested_value": float(current_value),
        "cash_weight": cash_weight,
        "target_cash_weight": cash_weight,
        "execution_shortfall_cash_weight": 0.0 if np.isfinite(cash_weight) else np.nan,
        "gross_exposure": float(current_value / nav_after_orders)
        if nav_after_orders > 0
        else np.nan,
        "traded_notional": float(traded_notional),
        "transaction_cost": float(transaction_cost.total_cost),
        "cost_commission": float(transaction_cost.commission),
        "cost_stamp_tax": float(transaction_cost.stamp_tax),
        "cost_transfer_fee": float(transaction_cost.transfer_fee),
        "cost_spread": float(transaction_cost.spread_cost),
        "cost_temporary_impact": float(transaction_cost.temporary_impact),
        "cost_permanent_impact": float(transaction_cost.permanent_impact),
        "cost_opportunity": float(transaction_cost.opportunity_cost),
        "cost_financing": float(transaction_cost.financing_cost),
        "open_orders": 0,
    }
