"""Bounded follow-through fixtures and recovery acceptance."""

import copy
import json
from dataclasses import replace

import pandas as pd
import pytest

from quant_backtest_core.planning.control_followthrough import (
    StudyCase,
    StudyLiquidationPolicy,
    build_study,
    restore_study,
    run_study,
    study_inputs,
)
from quant_backtest_core.planning.owner_control_case import OwnerControlCase


@pytest.mark.parametrize("path", ["flat", "up", "down", "oscillating", "jump"])
def test_price_paths(path):
    _, bars, _ = study_inputs(StudyCase(OwnerControlCase(), path))
    prices = {
        "flat": [10] * 8,
        "up": [10 + 0.02 * i for i in range(8)],
        "down": [10 - 0.02 * i for i in range(8)],
        "oscillating": [10 + x for x in [0, 0.04, -0.04, 0.04, -0.04, 0.04, -0.04, 0]],
        "jump": [10] * 6 + [9.8] * 2,
    }[path]
    assert list(bars.close[:3]) == [10] * 3
    for i, price in enumerate(prices):
        assert (
            (bars.iloc[3 + 3 * i : 6 + 3 * i][["open", "high", "low", "close"]] == price)
            .all()
            .all()
        )
    assert (bars.close.iloc[27:] == prices[-1]).all()
    assert (bars.amount == bars.close * bars.volume).all()


@pytest.mark.parametrize(
    "base,path,reserve",
    [
        (None, "flat", 0),
        (OwnerControlCase(), "bad", 0),
        (OwnerControlCase(), "flat", True),
        (OwnerControlCase(), "flat", 2),
        (OwnerControlCase(policy="twap"), "flat", 1),
    ],
)
def test_invalid_case(base, path, reserve):
    with pytest.raises(ValueError):
        StudyCase(base, path, reserve)


def test_causality_prefix():
    case = StudyCase(OwnerControlCase(), "up", 1)
    _, bars, _ = study_inputs(case)
    cutoff = bars.time.iloc[14]
    changed = bars.copy()
    changed.loc[changed.time > cutoff, ["open", "high", "low", "close"]] = 9
    changed.amount = changed.close * changed.volume
    left, right = build_study(case), build_study(case, bars=changed)
    while left.simulation.times[left.cursor] <= cutoff:
        left.step()
        right.step()
    assert left.policy.checkpoint() == right.policy.checkpoint()
    assert left.simulation.fills == right.simulation.fills
    assert left.simulation.orders == right.simulation.orders


@pytest.mark.parametrize(
    "quantity,participation,delay,liquidity",
    [(400, 0.1, 0, "normal"), (401, 0.1, 300, "outage"), (750, 0.1, 0, "outage")],
)
def test_reserve_conservation(quantity, participation, delay, liquidity):
    result, diagnostic = run_study(
        StudyCase(
            OwnerControlCase(
                quantity=quantity,
                participation=participation,
                report_delay_seconds=delay,
                liquidity=liquidity,
            ),
            "down",
            1,
        )
    )
    assert result.fills.query("side == 'sell'").quantity.sum() <= quantity
    assert all(
        row.get("target_quantity", 0) is None or row.get("target_quantity", 0) >= 0
        for row in diagnostic["policy_trace"]
    )
    if delay:
        assert any(r["action"] == "wait_pending" for r in diagnostic["policy_trace"])
    if quantity == 750:
        assert any(r["action"] == "planning_failure" for r in diagnostic["policy_trace"])


def test_every_boundary_recovery():
    case = StudyCase(
        OwnerControlCase(report_delay_seconds=300, latency_minutes=1, liquidity="outage"), "jump", 1
    )
    expected, diagnostic = run_study(case)
    session = build_study(case)
    while True:
        checkpoint = json.loads(json.dumps(session.checkpoint(), allow_nan=False))
        restored = restore_study(case, checkpoint)
        assert restored.checkpoint() == checkpoint
        actual = restored.run()
        for name in ("daily", "orders", "fills", "holdings"):
            pd.testing.assert_frame_equal(getattr(actual, name), getattr(expected, name))
        assert restored.policy.checkpoint() == diagnostic["checkpoint"]["policy"]
        if not session.step():
            break


def test_changed_bindings_and_malformed_state():
    case = StudyCase(OwnerControlCase(), "flat", 1)
    policy = StudyLiquidationPolicy(case)
    checkpoint = policy.checkpoint()
    for changed in (
        replace(case, price_path="up"),
        replace(case, reserve_slots=0),
        replace(case, base=replace(case.base, actual_multiplier=2)),
    ):
        with pytest.raises(ValueError):
            StudyLiquidationPolicy.restore(changed, checkpoint)
    for field, value in [
        ("dependencies", {}),
        ("trace", [{"slot": 3}]),
        ("fixed_sales", []),
        ("fixed_failure", "bad"),
        ("schema", "old"),
    ]:
        altered = copy.deepcopy(checkpoint)
        altered[field] = value
        with pytest.raises(ValueError):
            StudyLiquidationPolicy.restore(case, altered)


@pytest.mark.parametrize("policy", ["immediate", "twap", "open_loop", "rolling"])
def test_zero_reserve_all_policies_restore(policy):
    case = StudyCase(OwnerControlCase(policy=policy), "up")
    session = build_study(case)
    while session.step():
        checkpoint = session.policy.checkpoint()
        assert StudyLiquidationPolicy.restore(case, checkpoint).checkpoint() == checkpoint


def test_changed_helper_dependency_rejected(monkeypatch):
    from quant_backtest_core.planning import control_followthrough

    case = StudyCase(OwnerControlCase(), reserve_slots=1)
    checkpoint = build_study(case).checkpoint()
    monkeypatch.setattr(control_followthrough, "fingerprints", lambda: {"changed": True})
    with pytest.raises(ValueError, match="dependency"):
        restore_study(case, checkpoint)


@pytest.mark.parametrize(
    "field,value",
    [
        ("integer_sales", [1]),
        ("continuous_sales", [1.0]),
        ("pending_count", 1),
        ("failure", "bad"),
        ("target_quantity", 399),
        ("target_weight", float("nan")),
        ("extra", 1),
    ],
)
def test_tampered_decision_state(field, value):
    case = StudyCase(OwnerControlCase(), reserve_slots=1)
    session = build_study(case)
    while len(session.policy.trace) < 2:
        session.step()
    checkpoint = session.policy.checkpoint()
    checkpoint["trace"][-1][field] = value
    with pytest.raises(ValueError, match="policy"):
        StudyLiquidationPolicy.restore(case, checkpoint)
