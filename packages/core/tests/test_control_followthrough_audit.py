"""Hand arithmetic for moving-price execution evidence."""

import pandas as pd
import pytest

from quant_backtest_core.planning.control_followthrough_audit import price_decomposition


def test_partial_inventory_is_marked_not_free_liquidation():
    times = pd.to_datetime(["2025-01-03 09:31:00+08:00", "2025-01-03 09:32:00+08:00"])
    fills = pd.DataFrame(
        {"time": [times[0]], "quantity": [4], "price": [9.7], "transaction_cost": [0.04]}
    )
    bars = pd.DataFrame({"time": times, "close": [9.8, 9.0]})
    value = price_decomposition(
        fills,
        bars,
        quantity=10,
        benchmark=10.0,
        start=times[0] - pd.Timedelta(minutes=1),
        end=times[-1],
    )
    assert value["price_drift_cny"] == pytest.approx(0.8)
    assert value["execution_deviation_cny"] == pytest.approx(0.4)
    assert value["exit_fees_cny"] == 0.04
    assert value["residual_mark_shortfall_cny"] == 6
    assert value["full_target_marked_shortfall_cny"] == pytest.approx(7.24)
    assert value["inventory_share_minutes"] == 16
    assert value["inventory_squared_share_minutes"] == 136


def test_zero_impact_and_complete_price_drift():
    time = pd.Timestamp("2025-01-03 09:31", tz="Asia/Shanghai")
    fills = pd.DataFrame(
        {"time": [time], "quantity": [10], "price": [10.2], "transaction_cost": [0.0]}
    )
    bars = pd.DataFrame({"time": [time], "close": [10.2]})
    v = price_decomposition(
        fills, bars, quantity=10, benchmark=10.0, start=time - pd.Timedelta(minutes=1), end=time
    )
    assert v["execution_deviation_cny"] == 0
    assert v["full_target_marked_shortfall_cny"] == pytest.approx(-2)


def test_reject_missing_fill_raw_quote():
    time = pd.Timestamp("2025-01-03 09:31", tz="Asia/Shanghai")
    fills = pd.DataFrame(
        {"time": [time], "quantity": [1], "price": [10.0], "transaction_cost": [0.0]}
    )
    with pytest.raises(ValueError, match="raw"):
        price_decomposition(
            fills,
            pd.DataFrame({"time": [time + pd.Timedelta(minutes=1)], "close": [10.0]}),
            quantity=2,
            benchmark=10.0,
            start=time,
            end=time + pd.Timedelta(minutes=1),
        )


@pytest.mark.parametrize("path", ["flat", "up", "down", "oscillating", "jump"])
@pytest.mark.parametrize("reserve", [0, 1])
def test_owner_dynamic_mark_conservation(path, reserve):
    from quant_backtest_core.planning.control_followthrough import StudyCase, run_study
    from quant_backtest_core.planning.control_followthrough_audit import audit_study
    from quant_backtest_core.planning.owner_control_case import OwnerControlCase

    case = StudyCase(OwnerControlCase(), price_path=path, reserve_slots=reserve)
    result, diagnostics = run_study(case)
    value = audit_study(case, result, diagnostics)
    assert value["exit_quantity"] + value["residual_quantity"] == 400
    assert value["completed"]
    assert value["execution_deviation_cny"] >= 0
    assert value["full_target_marked_shortfall_cny"] == pytest.approx(
        4000
        - result.fills.query("side == 'sell'").gross_amount.sum()
        + result.fills.query("side == 'sell'").transaction_cost.sum()
    )


def test_failure_flags_preserve_uncompleted_owner_path():
    from quant_backtest_core.planning.control_followthrough import StudyCase, run_study
    from quant_backtest_core.planning.control_followthrough_audit import audit_study
    from quant_backtest_core.planning.owner_control_case import OwnerControlCase

    case = StudyCase(OwnerControlCase(quantity=1200))
    result, diagnostics = run_study(case)
    value = audit_study(case, result, diagnostics)
    assert not value["rankable"]
    assert value["planning_failure_observed"]
    assert value["insufficient_realized_clock_capacity"]


def test_immediate_wait_after_its_only_submission_is_not_a_lost_fixed_slot():
    from quant_backtest_core.planning.control_followthrough import StudyCase, run_study
    from quant_backtest_core.planning.control_followthrough_audit import audit_study
    from quant_backtest_core.planning.owner_control_case import OwnerControlCase

    case = StudyCase(OwnerControlCase(policy="immediate", report_delay_seconds=300.0))
    result, diag = run_study(case)
    metric = audit_study(case, result, diag)
    assert metric["wait_pending_decisions"] > 0
    assert metric["fixed_submission_slots_lost"] == 0
