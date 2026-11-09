# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_impact_planning.py
"""Independent analytic fixtures for a conservative cash-envelope convex QP."""

from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from quant_backtest_core.planning import impact_planning as planning


def request(**changes):
    values = {
        "initial_holdings": np.array([0.0]),
        "initial_cash": 100.0,
        "unaffected_prices": np.array([10.0]),
        "expected_returns": np.array([[0.1]]),
        "covariances": np.array([[[1.0]]]),
        "step_seconds": np.array([]),
        "initial_transient": np.array([0.0]),
        "transient": np.array([0.0]),
        "decay_seconds": np.array([10.0]),
        "capacity": np.array([[10.0]]),
        "decision_ns": 100,
        "forecast_available_ns": 100,
        "risk_available_ns": 100,
        "state_available_ns": 100,
    }
    return planning.ImpactPlanningRequest(**(values | changes))


def test_no_impact_reduces_to_hand_solved_risk_return_problem():
    # NAV=100; J=.5*(10h)^2/100 - .1*10h = .5h^2-h.
    result = planning.plan_with_impact(request())
    assert result.first_action == pytest.approx([1], abs=1e-6)
    assert result.objective == pytest.approx(-0.5)
    assert result.cash == pytest.approx([90])
    assert result.cash_lower_bounds == pytest.approx([90])
    assert result.maximum_violation <= 1e-7
    assert result.solver_success
    assert result.formulation == "convex_qp_conservative_affine_cash.v1"


def two_period(**changes):
    return request(
        **(
            {
                "expected_returns": np.array([[0.0], [0.1]]),
                "covariances": np.array([[[0.0]], [[0.0]]]),
                "risk_aversion": 0,
                "step_seconds": np.array([10 * np.log(2)]),
                "transient": np.array([1.0]),
                "initial_transient": np.array([2.0]),
                "capacity": np.array([[2.0], [2.0]]),
            }
            | changes
        )
    )


def test_positive_decaying_state_favors_waiting_hand_solution():
    # At t0 d=2, t1 d=1. Alpha rewards final holdings by 2/share.
    # J=q0^2/2+q1^2/2+.5q0q1 +(2-2)q0 +(1-2)q1.
    # Long-only solution q0=0, q1=1, J=-.5.
    result = planning.plan_with_impact(two_period(expected_returns=np.array([[0.0], [0.2]])))
    assert np.asarray(result.trades).ravel() == pytest.approx([0, 1], abs=1e-5)
    assert np.asarray(result.transient_before).ravel() == pytest.approx([2, 1], abs=1e-5)
    assert np.asarray(result.transient_after).ravel() == pytest.approx([2, 2], abs=1e-5)
    assert result.cash[-1] == pytest.approx(88.5, abs=1e-5)
    assert result.objective == pytest.approx(-0.5, abs=1e-6)


def test_future_capacity_and_earlier_alpha_change_first_action():
    base = two_period(initial_transient=np.array([0.0]))
    # J=.5q0^2+.5q1^2+.5q0q1-q0-q1 -> q0=q1=2/3.
    free = planning.plan_with_impact(base)
    constrained = planning.plan_with_impact(replace(base, capacity=np.array([[2.0], [0.0]])))
    early = planning.plan_with_impact(replace(base, expected_returns=np.array([[0.1], [0.0]])))
    assert np.asarray(free.trades).ravel() == pytest.approx([2 / 3, 2 / 3], abs=1e-5)
    assert constrained.first_action == pytest.approx([1], abs=1e-5)
    # The final negative trade relaxes transient state without shorting inventory.
    assert early.first_action[0] > free.first_action[0]


def test_cash_reservations_locked_holdings_and_zero_capacity():
    capped = planning.plan_with_impact(
        request(
            expected_returns=np.array([[10.0]]),
            reserved_cash=80,
            transient=np.array([0.2]),
            fee_per_share=np.array([0.5]),
        )
    )
    # Envelope price 10 + .5*.2*10 + .5 = 11.5.
    assert capped.first_action == pytest.approx([20 / 11.5], abs=1e-5)
    q = capped.first_action[0]
    assert capped.cash == pytest.approx([100 - 10 * q - 0.1 * q * q - 0.5 * q])
    assert capped.cash[0] >= capped.cash_lower_bounds[0] >= 80 - 1e-6
    locked = planning.plan_with_impact(
        request(
            initial_holdings=np.array([2.0]),
            locked_holdings=np.array([1.5]),
            expected_returns=np.array([[-1.0]]),
        )
    )
    assert locked.first_action == pytest.approx([-0.5], abs=1e-5)
    stopped = planning.plan_with_impact(request(capacity=np.array([[0.0]])))
    assert stopped.first_action == (0.0,)


