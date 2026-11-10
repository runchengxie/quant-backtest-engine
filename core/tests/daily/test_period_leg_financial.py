from __future__ import annotations

from dataclasses import fields, replace

import pandas as pd
import pytest

from quant_backtest_core.daily._execution_models import (
    BpsCostModel,
    NoSlippageModel,
    ParticipationSlippageModel,
    SideBpsCostModel,
)
from quant_backtest_core.daily.leg_financial import (
    _build_backtest_leg_result,
    _build_leg_turnover_report,
    _next_position_state,
)
from quant_backtest_core.daily.period_turnover import (
    period_result_from_leg,
    period_result_from_legs,
)
from quant_backtest_core.daily.pricing import slippage_pricing_row
from quant_backtest_core.daily.trade_accounting import (
    _compute_trade_summary,
    _drift_previous_weights,
    compute_trade_summary,
    drift_previous_weights,
)
from quant_backtest_core.daily.types import (
    BacktestPeriodResult,
    BacktestPositionState,
    CostBreakdown,
)


def build_leg(*, side="long", previous=None, weights=None, target=None):
    dates = list(pd.date_range("2026-01-05", periods=4))
    weights = pd.Series({"A": 0.4, "B": 0.2}) if weights is None else weights
    target = pd.Series({"A": 0.6, "C": 0.1}) if target is None else target
    return _build_backtest_leg_result(
        holdings=list(weights.index),
        target_weights=target,
        weights=weights,
        entry_prices=pd.Series({"A": 10.0, "B": 20.0}),
        exit_prices=pd.Series({"A": 12.0, "B": 18.0}),
        period_exit_idx=3,
        entry_idx=0,
        entry_date=dates[0],
        trade_dates=dates,
        entry_price_table=pd.DataFrame({"A": [10.0] * 4, "B": [20.0] * 4}, index=dates),
        side=side,
        previous=previous or BacktestPositionState(),
        cost_model=SideBpsCostModel(1, 2, 3, 4, 5),
        slippage_model=NoSlippageModel(),
        amount_tables={},
        preserve_gross_exposure=True,
    )


@pytest.mark.parametrize("side,sign", [("long", 1), ("short", -1)])
def test_explicit_leg_preserves_exposure_sign_and_cost_holding_days(side, sign):
    leg = build_leg(side=side)
    assert leg.gross == pytest.approx(sign * 0.06)
    assert leg.modeled_gross_exposure == pytest.approx(0.6)
    assert leg.modeled_cash_weight == pytest.approx(0.4)
    assert leg.target_holdings == ("A", "C")
    assert leg.target_gross_exposure == pytest.approx(0.7)
    assert leg.fee_cost == pytest.approx(0.00006 if side == "long" else 0.00108)
    assert leg.turnover == pytest.approx(0.6)
    assert leg.half_l1_turnover == pytest.approx(0.3)
    assert leg.is_initial
    assert leg.executed_full_l1 is None
    assert leg.target_weight_full_l1 == pytest.approx(0.7)
    assert leg.net == leg.gross - leg.fee_cost - leg.slippage_cost


def test_none_and_empty_prior_have_distinct_initial_turnover():
    initial = build_leg()
    cash = build_leg(previous=BacktestPositionState(holdings=set(), weights=pd.Series(dtype=float)))
    assert initial.is_initial and not cash.is_initial
    assert initial.turnover == pytest.approx(0.6)
    assert cash.turnover == pytest.approx(0.3)


def test_state_rollover_preserves_initial_cash_and_recorded_target():
    empty = pd.Series(dtype=float)
    cash = build_leg(weights=empty, target=empty)
    state = _next_position_state(cash, entry_date=pd.Timestamp("2026-01-05"))
    assert state == BacktestPositionState()
    target_cash = _next_position_state(
        replace(cash, target_holdings=("C",), target_weights=pd.Series({"C": 0.5})),
        entry_date=pd.Timestamp("2026-01-05"),
    )
    assert target_cash.holdings is None
    assert target_cash.target_holdings == {"C"}
    later = _next_position_state(
        replace(cash, is_initial=False), entry_date=pd.Timestamp("2026-01-05")
    )
    assert later.holdings == set() and later.target_holdings == set()
    assert later.weights is cash.weights


