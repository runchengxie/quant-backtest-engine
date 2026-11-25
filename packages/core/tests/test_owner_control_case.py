"""Synthetic owner bridge acceptance."""

import pytest

from quant_backtest_core.planning.owner_control_case import (
    OwnerControlCase,
    build_session,
    restore_case,
    run_case,
)


@pytest.mark.parametrize("policy", ["immediate", "twap", "open_loop", "rolling"])
def test_fixture_bootstrap_and_conservation(policy):
    case = OwnerControlCase(policy=policy)
    result, diagnostics = run_case(case)
    assert result.fills.query("side == 'buy'").quantity.sum() == 400
    assert result.fills.query("side == 'sell'").quantity.sum() <= 400
    assert len(diagnostics["policy_trace"]) == 9
    assert diagnostics["checkpoint"]["cursor"] > 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"quantity": True},
        {"quantity": 0},
        {"participation": float("nan")},
        {"latency_minutes": True},
        {"actual_multiplier": -1},
    ],
)
def test_reject_bad_case(kwargs):
    with pytest.raises(ValueError):
        OwnerControlCase(**kwargs)


def test_restore_expected_case():
    case = OwnerControlCase()
    session = build_session(case)
    for _ in range(8):
        session.step()
    checkpoint = session.checkpoint()
    restored = restore_case(case, checkpoint)
    assert restored.checkpoint() == checkpoint
    with pytest.raises(ValueError):
        restore_case(OwnerControlCase(policy="twap"), checkpoint)


@pytest.mark.parametrize("policy", ["immediate", "twap", "open_loop", "rolling"])
def test_every_boundary_recovery_delayed_outage(policy):
    import pandas as pd

    case = OwnerControlCase(
        policy=policy, report_delay_seconds=300, latency_minutes=1, liquidity="outage"
    )
    expected, diagnostics = run_case(case)
    session = build_session(case)
    while True:
        restored = restore_case(case, session.checkpoint())
        actual = restored.run()
        for name in ("daily", "orders", "fills", "holdings"):
            pd.testing.assert_frame_equal(getattr(actual, name), getattr(expected, name))
        assert restored.policy.checkpoint() == diagnostics["checkpoint"]["policy"]
        if not session.step():
            break


def test_helper_fingerprint_rejects_before_owner_restore(monkeypatch):
    from quant_backtest_core.planning import owner_control

    session = build_session(OwnerControlCase())
    checkpoint = session.checkpoint()
    monkeypatch.setattr(owner_control, "fingerprints", lambda: {"changed": True})
    with pytest.raises(ValueError, match="dependency"):
        restore_case(OwnerControlCase(), checkpoint)


def test_future_bar_changes_preserve_prefix():
    from quant_backtest_core.planning.owner_control_case import case_inputs

    case = OwnerControlCase()
    _, bars, _ = case_inputs(case)
    cutoff = bars.time.iloc[14]
    changed = bars.copy()
    changed.loc[changed.time > cutoff, "volume"] = 0
    changed.loc[changed.time > cutoff, "amount"] = 0
    left, right = build_session(case), build_session(case, bars=changed)
    while left.simulation.times[left.cursor] <= cutoff:
        left.step()
        right.step()
    assert left.policy.checkpoint() == right.policy.checkpoint()
    assert left.simulation.orders == right.simulation.orders
    assert left.simulation.fills == right.simulation.fills
