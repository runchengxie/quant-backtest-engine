"""Post-run reconciliation of synthetic owner tables; never match or mutate orders."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd  # type: ignore[import-untyped]
from pandas.api.types import is_bool_dtype, is_numeric_dtype  # type: ignore[import-untyped]

from quant_backtest_core.backtest.minute import MinuteExecutionConfig, MinuteExecutionResult


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def _near(left: float, right: float, message: str) -> None:
    _require(math.isclose(float(left), float(right), rel_tol=1e-10, abs_tol=1e-7), message)


def _numbers(frame: pd.DataFrame, names: tuple[str, ...]) -> None:
    for name in names:
        _require(
            is_numeric_dtype(frame[name]) and not is_bool_dtype(frame[name]),
            "numeric owner columns required: " + name,
        )
        _require(
            bool(np.isfinite(frame[name]).all() and frame[name].ge(0).all()),
            "finite nonnegative owner columns required: " + name,
        )


def _fills_and_orders(result: MinuteExecutionResult, config: MinuteExecutionConfig) -> None:
    orders, fills = result.orders, result.fills
    _require(not orders.order_id.duplicated().any(), "duplicate owner order identity")
    _require(set(fills.order_id) <= set(orders.order_id), "fill outside owner orders")
    _numbers(orders, ("quantity", "filled_quantity", "commission_paid", "tax_paid"))
    _numbers(
        fills, ("quantity", "price", "gross_amount", "commission", "sell_tax", "transaction_cost")
    )
    for row in fills.itertuples():
        _require(row.side in {"buy", "sell"} and row.symbol == "A", "unexpected fill side/symbol")
        _require(row.quantity > 0 and row.quantity == int(row.quantity), "invalid fill quantity")
        _near(row.gross_amount, row.quantity * row.price, "fill notional mismatch")
        _near(row.transaction_cost, row.commission + row.sell_tax, "fill fee mismatch")
    for order in orders.itertuples():
        part = fills.loc[fills.order_id.eq(order.order_id)]
        _require(
            order.side in {"buy", "sell"} and order.symbol == "A", "unexpected order side/symbol"
        )
        _require(
            part.side.eq(order.side).all() and part.symbol.eq(order.symbol).all(),
            "fill/order identity mismatch",
        )
        quantity, gross = float(part.quantity.sum()), float(part.gross_amount.sum())
        _near(order.filled_quantity, quantity, "owner filled quantity mismatch")
        _require(quantity <= order.quantity, "owner order quantity exceeded")
        if order.status == "filled":
            _near(quantity, order.quantity, "filled status quantity mismatch")
        _near(order.commission_paid, part.commission.sum(), "parent commission fee mismatch")
        _near(order.tax_paid, part.sell_tax.sum(), "parent tax fee mismatch")
        rate = config.buy_fee_bp if order.side == "buy" else config.sell_fee_bp - config.sell_tax_bp
        expected = max(config.commission_minimum_cny, gross * rate / 10000) if quantity else 0.0
        _near(order.commission_paid, expected, "owner commission fee convention mismatch")
        _near(
            order.tax_paid,
            gross * config.sell_tax_bp / 10000 if order.side == "sell" else 0.0,
            "owner tax fee convention mismatch",
        )


def _participation(
    result: MinuteExecutionResult, bars: pd.DataFrame, config: MinuteExecutionConfig
) -> None:
    _require(not bars.duplicated(["time", "symbol"]).any(), "duplicate market bar identity")
    market = bars.set_index(["time", "symbol"])
    for (time, symbol), part in result.fills.groupby(["time", "symbol"], sort=True):
        _require((time, symbol) in market.index, "fill missing actual market bar")
        bar = market.loc[(time, symbol)]
        capacity = (
            math.floor(float(bar.volume) * config.participation_rate / config.lot_size)
            * config.lot_size
        )
        _require(part.quantity.sum() <= capacity, "owner participation exceeded")
        for fill in part.itertuples():
            order = result.orders.loc[result.orders.order_id.eq(fill.order_id)].iloc[0]
            _require(
                bar.interval_start > order.entry_time + pd.Timedelta(minutes=config.latency_minutes)
                and time <= order.deadline,
                "owner execution clock/latency violated",
            )


def _balances(
    result: MinuteExecutionResult, initial_cash: float, benchmark_price: float
) -> tuple[float, float]:
    fills, daily, holdings = result.fills, result.daily, result.holdings
    _require(not daily.empty, "owner daily results missing")
    _numbers(
        daily,
        (
            "cash",
            "positions_value",
            "nav",
            "transaction_cost",
            "cash_receivable",
            "stock_receivable_value",
        ),
    )
    _require(
        daily.cash_receivable.eq(0).all() and daily.stock_receivable_value.eq(0).all(),
        "unexpected receivables in synthetic execution study",
    )
    _require(
        not daily.date.duplicated().any() and daily.date.is_monotonic_increasing,
        "ordered unique owner dates required",
    )
    _require(not holdings.duplicated(["date", "symbol"]).any(), "duplicate owner holdings")
    _require(holdings.date.isin(daily.date).all(), "holding outside owner calendar")
    _numbers(holdings, ("quantity",))
    # Each date is checked directly against source fills, with no replacement ledger.
    for row in daily.itertuples():
        prefix = fills.loc[fills.time.dt.date.le(row.date)]
        _near(row.transaction_cost, prefix.transaction_cost.sum(), "cumulative owner fee mismatch")
        signed = float(
            prefix.loc[prefix.side.eq("buy"), "quantity"].sum()
            - prefix.loc[prefix.side.eq("sell"), "quantity"].sum()
        )
        _require(signed >= 0, "owner inventory quantity oversold")
        held = holdings.loc[holdings.date.eq(row.date)]
        _require(held.symbol.eq("A").all(), "unexpected holding symbol")
        _near(held.quantity.sum(), signed, "owner holding quantity mismatch")
        _near(row.positions_value, signed * benchmark_price, "owner mark mismatch")
        net_notional = (
            prefix.loc[prefix.side.eq("sell"), "gross_amount"].sum()
            - prefix.loc[prefix.side.eq("buy"), "gross_amount"].sum()
        )
        _near(
            row.cash,
            initial_cash + net_notional - prefix.transaction_cost.sum(),
            "owner cash mismatch",
        )
        _near(row.nav, row.cash + row.positions_value, "owner equity mismatch")
    return signed, float(daily.iloc[-1].cash)


def audit_owner_tables(
    result: MinuteExecutionResult,
    bars: pd.DataFrame,
    config: MinuteExecutionConfig,
    *,
    quantity: int,
    exit_start: pd.Timestamp,
    benchmark_price: float = 10.0,
) -> dict[str, Any]:
    """Audit the declared one-instrument flat-price profile using owner's amounts.

    Implementation shortfall is fill price difference plus actual owner fees.
    Neither model risk penalties nor a second impact charge enter cash costs.
    This algebra validates tables; it is not an alternative account ledger.
    """
    _require(type(quantity) is int and quantity > 0, "positive target quantity required")
    _require(
        math.isfinite(benchmark_price) and benchmark_price > 0, "positive reference price required"
    )
    _fills_and_orders(result, config)
    _participation(result, bars, config)
    residual, cash = _balances(result, config.initial_cash, benchmark_price)
    fills = result.fills
    seed, exit_fills = fills.loc[fills.time < exit_start], fills.loc[fills.time >= exit_start]
    _require(
        seed.side.eq("buy").all() and exit_fills.side.eq("sell").all(),
        "unexpected seed/exit direction",
    )
    seed_quantity, exit_quantity = float(seed.quantity.sum()), float(exit_fills.quantity.sum())
    _near(seed_quantity, quantity, "seed quantity not established")
    _near(exit_quantity + residual, quantity, "liquidation share quantity mismatch")
    shortfall = float((exit_fills.quantity * (benchmark_price - exit_fills.price)).sum())
    fees = float(exit_fills.transaction_cost.sum())
    completed = residual == 0
    pending = int(result.summary["financial_reports_pending"])
    open_orders = int(result.orders.status.eq("pending").sum())
    return {
        "seed_quantity": seed_quantity,
        "exit_quantity": exit_quantity,
        "filled_fraction": exit_quantity / quantity,
        "residual_quantity": residual,
        "completed": completed,
        "rankable": completed and pending == 0 and open_orders == 0,
        "exit_price_shortfall_cny": shortfall,
        "exit_fees_cny": fees,
        "exit_cost_cny": shortfall + fees,
        "exit_cost_bp_on_target": (shortfall + fees) / (quantity * benchmark_price) * 10000,
        "exit_cost_bp_on_filled": (
            (shortfall + fees) / (exit_quantity * benchmark_price) * 10000
            if exit_quantity
            else None
        ),
        "seed_fees_cny": float(seed.transaction_cost.sum()),
        "all_owner_fees_cny": float(fills.transaction_cost.sum()),
        "owner_final_cash": cash,
        "owner_final_nav": float(result.daily.iloc[-1].nav),
        "owner_fill_rows": len(fills),
        "owner_parent_orders": len(result.orders),
        "pending_financial_reports": pending,
        "open_parent_orders": open_orders,
    }
