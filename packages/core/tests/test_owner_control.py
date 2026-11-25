import pytest

from quant_backtest_core.planning.owner_control_case import OwnerControlCase, run_case


def test_immediate_no_retry_and_fixed_schedule_no_catchup():
    result, diagnostics = run_case(OwnerControlCase(policy="immediate", liquidity="outage"))
    assert result.fills.query("side == 'sell'").empty
    assert len(result.orders.query("side == 'sell'")) == 1
    assert sum(r["action"] == "submit" for r in diagnostics["policy_trace"]) == 1


def test_infeasible_records_failure_without_fallback():
    result, diagnostics = run_case(OwnerControlCase(quantity=1200, participation=0.05))
    assert result.fills.query("side == 'sell'").empty
    assert any(r["action"] == "planning_failure" for r in diagnostics["policy_trace"])


def test_pending_reports_gate_policy():
    _, diagnostics = run_case(OwnerControlCase(report_delay_seconds=300))
    assert any(r["action"] == "wait_pending" for r in diagnostics["policy_trace"])


@pytest.mark.parametrize("policy", ["twap", "open_loop", "rolling"])
def test_encoded_targets_match_actual_owner_order(policy):
    result, diagnostics = run_case(OwnerControlCase(policy=policy, quantity=401))
    trace = {r["time"]: r for r in diagnostics["policy_trace"] if r["action"] == "submit"}
    for order in result.orders.query("side == 'sell'").itertuples():
        row = trace[order.decision_time.isoformat()]
        assert order.quantity == row["delivered_quantity"] - row["target_quantity"]
    if policy != "rolling":
        first = next(iter(trace.values()))
        assert sum(first["integer_sales"]) == 401


def test_zero_impact_zero_fee_hand_cash():
    from dataclasses import replace

    from quant_backtest_core.backtest.minute_session import MinuteSession
    from quant_backtest_core.planning.owner_control import OwnerLiquidationPolicy
    from quant_backtest_core.planning.owner_control_case import case_inputs

    case = OwnerControlCase(policy="twap", quantity=80)
    targets, bars, config = case_inputs(case)
    config = replace(config, buy_fee_bp=0, sell_fee_bp=0, sell_tax_bp=0)
    session = MinuteSession(targets, bars, config, policy=OwnerLiquidationPolicy(case))
    result = session.run()
    assert result.fills.query("side == 'sell'").quantity.sum() == 80
    assert result.daily.iloc[-1]["cash"] == 1600


def test_policy_projects_control_only_and_hides_actual_scenario():
    from types import SimpleNamespace

    import pandas as pd

    from quant_backtest_core.planning.owner_control import OwnerLiquidationPolicy

    left = OwnerLiquidationPolicy(OwnerControlCase())
    right = OwnerLiquidationPolicy(OwnerControlCase(actual_multiplier=2, liquidity="outage"))
    assert not hasattr(left, "case")
    expected = {"policy", "quantity", "participation", "belief_multiplier"}
    assert set(vars(left.control)) == expected
    checkpoint = left.checkpoint()
    assert "case" not in checkpoint
    assert set(checkpoint["control"]) == expected
    assert not any(field in checkpoint for field in ("actual_multiplier", "liquidity"))
    state = SimpleNamespace(
        time=pd.Timestamp("2025-01-03 09:29", tz="Asia/Shanghai"),
        holdings={"A": 400},
        pending_orders=(),
        marks={"A": 10},
        nav=8000.0,
    )
    assert left(state, {}) == right(state, {})
    assert left.trace == right.trace
    assert left.checkpoint()["case_binding"] != right.checkpoint()["case_binding"]
    assert "pandas" in checkpoint["dependencies"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("fixed_sales", []),
        ("fixed_sales", [True] * 8),
        ("fixed_continuous", [float("nan")] * 8),
        ("fixed_continuous", ["50"] * 8),
        ("trace", [{"slot": 3}]),
        ("fixed_failure", ""),
    ],
)
def test_malformed_policy_state_rejects(field, value):
    from quant_backtest_core.planning.owner_control import OwnerLiquidationPolicy
    from quant_backtest_core.planning.owner_control_case import build_session

    case = OwnerControlCase(policy="twap")
    session = build_session(case)
    while len(session.policy.trace) < 2:
        session.step()
    checkpoint = session.policy.checkpoint()
    checkpoint[field] = value
    with pytest.raises(ValueError, match="policy"):
        OwnerLiquidationPolicy.restore(case, checkpoint)


def test_empty_fixed_schedule_rejects_before_owner_restore(monkeypatch):
    from quant_backtest_core.backtest._minute_checkpoint import _digest
    from quant_backtest_core.backtest.minute_session import MinuteSession
    from quant_backtest_core.planning.owner_control_case import build_session, restore_case

    case = OwnerControlCase(policy="twap")
    session = build_session(case)
    while len(session.policy.trace) < 2:
        session.step()
    checkpoint = session.checkpoint()
    checkpoint["policy"]["fixed_sales"] = []
    checkpoint["digest"] = _digest(
        {key: value for key, value in checkpoint.items() if key != "digest"}
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("owner restore must not run")

    monkeypatch.setattr(MinuteSession, "restore", forbidden)
    with pytest.raises(ValueError, match="policy"):
        restore_case(case, checkpoint)


@pytest.mark.parametrize("policy", ["open_loop", "rolling"])
def test_legal_infeasible_policy_state_restores_every_boundary(policy):
    from quant_backtest_core.planning.owner_control import OwnerLiquidationPolicy
    from quant_backtest_core.planning.owner_control_case import build_session

    case = OwnerControlCase(policy=policy, quantity=1200, participation=0.05)
    session = build_session(case)
    while True:
        checkpoint = session.policy.checkpoint()
        assert OwnerLiquidationPolicy.restore(case, checkpoint).checkpoint() == checkpoint
        if not session.step():
            break
