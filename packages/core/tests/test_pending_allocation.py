"""Independent fill corners and delivered-state resource admission, synthetic only."""

from dataclasses import replace
from itertools import product

import numpy as np
import pandas as pd
import pytest
from pending_fixtures import LiteralOptimizer, factor_request

from quant_backtest_core.backtest.account_events import (
    AccountEvent,
    AccountEventAdapter,
    EventAccountConfig,
)
from quant_backtest_core.backtest.paper_account import PaperState
from quant_backtest_core.planning import pending_allocation as pending


def observation(r, orders=(), **changes):
    index = r.current_weights.index
    values = {
        "delivered_quantities": pd.Series(0, index=index),
        "raw_prices": pd.Series(10.0, index=index),
        "quote_times": pd.Series(r.information_time, index=index),
        "nav": 1000.0,
        "cash_before_reserves": 1000.0,
        "sell_capacity_quantities": pd.Series(100, index=index),
        "new_fee_rates": pd.Series(0.0, index=index),
        "outstanding_orders": tuple(orders),
        "delivered_at": r.information_time,
        "orders_as_of": r.information_time,
        "complete_order_snapshot": True,
        "assumptions": "Fixed raw prices and NAV, independent fills, no sale proceeds funding buys",
    }
    values.update(changes)
    return pending.PendingAllocationState(**values)


def order(r, ident, symbol, remaining, fee=0.0):
    return pending.PendingOrder(ident, symbol, remaining, 10.0, fee, r.information_time)


def solve(r, state, net_band=(-1.0, 1.0), *, weights=(0.0, 0.0, 0.0)):
    return pending.solve_pending_allocation(
        LiteralOptimizer(r, weights), r, state, net_band=net_band
    )


def test_opposite_pending_never_net_and_zero_base_is_not_claimed_neutral():
    r = factor_request(factor_bounds={"beta": (-0.5, 0.5)})
    orders = [order(r, "buy", "a", 10, 1), order(r, "sell", "a", -10, 2)]
    state = observation(r, orders, cash_before_reserves=123)
    envelope = pending.pending_allocation_envelope(r, state, net_band=(-0.2, 0.2))
    assert envelope.gross_limit == pytest.approx(0.8)
    assert envelope.factor_bounds["beta"] == pytest.approx((-0.3, 0.3))
    assert envelope.net_base_bounds == pytest.approx((-0.1, 0.1))
    assert envelope.reserved_cash == pytest.approx(103)
    assert envelope.available_cash == pytest.approx(20)
    assert envelope.remaining_sell_quantities["a"] == 90
    result = solve(r, state, (-0.2, 0.2))
    assert result.status == "optimal"
    assert result.endpoint_net_bounds == pytest.approx((-0.1, 0.1), abs=1e-7)
    assert result.new_trade_weights.equals(result.base_result.weights - r.current_weights)
    failed = solve(r, state, (0.0, 0.0))
    assert failed.status == "infeasible" and failed.base_result is None


def test_cash_and_locates_cap_new_trades_without_using_pending_sale_proceeds():
    r = factor_request(expected_returns=pd.Series([10.0, -10.0, 0.0], index=["a", "b", "c"]))
    state = observation(
        r,
        [order(r, "buy", "a", 4, 1), order(r, "sell", "b", -7, 1)],
        cash_before_reserves=64,
        sell_capacity_quantities=pd.Series([100, 10, 100], index=r.current_weights.index),
        new_fee_rates=pd.Series(0.1, index=r.current_weights.index),
    )
    result = solve(r, state, weights=(22 / 1.2 / 1000, -22 / 1.2 / 1000, 0))
    assert result.status == "optimal"
    trades = result.new_trade_weights
    # The 22 dollars cover each buy dollar plus 0.1 fee on each of two legs.
    assert trades["a"] == pytest.approx(22 / 1.2 / 1000, abs=1e-7)
    assert -trades["b"] <= 0.03 + 1e-7
    assert result.new_cash_required <= 22 + 1e-5
    assert result.base_result.turnover == pytest.approx(abs(trades).sum())
    assert r.current_weights.eq(0).all()


