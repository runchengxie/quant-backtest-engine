from __future__ import annotations

import inspect

import pandas as pd

import quant_backtest_core.daily.execution_sim as execution_sim
import quant_backtest_core.daily.execution_sim.core as execution_core
import quant_backtest_core.daily.execution_sim.table_preparation as table_preparation
from quant_backtest_core.daily.execution_sim import (
    ExecutionSimConfig,
    prepare_execution_tables,
    simulate_capacity_execution,
    simulate_execution_adjusted_nav,
    simulate_ideal_daily_nav,
)


def test_execution_sim_package_exports_are_stable() -> None:
    assert execution_sim.__all__ == [
        "CorporateAction",
        "SELL_UNTIL_NEXT_REBALANCE",
        "ExecutionAdjustedNavResult",
        "ExecutionSimConfig",
        "ExecutionSimResult",
        "PreparedExecutionTables",
        "TradeFeeModel",
        "UnifiedLedger",
        "audit_delisting_exits",
        "build_execution_sim_config",
        "describe_execution_sim_config",
        "describe_trade_fee_model",
        "prepare_execution_tables",
        "required_execution_sim_columns",
        "simulate_capacity_execution",
        "simulate_execution_adjusted_nav",
        "simulate_ideal_daily_nav",
        "to_unified_ledger",
    ]
    assert execution_core.prepare_execution_tables is prepare_execution_tables
    assert execution_core.simulate_capacity_execution is simulate_capacity_execution
    assert execution_core.simulate_execution_adjusted_nav is simulate_execution_adjusted_nav
    assert execution_core.simulate_ideal_daily_nav is simulate_ideal_daily_nav
    assert inspect.signature(execution_core.prepare_execution_tables) == inspect.signature(
        table_preparation.prepare_execution_tables
    )


def test_adjusted_nav_accepts_reused_prepared_execution_tables(monkeypatch):
    dates = pd.date_range("2020-01-01", periods=3, freq="B")
    pricing = pd.DataFrame(
        {
            "trade_date": dates,
            "symbol": ["AAA"] * len(dates),
            "open": [10.0] * len(dates),
            "amount": [500_000.0] * len(dates),
            "medadv20_amount": [500_000.0] * len(dates),
            "is_tradable": [True] * len(dates),
        }
    )
    positions = pd.DataFrame(
        {
            "rebalance_date": [dates[0]],
            "entry_date": [dates[1]],
            "symbol": ["AAA"],
            "weight": [1.0],
        }
    )
    config = ExecutionSimConfig(
        enabled=True,
        portfolio_value=1_000_000.0,
        liquidity_cols=("amount",),
        round_lot=100,
        enforce_t1=True,
    )
    prepared = prepare_execution_tables(
        pricing,
        config,
        price_col="open",
        tradable_col="amount",
    )

    def unexpected_rebuild(*args, **kwargs):
        raise AssertionError("execution tables were rebuilt")

    monkeypatch.setattr(table_preparation, "_build_execution_tables", unexpected_rebuild)
    result = simulate_execution_adjusted_nav(
        positions,
        pricing,
        config,
        price_col="open",
        tradable_col="amount",
        prepared_tables=prepared,
    )

    assert result.summary["status"] == "ok"
