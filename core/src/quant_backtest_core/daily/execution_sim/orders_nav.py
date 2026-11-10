"""Order construction submodules (split from orders.py for maintainability)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ..dated_fees import DatedTradeFeeModel
from ..execution import SlippageModel
from ..types import CostBreakdown
from .capacity import (
    _capacity_notional,
    _capacity_weight,
    _execution_window_dates,
    _limit_down_at,
    _limit_up_at,
    _listing_status_at,
    _price_at,
)
from .config import (
    ExecutionSimConfig,
)
from .models import (
    SupportedTradeFeeModel,
    _add_breakdown,
    _ExecutionTables,
    _MarketRules,
    _NavOrder,
    _OrderSink,
)
from .orders_nav_fees import (
    _accrue_nav_fee_quote,
    _nav_fee_group_id,  # noqa: F401  re-exported for compatibility
    _nav_fee_order_id,
    _nav_trade_fee,
    _slippage_pricing_row,  # noqa: F401  re-exported for compatibility
)
from .orders_nav_quantities import _quantize_nav_sell_quantity
from .orders_nav_states import (
    _append_nav_order_row,  # noqa: F401  re-exported for core/ideal
    _append_order_rows,
    _build_order_states,
    _finalize_open_nav_orders,  # noqa: F401  re-exported for core
    _nav_order_is_complete,
    _nav_order_should_abort_buy,  # noqa: F401  re-exported for core
    _record_fill,
    _record_nav_fill_audit,
    _update_nav_order,
    _update_state,
)

TradeFeeModel = SupportedTradeFeeModel


def _apply_nav_sell_fill(
    *,
    order: _NavOrder,
    fill: float,
    fill_quantity: float,
    held_quantity: float,
    remaining_before_notional: float,
    trade_date: pd.Timestamp,
    trade_idx: int,
    capacity: float,
    shares: dict[str, float],
    cash_ref: dict[str, float],
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
    cost_rate: float,
    trade_fee_model: TradeFeeModel | None,
    slippage_model: SlippageModel | None,
    fill_rows: list[dict[str, Any]],
    fee_group_notionals: dict[str, float],
) -> CostBreakdown | None:
    fee_quote, fee_group_id = _nav_trade_fee(
        fill,
        order=order,
        trade_date=trade_date,
        tables=tables,
        config=config,
        cost_rate=cost_rate,
        trade_fee_model=trade_fee_model,
        slippage_model=slippage_model,
        fee_group_notionals=fee_group_notionals,
    )
    cost = fee_quote.breakdown
    if (
        isinstance(trade_fee_model, DatedTradeFeeModel)
        and float(cash_ref.get("cash", 0.0)) + fill - cost.total_cost < -1e-8
    ):
        return None
    shares[order.symbol] = max(held_quantity - fill_quantity, 0.0)
    if shares[order.symbol] <= 1e-10:
        shares.pop(order.symbol, None)
    cash_ref["cash"] = float(cash_ref.get("cash", 0.0)) + fill - cost.total_cost
    _update_nav_order(order, trade_date, fill, filled_quantity=fill_quantity)
    _accrue_nav_fee_quote(
        fee_group_notionals,
        fee_group_id=fee_group_id,
        fee_quote=fee_quote,
    )
    _record_nav_fill_audit(
        fill_rows,
        order=order,
        trade_date=trade_date,
        trade_idx=trade_idx,
        capacity_notional=capacity,
        filled_notional=fill,
        transaction_cost=cost.total_cost,
        cost_breakdown=cost,
        remaining_before_notional=remaining_before_notional,
        valuation_time=trade_date,
        fee_quote=fee_quote,
        fee_order_id=_nav_fee_order_id(order),
        fee_group_id=fee_group_id,
    )
    return cost


def _apply_nav_buy_fill(
    *,
    order: _NavOrder,
    fill: float,
    price: float,
    capacity: float,
    trade_date: pd.Timestamp,
    trade_idx: int,
    shares: dict[str, float],
    cash_ref: dict[str, float],
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
    cost_rate: float,
    trade_fee_model: TradeFeeModel | None,
    slippage_model: SlippageModel | None,
    fill_rows: list[dict[str, Any]],
    fee_group_notionals: dict[str, float],
) -> CostBreakdown:
    fee_quote, fee_group_id = _nav_trade_fee(
        fill,
        order=order,
        trade_date=trade_date,
        tables=tables,
        config=config,
        cost_rate=cost_rate,
        trade_fee_model=trade_fee_model,
        slippage_model=slippage_model,
        fee_group_notionals=fee_group_notionals,
    )
    cost = fee_quote.breakdown
    quantity = fill / float(price)
    shares[order.symbol] = float(shares.get(order.symbol, 0.0)) + quantity
    cash_after = float(cash_ref.get("cash", 0.0)) - fill - cost.total_cost
    if cash_after < -1e-8:
        raise RuntimeError("fee-inclusive affordability invariant violated")
    cash_ref["cash"] = max(cash_after, 0.0)
    _update_nav_order(order, trade_date, fill)
    _accrue_nav_fee_quote(
        fee_group_notionals,
        fee_group_id=fee_group_id,
        fee_quote=fee_quote,
    )
    order.zero_fill_days = 0
    _record_nav_fill_audit(
        fill_rows,
        order=order,
        trade_date=trade_date,
        trade_idx=trade_idx,
        capacity_notional=capacity,
        filled_notional=fill,
        transaction_cost=cost.total_cost,
        cost_breakdown=cost,
        valuation_time=trade_date,
        fee_quote=fee_quote,
        fee_order_id=_nav_fee_order_id(order),
        fee_group_id=fee_group_id,
    )
    return cost


def _nav_buy_cash_required(
    raw_fills: dict[str, tuple[_NavOrder, float, float, float]],
    *,
    trade_date: pd.Timestamp,
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
    cost_rate: float,
    trade_fee_model: TradeFeeModel | None,
    slippage_model: SlippageModel | None,
    fee_group_notionals: dict[str, float],
) -> float:
    return sum(
        item[3]
        + _nav_trade_fee(
            item[3],
            order=item[0],
            trade_date=trade_date,
            tables=tables,
            config=config,
            cost_rate=cost_rate,
            trade_fee_model=trade_fee_model,
            slippage_model=slippage_model,
            fee_group_notionals=fee_group_notionals,
        )[0].breakdown.total_cost
        for item in raw_fills.values()
    )


def _affordable_nav_buy_fill(
    candidate_fill: float,
    *,
    order: _NavOrder,
    price: float,
    cash: float,
    round_lot: int | None,
    trade_date: pd.Timestamp,
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
    cost_rate: float,
    trade_fee_model: TradeFeeModel | None,
    slippage_model: SlippageModel | None,
    fee_group_notionals: dict[str, float],
) -> float:
    """Find the largest candidate whose pure fee preview fits available cash."""

    def required(fill: float) -> float:
        quote, _ = _nav_trade_fee(
            fill,
            order=order,
            trade_date=trade_date,
            tables=tables,
            config=config,
            cost_rate=cost_rate,
            trade_fee_model=trade_fee_model,
            slippage_model=slippage_model,
            fee_group_notionals=fee_group_notionals,
        )
        return fill + quote.breakdown.total_cost

    candidate = max(float(candidate_fill), 0.0)
    available = max(float(cash), 0.0)
    if candidate <= 0.0 or available <= 0.0:
        return 0.0
    if required(candidate) <= available + 1e-9:
        return candidate
    if round_lot is not None and round_lot > 0 and price > 0:
        lot_notional = float(round_lot) * float(price)
        low_lots = 0
        high_lots = int(candidate // lot_notional)
        while low_lots < high_lots:
            mid_lots = (low_lots + high_lots + 1) // 2
            if required(mid_lots * lot_notional) <= available + 1e-9:
                low_lots = mid_lots
            else:
                high_lots = mid_lots - 1
        return float(low_lots) * lot_notional
    lower = 0.0
    upper = candidate
    for _ in range(64):
        midpoint = (lower + upper) / 2.0
        if required(midpoint) <= available:
            lower = midpoint
        else:
            upper = midpoint
    return lower


def _execute_sell_orders(
    *,
    rebalance_date: pd.Timestamp,
    entry_date: pd.Timestamp,
    next_entry_date: pd.Timestamp | None,
    requests: dict[str, float],
    current_weights: dict[str, float],
    cash_weight: float,
    config: ExecutionSimConfig,
    tables: _ExecutionTables,
    sink: _OrderSink,
) -> float:
    remaining = dict(requests)
    states = _build_order_states(requests)
    window_dates = _execution_window_dates(
        entry_date,
        max_days=config.sell_max_days,
        next_entry_date=next_entry_date,
        trade_dates=tables.trade_dates,
        date_to_idx=tables.date_to_idx,
    )
    for day_number, trade_date in enumerate(window_dates, start=1):
        for symbol in sorted(remaining):
            before = remaining[symbol]
            capacity = _capacity_weight(
                symbol,
                trade_date,
                config=config,
                price_table=tables.price_table,
                tradable_table=tables.sell_tradable_table,
                liquidity_tables=tables.liquidity_tables,
            )
            fill = min(before, capacity)
            if fill > 1e-12:
                remaining[symbol] = max(before - fill, 0.0)
                current_weights[symbol] = max(current_weights.get(symbol, 0.0) - fill, 0.0)
                if current_weights[symbol] <= 1e-12:
                    current_weights.pop(symbol, None)
                cash_weight += fill
                _record_fill(
                    sink.fill_rows,
                    rebalance_date=rebalance_date,
                    entry_date=entry_date,
                    trade_date=trade_date,
                    day_number=day_number,
                    side="sell",
                    symbol=symbol,
                    remaining_before=before,
                    capacity=capacity,
                    fill=fill,
                    config=config,
                )
                _update_state(states[symbol], trade_date, fill)
            if remaining.get(symbol, 0.0) <= 1e-12:
                remaining.pop(symbol, None)
        if not remaining:
            break
    _append_order_rows(
        sink.order_rows,
        rebalance_date=rebalance_date,
        entry_date=entry_date,
        side="sell",
        requests=requests,
        remaining=remaining,
        states=states,
        max_days=len(window_dates),
        config=config,
        unfilled_status="delayed_sell",
    )
    return cash_weight


def _execute_buy_orders(
    *,
    rebalance_date: pd.Timestamp,
    entry_date: pd.Timestamp,
    requests: dict[str, float],
    current_weights: dict[str, float],
    cash_weight: float,
    config: ExecutionSimConfig,
    tables: _ExecutionTables,
    sink: _OrderSink,
) -> float:
    remaining = dict(requests)
    states = _build_order_states(requests)
    abandoned: set[str] = set()
    window_dates = _execution_window_dates(
        entry_date,
        max_days=config.buy_max_days,
        next_entry_date=None,
        trade_dates=tables.trade_dates,
        date_to_idx=tables.date_to_idx,
    )
    for day_number, trade_date in enumerate(window_dates, start=1):
        daily_fills: dict[str, tuple[float, float]] = {}
        for symbol in sorted(remaining):
            if symbol in abandoned:
                continue
            before = remaining[symbol]
            capacity = _capacity_weight(
                symbol,
                trade_date,
                config=config,
                price_table=tables.price_table,
                tradable_table=tables.buy_tradable_table,
                liquidity_tables=tables.liquidity_tables,
            )
            fill = min(before, capacity)
            daily_fills[symbol] = (capacity, fill)

        total_requested_fill = sum(fill for _, fill in daily_fills.values())
        scale = 1.0
        if total_requested_fill > max(cash_weight, 0.0) and total_requested_fill > 0:
            scale = max(cash_weight, 0.0) / total_requested_fill

        cash_weight = _apply_buy_day_fills(
            daily_fills,
            remaining=remaining,
            states=states,
            abandoned=abandoned,
            current_weights=current_weights,
            cash_weight=cash_weight,
            scale=scale,
            rebalance_date=rebalance_date,
            entry_date=entry_date,
            trade_date=trade_date,
            day_number=day_number,
            config=config,
            sink=sink,
        )
        if not remaining:
            break
        if set(remaining).issubset(abandoned):
            break

    _append_order_rows(
        sink.order_rows,
        rebalance_date=rebalance_date,
        entry_date=entry_date,
        side="buy",
        requests=requests,
        remaining=remaining,
        states=states,
        max_days=len(window_dates),
        config=config,
        unfilled_status="cancelled_buy_deadline",
        abandoned=abandoned,
    )
    return cash_weight


def _apply_buy_day_fills(
    daily_fills: dict[str, tuple[float, float]],
    *,
    remaining: dict[str, float],
    states: dict[str, dict[str, Any]],
    abandoned: set[str],
    current_weights: dict[str, float],
    cash_weight: float,
    scale: float,
    rebalance_date: pd.Timestamp,
    entry_date: pd.Timestamp,
    trade_date: pd.Timestamp,
    day_number: int,
    config: ExecutionSimConfig,
    sink: _OrderSink,
) -> float:
    for symbol in sorted(remaining):
        if symbol in abandoned:
            continue
        before = remaining[symbol]
        capacity, raw_fill = daily_fills.get(symbol, (0.0, 0.0))
        fill = min(before, raw_fill * scale)
        if fill > 1e-12:
            remaining[symbol] = max(before - fill, 0.0)
            current_weights[symbol] = current_weights.get(symbol, 0.0) + fill
            cash_weight = max(cash_weight - fill, 0.0)
            _record_fill(
                sink.fill_rows,
                rebalance_date=rebalance_date,
                entry_date=entry_date,
                trade_date=trade_date,
                day_number=day_number,
                side="buy",
                symbol=symbol,
                remaining_before=before,
                capacity=capacity,
                fill=fill,
                config=config,
            )
            _update_state(states[symbol], trade_date, fill)
            states[symbol]["zero_fill_days"] = 0
        elif capacity <= 1e-12:
            states[symbol]["zero_fill_days"] += 1
            if (
                config.zero_fill_abort_days_buy is not None
                and states[symbol]["zero_fill_days"] >= config.zero_fill_abort_days_buy
            ):
                abandoned.add(symbol)
        if remaining.get(symbol, 0.0) <= 1e-12:
            remaining.pop(symbol, None)
    return cash_weight


def _execute_nav_orders_for_day(
    *,
    open_orders: list[_NavOrder],
    shares: dict[str, float],
    cash_ref: dict[str, float],
    trade_date: pd.Timestamp,
    trade_idx: int,
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
    cost_rate: float,
    trade_fee_model: TradeFeeModel | None,
    slippage_model: SlippageModel | None,
    fill_rows: list[dict[str, Any]],
    fee_group_notionals: dict[str, float],
    market_rules: _MarketRules | None = None,
    t1_available: dict[str, float] | None = None,
) -> tuple[float, CostBreakdown]:
    traded_notional = 0.0
    transaction_cost = CostBreakdown()
    sell_traded, sell_cost = _execute_nav_sell_orders_for_day(
        open_orders=open_orders,
        shares=shares,
        cash_ref=cash_ref,
        trade_date=trade_date,
        trade_idx=trade_idx,
        tables=tables,
        config=config,
        cost_rate=cost_rate,
        trade_fee_model=trade_fee_model,
        slippage_model=slippage_model,
        fill_rows=fill_rows,
        fee_group_notionals=fee_group_notionals,
        market_rules=market_rules,
        t1_available=t1_available,
    )
    traded_notional += sell_traded
    transaction_cost = _add_breakdown(transaction_cost, sell_cost)

    buy_traded, buy_cost = _execute_nav_buy_orders_for_day(
        open_orders=open_orders,
        shares=shares,
        cash_ref=cash_ref,
        trade_date=trade_date,
        trade_idx=trade_idx,
        tables=tables,
        config=config,
        cost_rate=cost_rate,
        trade_fee_model=trade_fee_model,
        slippage_model=slippage_model,
        fill_rows=fill_rows,
        fee_group_notionals=fee_group_notionals,
        market_rules=market_rules,
    )
    traded_notional += buy_traded
    transaction_cost = _add_breakdown(transaction_cost, buy_cost)
    return float(traded_notional), transaction_cost


def _execute_nav_sell_orders_for_day(
    *,
    open_orders: list[_NavOrder],
    shares: dict[str, float],
    cash_ref: dict[str, float],
    trade_date: pd.Timestamp,
    trade_idx: int,
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
    cost_rate: float,
    trade_fee_model: TradeFeeModel | None,
    slippage_model: SlippageModel | None,
    fill_rows: list[dict[str, Any]],
    fee_group_notionals: dict[str, float],
    market_rules: _MarketRules | None = None,
    t1_available: dict[str, float] | None = None,
) -> tuple[float, CostBreakdown]:
    traded_notional = 0.0
    transaction_cost = CostBreakdown()
    for order in sorted(
        [item for item in open_orders if item.side == "sell" and not _nav_order_is_complete(item)],
        key=lambda item: item.symbol,
    ):
        # Phase 4: 上市/停牌/退市 — 非 listed 状态当日不可卖.
        if (
            market_rules is not None
            and market_rules.enforce_listing_status
            and _listing_status_at(order.symbol, trade_date, tables.listing_status_table)
            != "listed"
        ):
            continue
        # Phase 4: 跌停 — 价格向下触板当日不可卖.
        if (
            market_rules is not None
            and market_rules.enforce_price_limits
            and _limit_down_at(order.symbol, trade_date, tables.limit_down_table)
        ):
            continue
        price = _price_at(order.symbol, trade_date, tables.price_table)
        if not np.isfinite(price):
            continue
        held_quantity = max(float(shares.get(order.symbol, 0.0)), 0.0)
        capacity = _capacity_notional(
            order.symbol,
            trade_date,
            config=config,
            price_table=tables.price_table,
            tradable_table=tables.sell_tradable_table,
            liquidity_tables=tables.liquidity_tables,
        )
        remaining_quantity = (
            max(float(order.remaining_quantity), 0.0)
            if order.remaining_quantity is not None
            else max(float(order.remaining_notional) / float(price), 0.0)
        )
        # Phase 4: T+1 — 当日可卖数量以 T+1 账本为上限 (排除当日新买).
        sellable_quantity = held_quantity
        if market_rules is not None and market_rules.enforce_t1 and t1_available is not None:
            sellable_quantity = min(
                held_quantity, max(float(t1_available.get(order.symbol, 0.0)), 0.0)
            )
        fill_quantity = min(
            remaining_quantity,
            sellable_quantity,
            max(float(capacity) / float(price), 0.0),
        )
        fill_quantity = _quantize_nav_sell_quantity(
            fill_quantity, held_quantity=held_quantity, config=config
        )
        fill = fill_quantity * float(price)
        if fill <= 1e-8:
            continue
        remaining_before_notional = remaining_quantity * float(price)
        cost = _apply_nav_sell_fill(
            order=order,
            fill=fill,
            fill_quantity=fill_quantity,
            held_quantity=held_quantity,
            remaining_before_notional=remaining_before_notional,
            trade_date=trade_date,
            trade_idx=trade_idx,
            capacity=capacity,
            shares=shares,
            cash_ref=cash_ref,
            tables=tables,
            config=config,
            cost_rate=cost_rate,
            trade_fee_model=trade_fee_model,
            slippage_model=slippage_model,
            fill_rows=fill_rows,
            fee_group_notionals=fee_group_notionals,
        )
        if cost is None:
            continue
        traded_notional += fill
        transaction_cost = _add_breakdown(transaction_cost, cost)
    return float(traded_notional), transaction_cost


def _execute_nav_buy_orders_for_day(
    *,
    open_orders: list[_NavOrder],
    shares: dict[str, float],
    cash_ref: dict[str, float],
    trade_date: pd.Timestamp,
    trade_idx: int,
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
    cost_rate: float,
    trade_fee_model: TradeFeeModel | None,
    slippage_model: SlippageModel | None,
    fill_rows: list[dict[str, Any]],
    fee_group_notionals: dict[str, float],
    market_rules: _MarketRules | None = None,
) -> tuple[float, CostBreakdown]:
    candidates = [
        item for item in open_orders if item.side == "buy" and item.remaining_notional > 1e-8
    ]
    raw_fills: dict[str, tuple[_NavOrder, float, float, float]] = {}
    for order in sorted(candidates, key=lambda item: item.symbol):
        # Phase 4: 涨停 — 价格向上触板当日不可买 (计入 zero_fill, 不放弃).
        if (
            market_rules is not None
            and market_rules.enforce_price_limits
            and _limit_up_at(order.symbol, trade_date, tables.limit_up_table)
        ):
            order.zero_fill_days += 1
            continue
        price = _price_at(order.symbol, trade_date, tables.price_table)
        capacity = _capacity_notional(
            order.symbol,
            trade_date,
            config=config,
            price_table=tables.price_table,
            tradable_table=tables.buy_tradable_table,
            liquidity_tables=tables.liquidity_tables,
        )
        raw_fill = min(float(order.remaining_notional), capacity)
        if raw_fill <= 1e-8:
            if capacity <= 1e-8:
                order.zero_fill_days += 1
            continue
        raw_fills[order.symbol] = (order, float(price), capacity, raw_fill)

    total_raw_fill = sum(item[3] for item in raw_fills.values())
    if total_raw_fill <= 1e-8:
        return 0.0, CostBreakdown()
    cash = max(float(cash_ref.get("cash", 0.0)), 0.0)
    total_cash_required = _nav_buy_cash_required(
        raw_fills,
        trade_date=trade_date,
        tables=tables,
        config=config,
        cost_rate=cost_rate,
        trade_fee_model=trade_fee_model,
        slippage_model=slippage_model,
        fee_group_notionals=fee_group_notionals,
    )
    scale = min(1.0, cash / total_cash_required) if total_cash_required > 0 else 0.0
    if scale <= 1e-12:
        return 0.0, CostBreakdown()

    return _apply_nav_buy_fills(
        raw_fills,
        total_raw_fill=total_raw_fill,
        scale=scale,
        shares=shares,
        cash_ref=cash_ref,
        trade_date=trade_date,
        trade_idx=trade_idx,
        tables=tables,
        config=config,
        cost_rate=cost_rate,
        trade_fee_model=trade_fee_model,
        slippage_model=slippage_model,
        fill_rows=fill_rows,
        fee_group_notionals=fee_group_notionals,
        market_rules=market_rules,
    )


def _apply_nav_buy_fills(
    raw_fills: dict[str, tuple[_NavOrder, float, float, float]],
    *,
    total_raw_fill: float,
    scale: float,
    shares: dict[str, float],
    cash_ref: dict[str, float],
    trade_date: pd.Timestamp,
    trade_idx: int,
    tables: _ExecutionTables,
    config: ExecutionSimConfig,
    cost_rate: float,
    trade_fee_model: TradeFeeModel | None,
    slippage_model: SlippageModel | None,
    fill_rows: list[dict[str, Any]],
    fee_group_notionals: dict[str, float],
    market_rules: _MarketRules | None,
) -> tuple[float, CostBreakdown]:
    traded_notional = 0.0
    transaction_cost = CostBreakdown()
    for _, (order, price, capacity, raw_fill) in sorted(raw_fills.items()):
        round_lot = market_rules.round_lot if market_rules is not None else None
        dated_fees_alone_require_scaling = (
            isinstance(trade_fee_model, DatedTradeFeeModel)
            and total_raw_fill <= float(cash_ref.get("cash", 0.0)) + 1e-9
        )
        fill = (
            raw_fill
            if round_lot is not None and round_lot > 0 and dated_fees_alone_require_scaling
            else raw_fill * scale
        )
        if fill <= 1e-8:
            continue
        # Phase 4: 整手买入 — 成交数量向下取整到整手股数, 不足一手则当日不买.
        lot_tolerance = market_rules.lot_tolerance if market_rules is not None else 0.0
        if round_lot is not None and round_lot > 0 and price > 0:
            lot = float(round_lot)
            raw_quantity = fill / float(price)
            lot_quantity = (raw_quantity // lot) * lot
            if lot_quantity < lot - lot_tolerance:
                order.zero_fill_days += 1
                continue
            fill = lot_quantity * float(price)
            if fill <= 1e-8:
                order.zero_fill_days += 1
                continue
        fill = _affordable_nav_buy_fill(
            fill,
            order=order,
            price=price,
            cash=float(cash_ref.get("cash", 0.0)),
            round_lot=round_lot,
            trade_date=trade_date,
            tables=tables,
            config=config,
            cost_rate=cost_rate,
            trade_fee_model=trade_fee_model,
            slippage_model=slippage_model,
            fee_group_notionals=fee_group_notionals,
        )
        if fill <= 1e-8:
            order.zero_fill_days += 1
            continue
        cost = _apply_nav_buy_fill(
            order=order,
            fill=fill,
            price=price,
            capacity=capacity,
            trade_date=trade_date,
            trade_idx=trade_idx,
            shares=shares,
            cash_ref=cash_ref,
            tables=tables,
            config=config,
            cost_rate=cost_rate,
            trade_fee_model=trade_fee_model,
            slippage_model=slippage_model,
            fill_rows=fill_rows,
            fee_group_notionals=fee_group_notionals,
        )
        traded_notional += fill
        transaction_cost = _add_breakdown(transaction_cost, cost)
    return float(traded_notional), transaction_cost
