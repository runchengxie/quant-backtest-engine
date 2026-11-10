"""Synthetic raw-share sell policy, independent of exchange or strategy defaults."""

from dataclasses import asdict

import pandas as pd
import pytest

from quant_backtest_core.daily.execution_sim import (
    ExecutionSimConfig,
    build_execution_sim_config,
    describe_execution_sim_config,
    simulate_capacity_execution,
)
from quant_backtest_core.daily.execution_sim.models import _ExecutionTables, _MarketRules, _NavOrder
from quant_backtest_core.daily.execution_sim.orders_nav import _execute_nav_sell_orders_for_day


def _sell(*, held, requested, capacity=10000, available=None, lot=100):
    day = pd.Timestamp("2020-01-02")
    table = pd.DataFrame({"AAA": [10.0]}, index=[day])
    tables = _ExecutionTables([day], {day: 0}, table, None, None, {"amount": table * capacity})
    config = ExecutionSimConfig(
        enabled=True,
        participation_rate=1,
        liquidity_cols=("amount",),
        sell_round_lot=lot,
        enforce_t1=available is not None,
    )
    rules = _MarketRules.from_config(
        config, limit_up_table=None, limit_down_table=None, listing_status_table=None
    )
    order = _NavOrder(
        day,
        day,
        "sell",
        "AAA",
        requested * 10,
        requested * 10,
        0,
        1,
        requested_quantity=requested,
        remaining_quantity=requested,
    )
    shares = {"AAA": held}
    cash = {"cash": 0.0}
    fills = []
    _execute_nav_sell_orders_for_day(
        open_orders=[order],
        shares=shares,
        cash_ref=cash,
        trade_date=day,
        trade_idx=0,
        tables=tables,
        config=config,
        cost_rate=0,
        trade_fee_model=None,
        slippage_model=None,
        fill_rows=fills,
        fee_group_notionals={},
        market_rules=rules,
        t1_available=None if available is None else {"AAA": available},
    )
    return shares, cash, order, fills


@pytest.mark.parametrize(
    ("held", "requested", "capacity", "available", "sold"),
    [
        (300, 50, 10000, None, 0),
        (300, 175, 10000, None, 100),
        (250, 250, 175, None, 100),
        (250, 250, 10000, 175, 100),
        (50, 50, 49, None, 0),
        (50, 50, 10000, 49, 0),
        (250, 250, 10000, None, 250),
        (50, 50, 10000, 50, 50),
        (300, 300, 99.9999999, None, 0),
        (300, 300, 10000, 99.9999999, 0),
    ],
)
def test_sell_lots_respect_request_capacity_and_settlement(
    held, requested, capacity, available, sold
):
    shares, cash, order, fills = _sell(
        held=held, requested=requested, capacity=capacity, available=available
    )
    assert shares.get("AAA", 0) == held - sold
    assert cash["cash"] == sold * 10
    assert order.filled_quantity == sold
    assert len(fills) == (1 if sold else 0)


def test_fractional_entitlements_fail_closed():
    with pytest.raises(ValueError, match=r"integral.*holding"):
        _sell(held=250.5, requested=250.5)


def test_default_retains_continuous_adjusted_share_sells():
    shares, cash, order, _ = _sell(held=250.5, requested=73.25, lot=None)
    assert shares["AAA"] == 177.25
    assert cash["cash"] == 732.5
    assert order.filled_quantity == 73.25


@pytest.mark.parametrize("value", [0, -1, 1.5, True, float("nan"), float("inf"), "100"])
@pytest.mark.parametrize("direct", [True, False])
def test_sell_lot_validation_matches_direct_and_mapping_construction(value, direct):
    with pytest.raises(ValueError, match="sell_round_lot"):
        if direct:
            ExecutionSimConfig(sell_round_lot=value)
        else:
            build_execution_sim_config({"enabled": True, "sell_round_lot": value})


def test_sell_lot_survives_config_description_roundtrip():
    config = ExecutionSimConfig(enabled=True, sell_round_lot=100)
    assert asdict(build_execution_sim_config(describe_execution_sim_config(config))) == asdict(
        config
    )


def test_weight_only_capacity_simulation_rejects_share_policy():
    with pytest.raises(ValueError, match=r"sell_round_lot.*share"):
        simulate_capacity_execution(
            None, None, ExecutionSimConfig(enabled=True, sell_round_lot=100), price_col="open"
        )


