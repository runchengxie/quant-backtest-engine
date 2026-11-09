# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_multiperiod.py
from dataclasses import replace

import numpy as np
import pytest

from quant_backtest_core.planning.multiperiod import MultiPeriodRequest, plan_trades


def request(alpha=((0.0,),), **kwargs):
    alpha = np.array(alpha)
    return MultiPeriodRequest(
        alpha,
        np.repeat(np.eye(alpha.shape[1])[None], len(alpha), axis=0),
        np.zeros(alpha.shape[1]),
        decision_ns=100,
        forecast_available_ns=90,
        **kwargs,
    )


def test_one_period_matches_analytic_solution_and_neutral_signal_does_not_churn():
    plan = plan_trades(request(((0.2,),), cost_linear=0, cost_quadratic=1))
    assert plan.weights[0][0] == pytest.approx(0.1, abs=1e-6)
    neutral = replace(request(cost_linear=0.01), previous_weights=np.array([0.3]))
    neutral = replace(neutral, covariances=np.zeros((1, 1, 1)))
    assert plan_trades(neutral).first_trade == pytest.approx((0,), abs=1e-7)


def test_future_forecast_and_capacity_change_current_plan_without_future_realizations():
    single = plan_trades(request(((0.0,),), max_trade=0.1))
    multiple = plan_trades(request(((0.0,), (0.8,)), max_trade=0.1))
    assert multiple.first_trade[0] > single.first_trade[0] + 0.05
    assert max(abs(x) for x in multiple.first_trade) <= 0.1 + 1e-7


def test_cash_reservations_costs_and_infeasibility_are_enforced():
    plan = plan_trades(request(((10.0,),), cost_linear=0.1, reserved_cash=0.5))
    assert plan.weights[0][0] * 1.1 <= 0.5 + 1e-7
    with pytest.raises(ValueError, match="infeasible"):
        plan_trades(
            replace(request(max_weight=0.1, max_trade=0.1), previous_weights=np.array([0.8]))
        )


def test_future_or_non_psd_inputs_rejected():
    with pytest.raises(ValueError, match="future"):
        plan_trades(replace(request(), forecast_available_ns=101))
    with pytest.raises(ValueError, match="PSD"):
        plan_trades(replace(request(), covariances=-np.ones((1, 1, 1))))
