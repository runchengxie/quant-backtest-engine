"""Synthetic literal wealth oracle for the owner-replayed finite benchmark."""

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest
from test_minute_execution import bars

from quant_backtest_core.backtest.minute import MinuteExecutionConfig
from quant_backtest_core.planning.joint_execution import (
    JointExecutionRequest,
    evaluate_joint_path,
    solve_joint_execution,
)


def request(**changes):
    market = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:33"))
    market.loc[2, ["open", "high", "low", "close"]] = 11
    market.loc[2, "amount"] = 11000
    clock = pd.Timestamp("2026-01-05 09:29", tz="Asia/Shanghai").value
    base = JointExecutionRequest(
        names=("A",),
        decision_ns=clock,
        forecast_available_ns=clock,
        risk_available_ns=clock,
        past_bars=market.iloc[:1],
        forecast_bars=market.iloc[1:],
        decision_times=(clock,),
        entry_times=(clock + 60_000_000_000,),
        weight_choices=(((0.0,), (0.5,), (1.0,)),),
        config=MinuteExecutionConfig(1000, 1, 0, 0, lot_size=10),
        terminal_covariance=np.zeros((1, 1)),
    )
    return replace(base, **changes)


def test_literal_wealth_oracle_and_actual_owner_shares():
    req = request()
    values = [evaluate_joint_path(req, (i,)) for i in range(3)]
    assert [v.terminal_nav for v in values] == [1000, 1050, 1100]
    assert [v.objective for v in values] == [0, -50, -100]
    plan = solve_joint_execution(req)
    assert plan.indices == (2,) and plan.status == "optimal_exhaustive"
    assert plan.evaluation_count == 3
    assert plan.evaluation.result.fills.quantity.tolist() == [100]
    assert plan.evaluation.result.daily.iloc[-1].cash == 0


def test_risk_and_minimum_fee_change_first_action():
    assert solve_joint_execution(
        request(risk_aversion=1, terminal_covariance=np.ones((1, 1)))
    ).indices == (0,)
    req = request(
        config=MinuteExecutionConfig(1000, 1, 0, 0, lot_size=100, commission_minimum_cny=101)
    )
    assert solve_joint_execution(req).indices == (0,)


def test_availability_budget_and_snapshot():
    req = request(max_evaluations=1)
    old = req.forecast_bars.copy(deep=True)
    plan = solve_joint_execution(req)
    assert plan.status == "heuristic_budgeted" and plan.evaluation_count == 1
    pd.testing.assert_frame_equal(old, req.forecast_bars)
    with pytest.raises(ValueError, match="available"):
        solve_joint_execution(replace(req, forecast_available_ns=req.decision_ns + 1))
    with pytest.raises(ValueError, match="PSD"):
        solve_joint_execution(replace(req, terminal_covariance=np.array([[-1.0]])))


def two_period(**changes):
    times = (
        "2026-01-05 09:29",
        "2026-01-05 09:32",
        "2026-01-06 09:29",
        "2026-01-06 09:32",
        "2026-01-06 09:33",
    )
    market = bars(times)
    market.loc[4, ["open", "high", "low", "close"]] = 11
    market.loc[4, "amount"] = 11000
    req = request()
    second = pd.Timestamp(times[2], tz="Asia/Shanghai").value
    return replace(
        req,
        forecast_bars=market.iloc[1:],
        decision_times=(req.decision_ns, second),
        entry_times=(req.entry_times[0], second + 60_000_000_000),
        weight_choices=(((0.0,), (1.0,)), ((0.0,), (1.0,))),
        **changes,
    )


def test_all_paths_future_capacity_changes_first_action():
    req = two_period()
    # With equal wealth, deterministic lexicographic tie chooses to wait.
    assert solve_joint_execution(req).indices == (0, 1)
    blocked = req.forecast_bars.copy()
    blocked.loc[blocked.time.dt.day == 6, "volume"] = 0
    blocked.loc[blocked.time.dt.day == 6, "amount"] = 0
    plan = solve_joint_execution(replace(req, forecast_bars=blocked))
    assert plan.indices[0] == 1
    assert plan.evaluation_count == 4
    assert plan.evaluation.result.fills.quantity.tolist() == [100]


