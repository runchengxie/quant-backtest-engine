"""Capacity-limited execution simulation."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .config import ExecutionSimConfig
from .models import SupportedTradeFeeModel, _ExecutionTables, _OrderSink
from .orders import _build_targets_by_rebalance, _execute_buy_orders, _execute_sell_orders
from .reporting import _empty_result, _fill_columns, _order_columns, _summarize_orders
from .results import ExecutionSimResult
from .table_preparation import _prepare_execution_tables, _prepare_long_only_execution_positions

TradeFeeModel = SupportedTradeFeeModel


def simulate_capacity_execution(
    positions: pd.DataFrame | None,
    pricing_data: pd.DataFrame | None,
    config: ExecutionSimConfig,
    *,
    price_col: str,
    tradable_col: str | None = None,
    buy_tradable_col: str | None = None,
    sell_tradable_col: str | None = None,
    limit_up_col: str | None = None,
    limit_down_col: str | None = None,
    listing_status_col: str | None = None,
) -> ExecutionSimResult:
    if config.sell_round_lot is not None:
        raise ValueError(
            "execution_sim.sell_round_lot requires a share ledger; "
            "use simulate_execution_adjusted_nav."
        )
    if not config.enabled:
        return _empty_result(config, status="disabled")
    if positions is None or positions.empty:
        return _empty_result(config, status="no_positions")
    if pricing_data is None or pricing_data.empty:
        return _empty_result(config, status="no_pricing_data")

    work_positions, status, extra = _prepare_long_only_execution_positions(positions)
    if status is not None or work_positions is None:
        return _empty_result(config, status=status or "no_usable_positions", extra=extra)

    execution_tables, status, extra = _prepare_execution_tables(
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
    if status is not None or execution_tables is None:
        return _empty_result(config, status=status or "no_trade_dates", extra=extra)

    orders, fills, cash_weight, current_weights, rebalance_count = _run_capacity_rebalances(
        work_positions,
        tables=execution_tables,
        config=config,
    )
    summary = _summarize_orders(
        config,
        orders,
        rebalances=rebalance_count,
        final_cash_weight=cash_weight,
        final_invested_weight=sum(current_weights.values()),
        status="ok",
    )
    return ExecutionSimResult(summary=summary, orders=orders, fills=fills)


def _run_capacity_rebalances(
    work_positions: pd.DataFrame,
    *,
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, float, dict[str, float], int]:
    targets_by_rebalance = _build_targets_by_rebalance(work_positions)
    current_weights: dict[str, float] = {}
    cash_weight = 1.0
    order_rows: list[dict[str, Any]] = []
    fill_rows: list[dict[str, Any]] = []
    order_sink = _OrderSink(order_rows=order_rows, fill_rows=fill_rows)

    for idx, target in enumerate(targets_by_rebalance):
        cash_weight = _execute_capacity_rebalance(
            target,
            target_idx=idx,
            targets_by_rebalance=targets_by_rebalance,
            current_weights=current_weights,
            cash_weight=cash_weight,
            config=config,
            tables=tables,
            sink=order_sink,
        )

    orders = pd.DataFrame(order_rows, columns=_order_columns())
    fills = pd.DataFrame(fill_rows, columns=_fill_columns())
    return orders, fills, cash_weight, current_weights, len(targets_by_rebalance)


def _execute_capacity_rebalance(
    target: tuple[pd.Timestamp, dict[str, Any]],
    *,
    target_idx: int,
    targets_by_rebalance: list[tuple[pd.Timestamp, dict[str, Any]]],
    current_weights: dict[str, float],
    cash_weight: float,
    config: ExecutionSimConfig,
    tables: _ExecutionTables,
    sink: _OrderSink,
) -> float:
    rebalance_date, target_info = target
    entry_date = target_info["entry_date"]
    if entry_date not in tables.date_to_idx:
        return cash_weight

    next_entry_date = (
        targets_by_rebalance[target_idx + 1][1]["entry_date"]
        if target_idx + 1 < len(targets_by_rebalance)
        else None
    )
    target_weights = target_info["weights"]
    symbols = sorted(set(current_weights) | set(target_weights))
    deltas = {
        symbol: float(target_weights.get(symbol, 0.0) - current_weights.get(symbol, 0.0))
        for symbol in symbols
    }
    sell_requests = {symbol: -delta for symbol, delta in deltas.items() if delta < -1e-12}
    if sell_requests:
        cash_weight = _execute_sell_orders(
            rebalance_date=rebalance_date,
            entry_date=entry_date,
            next_entry_date=next_entry_date,
            requests=sell_requests,
            current_weights=current_weights,
            cash_weight=cash_weight,
            config=config,
            tables=tables,
            sink=sink,
        )

    buy_requests = {
        symbol: max(float(target_weights.get(symbol, 0.0) - current_weights.get(symbol, 0.0)), 0.0)
        for symbol in target_weights
    }
    buy_requests = {symbol: amount for symbol, amount in buy_requests.items() if amount > 1e-12}
    if buy_requests:
        return _execute_buy_orders(
            rebalance_date=rebalance_date,
            entry_date=entry_date,
            requests=buy_requests,
            current_weights=current_weights,
            cash_weight=cash_weight,
            config=config,
            tables=tables,
            sink=sink,
        )
    return cash_weight
