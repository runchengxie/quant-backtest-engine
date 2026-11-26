"""Attribution is captured at the existing financial owner, never replayed."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from test_held_position_marks import DAYS, request
from test_suspension_valuation import replay

from quant_backtest_core.daily.execution import DetailedTradeFeeModel
from quant_backtest_core.daily.runner import run_daily


def test_live_symbol_components_include_exit_fees_and_reconcile():
    req = request(
        "adjusted",
        prices={(DAYS[1], "A"): 12},
        targets=[(DAYS[0], "A", 1), (DAYS[2], "B", 1)],
    )
    req = replace(
        req,
        fee_model=DetailedTradeFeeModel(
            buy_slippage_bps=10,
            sell_slippage_bps=10,
            buy_commission_bps=0,
            sell_commission_bps=0,
            sell_stamp_duty_bps=0,
            transfer_fee_bps=0,
            min_commission=0,
        ),
    )
    result = run_daily(req)
    symbols = result.symbol_attribution
    daily = result.daily_attribution
    assert symbols.status.eq("complete").all()
    assert daily.status.eq("complete").all()
    assert daily.residual.abs().max() < 1e-9
    assert daily.cash_pnl.eq(0).all() and daily.receivable_pnl.eq(0).all()
    assert symbols.fees.sum() == pytest.approx(result.fills.transaction_cost.sum())
    assert symbols.net_pnl.sum() == pytest.approx(result.daily.portfolio_value.iloc[-1] - 1000)
    assert symbols.iloc[0].net_pnl == pytest.approx(-symbols.iloc[0].fees)
    exit_row = symbols.loc[symbols.trade_date.eq("20200106") & symbols.symbol.eq("A")].iloc[0]
    assert exit_row.closing_value == 0 and exit_row.sell_principal > 0
    assert exit_row.net_pnl == pytest.approx(
        exit_row.closing_value
        - exit_row.opening_value
        - exit_row.buy_principal
        + exit_row.sell_principal
        - exit_row.fees
    )
    expected = result.daily.portfolio_value.diff().fillna(
        result.daily.portfolio_value.iloc[0] - 1000
    )
    np.testing.assert_allclose(daily.symbol_net_pnl, expected, atol=1e-9)


def test_policy_valued_endpoint_uses_owner_carried_value():
    result = run_daily(replay())
    row = result.symbol_attribution.iloc[1]
    assert row.status == "complete" and row.policy_valued
    assert row.opening_value == row.closing_value == 1000 and row.net_pnl == 0


def test_incomplete_endpoint_withholds_both_adjacent_intervals():
    result = run_daily(request("adjusted", prices={(DAYS[1], "A"): np.nan}))
    assert result.daily_attribution.status.tolist() == [
        "complete",
        "incomplete_valuation",
        "incomplete_valuation",
        "complete",
        "complete",
    ]
    assert result.daily_attribution.iloc[1:3].symbol_net_pnl.isna().all()
    assert result.symbol_attribution.iloc[1:3].net_pnl.isna().all()


def test_corporate_actions_withhold_instead_of_plugging_receivables():
    from test_execution_corporate_actions import action, run

    result = run([action()])
    assert result.daily_attribution.status.eq("unsupported_corporate_actions").all()
    assert result.daily_attribution.symbol_net_pnl.isna().all()
    assert result.daily_attribution.receivable_pnl.isna().all()
    assert result.symbol_attribution.net_pnl.isna().all()


def test_same_session_round_trip_and_fee_only_symbol_are_retained():
    from quant_backtest_core.daily.execution_sim.attribution import endpoint_attribution

    marks = dict(trade_date="20200102", endpoint_complete=True, policy_valued_symbols=())
    rows, daily = endpoint_attribution(
        opening_values={},
        closing_values={},
        fills=[
            dict(symbol="A", side="buy", filled_notional=100, transaction_cost=1),
            dict(symbol="A", side="sell", filled_notional=110, transaction_cost=2),
            dict(symbol="B", side="buy", filled_notional=0, transaction_cost=3),
        ],
        opening_equity=1000,
        closing_equity=1004,
        opening_complete=True,
        marks=marks,
        corporate_actions=False,
    )
    assert [row["net_pnl"] for row in rows] == [7, -3]
    assert daily["symbol_net_pnl"] == 4 and daily["residual"] == 0


def test_cash_only_and_unexplained_equity_change_never_get_symbol_plug():
    from quant_backtest_core.daily.execution_sim.attribution import endpoint_attribution

    kwargs = dict(
        opening_values={},
        closing_values={},
        fills=[],
        opening_equity=1000,
        opening_complete=True,
        marks=dict(trade_date="20200102", endpoint_complete=True, policy_valued_symbols=()),
        corporate_actions=False,
    )
    rows, daily = endpoint_attribution(**kwargs, closing_equity=1000)
    assert rows == [] and daily["symbol_net_pnl"] == 0 and daily["status"] == "complete"
    rows, daily = endpoint_attribution(**kwargs, closing_equity=1001)
    assert rows == [] and daily["residual"] == 1 and daily["status"] == "unreconciled"
    assert np.isnan(daily["symbol_net_pnl"])


@pytest.mark.parametrize("mode", ["adjusted", "sequenced"])
def test_owner_capture_does_not_change_legacy_tables(monkeypatch, mode):
    from quant_backtest_core.daily.execution_sim import adjusted_nav

    req = request(mode)
    captured = run_daily(req)
    original = adjusted_nav.endpoint_attribution

    def discard(*args, **kwargs):
        original(*args, **kwargs)
        return [], {}

    monkeypatch.setattr(adjusted_nav, "endpoint_attribution", discard)
    discarded = run_daily(req)
    for name in ("daily", "orders", "fills", "valuation_marks"):
        pd.testing.assert_frame_equal(getattr(captured, name), getattr(discarded, name))
    assert captured.summary == discarded.summary