@pytest.mark.parametrize("kind", ["future_quote", "future_order", "unknown", "incomplete"])
def test_unknown_or_future_information_is_rejected(kind):
    r = factor_request()
    state = observation(r)
    if kind == "future_quote":
        state = replace(state, quote_times=state.quote_times + pd.Timedelta(days=2))
    elif kind == "future_order":
        o = replace(order(r, "buy", "a", 1), observed_at=r.decision_time)
        state = replace(state, outstanding_orders=(o,))
    elif kind == "unknown":
        state = replace(state, outstanding_orders=(order(r, "buy", "missing", 1),))
    else:
        state = replace(state, complete_order_snapshot=False)
    with pytest.raises(ValueError):
        solve(r, state)


def test_insufficient_reserved_resources_and_impossible_factor_envelope_release_no_target():
    r = factor_request(factor_bounds={"beta": (0.0, 0.0)})
    state = observation(r, [order(r, "buy", "a", 1)])
    assert solve(r, state).status == "infeasible"
    r = replace(r, factor_bounds={})
    failed = solve(r, replace(state, cash_before_reserves=1))
    assert failed.status == "infeasible" and failed.new_trade_weights is None


def account_observation(r, account):
    orders = [
        pending.PendingOrder(
            ident,
            o["symbol"],
            o["remaining"],
            o["limit_price"],
            o["fee_remaining"],
            r.information_time,
        )
        for ident, o in account.pending.items()
    ]
    quantities = pd.Series(account.visible.quantities).reindex(
        r.current_weights.index, fill_value=0
    )
    return observation(
        r,
        orders,
        delivered_quantities=quantities,
        cash_before_reserves=(
            account.available_cash(r.information_time)
            + sum(o["reserved_cash"] for o in account.pending.values())
        ),
        delivered_at=account.visible.as_of,
    )


def test_delayed_partial_fill_uses_only_visible_holdings_and_delivered_remaining():
    r = factor_request(current_weights=pd.Series([0.1, -0.1, 0], index=["a", "b", "c"]))
    t = r.information_time
    account = AccountEventAdapter(
        PaperState(t, 1000, {"a": 10, "b": -10}, {"a": 10, "b": 10}),
        EventAccountConfig("synthetic-v1", "fixed-raw-v1"),
    )
    account.admit_order(
        "buy",
        "a",
        10,
        10,
        as_of=t,
        locate_quantity=100,
        risk_limit=10000,
    )
    account.request_cancel("buy", as_of=t)
    before = solve(r, account_observation(r, account))
    observed = {"value": 10, "available_at": t.isoformat()}
    supplied_inputs = {
        "price_basis": "raw",
        "marks": {"a": observed, "b": observed},
        "borrow_rates": {"a": {**observed, "value": 0}, "b": {**observed, "value": 0}},
        "locate_quantities": {"a": {**observed, "value": 100}, "b": {**observed, "value": 100}},
        "financing_rate": {**observed, "value": 0},
    }
    account.apply(
        AccountEvent(
            "fill",
            "fill",
            t,
            t + pd.Timedelta(seconds=10),
            {"order_id": "buy", "quantity": 4, "price": 10, "inputs": supplied_inputs},
        )
    )
    assert account.actual.quantities["a"] == 14
    assert account.visible.quantities["a"] == 10
    hidden = solve(r, account_observation(r, account))
    pd.testing.assert_series_equal(before.new_trade_weights, hidden.new_trade_weights)
    assert hidden.envelope.pending_upper["a"] == pytest.approx(0.1)
    account.deliver(t + pd.Timedelta(seconds=10))
    r = replace(
        r,
        information_time=t + pd.Timedelta(seconds=10),
        current_weights=pd.Series([0.14, -0.1, 0], index=r.current_weights.index),
    )
    delivered = solve(r, account_observation(r, account))
    assert delivered.status == "optimal"
    assert delivered.envelope.pending_upper["a"] == pytest.approx(0.06)
    pd.testing.assert_series_equal(
        delivered.new_trade_weights,
        delivered.base_result.weights - r.current_weights,
    )
    assert delivered.base_result.turnover == pytest.approx(delivered.new_trade_weights.abs().sum())