def test_quantity_and_currency_rescaling_preserve_economics():
    base = two_period(initial_transient=np.array([0.0]), fee_per_share=np.array([0.1]))
    result = planning.plan_with_impact(base)
    # One old share becomes 10 new shares; prices/state/fees divide by 10, k by 100.
    split = replace(
        base,
        unaffected_prices=base.unaffected_prices / 10,
        initial_holdings=base.initial_holdings * 10,
        capacity=base.capacity * 10,
        initial_transient=base.initial_transient / 10,
        transient=base.transient / 100,
        fee_per_share=np.array([0.01]),
    )
    scaled = planning.plan_with_impact(split)
    assert np.asarray(scaled.trades) / 10 == pytest.approx(np.asarray(result.trades), abs=1e-5)
    assert scaled.objective == pytest.approx(result.objective, abs=1e-6)
    assert scaled.cash == pytest.approx(result.cash, abs=1e-5)
    currency = replace(
        base,
        initial_cash=base.initial_cash * 100,
        unaffected_prices=base.unaffected_prices * 100,
        transient=base.transient * 100,
        fee_per_share=np.array([10.0]),
    )
    converted = planning.plan_with_impact(currency)
    assert converted.trades == pytest.approx(np.asarray(result.trades), abs=1e-5)
    assert converted.objective / 100 == pytest.approx(result.objective, abs=1e-6)
    assert np.asarray(converted.cash) / 100 == pytest.approx(result.cash, abs=1e-5)


@pytest.mark.parametrize(
    "changes",
    [
        {"covariances": np.array([[[-1.0]]])},
        {"units": "normalized"},
        {"fee_rate": 0.001},
        {"minimum_fee": 1},
        {"quantity_step": 100},
        {"permanent": 0.01},
        {"fee_per_share": -1},
        {"spread_per_share": -1},
        {"forecast_available_ns": 101},
        {"risk_available_ns": 101},
        {"state_available_ns": 101},
        {"decision_ns": 1.5},
        {"capacity": np.array([[np.inf]])},
        {"decay_seconds": np.array([0.0])},
        {"reserved_cash": 101},
        {"locked_holdings": np.array([1.0])},
        {"initial_transient": np.array([20.0])},
    ],
)
def test_invalid_or_unsupported_semantics_are_rejected(changes):
    with pytest.raises(ValueError):
        planning.plan_with_impact(request(**changes))


def test_optimizer_failure_and_false_feasibility_are_observable(monkeypatch):
    def failed(*args, **kwargs):
        return SimpleNamespace(x=np.zeros(2), success=False, status=9, message="iteration limit")

    monkeypatch.setattr(planning, "minimize", failed)
    with pytest.raises(ValueError, match="iteration limit"):
        planning.plan_with_impact(request())

    def false_success(*args, **kwargs):
        return SimpleNamespace(x=np.array([2.0, 2.0]), success=True, status=0, message="success")

    monkeypatch.setattr(planning, "minimize", false_success)
    with pytest.raises(ValueError, match="violation"):
        planning.plan_with_impact(request())


@pytest.mark.parametrize("gap, expected_cash", [(0.0, 100.0), (10 * np.log(2), 99.5)])
def test_planned_round_trip_has_analytic_nonnegative_cost(gap, expected_cash):
    result = planning.plan_with_impact(
        two_period(
            initial_transient=np.array([0.0]),
            step_seconds=np.array([gap]),
            expected_returns=np.array([[1.0], [-2.0]]),
            capacity=np.array([[1.0], [1.0]]),
        )
    )
    assert np.asarray(result.trades).ravel() == pytest.approx([1, -1], abs=1e-7)
    assert result.holdings[-1] == pytest.approx([0], abs=1e-7)
    assert result.cash[-1] == pytest.approx(expected_cash, abs=1e-7)
    assert result.cash[-1] <= 100 + 1e-7


def test_same_clock_slicing_preserves_cash_and_half_own_increment():
    whole = planning.plan_with_impact(
        two_period(
            initial_transient=np.array([0.0]),
            step_seconds=np.array([0.0]),
            expected_returns=np.array([[1.0], [-10.0]]),
            capacity=np.array([[2.0], [2.0]]),
            fee_per_share=0.1,
            spread_per_share=0.2,
        )
    )
    split = planning.plan_with_impact(
        request(
            initial_transient=np.array([0.0]),
            transient=np.array([1.0]),
            step_seconds=np.array([0.0, 0.0]),
            expected_returns=np.array([[1.0], [1.0], [-10.0]]),
            covariances=np.zeros((3, 1, 1)),
            capacity=np.array([[1.0], [1.0], [2.0]]),
            risk_aversion=0,
            fee_per_share=0.1,
            spread_per_share=0.2,
        )
    )
    assert np.asarray(split.trades).ravel() == pytest.approx([1, 1, -2], abs=1e-7)
    assert np.asarray(split.execution_prices).ravel() == pytest.approx([10.7, 11.7, 10.8])
    assert split.cash[-1] == pytest.approx(98.8)
    assert whole.cash[-1] == pytest.approx(split.cash[-1])


