"""Pure explicit-input financial closure from pinned Platform (Apache-2.0)."""

from __future__ import annotations

from typing import Literal

import pandas as pd

from ._execution_models import CostModel, SlippageModel
from ._period_helpers import _compute_trade_summary
from .pricing import slippage_pricing_row
from .turnover import (
    RebalanceTurnoverReport,
    build_rebalance_turnover_report,
    turnover_from_trade_weights,
)
from .types import BacktestLegResult, BacktestPositionState


def _next_position_state(
    leg: BacktestLegResult,
    *,
    entry_date: pd.Timestamp,
) -> BacktestPositionState:
    initial_cash = not leg.holdings and leg.is_initial
    has_recorded_target = bool(leg.target_holdings) or not leg.is_initial
    return BacktestPositionState(
        holdings=None if initial_cash else set(leg.holdings),
        weights=None if initial_cash else leg.weights,
        entry_date=None if initial_cash else entry_date,
        entry_prices=None if initial_cash else leg.entry_prices,
        target_holdings=set(leg.target_holdings) if has_recorded_target else None,
        target_weights=leg.target_weights if has_recorded_target else None,
    )


def _build_leg_turnover_report(
    previous: BacktestPositionState,
    target_weights: pd.Series,
    trade_weights: pd.Series,
) -> RebalanceTurnoverReport:
    previous_holdings = (
        previous.target_holdings if previous.target_holdings is not None else previous.holdings
    )
    previous_target_weights = (
        previous.target_weights if previous.target_weights is not None else previous.weights
    )
    return build_rebalance_turnover_report(
        previous_holdings=previous_holdings,
        target_holdings=target_weights[target_weights > 1e-12].index,
        previous_target_weights=previous_target_weights,
        target_weights=target_weights,
        pretrade_trade_weights=trade_weights,
    )


def _build_backtest_leg_result(
    *,
    holdings: list[str],
    target_weights: pd.Series,
    weights: pd.Series,
    entry_prices: pd.Series,
    exit_prices: pd.Series,
    period_exit_idx: int,
    entry_idx: int,
    entry_date: pd.Timestamp,
    trade_dates: list[pd.Timestamp],
    entry_price_table: pd.DataFrame,
    side: Literal["long", "short"],
    previous: BacktestPositionState,
    cost_model: CostModel,
    slippage_model: SlippageModel,
    amount_tables: dict[str, pd.DataFrame],
    preserve_gross_exposure: bool = False,
) -> BacktestLegResult:
    period_returns = (exit_prices / entry_prices) - 1.0
    gross = float((period_returns * weights.reindex(period_returns.index)).sum())
    if side == "short":
        gross = -gross

    turnover, entry_turnover, exit_turnover, trade_weights = _compute_trade_summary(
        previous.weights,
        previous.entry_prices,
        previous.entry_date,
        weights,
        entry_date,
        price_table=entry_price_table,
        preserve_gross_exposure=preserve_gross_exposure,
    )
    turnover_breakdown = turnover_from_trade_weights(
        trade_weights,
        is_initial=previous.weights is None,
    )
    turnover_report = _build_leg_turnover_report(previous, target_weights, trade_weights)
    fee_cost = cost_model.cost(
        turnover,
        is_initial=previous.weights is None,
        side=side,
        entry_turnover=entry_turnover,
        exit_turnover=exit_turnover,
        holding_days=int(period_exit_idx - entry_idx),
        gross_exposure=float(weights.abs().sum()),
    )
    slippage_cost = slippage_model.cost(
        trade_weights,
        pricing_row=slippage_pricing_row(
            slippage_model=slippage_model,
            amount_tables=amount_tables,
            entry_date=entry_date,
        ),
        is_initial=previous.weights is None,
        side=side,
    )
    return BacktestLegResult(
        holdings=holdings,
        weights=weights,
        entry_prices=entry_prices,
        exit_idx=period_exit_idx,
        exit_date=trade_dates[period_exit_idx],
        gross=gross,
        turnover=turnover,
        fee_cost=fee_cost,
        slippage_cost=slippage_cost,
        buy_turnover=turnover_breakdown.buy_weight,
        sell_turnover=turnover_breakdown.sell_weight,
        gross_traded_weight=turnover_breakdown.gross_traded_weight,
        half_l1_turnover=turnover_breakdown.half_l1_turnover,
        is_initial=turnover_breakdown.is_initial,
        target_name_turnover=turnover_report.target_name_turnover,
        target_entered_names=turnover_report.target_entered_names,
        target_exited_names=turnover_report.target_exited_names,
        target_overlap_names=turnover_report.target_overlap_names,
        target_weight_full_l1=turnover_report.target_weight_full_l1,
        target_weight_half_l1=turnover_report.target_weight_half_l1,
        pretrade_demand_buy=turnover_report.pretrade_demand_buy,
        pretrade_demand_sell=turnover_report.pretrade_demand_sell,
        pretrade_demand_full_l1=turnover_report.pretrade_demand_full_l1,
        pretrade_demand_half_l1=turnover_report.pretrade_demand_half_l1,
        executed_buy=turnover_report.executed_buy,
        executed_sell=turnover_report.executed_sell,
        executed_gross=turnover_report.executed_gross,
        executed_full_l1=turnover_report.executed_full_l1,
        executed_half_l1=turnover_report.executed_half_l1,
        executed_cost=turnover_report.executed_cost,
        target_holdings=tuple(str(symbol) for symbol in target_weights.index),
        target_weights=target_weights.copy(),
        target_gross_exposure=float(target_weights.abs().sum()),
        target_cash_weight=max(0.0, 1.0 - float(target_weights.abs().sum())),
        modeled_gross_exposure=float(weights.abs().sum()),
        modeled_cash_weight=max(0.0, 1.0 - float(weights.abs().sum())),
    )
