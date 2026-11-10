"""Adjusted and ideal NAV execution simulation paths."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

from quant_backtest_core._minute.corporate_actions import (
    CorporateAction,
    normalize_corporate_actions,
)

from ..dated_fees import DatedTradeFeeModel
from ..execution import DetailedTradeFeeModel, SlippageModel
from ..types import CostBreakdown
from .capacity import _positions_value, _refresh_last_prices
from .config import ExecutionSimConfig
from .corporate_actions import RECEIVABLE_COLUMNS, _action_conventions, _CorporateActionLedger
from .models import (
    SupportedTradeFeeModel,
    _AdjustedNavLedger,
    _AdjustedNavPlan,
    _ExecutionTables,
    _MarketRules,
    _NavOrder,
)
from .orders import (
    _append_nav_order_row,
    _build_nav_orders_for_target,
    _build_targets_by_rebalance,
    _cash_weight_breakdown,
    _execute_nav_orders_for_day,
    _finalize_open_nav_orders,
    _nav_order_is_complete,
    _nav_order_should_abort_buy,
    _target_cash_notional,
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
    _prepare_execution_tables,
    _prepare_long_only_execution_positions,
)

TradeFeeModel = SupportedTradeFeeModel


def _build_adjusted_nav_plan(
    work_positions: pd.DataFrame,
    *,
    tables: _ExecutionTables,
    cost_rate: float,
    slippage_model: SlippageModel | None = None,
) -> tuple[_AdjustedNavPlan | None, str | None]:
    targets_by_rebalance = _build_targets_by_rebalance(work_positions)
    targets_by_entry = {
        info["entry_date"]: (rebalance_date, info["weights"])
        for rebalance_date, info in targets_by_rebalance
        if info["entry_date"] in tables.date_to_idx
    }
    if not targets_by_entry:
        return None, "no_executable_entry_dates"
    entry_dates = sorted(targets_by_entry)
    next_entry_by_date = {
        entry_date: entry_dates[idx + 1] if idx + 1 < len(entry_dates) else None
        for idx, entry_date in enumerate(entry_dates)
    }
    return (
        _AdjustedNavPlan(
            tables=tables,
            targets_by_entry=targets_by_entry,
            next_entry_by_date=next_entry_by_date,
            start_idx=tables.date_to_idx[entry_dates[0]],
            cost_rate=cost_rate,
            slippage_model=slippage_model,
        ),
        None,
    )


def _initial_adjusted_nav_ledger(config: ExecutionSimConfig) -> _AdjustedNavLedger:
    initial_value = float(config.portfolio_value)
    return _AdjustedNavLedger(
        cash=initial_value,
        previous_nav=initial_value,
        target_cash_notional=0.0,
        shares={},
        last_prices={},
        open_orders=[],
        order_rows=[],
        fill_rows=[],
        daily_rows=[],
        fee_group_notionals={},
    )


def _start_adjusted_nav_target_orders(
    ledger: _AdjustedNavLedger,
    *,
    plan: _AdjustedNavPlan,
    trade_date: pd.Timestamp,
    trade_idx: int,
    nav_before_orders: float,
    config: ExecutionSimConfig,
) -> None:
    _finalize_open_nav_orders(
        ledger.open_orders,
        ledger.order_rows,
        trade_date=trade_date,
        participation_rate=config.participation_rate,
        status_by_side={"buy": "cancelled_new_target", "sell": "replaced_new_target"},
    )
    ledger.open_orders = []
    rebalance_date, target_weights = plan.targets_by_entry[trade_date]
    ledger.target_cash_notional = _target_cash_notional(target_weights, nav_before_orders)
    if ledger.corporate_actions is not None:
        # Pending stock already contributes to economic exposure. Reduce only
        # the held-share target; never put untradable rights in execution shares.
        target_weights = dict(target_weights)
        for symbol, quantity in ledger.corporate_actions.stock_by_symbol().items():
            value = quantity * float(plan.tables.price_table.at[trade_date, symbol])
            weight = value / nav_before_orders if nav_before_orders > 0 else 0.0
            target_weights[symbol] = max(target_weights.get(symbol, 0.0) - weight, 0.0)
    ledger.open_orders = _build_nav_orders_for_target(
        rebalance_date=rebalance_date,
        entry_date=trade_date,
        next_entry_date=plan.next_entry_by_date[trade_date],
        target_weights=target_weights,
        shares=ledger.shares,
        cash=ledger.cash,
        nav=nav_before_orders,
        trade_idx=trade_idx,
        tables=plan.tables,
        config=config,
        last_prices=ledger.last_prices,
    )


def _retain_open_adjusted_nav_orders(
    ledger: _AdjustedNavLedger,
    *,
    trade_date: pd.Timestamp,
    trade_idx: int,
    config: ExecutionSimConfig,
) -> None:
    still_open: list[_NavOrder] = []
    for order in ledger.open_orders:
        day_number = trade_idx - order.start_idx + 1
        if _nav_order_is_complete(order):
            order.status = "filled"
            _append_nav_order_row(
                ledger.order_rows,
                order,
                trade_date=trade_date,
                participation_rate=config.participation_rate,
            )
        elif order.side == "buy" and _nav_order_should_abort_buy(order, config):
            order.status = "abandoned_zero_fill"
            _append_nav_order_row(
                ledger.order_rows,
                order,
                trade_date=trade_date,
                participation_rate=config.participation_rate,
            )
        elif day_number >= order.max_days:
            order.status = "cancelled_buy_deadline" if order.side == "buy" else "delayed_sell"
            _append_nav_order_row(
                ledger.order_rows,
                order,
                trade_date=trade_date,
                participation_rate=config.participation_rate,
            )
        else:
            still_open.append(order)
    ledger.open_orders = still_open


def _append_adjusted_nav_daily_row(
    ledger: _AdjustedNavLedger,
    *,
    plan: _AdjustedNavPlan,
    trade_date: pd.Timestamp,
    traded_notional: float,
    transaction_cost: CostBreakdown,
    config: ExecutionSimConfig,
) -> None:
    current_value = _positions_value(
        ledger.shares,
        trade_date,
        plan.tables.price_table,
        ledger.last_prices,
    )
    nav_after_orders = ledger.cash + current_value
    receipts: dict[str, float] = {}
    if ledger.corporate_actions is not None:
        cash_right, stock_right = ledger.corporate_actions.values(trade_date, plan.tables)
        nav_after_orders += cash_right + stock_right
        receipts = dict(zip(RECEIVABLE_COLUMNS, (cash_right, stock_right), strict=True))
    daily_return = (
        nav_after_orders / ledger.previous_nav - 1.0 if ledger.previous_nav > 0 else np.nan
    )
    ledger.previous_nav = nav_after_orders
    cash_weight, target_cash_weight, shortfall_cash_weight = _cash_weight_breakdown(
        cash=ledger.cash,
        target_cash_notional=ledger.target_cash_notional,
        nav=nav_after_orders,
    )
    ledger.daily_rows.append(
        {
            "trade_date": _format_date(trade_date),
            "executed_return": float(daily_return),
            "executed_nav": float(nav_after_orders / float(config.portfolio_value)),
            "portfolio_value": float(nav_after_orders),
            "cash": float(ledger.cash),
            "invested_value": float(current_value),
            "cash_weight": cash_weight,
            "target_cash_weight": target_cash_weight,
            "execution_shortfall_cash_weight": shortfall_cash_weight,
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
            "open_orders": len(ledger.open_orders),
            **receipts,
        }
    )


def _process_adjusted_nav_trade_day(
    ledger: _AdjustedNavLedger,
    *,
    plan: _AdjustedNavPlan,
    trade_idx: int,
    config: ExecutionSimConfig,
    trade_fee_model: TradeFeeModel | None,
) -> None:
    trade_date = plan.tables.trade_dates[trade_idx]
    actions = ledger.corporate_actions
    if actions is not None:
        affected = actions.open_day(ledger, trade_date)
        actions.validate_marks(ledger, trade_date, plan.tables)
        _finalize_open_nav_orders(
            [order for order in ledger.open_orders if order.symbol in affected],
            ledger.order_rows,
            trade_date=trade_date,
            participation_rate=config.participation_rate,
            status_by_side={
                "buy": "cancelled_corporate_action",
                "sell": "cancelled_corporate_action",
            },
        )
        ledger.open_orders = [order for order in ledger.open_orders if order.symbol not in affected]
    _refresh_last_prices(ledger.last_prices, ledger.shares, trade_date, plan.tables.price_table)
    nav_before_orders = ledger.cash + _positions_value(
        ledger.shares,
        trade_date,
        plan.tables.price_table,
        ledger.last_prices,
    )
    if actions is not None:
        nav_before_orders += sum(actions.values(trade_date, plan.tables))
    if trade_date in plan.targets_by_entry:
        _start_adjusted_nav_target_orders(
            ledger,
            plan=plan,
            trade_date=trade_date,
            trade_idx=trade_idx,
            nav_before_orders=nav_before_orders,
            config=config,
        )

    cash_box = {"cash": ledger.cash}
    # Phase 4 T+1: 当日可卖数量 = 当日开盘前持仓快照 (排除当日新买).
    if config.enforce_t1:
        ledger.t1_available = {symbol: float(q) for symbol, q in ledger.shares.items()}
    else:
        ledger.t1_available = None
    market_rules = _MarketRules.from_config(
        config,
        limit_up_table=plan.tables.limit_up_table,
        limit_down_table=plan.tables.limit_down_table,
        listing_status_table=plan.tables.listing_status_table,
    )
    traded_notional, transaction_cost = _execute_nav_orders_for_day(
        open_orders=ledger.open_orders,
        shares=ledger.shares,
        cash_ref=cash_box,
        trade_date=trade_date,
        trade_idx=trade_idx,
        tables=plan.tables,
        config=config,
        cost_rate=plan.cost_rate,
        trade_fee_model=trade_fee_model,
        slippage_model=plan.slippage_model,
        fill_rows=ledger.fill_rows,
        fee_group_notionals=ledger.fee_group_notionals,
        market_rules=market_rules,
        t1_available=ledger.t1_available,
    )
    ledger.cash = float(cash_box["cash"])
    if actions is not None:
        actions.validate_marks(ledger, trade_date, plan.tables)
        actions.capture_close(ledger, trade_date)
        actions.snapshot(ledger, trade_date, plan.tables)
    # Include newly acquired positions before a later missing quote needs this mark.
    _refresh_last_prices(ledger.last_prices, ledger.shares, trade_date, plan.tables.price_table)
    _retain_open_adjusted_nav_orders(
        ledger,
        trade_date=trade_date,
        trade_idx=trade_idx,
        config=config,
    )
    _append_adjusted_nav_daily_row(
        ledger,
        plan=plan,
        trade_date=trade_date,
        traded_notional=traded_notional,
        transaction_cost=transaction_cost,
        config=config,
    )


def _run_adjusted_nav_ledger(
    *,
    plan: _AdjustedNavPlan,
    config: ExecutionSimConfig,
    trade_fee_model: TradeFeeModel | None,
    corporate_actions: _CorporateActionLedger | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ledger = _initial_adjusted_nav_ledger(config)
    ledger.corporate_actions = corporate_actions
    for trade_idx in range(plan.start_idx, len(plan.tables.trade_dates)):
        _process_adjusted_nav_trade_day(
            ledger,
            plan=plan,
            trade_idx=trade_idx,
            config=config,
            trade_fee_model=trade_fee_model,
        )

    if ledger.open_orders:
        final_date = plan.tables.trade_dates[-1]
        _finalize_open_nav_orders(
            ledger.open_orders,
            ledger.order_rows,
            trade_date=final_date,
            participation_rate=config.participation_rate,
            status_by_side={"buy": "cancelled_buy_deadline", "sell": "delayed_sell"},
        )

    columns = _executed_daily_columns() + (
        RECEIVABLE_COLUMNS if corporate_actions is not None else []
    )
    daily = pd.DataFrame(ledger.daily_rows, columns=columns)
    orders = pd.DataFrame(ledger.order_rows, columns=_nav_order_columns())
    fills = pd.DataFrame(ledger.fill_rows, columns=_nav_fill_columns())
    return daily, orders, fills


def simulate_execution_adjusted_nav(
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
    transaction_cost_bps: float = 0.0,
    trading_days_per_year: int = 252,
    trade_fee_model: TradeFeeModel | None = None,
    slippage_model: SlippageModel | None = None,
    prepared_tables: _ExecutionTables | None = None,
    corporate_actions: Iterable[CorporateAction] | None = None,
    price_basis: str | None = None,
) -> ExecutionAdjustedNavResult:
    if config.sell_round_lot is not None and price_basis not in (None, "raw"):
        raise ValueError("execution_sim.sell_round_lot requires raw share prices.")
    events = normalize_corporate_actions(corporate_actions, price_basis)
    if not config.enabled:
        return _empty_adjusted_nav_result(config, status="disabled")
    if positions is None or positions.empty:
        return _empty_adjusted_nav_result(config, status="no_positions")
    if pricing_data is None or pricing_data.empty:
        return _empty_adjusted_nav_result(config, status="no_pricing_data")

    work_positions, status, extra = _prepare_long_only_execution_positions(positions)
    if status is not None or work_positions is None:
        return _empty_adjusted_nav_result(config, status=status, extra=extra)

    if prepared_tables is None:
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
        if status is not None or tables is None:
            return _empty_adjusted_nav_result(
                config, status=status or "no_trade_dates", extra=extra
            )
    else:
        tables = prepared_tables

    plan, status = _build_adjusted_nav_plan(
        work_positions,
        tables=tables,
        cost_rate=max(float(transaction_cost_bps), 0.0) / 10_000.0,
        slippage_model=slippage_model,
    )
    if status is not None or plan is None:
        return _empty_adjusted_nav_result(config, status=status or "no_executable_entry_dates")

    _validate_continuous_trade_fee_model(
        trade_fee_model,
        work_positions=work_positions,
        trade_dates=tables.trade_dates[plan.start_idx :],
    )

    action_ledger = (
        _CorporateActionLedger(events, tables.trade_dates[plan.start_idx :])
        if events is not None
        else None
    )
    daily, orders, fills = _run_adjusted_nav_ledger(
        plan=plan,
        config=config,
        trade_fee_model=trade_fee_model,
        corporate_actions=action_ledger,
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
    action_frame, holdings = None, None
    if action_ledger is not None:
        summary["corporate_actions"] = _action_conventions()
        action_frame, holdings = action_ledger.frames()
    return ExecutionAdjustedNavResult(
        summary=summary,
        daily=daily,
        orders=orders,
        fills=fills,
        actions=action_frame,
        holdings=holdings,
    )


def _validate_continuous_trade_fee_model(
    trade_fee_model: TradeFeeModel | None,
    *,
    work_positions: pd.DataFrame,
    trade_dates: list[pd.Timestamp],
) -> None:
    if trade_fee_model is None or isinstance(trade_fee_model, DetailedTradeFeeModel):
        return
    if not isinstance(trade_fee_model, DatedTradeFeeModel):
        raise TypeError(f"unsupported trade_fee_model type: {type(trade_fee_model).__name__}")
    symbols = sorted(
        {
            str(symbol)
            for symbol in work_positions.loc[work_positions["weight"] > 0, "symbol"].tolist()
        }
    )
    markets = {trade_fee_model.market_for(symbol) for symbol in symbols}
    for market in markets:
        for trade_date in trade_dates:
            trade_fee_model.schedule.resolve(trade_date, market=market)