def test_integer_first_action_executes_once_through_owner_and_restores_state():
    import pandas as pd
    from test_minute_execution import bars, targets

    from quant_backtest_core.backtest.impact import LinearImpact
    from quant_backtest_core.backtest.minute import MinuteExecutionConfig, simulate_minute_execution

    decision = pd.Timestamp("2026-01-05 09:30", tz="Asia/Shanghai").value
    req = request(
        initial_cash=10000,
        transient=np.array([0.001]),
        capacity=np.array([[100.0]]),
        risk_aversion=0,
        decision_ns=decision,
        forecast_available_ns=decision,
        risk_available_ns=decision,
        state_available_ns=decision,
    )
    planned = planning.plan_with_impact(req)
    # Explicit owner rounding/recheck: this analytic solution is exactly one 100-share lot.
    quantity = round(planned.first_action[0])
    assert quantity == 100
    assert planned.first_action[0] == pytest.approx(quantity, abs=1e-6)
    result = simulate_minute_execution(
        targets(weights=(quantity * 10 / 10000,)),
        bars(),
        MinuteExecutionConfig(10000, 0.1, 0, 0),
        impact_model=LinearImpact(transient=0.001, decay_seconds=10),
    )
    assert result.fills.quantity.tolist() == [100]
    assert result.fills.price.tolist() == pytest.approx([10.05])
    assert result.daily.iloc[-1].cash == pytest.approx(8995)
    assert result.daily.iloc[-1].cash == pytest.approx(planned.cash[0])
    assert result.daily.iloc[-1].transaction_cost == 0  # impact is already inside fill price
    checkpoint = result.summary["impact_checkpoint"]
    restored = LinearImpact.restore(checkpoint)
    state = checkpoint["states"]["A"]
    assert restored.offset("A", state["time"]) == pytest.approx(planned.transient_after[0][0])
    second = planning.plan_with_impact(
        replace(
            req,
            initial_holdings=np.array([100.0]),
            initial_cash=8995,
            initial_transient=np.array([state["transient"]]),
            decision_ns=round(state["time"] * 1e9),
            state_available_ns=round(state["time"] * 1e9),
        )
    )
    q = second.first_action[0]
    assert second.execution_prices[0][0] == pytest.approx(
        10 + restored.execute("A", state["time"], q)
    )
    assert second.cash[0] == pytest.approx(8995 - q * second.execution_prices[0][0])


def test_request_digest_binds_exact_consumed_values_config_and_clocks():
    req = request()
    result = planning.plan_with_impact(req)
    assert len(result.request_digest) == 64
    assert result.request_digest == planning.plan_with_impact(req).request_digest
    for changed in (
        replace(req, expected_returns=np.array([[np.nextafter(0.1, 1)]])),
        replace(req, state_available_ns=99),
        replace(req, spread_per_share=0.001),
    ):
        assert result.request_digest != planning.plan_with_impact(changed).request_digest
    req.expected_returns[0, 0] = 0.5
    assert result.request_digest != planning.plan_with_impact(req).request_digest


def test_correlated_two_name_risk_has_independent_hand_solution():
    # Optimal dollar weights solve wA+.5wB=.1, .5wA+2wB=.2:
    # w=(2/35, 3/35); raw holdings are (4/7, 3/7).
    result = planning.plan_with_impact(
        request(
            initial_holdings=np.zeros(2),
            unaffected_prices=np.array([10.0, 20.0]),
            expected_returns=np.array([[0.1, 0.2]]),
            covariances=np.array([[[1.0, 0.5], [0.5, 2.0]]]),
            capacity=np.array([[2.0, 2.0]]),
            initial_transient=np.zeros(2),
            transient=np.zeros(2),
            decay_seconds=np.array([10.0, 20.0]),
        )
    )
    assert result.first_action == pytest.approx([4 / 7, 3 / 7], abs=1e-5)
    assert result.objective == pytest.approx(-8 / 7, abs=1e-8)
    assert result.cash == pytest.approx([600 / 7], abs=1e-5)