def test_prefix_replays_actual_state_and_impact_checkpoint_recovery():
    from quant_backtest_core.backtest.minute_session import MinuteSession
    from quant_backtest_core.planning.joint_execution import _Policy

    req = two_period(transient=0.001, permanent=0.001, decay_seconds=3600)
    market = pd.concat([req.past_bars, req.forecast_bars], ignore_index=True)
    committed = pd.DataFrame(
        [
            dict(
                decision_time=pd.Timestamp(req.decision_ns, tz="UTC"),
                entry_time=pd.Timestamp(req.entry_times[0], tz="UTC"),
                symbol="A",
                weight=0.5,
            )
        ]
    )
    second = req.decision_times[1]
    future = market[pd.DatetimeIndex(market.time).as_unit("ns").asi8 > second]
    past = market[pd.DatetimeIndex(market.time).as_unit("ns").asi8 <= second]
    replanned = replace(
        req,
        decision_ns=second,
        forecast_available_ns=second,
        risk_available_ns=second,
        past_bars=past,
        forecast_bars=future,
        committed_targets=committed,
        decision_times=(second,),
        entry_times=(req.entry_times[1],),
        weight_choices=(((0.5,),),),
    )
    value = evaluate_joint_path(replanned, (0,))
    assert value.decision_checkpoint["delivery"]
    assert value.result.fills.iloc[0].quantity == 50
    assert value.result.fills.iloc[0].price == 10.05
    state = value.terminal_checkpoint["impact"]["states"]["A"]
    assert state["permanent"] > 0 and state["transient"] != 0
    # Exact unchanged owner inputs/policy restore the full financial checkpoint.
    all_targets = pd.concat(
        [
            committed,
            pd.DataFrame(
                [
                    dict(
                        decision_time=pd.Timestamp(second, tz="UTC"),
                        entry_time=pd.Timestamp(req.entry_times[1], tz="UTC"),
                        symbol="A",
                        weight=0.5,
                    )
                ]
            ),
        ],
        ignore_index=True,
    )
    restored = MinuteSession.restore(
        all_targets, market, req.config, value.terminal_checkpoint, policy=_Policy()
    )
    assert restored.checkpoint() == value.terminal_checkpoint


def test_delayed_reports_wait_and_impact_changes_best_action():
    req = two_period(report_delay_seconds=172800)
    evaluated = evaluate_joint_path(req, (1, 0))
    assert len(evaluated.result.orders) == 1
    from quant_backtest_core.backtest._minute_checkpoint import _unwire

    assert any(
        row["action"] == "wait_reports"
        for row in _unwire(evaluated.terminal_checkpoint["delivery"])[2]
    )
    assert solve_joint_execution(request(transient=0.1, permanent=0.1)).indices == (0,)


def test_blocked_sale_does_not_fund_another_name_but_cash_control_does():
    first = pd.Timestamp("2026-01-05 09:29", tz="Asia/Shanghai").value
    second = pd.Timestamp("2026-01-06 09:29", tz="Asia/Shanghai").value
    frames = []
    for symbol in ("A", "B"):
        frame = bars(
            ("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:29", "2026-01-06 09:32")
        )
        frame["symbol"] = symbol
        if symbol == "A":
            frame.loc[frame.time.dt.day == 6, "tradable"] = False
        frames.append(frame)
    market = pd.concat(frames, ignore_index=True)
    prefix = pd.DataFrame(
        [
            dict(
                decision_time=pd.Timestamp(first, tz="UTC"),
                entry_time=pd.Timestamp(first + 60_000_000_000, tz="UTC"),
                symbol="A",
                weight=1.0,
            )
        ]
    )
    for cash, weight, expected in ((100, 1.0, ["A"]), (200, 0.5, ["A", "B"])):
        committed = prefix.copy()
        committed["weight"] = weight
        req = request(
            names=("A", "B"),
            decision_ns=second,
            forecast_available_ns=second,
            risk_available_ns=second,
            past_bars=market[market.time <= pd.Timestamp(second, tz="UTC")],
            forecast_bars=market[market.time > pd.Timestamp(second, tz="UTC")],
            committed_targets=committed,
            decision_times=(second,),
            entry_times=(second + 60_000_000_000,),
            weight_choices=(((0.0, weight),),),
            terminal_covariance=np.zeros((2, 2)),
            config=MinuteExecutionConfig(cash, 1, 0, 0, lot_size=1),
        )
        value = evaluate_joint_path(req, (0,))
        assert value.result.fills.symbol.tolist() == expected
        assert value.result.fills.side.tolist() == ["buy"] * len(expected)
        assert value.result.daily.iloc[-1].cash == 0