def test_turnover_report_uses_previous_targets_instead_of_executed_holdings():
    report = _build_leg_turnover_report(
        BacktestPositionState(
            holdings={"A"},
            weights=pd.Series({"A": 0.4}),
            target_holdings={"B"},
            target_weights=pd.Series({"B": 0.7}),
        ),
        pd.Series({"B": 0.3, "C": 0.2}),
        pd.Series({"A": -0.4, "B": 0.3, "C": 0.2}),
    )
    assert report.target_entered_names == ("C",)
    assert report.target_exited_names == ()
    assert report.target_overlap_names == ("B",)
    assert report.target_weight_full_l1 == pytest.approx(0.6)
    assert report.pretrade_demand_full_l1 == pytest.approx(0.9)
    assert report.executed_full_l1 is None


def test_period_aggregation_preserves_every_leg_field_and_owned_class():
    leg = build_leg()
    result = period_result_from_leg(leg)
    assert isinstance(result, BacktestPeriodResult)
    for field in fields(result):
        if field.name in {"is_initial_build", "net", "total_cost"}:
            continue
        assert getattr(result, field.name) == getattr(leg, field.name)
    assert result.is_initial_build == leg.is_initial
    assert result.net == leg.net
    assert result.total_cost == leg.total_cost
    assert type(result.cost_breakdown) is CostBreakdown


def test_asymmetric_period_exits_unknowns_and_sorted_names():
    long_leg = build_leg()
    short_leg = replace(
        build_leg(side="short"),
        exit_idx=1,
        target_entered_names=("Z", "A"),
        target_overlap_names=("B",),
        target_name_turnover=0.5,
        executed_buy=0.0,
    )
    dates = list(pd.date_range("2026-01-05", periods=4))
    result = period_result_from_legs(long_leg, short_leg, trade_dates=dates)
    assert result.exit_idx == 3 and result.exit_date == dates[3]
    assert result.executed_buy is None
    assert result.target_name_turnover == pytest.approx(1.5)
    assert result.target_entered_names == tuple(
        sorted(set(long_leg.target_entered_names) | {"A", "Z"})
    )
    assert result.total_cost == long_leg.total_cost + short_leg.total_cost
    assert result.net == result.gross - result.total_cost
    assert result.target_cash_weight == 0.0


def test_supplied_participation_table_only_and_original_key_errors():
    date = pd.Timestamp("2026-01-05")
    model = ParticipationSlippageModel(amount_col="volume")
    table = pd.DataFrame({"A": [1000.0]}, index=[date])
    pd.testing.assert_series_equal(
        slippage_pricing_row(
            slippage_model=model, amount_tables={"volume": table}, entry_date=date
        ),
        table.loc[date],
    )
    assert (
        slippage_pricing_row(
            slippage_model=NoSlippageModel(),
            amount_tables={},
            entry_date=date,
        )
        is None
    )
    with pytest.raises(KeyError):
        slippage_pricing_row(slippage_model=model, amount_tables={}, entry_date=date)
    with pytest.raises(KeyError):
        slippage_pricing_row(
            slippage_model=model,
            amount_tables={"volume": table},
            entry_date=date + pd.Timedelta(days=1),
        )


def test_legacy_api_alias_identity_and_empty_target_semantics():
    assert _compute_trade_summary is compute_trade_summary
    assert _drift_previous_weights is drift_previous_weights
    date = pd.Timestamp("2026-01-05")
    summary = compute_trade_summary(
        pd.Series({"A": 1.0}),
        None,
        None,
        pd.Series(dtype=float),
        date,
        price_table=pd.DataFrame(),
    )
    assert summary[:3] == (0.0, 0.0, 0.0)
    assert summary[3].empty


def test_original_bps_cost_model_is_still_used():
    assert BpsCostModel(10).cost(
        0.5,
        is_initial=True,
        side="long",
        gross_exposure=0.4,
    ) == pytest.approx(0.0004)


def test_unknown_optional_target_diagnostics_remain_unknown():
    leg = replace(build_leg(), target_name_turnover=None, target_weight_full_l1=None)
    result = period_result_from_legs(
        leg, build_leg(side="short"), trade_dates=list(pd.date_range("2026-01-05", periods=4))
    )
    assert result.target_name_turnover is None
    assert result.target_weight_full_l1 is None