def _public_sell(lot, *, price_basis="raw"):
    from quant_backtest_core.daily.execution_sim import simulate_execution_adjusted_nav

    positions = pd.DataFrame(
        [
            {
                "rebalance_date": "20200102",
                "entry_date": "20200102",
                "symbol": "AAA",
                "weight": 1.0,
            },
            {
                "rebalance_date": "20200103",
                "entry_date": "20200103",
                "symbol": "AAA",
                "weight": 0.5,
            },
        ]
    )
    pricing = pd.DataFrame(
        [
            {"trade_date": day, "symbol": "AAA", "raw": 10.0, "amount": 10000.0}
            for day in ["20200102", "20200103"]
        ]
    )
    return simulate_execution_adjusted_nav(
        positions,
        pricing,
        ExecutionSimConfig(
            enabled=True,
            portfolio_value=3000,
            participation_rate=1,
            liquidity_cols=("amount",),
            buy_max_days=1,
            sell_max_days=1,
            sell_round_lot=lot,
        ),
        price_col="raw",
        price_basis=price_basis,
    )


def test_public_ledger_sell_policy_and_default_continuous_compatibility():
    constrained = _public_sell(100)
    continuous = _public_sell(None, price_basis="adjusted")
    assert constrained.fills.query("side == 'sell'")["filled_notional"].tolist() == [1000.0]
    assert continuous.fills.query("side == 'sell'")["filled_notional"].tolist() == [1500.0]
    assert constrained.daily["cash"].tolist() == [0.0, 1000.0]
    assert constrained.daily["invested_value"].tolist() == [3000.0, 2000.0]
    assert constrained.summary["warnings"] == []
    assert constrained.summary["config"]["sell_round_lot"] == 100


def test_explicit_adjusted_basis_rejects_raw_share_sell_policy():
    with pytest.raises(ValueError, match=r"sell_round_lot.*raw"):
        _public_sell(100, price_basis="adjusted")


@pytest.mark.parametrize("held", [250.0000005, 250.00000005])
def test_lot_tolerance_does_not_accept_fractional_entitlements(held):
    with pytest.raises(ValueError, match=r"integral.*holding"):
        _sell(held=held, requested=held)


def test_numerical_share_residue_is_preserved_without_expanding_capacity():
    held = 250.000000001
    shares, cash, order, _ = _sell(held=held, requested=held)
    assert shares == {}
    assert order.filled_quantity == held
    assert cash["cash"] == held * 10
    shares, cash, order, _ = _sell(held=held, requested=held, capacity=250)
    assert shares["AAA"] == pytest.approx(50.000000001)
    assert order.filled_quantity == 200
    assert cash["cash"] == 2000


def test_sell_lot_deadline_retains_residual_and_charges_actual_fill_fees():
    from quant_backtest_core.daily.execution_sim import simulate_execution_adjusted_nav

    positions = pd.DataFrame(
        [
            {"rebalance_date": day, "entry_date": day, "symbol": "AAA", "weight": weight}
            for day, weight in [("20200102", 0.8), ("20200103", 0.3)]
        ]
    )
    pricing = pd.DataFrame(
        [
            {"trade_date": day, "symbol": "AAA", "raw": 10.0, "amount": 10000.0}
            for day in ["20200102", "20200103"]
        ]
    )
    result = simulate_execution_adjusted_nav(
        positions,
        pricing,
        ExecutionSimConfig(
            enabled=True,
            portfolio_value=5000,
            participation_rate=1,
            liquidity_cols=("amount",),
            buy_max_days=1,
            sell_max_days=1,
            round_lot=100,
            sell_round_lot=100,
        ),
        price_col="raw",
        price_basis="raw",
        transaction_cost_bps=10,
    )
    assert result.fills["filled_notional"].tolist() == [4000.0, 2000.0]
    assert result.fills["transaction_cost"].tolist() == [4.0, 2.0]
    assert result.daily["cash"].tolist() == [996.0, 2994.0]
    assert result.daily["invested_value"].tolist() == [4000.0, 2000.0]
    sell = result.orders.query("side == 'sell'").iloc[0]
    assert sell["status"] == "delayed_sell"
    assert sell["unfilled_notional"] == pytest.approx(501.2)


@pytest.mark.parametrize("tolerance", [float("nan"), float("inf"), -1.0])
def test_raw_sell_policy_rejects_invalid_direct_lot_tolerance(tolerance):
    with pytest.raises(ValueError, match="lot_tolerance"):
        ExecutionSimConfig(sell_round_lot=100, lot_tolerance=tolerance)
