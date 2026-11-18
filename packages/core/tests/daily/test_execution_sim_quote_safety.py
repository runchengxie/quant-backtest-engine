"""Synthetic regressions for valuation memory and explicit trading controls."""

import numpy as np
import pandas as pd
import pytest

from quant_backtest_core.daily.execution_sim import (
    ExecutionSimConfig,
    prepare_execution_tables,
    simulate_capacity_execution,
    simulate_execution_adjusted_nav,
    simulate_ideal_daily_nav,
)


def inputs():
    dates = pd.date_range("2020-01-06", periods=4, freq="B")
    pricing = pd.DataFrame(
        {"trade_date": dates, "symbol": "AAA", "close": 10.0, "amount": 1_000_000.0}
    )
    positions = pd.DataFrame(
        {"rebalance_date": [dates[0]], "entry_date": [dates[0]], "symbol": ["AAA"], "weight": [1.0]}
    )
    config = ExecutionSimConfig(
        enabled=True,
        portfolio_value=1_000.0,
        participation_rate=1.0,
        liquidity_cols=("amount",),
    )
    return pricing, positions, config


def test_new_holding_keeps_last_observed_value_without_trading_missing_quote():
    pricing, positions, config = inputs()
    pricing.loc[1, "close"] = np.nan
    result = simulate_execution_adjusted_nav(
        positions,
        pricing,
        config,
        price_col="close",
        transaction_cost_bps=25,
    )
    # Buying with a 0.25% fee spends 1000 = notional * 1.0025.
    expected_value = 1_000.0 / 1.0025
    assert result.daily["portfolio_value"].tolist() == pytest.approx([expected_value] * 4)
    assert result.daily["executed_return"].iloc[0] == pytest.approx(1 / 1.0025 - 1)
    assert result.daily["executed_return"].iloc[1] == pytest.approx(0)
    assert result.daily["traded_notional"].iloc[1] == 0
    assert result.daily["transaction_cost"].iloc[1] == 0
    assert len(result.fills) == 1
    pricing.loc[3, "close"] = 20.0
    changed_future = simulate_execution_adjusted_nav(
        positions,
        pricing,
        config,
        price_col="close",
        transaction_cost_bps=25,
    )
    pd.testing.assert_frame_equal(result.daily.iloc[:3], changed_future.daily.iloc[:3])


@pytest.mark.parametrize("run", [simulate_capacity_execution, simulate_execution_adjusted_nav])
@pytest.mark.parametrize("keyword", ["tradable_col", "buy_tradable_col", "sell_tradable_col"])
def test_explicit_missing_trading_control_blocks_execution(run, keyword):
    pricing, positions, config = inputs()
    result = run(positions, pricing, config, price_col="close", **{keyword: "absent_flag"})
    assert result.summary["status"] == "missing_pricing_columns"
    assert result.summary["missing_pricing_columns"] == ["absent_flag"]
    assert result.fills.empty


def test_prepared_tables_reject_explicit_missing_side_control():
    pricing, _, config = inputs()
    with pytest.raises(ValueError, match="missing_pricing_columns"):
        prepare_execution_tables(pricing, config, price_col="close", buy_tradable_col="typo")


def test_ideal_new_holding_keeps_its_entry_valuation_on_missing_next_quote():
    pricing, positions, _ = inputs()
    pricing.loc[1, "close"] = np.nan
    result = simulate_ideal_daily_nav(
        positions,
        pricing,
        price_col="close",
        portfolio_value=1_000.0,
    )
    assert result.daily["portfolio_value"].tolist() == pytest.approx([1_000.0] * 4)