@pytest.mark.parametrize(
    ("quantity", "pending_sell", "pending_buy", "capacity", "new_sell"),
    [(10, -8, 10, 10, 0.02), (-10, -2, 8, 3, 0.01)],
)
def test_pending_buys_and_short_covers_do_not_replenish_new_sale_capacity(
    quantity,
    pending_sell,
    pending_buy,
    capacity,
    new_sell,
):
    r = factor_request(
        current_weights=pd.Series([quantity / 100, 0, 0], index=["a", "b", "c"]),
        net_target=quantity / 100,
        expected_returns=pd.Series([-10.0, 10.0, 0.0], index=["a", "b", "c"]),
    )
    state = observation(
        r,
        [order(r, "sell", "a", pending_sell), order(r, "buy", "a", pending_buy)],
        delivered_quantities=pd.Series([quantity, 0, 0], index=r.current_weights.index),
        sell_capacity_quantities=pd.Series([capacity, 100, 100], index=r.current_weights.index),
    )
    result = solve(r, state, weights=(quantity / 100 - new_sell, new_sell, 0))
    assert result.status == "optimal"
    assert -result.new_trade_weights["a"] == pytest.approx(new_sell, abs=1e-7)
    assert result.base_result.turnover == pytest.approx(result.new_trade_weights.abs().sum())


def test_observed_holdings_cannot_be_replaced_with_an_assumed_filled_portfolio():
    r = factor_request(current_weights=pd.Series([0.1, 0, 0], index=["a", "b", "c"]))
    with pytest.raises(ValueError, match="delivered holdings"):
        solve(r, observation(r, [order(r, "buy", "a", 10)]))


def test_optimizer_failure_releases_no_conditional_target_or_trades():
    r = factor_request()
    result = pending.solve_pending_allocation(
        LiteralOptimizer(r, status="numerical_failure"),
        r,
        observation(r),
        net_band=(-1, 1),
    )
    assert result.status == "numerical_failure"
    assert result.base_result is None and result.new_trade_weights is None


def test_all_independent_fill_corners_fit_constraints_for_forty_synthetic_cases():
    rng = np.random.default_rng(42)
    for _ in range(40):
        r = factor_request(factor_bounds={"beta": (-0.35, 0.35)})
        r = replace(
            r,
            expected_returns=pd.Series(rng.normal(size=3), index=r.current_weights.index),
            factor_loadings=pd.DataFrame(
                {"beta": rng.choice([-2.0, 1.0, 0.5], size=3)},
                index=r.current_weights.index,
            ),
        )
        orders = [order(r, "buy", "a", int(rng.integers(1, 8))), order(r, "sell", "b", -5)]
        state = observation(r, orders)
        got = solve(r, state, (-0.15, 0.15))
        assert got.status == "optimal"
        base = got.base_result.weights
        for fractions in product((0.0, 1.0), repeat=2):
            endpoint = base.copy()
            for o, fraction in zip(orders, fractions, strict=True):
                endpoint[o.symbol] += fraction * o.remaining_quantity * 10 / 1000
            assert endpoint.abs().sum() <= 1.0 + 1e-7
            assert -0.15 - 1e-7 <= endpoint.sum() <= 0.15 + 1e-7
            assert -0.35 - 1e-7 <= r.factor_loadings["beta"] @ endpoint <= 0.35 + 1e-7
            assert (endpoint >= r.lower_bounds - 1e-7).all()
            assert (endpoint <= r.upper_bounds + 1e-7).all()
