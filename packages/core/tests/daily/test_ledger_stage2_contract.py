import numpy as np
import pandas as pd
import pytest

from quant_backtest_core.daily.execution_sim import (
    UnifiedLedger,
    simulate_ideal_daily_nav,
)


def _pricing_frame(dates, symbols, *, amount=500_000.0, price=10.0, tradable=True):
    rows = []
    for i, date in enumerate(pd.to_datetime(dates)):
        for symbol in symbols:
            rows.append(
                {
                    "trade_date": date,
                    "symbol": symbol,
                    "open": float(price) + i,
                    "amount": float(amount),
                    "medadv20_amount": float(amount),
                    "is_tradable": bool(tradable),
                }
            )
    return pd.DataFrame(rows)


def _positions(rebalance_date, entry_date, symbols, weight):
    return pd.DataFrame(
        {
            "rebalance_date": [rebalance_date] * len(symbols),
            "entry_date": [entry_date] * len(symbols),
            "symbol": symbols,
            "weight": [weight] * len(symbols),
            "side": ["long"] * len(symbols),
        }
    )


def test_unified_ledger_has_eight_fields_and_conserves():
    dates = pd.date_range("2020-01-02", periods=4, freq="B")
    positions = _positions("20200102", "20200102", ["AAA"], 1.0)
    pricing = _pricing_frame(dates, ["AAA"])
    result = simulate_ideal_daily_nav(
        positions,
        pricing,
        price_col="open",
        transaction_cost_bps=0.0,
        portfolio_value=1_000.0,
    )
    ledger = result.to_unified_ledger(portfolio_value=1_000.0)

    assert isinstance(ledger, UnifiedLedger)
    for field in (
        "targets",
        "orders",
        "fills",
        "daily_positions",
        "daily_cash",
        "daily_nav",
        "cost_breakdown",
        "turnover_breakdown",
    ):
        assert getattr(ledger, field).shape[0] >= 0

    nav = ledger.daily_nav["nav"].to_numpy(dtype=float)
    cash = ledger.daily_cash["cash"].to_numpy(dtype=float)
    positions_value = ledger.daily_positions["positions_value"].to_numpy(dtype=float)
    assert np.allclose(nav, cash + positions_value, rtol=1e-9)
    assert ledger.daily_nav["trade_date"].equals(ledger.daily_cash["trade_date"])
    assert ledger.daily_cash["trade_date"].equals(ledger.daily_positions["trade_date"])


def test_unified_ledger_cost_turnover_breakdown_by_side():
    dates = pd.date_range("2020-01-02", periods=3, freq="B")
    positions = _positions("20200102", "20200102", ["AAA", "BBB"], 0.5)
    pricing = _pricing_frame(dates, ["AAA", "BBB"])
    result = simulate_ideal_daily_nav(
        positions,
        pricing,
        price_col="open",
        transaction_cost_bps=10.0,
        portfolio_value=10_000.0,
    )
    ledger = result.to_unified_ledger(portfolio_value=10_000.0)

    total_cost = float(
        ledger.cost_breakdown.loc[
            ledger.cost_breakdown["side"].eq("total"), "transaction_cost"
        ].iloc[0]
    )
    side_cost = ledger.cost_breakdown[ledger.cost_breakdown["side"].ne("total")][
        "transaction_cost"
    ].sum()
    assert total_cost == pytest.approx(side_cost, rel=1e-9)
    assert total_cost > 0.0

    total_turn = float(
        ledger.turnover_breakdown.loc[
            ledger.turnover_breakdown["side"].eq("total"), "filled_notional"
        ].iloc[0]
    )
    side_turn = ledger.turnover_breakdown[ledger.turnover_breakdown["side"].ne("total")][
        "filled_notional"
    ].sum()
    assert total_turn == pytest.approx(side_turn, rel=1e-9)


def test_unified_ledger_respects_minimum_commission():
    from quant_backtest_core.daily.execution_sim import TradeFeeModel

    dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
    positions = _positions("20200102", "20200102", ["AAA", "BBB"], 0.01)
    pricing = _pricing_frame(dates, ["AAA", "BBB"], amount=500_000.0, price=10.0)
    fee_model = TradeFeeModel(
        buy_commission_bps=1.0,
        sell_commission_bps=1.0,
        min_commission=5.0,
    )
    result = simulate_ideal_daily_nav(
        positions,
        pricing,
        price_col="open",
        transaction_cost_bps=0.0,
        portfolio_value=10_000.0,
        trade_fee_model=fee_model,
    )
    ledger = result.to_unified_ledger(portfolio_value=10_000.0)

    assert not ledger.fills.empty
    assert float(ledger.fills["transaction_cost"].min()) >= 5.0 - 1e-9
    total_cost = float(
        ledger.cost_breakdown.loc[
            ledger.cost_breakdown["side"].eq("total"), "transaction_cost"
        ].iloc[0]
    )
    assert total_cost >= 2.0 * 5.0 - 1e-9