def test_request_digest_is_path_independent_and_binds_forecast():
    req = request()
    first = evaluate_joint_path(req, (0,))
    assert first.request_digest == evaluate_joint_path(req, (2,)).request_digest
    changed = req.forecast_bars.copy()
    changed.loc[changed.index[-1], "volume"] += 1
    assert (
        first.request_digest
        != evaluate_joint_path(replace(req, forecast_bars=changed), (0,)).request_digest
    )


def test_partial_fills_charge_parent_minimum_once_literal_cash():
    req = request(
        config=MinuteExecutionConfig(1000, 0.01, 0, 0, lot_size=10, commission_minimum_cny=3)
    )
    forecast = req.forecast_bars.copy()
    forecast.loc[forecast.index[-1], ["open", "high", "low", "close"]] = 10.5
    forecast.loc[forecast.index[-1], "amount"] = 10500
    value = evaluate_joint_path(replace(req, forecast_bars=forecast), (2,))
    assert value.result.fills.quantity.tolist() == [10, 10]
    assert value.result.fills.transaction_cost.tolist() == [3, 0]
    assert value.result.daily.iloc[-1].cash == 792
    assert value.terminal_nav == 1002 and value.objective == -2


def test_signal_arriving_before_later_entry_changes_first_action():
    req = two_period()
    assert solve_joint_execution(req).indices[0] == 0
    forecast = req.forecast_bars.copy()
    at_second = forecast.time == pd.Timestamp(req.decision_times[1], tz="UTC")
    forecast.loc[at_second, ["open", "high", "low", "close"]] = 11
    forecast.loc[at_second, "amount"] = 11000
    # The late entry now costs 11 as well; early inventory captured the rise.
    late = forecast.time == pd.Timestamp("2026-01-06 09:32", tz="Asia/Shanghai")
    forecast.loc[late, ["open", "high", "low", "close"]] = 11
    forecast.loc[late, "amount"] = 11000
    assert solve_joint_execution(replace(req, forecast_bars=forecast)).indices[0] == 1


@pytest.mark.parametrize("weights", [(float("nan"),), (1.1,), (-0.1,)])
def test_committed_prefix_rejects_invalid_weights(weights):
    req = two_period()
    first = req.decision_ns
    second = req.decision_times[1]
    committed = pd.DataFrame(
        [
            dict(
                decision_time=pd.Timestamp(first, tz="UTC"),
                entry_time=pd.Timestamp(req.entry_times[0], tz="UTC"),
                symbol="A",
                weight=weights[0],
            )
        ]
    )
    market = pd.concat([req.past_bars, req.forecast_bars], ignore_index=True)
    req = replace(
        req,
        decision_ns=second,
        forecast_available_ns=second,
        risk_available_ns=second,
        past_bars=market[market.time <= pd.Timestamp(second, tz="UTC")],
        forecast_bars=market[market.time > pd.Timestamp(second, tz="UTC")],
        committed_targets=committed,
        decision_times=(second,),
        entry_times=(req.entry_times[1],),
        weight_choices=(((0.0,),),),
    )
    with pytest.raises(ValueError, match="prefix"):
        solve_joint_execution(req)


def test_digest_does_not_depend_on_selected_weight_scalar_type():
    req = request(weight_choices=(((0,), (0.5,)),))
    assert (
        evaluate_joint_path(req, (0,)).request_digest
        == evaluate_joint_path(req, (1,)).request_digest
    )


def test_digest_binds_ordered_names_and_weight_mapping():
    req = request()
    b = pd.concat([req.past_bars, req.forecast_bars], ignore_index=True)
    b["symbol"] = "B"
    b[["open", "high", "low", "close"]] = 10.0
    b["amount"] = 10000.0
    first = replace(
        req,
        names=("A", "B"),
        terminal_covariance=np.zeros((2, 2)),
        past_bars=pd.concat([req.past_bars, b.iloc[:1]], ignore_index=True),
        forecast_bars=pd.concat([req.forecast_bars, b.iloc[1:]], ignore_index=True),
        weight_choices=(((1.0, 0.0),),),
    )
    a = evaluate_joint_path(first, (0,))
    b = evaluate_joint_path(replace(first, names=("B", "A")), (0,))
    assert a.result.fills.symbol.tolist() == ["A"]
    assert b.result.fills.symbol.tolist() == ["B"]
    assert a.terminal_nav != b.terminal_nav
    assert a.request_digest != b.request_digest
