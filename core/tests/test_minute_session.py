# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_minute_session.py
import json

import pandas as pd
import pytest
from test_minute_execution import bars, targets

from quant_backtest_core.backtest.impact import LinearImpact
from quant_backtest_core.backtest.minute import MinuteExecutionConfig, simulate_minute_execution
from quant_backtest_core.backtest.minute_session import MinuteSession


class Policy:
    def __init__(self):
        self.rows = []

    def __call__(self, state, proposed):
        self.rows.append(
            {
                "cash": state.cash,
                "holdings": dict(state.holdings),
                "pending": bool(state.pending_orders),
            }
        )
        return None if state.pending_orders else proposed

    def checkpoint(self):
        return self.rows.copy()


def make(delay=0):
    return MinuteSession(
        targets(("2026-01-05 09:30", "2026-01-05 09:34"), (1, 1)),
        bars(),
        MinuteExecutionConfig(10000, 0.1, 3, 8),
        policy=Policy(),
        report_delay_seconds=delay,
        impact=LinearImpact(permanent=0.0001),
    )


def test_zero_delay_matches_existing_owner_and_hidden_reports_do_not_duplicate():
    session = make()
    expected = simulate_minute_execution(
        session.targets,
        session.bars,
        session.config,
        decision_policy=Policy(),
        impact_model=LinearImpact(permanent=0.0001),
    )
    result = session.run()
    for table in ("daily", "orders", "fills", "holdings"):
        pd.testing.assert_frame_equal(getattr(result, table), getattr(expected, table))
    delayed = make(600)
    delayed.run()
    assert delayed.policy.rows[1]["holdings"] == {}
    assert delayed.policy.rows[1]["pending"]
    assert len(delayed.simulation.orders) == 1


def test_every_event_boundary_recovers_all_state_and_rejects_changed_source():
    full = make(600)
    expected = full.run()
    for boundary in range(len(full.simulation.times) + 1):
        session = make(600)
        for _ in range(boundary):
            session.step()
        wire = json.loads(json.dumps(session.checkpoint(), allow_nan=False))
        policy = Policy()
        policy.rows = json.loads(json.dumps(wire["policy"]))
        restored = MinuteSession.restore(
            session.targets, session.bars, session.config, wire, policy=policy
        )
        result = restored.run()
        for table in ("daily", "orders", "fills", "holdings"):
            pd.testing.assert_frame_equal(getattr(result, table), getattr(expected, table))
        assert restored.policy.rows == full.policy.rows
        changed = session.bars.copy()
        changed.loc[0, "volume"] += 1
        with pytest.raises(ValueError, match="binding"):
            MinuteSession.restore(session.targets, changed, session.config, wire, policy=policy)
    with pytest.raises(ValueError, match="finished"):
        full.checkpoint()


def test_entry_guard_rechecks_reports_and_pending_contract_is_read_only():
    class ReadingPolicy(Policy):
        def __call__(self, state, proposed):
            if state.pending_orders:
                pending = state.pending_orders[0]
                assert pending["remaining_quantity"] >= 0
                with pytest.raises(TypeError):
                    pending["remaining_quantity"] = 0
            return super().__call__(state, proposed)

    t = targets(("2026-01-05 09:30", "2026-01-05 09:34"), (1, 0.5))
    t["decision_time"] = pd.Timestamp("2026-01-05 09:28", tz="Asia/Shanghai")
    session = MinuteSession(
        t,
        bars(),
        MinuteExecutionConfig(10000, 0.1, 0, 0),
        policy=ReadingPolicy(),
        report_delay_seconds=600,
    )
    session.run()
    assert len(session.simulation.orders) == 1
    session = make()
    session.policy = ReadingPolicy()
    session.run()


def test_recovery_binds_policy_implementation_even_with_same_state():
    session = make()
    checkpoint = session.checkpoint()

    class OtherPolicy(Policy):
        def __call__(self, state, proposed):
            return {}

    with pytest.raises(ValueError, match="binding"):
        MinuteSession.restore(
            session.targets, session.bars, session.config, checkpoint, policy=OtherPolicy()
        )


def test_multiday_recovery_preserves_t_plus_one_and_commission_parent():
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30"), (1, 0))
    b = pd.concat(
        [
            bars(),
            bars().assign(
                time=lambda f: f.time + pd.Timedelta(days=1),
                interval_start=lambda f: f.interval_start + pd.Timedelta(days=1),
            ),
        ],
        ignore_index=True,
    )
    cfg = MinuteExecutionConfig(10000, 0.1, 3, 8, commission_minimum_cny=5)
    policy = Policy()
    session = MinuteSession(t, b, cfg, policy=policy)
    for _ in range(len(session.simulation.times) // 2):
        session.step()
    wire = json.loads(json.dumps(session.checkpoint(), allow_nan=False))
    restored_policy = Policy()
    restored_policy.rows = json.loads(json.dumps(wire["policy"]))
    restored = MinuteSession.restore(t, b, cfg, wire, policy=restored_policy)
    full = session.run()
    recovered = restored.run()
    pd.testing.assert_frame_equal(full.daily, recovered.daily)
    pd.testing.assert_frame_equal(full.fills, recovered.fills)
    assert (
        full.fills.loc[full.fills.side == "sell", "time"].min().date().isoformat() == "2026-01-06"
    )
    assert full.fills.commission.sum() >= 10


def test_checkpoint_detects_tampering_and_caller_input_mutation_is_isolated():
    session = make()
    wire = json.loads(json.dumps(session.checkpoint()))
    wire["cursor"] = 1
    with pytest.raises(ValueError, match="integrity"):
        MinuteSession.restore(session.targets, session.bars, session.config, wire, policy=Policy())
    original = session.simulation.bars.copy()
    session.bars.loc[0, "close"] = 9.9
    pd.testing.assert_frame_equal(session.simulation.bars, original)


def test_unrestorable_impact_subclass_is_rejected():
    class CustomImpact(LinearImpact):
        def preview(self, *args):
            return 0

    with pytest.raises(ValueError, match="LinearImpact"):
        MinuteSession(
            targets(),
            bars(),
            MinuteExecutionConfig(10000, 0.1, 0, 0),
            policy=Policy(),
            impact=CustomImpact(),
        )
