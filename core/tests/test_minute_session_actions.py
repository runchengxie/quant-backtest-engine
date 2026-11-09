# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_minute_session_actions.py
import json

import pandas as pd
import pytest
from test_minute_execution import bars, targets
from test_minute_session import Policy

from quant_backtest_core._minute.corporate_actions import CorporateAction
from quant_backtest_core._minute.valuation_events import ValuationEvent
from quant_backtest_core.backtest.minute import MinuteExecutionConfig, simulate_minute_execution
from quant_backtest_core.backtest.minute_session import MinuteSession
from quant_backtest_core.backtest.quantity_locks import QuantityLock


def inputs():
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30", "2026-01-07 09:30"), (1, 0, 0))
    b = pd.concat(
        [
            bars(),
            bars(("2026-01-06 09:29", "2026-01-06 09:32"), price=4.5),
            bars(("2026-01-07 09:29", "2026-01-07 09:32"), price=4.5),
        ],
        ignore_index=True,
    )
    b["down_limit"] = 1.0
    cfg = MinuteExecutionConfig(10000, 0.1, 0, 0)
    action = CorporateAction(
        "distribution",
        "A",
        "2026-01-04",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-07",
        stock_per_share=1,
        stock_tradable_date="2026-01-07",
    )
    return t, b, cfg, action


def make(delay=0, locked=False, valuation=False):
    t, b, cfg, action = inputs()
    events = ()
    if valuation:
        b.loc[b.time.dt.day >= 6, "tradable"] = False
        events = (
            ValuationEvent(
                "residual",
                "A",
                "2026-01-06 09:29+08:00",
                "2026-01-06 09:28+08:00",
                4.5,
                "declared",
                "synthetic",
            ),
        )
    locks = ()
    if locked:
        locks = (
            QuantityLock(
                pd.Timestamp("2026-01-06", tz="Asia/Shanghai").value,
                pd.Timestamp("2026-01-06", tz="Asia/Shanghai").value,
                pd.Timestamp("2026-01-07 09:30", tz="Asia/Shanghai").value,
                ("A",),
                "synthetic",
            ),
        )
    return MinuteSession(
        t,
        b,
        cfg,
        policy=Policy(),
        report_delay_seconds=delay,
        corporate_actions=(action,),
        valuation_events=events,
        quantity_locks=locks,
    )


def restore(session):
    wire = json.loads(json.dumps(session.checkpoint(), allow_nan=False))
    policy = Policy()
    policy.rows = wire["policy"]
    return MinuteSession.restore(session.targets, session.bars, session.config, wire, policy=policy)


@pytest.mark.parametrize(
    "delay,locked,valuation", [(0, False, False), (600, True, False), (600, False, True)]
)
def test_actions_restore_every_boundary(delay, locked, valuation):
    full = make(delay, locked, valuation)
    result = full.run()
    for boundary in range(len(full.simulation.times) + 1):
        part = make(delay, locked, valuation)
        for _ in range(boundary):
            part.step()
        resumed = restore(part)
        assert resumed.checkpoint() == part.checkpoint()
        actual = resumed.run()
        for name in ("daily", "orders", "fills", "holdings", "valuation_ledger"):
            pd.testing.assert_frame_equal(getattr(actual, name), getattr(result, name))
        assert resumed.policy.rows == full.policy.rows
        assert resumed.simulation.rights == full.simulation.rights
        assert resumed.simulation.bought == full.simulation.bought
        assert resumed.delivered == full.delivered
        assert resumed.queue == full.queue
        assert resumed.trace == full.trace
        assert actual.summary == result.summary
    if not delay and not locked:
        expected = simulate_minute_execution(
            full.targets,
            full.bars,
            full.config,
            corporate_actions=full.corporate_actions,
            valuation_events=full.valuation_events,
            decision_policy=Policy(),
        )
        for name in ("daily", "orders", "fills", "holdings", "valuation_ledger"):
            pd.testing.assert_frame_equal(getattr(result, name), getattr(expected, name))


def test_split_locked_inventory_and_entitlement_release_hand_values():
    session = make(locked=True)
    while session.step():
        if session.simulation.current_time == pd.Timestamp("2026-01-06 09:32", tz="Asia/Shanghai"):
            assert session.simulation.holdings == {"A": 200}
            assert session.simulation.rights["distribution"] == {
                "symbol": "A",
                "cash": 200,
                "stock": 200,
                "ex": True,
            }
            assert session.simulation.receivables() == (200, 900)
    result = session.run()
    assert session.simulation.holdings == {"A": 400}
    assert session.simulation.cash == 8200
    assert session.simulation.receivables() == (0, 0)
    assert result.fills.side.tolist() == ["buy", "buy"]
    assert result.daily.nav.tolist() == [10000, 10000, 10000]


def test_action_and_valuation_tapes_and_exact_float_identity():
    session = make()
    checkpoint = session.checkpoint()
    changed = session.bars.copy()
    changed.loc[0, "amount"] += 1e-8
    with pytest.raises(ValueError, match="binding"):
        MinuteSession.restore(session.targets, changed, session.config, checkpoint, policy=Policy())
    with pytest.raises(ValueError, match="binding"):
        MinuteSession.restore(
            session.targets,
            session.bars,
            session.config,
            checkpoint,
            policy=Policy(),
            corporate_actions=(),
        )
    with pytest.raises(ValueError, match="CorporateAction"):
        MinuteSession(
            session.targets,
            session.bars,
            session.config,
            policy=Policy(),
            corporate_actions=({"type": "merger"},),
        )


def test_old_checkpoint_rejection_is_actionable():
    session = MinuteSession(
        targets(), bars(), MinuteExecutionConfig(10000, 0.1, 0, 0), policy=Policy()
    )
    checkpoint = session.checkpoint()
    checkpoint["schema"] = "minute-session.v1"
    with pytest.raises(ValueError, match=r"restart.*original"):
        MinuteSession.restore(
            session.targets, session.bars, session.config, checkpoint, policy=Policy()
        )


def test_external_capital_is_not_pnl_or_return():
    from quant_backtest_core.backtest.minute import CapitalFlow

    t, b, cfg, _ = inputs()
    flow = CapitalFlow(
        "deposit", "2026-01-06 09:28+08:00", "2026-01-06 09:30+08:00", 1000, "synthetic"
    )
    b.loc[:, ["open", "high", "low", "close"]] = 10.0
    b["amount"] = b.volume * 10
    session = MinuteSession(t, b, cfg, policy=Policy(), capital_flows=(flow,))
    result = session.run()
    assert result.daily.cumulative_capital_flow.tolist() == [0, 1000, 1000]
    assert result.daily.pnl.tolist() == [0, 0, 0]
    assert result.daily.cumulative_return.tolist() == [0, 0, 0]
    assert result.capital_flow_ledger.amount.tolist() == [1000]
    for boundary in range(len(session.simulation.times) + 1):
        part = MinuteSession(t, b, cfg, policy=Policy(), capital_flows=(flow,))
        for _ in range(boundary):
            part.step()
        recovered = restore(part).run()
        pd.testing.assert_frame_equal(recovered.daily, result.daily)
        pd.testing.assert_frame_equal(recovered.capital_flow_ledger, result.capital_flow_ledger)
    expected = simulate_minute_execution(t, b, cfg, decision_policy=Policy(), capital_flows=(flow,))
    pd.testing.assert_frame_equal(expected.daily, result.daily)


class FinancialPolicy(Policy):
    def __call__(self, state, proposed):
        self.rows.append(
            {
                "time": state.time.isoformat(),
                "cash": state.cash,
                "holdings": dict(state.holdings),
                "nav": state.nav,
                "cash_right": state.cash_receivable,
                "stock_right": state.stock_receivable_value,
                "pending": bool(state.pending_orders),
            }
        )
        return proposed


def test_same_clock_actions_then_valuation_then_flow_then_delayed_decision():
    from quant_backtest_core.backtest.minute import CapitalFlow

    t, b, cfg, action = inputs()
    t.loc[2, "decision_time"] = pd.Timestamp("2026-01-07 09:29", tz="Asia/Shanghai")
    b.loc[b.time.dt.day >= 7, "tradable"] = False
    valuation = ValuationEvent(
        "terminal",
        "A",
        "2026-01-07 09:29+08:00",
        "2026-01-07 09:28+08:00",
        3,
        "declared",
        "synthetic",
    )
    flow = CapitalFlow(
        "deposit", "2026-01-07 09:28+08:00", "2026-01-07 09:29+08:00", 1000, "synthetic"
    )
    policy = FinancialPolicy()
    session = MinuteSession(
        t,
        b,
        cfg,
        policy=policy,
        report_delay_seconds=600,
        corporate_actions=(action,),
        valuation_events=(valuation,),
        capital_flows=(flow,),
    )
    result = session.run()
    v = result.valuation_ledger.iloc[0]
    assert v.quantity == 400 and v.stock_receivable_quantity == 0
    assert v.cash_before == v.cash_after == 8200
    assert result.capital_flow_ledger.nav_before.iloc[0] == 9400
    row = policy.rows[-1]
    assert row["cash"] == 8000 and row["holdings"] == {"A": 200}
    assert row["cash_right"] == 200 and row["stock_right"] == 600
    assert row["nav"] == 9400 and row["pending"]
    assert session.trace[-1]["action"] == "wait_reports"
    assert len(session.simulation.orders) == 1


@pytest.mark.parametrize("clock", ["2026-01-06 09:29+08:00", "2026-01-06 09:30+08:00"])
def test_flow_stale_or_missing_marks_never_fabricate_return(clock):
    from quant_backtest_core.backtest.minute import CapitalFlow

    t, b, cfg, _ = inputs()
    flow = CapitalFlow("deposit", clock, clock, 1000, "synthetic")
    session = MinuteSession(t, b, cfg, policy=Policy(), capital_flows=(flow,))
    if "09:30" in clock:
        while session.simulation.current_time != pd.Timestamp("2026-01-06 09:29+08:00"):
            session.step()
        session.simulation.marks.clear()
    result = session.run()
    assert pd.isna(result.capital_flow_ledger.nav_before.iloc[0])
    assert result.daily.cumulative_return.iloc[1:].isna().all()


def test_flow_returns_chain_and_withdrawals_have_no_return():
    from quant_backtest_core.backtest.minute import CapitalFlow

    t = targets()
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:33", "2026-01-05 09:34"))
    # Buy 100 at 10, value 100 at 20: pre-flow NAV 11,000.
    b.loc[2:, ["open", "high", "low", "close"]] = 20
    b.loc[2:, "amount"] = 20000
    b.loc[2:, "tradable"] = False
    b["up_limit"] = 30
    flows = (
        CapitalFlow(
            "b-withdraw", "2026-01-05 09:34+08:00", "2026-01-05 09:34+08:00", -1000, "synthetic"
        ),
        CapitalFlow(
            "a-deposit", "2026-01-05 09:34+08:00", "2026-01-05 09:34+08:00", 2000, "synthetic"
        ),
    )
    result = MinuteSession(
        t, b, MinuteExecutionConfig(10000, 0.1, 0, 0), policy=Policy(), capital_flows=flows
    ).run()
    assert result.capital_flow_ledger.event_id.tolist() == ["a-deposit", "b-withdraw"]
    assert result.daily.pnl.iloc[0] == 1000
    assert result.daily.nav.iloc[0] == 12000
    assert result.daily.cumulative_return.iloc[0] == pytest.approx(0.1)


def test_failed_withdrawal_poisoned_session_cannot_checkpoint_or_continue():
    from quant_backtest_core.backtest.minute import CapitalFlow

    flows = (
        CapitalFlow(
            "a-deposit", "2026-01-05 09:30+08:00", "2026-01-05 09:30+08:00", 100, "synthetic"
        ),
        CapitalFlow(
            "b-withdraw", "2026-01-05 09:30+08:00", "2026-01-05 09:30+08:00", -20000, "synthetic"
        ),
    )
    session = MinuteSession(
        targets(),
        bars(),
        MinuteExecutionConfig(10000, 0.1, 0, 0),
        policy=Policy(),
        capital_flows=flows,
    )
    assert session.step()
    safe = session.checkpoint()
    with pytest.raises(ValueError, match="withdrawal"):
        session.step()
    assert session.simulation.cash == 10100  # Partial attempt must be abandoned.
    for operation in (session.checkpoint, session.step, session.run):
        with pytest.raises(ValueError, match=r"failed session.*reconstruct"):
            operation()
    policy = Policy()
    policy.rows = safe["policy"]
    restored = MinuteSession.restore(
        session.targets, session.bars, session.config, safe, policy=policy
    )
    assert restored.simulation.cash == 10000


def test_zero_wealth_return_and_all_capital_validation_boundaries():
    from quant_backtest_core.backtest.minute import CapitalFlow

    clock = "2026-01-05 09:30+08:00"
    flow = CapitalFlow("withdraw", clock, clock, -10000, "synthetic")
    result = MinuteSession(
        targets(),
        bars(),
        MinuteExecutionConfig(10000, 0.1, 0, 0),
        policy=Policy(),
        capital_flows=(flow,),
    ).run()
    assert result.daily.nav.iloc[0] == 0
    assert pd.isna(result.daily.cumulative_return.iloc[0])
    for amount in (0, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            CapitalFlow("bad", clock, clock, amount, "synthetic")
    with pytest.raises(ValueError, match="available_time"):
        CapitalFlow("bad", "2026-01-05 09:31+08:00", clock, 10, "synthetic")
    with pytest.raises(ValueError, match="timezone aware"):
        CapitalFlow("bad", "2026-01-05", "2026-01-05", 10, "synthetic")
    for flows, match in (
        ((flow, flow), "duplicate"),
        ((CapitalFlow("late", clock, "2026-01-08 09:30+08:00", 10, "synthetic"),), "window"),
    ):
        with pytest.raises(ValueError, match=match):
            MinuteSession(
                targets(),
                bars(),
                MinuteExecutionConfig(10000, 0.1, 0, 0),
                policy=Policy(),
                capital_flows=flows,
            )


def test_complete_state_required_and_tape_and_helper_source_changes_rejected(monkeypatch):
    from pathlib import Path

    from quant_backtest_core.backtest._minute_checkpoint import _digest, _unwire, _wire

    session = make(valuation=True)
    checkpoint = session.checkpoint()
    with pytest.raises(ValueError, match="binding"):
        MinuteSession.restore(
            session.targets,
            session.bars,
            session.config,
            checkpoint,
            policy=Policy(),
            valuation_events=(),
        )
    state = _unwire(checkpoint["state"])
    del state["rights"]
    broken = {**checkpoint, "state": _wire(state)}
    broken.pop("digest")
    broken["digest"] = _digest(broken)
    with pytest.raises(ValueError, match="incomplete"):
        MinuteSession.restore(
            session.targets, session.bars, session.config, broken, policy=Policy()
        )
    original = Path.read_bytes
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda p: (
            original(p) + (b"# changed owner helper" if p.name == "corporate_actions.py" else b"")
        ),
    )
    with pytest.raises(ValueError, match="binding"):
        MinuteSession.restore(
            session.targets, session.bars, session.config, checkpoint, policy=Policy()
        )


def test_unsupported_event_subclasses_fail_explicitly():
    class UnsupportedAction(CorporateAction):
        pass

    t, b, cfg, action = inputs()
    from dataclasses import asdict

    with pytest.raises(ValueError, match="exact CorporateAction"):
        MinuteSession(
            t, b, cfg, policy=Policy(), corporate_actions=(UnsupportedAction(**asdict(action)),)
        )


def test_capital_overflow_cannot_create_infinite_cash():
    from quant_backtest_core.backtest.minute import CapitalFlow

    clock = "2026-01-05 09:30+08:00"
    session = MinuteSession(
        targets(),
        bars(),
        MinuteExecutionConfig(1e308, 0.1, 0, 0),
        policy=Policy(),
        capital_flows=(CapitalFlow("deposit", clock, clock, 1e308, "synthetic"),),
    )
    session.step()
    with pytest.raises(ValueError, match="finite"):
        session.step()
    with pytest.raises(ValueError, match="failed session"):
        session.checkpoint()


def test_actions_valuation_and_impact_restore_full_state_each_boundary():
    from quant_backtest_core.backtest.impact import LinearImpact

    baseline = make(600, True, True)

    def build():
        return MinuteSession(
            baseline.targets,
            baseline.bars,
            baseline.config,
            policy=Policy(),
            corporate_actions=baseline.corporate_actions,
            valuation_events=baseline.valuation_events,
            quantity_locks=baseline.quantity_locks,
            report_delay_seconds=600,
            impact=LinearImpact(permanent=0.0001),
        )

    full = build()
    expected = full.run()
    for boundary in range(len(full.simulation.times) + 1):
        part = build()
        for _ in range(boundary):
            part.step()
        resumed = restore(part)
        assert resumed.checkpoint() == part.checkpoint()
        result = resumed.run()
        for name in (
            "daily",
            "orders",
            "fills",
            "holdings",
            "valuation_ledger",
            "capital_flow_ledger",
        ):
            pd.testing.assert_frame_equal(getattr(result, name), getattr(expected, name))
        assert result.summary == expected.summary
        assert resumed.queue == full.queue


def test_utc_flow_crossing_local_midnight_uses_owner_calendar_once():
    from quant_backtest_core.backtest.minute import CapitalFlow

    t = targets(("2026-01-05 23:57",), (1,))
    b = bars(("2026-01-05 23:56", "2026-01-05 23:59", "2026-01-06 00:01"))
    b.loc[2, "tradable"] = False
    action = CorporateAction(
        "split",
        "A",
        "2026-01-04",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-06",
        stock_per_share=1,
        stock_tradable_date="2026-01-06",
    )
    valuation = ValuationEvent(
        "valuation",
        "A",
        "2026-01-06 00:00+08:00",
        "2026-01-05 23:59+08:00",
        4.5,
        "declared",
        "synthetic",
    )
    flow = CapitalFlow(
        "deposit", "2026-01-05 15:59+00:00", "2026-01-05 16:00+00:00", 1000, "synthetic"
    )

    def build():
        return MinuteSession(
            t,
            b,
            MinuteExecutionConfig(10000, 0.1, 0, 0),
            policy=Policy(),
            corporate_actions=(action,),
            valuation_events=(valuation,),
            capital_flows=(flow,),
        )

    full = build()
    assert {str(time.tz) for time in full.simulation.times} == {"Asia/Shanghai"}
    expected = full.run()
    assert expected.daily.date.astype(str).tolist() == ["2026-01-05", "2026-01-06"]
    assert full.simulation.holdings == {"A": 200}
    assert full.simulation.bought == {}
    assert full.simulation.cash == 10100
    assert expected.daily.nav.tolist() == [10000, 11000]
    assert expected.daily.pnl.tolist() == [0, 0]
    assert expected.daily.cumulative_return.tolist() == [0, 0]
    assert expected.valuation_ledger.quantity.tolist() == [200]
    assert expected.capital_flow_ledger.event_id.tolist() == ["deposit"]
    for boundary in range(len(full.simulation.times) + 1):
        part = build()
        for _ in range(boundary):
            part.step()
        resumed = restore(part)
        assert resumed.checkpoint() == part.checkpoint()
        result = resumed.run()
        for name in ("daily", "holdings", "fills", "valuation_ledger", "capital_flow_ledger"):
            pd.testing.assert_frame_equal(getattr(result, name), getattr(expected, name))


def earlier_decision_valuation_inputs():
    t = targets()
    t.loc[0, "decision_time"] = pd.Timestamp("2026-01-05 09:27", tz="Asia/Shanghai")
    b = bars().assign(tradable=False)
    event = ValuationEvent(
        "residual",
        "A",
        "2026-01-05 09:28+08:00",
        "2026-01-05 09:26+08:00",
        3,
        "declared",
        "synthetic",
    )
    return t, b, MinuteExecutionConfig(10000, 0.1, 0, 0), event


def test_earlier_decision_executes_newly_in_window_valuation_synchronously():
    t, b, cfg, event = earlier_decision_valuation_inputs()
    result = simulate_minute_execution(
        t, b, cfg, decision_policy=Policy(), valuation_events=(event,)
    )
    assert result.valuation_ledger.event_id.tolist() == ["residual"]
    assert result.valuation_ledger.time.tolist() == [event.effective_time]
    assert result.daily.valuation_marks.iloc[-1][0]["value_per_share"] == 3
    assert result.summary["nontrading_valuation_symbols"] == ["A"]


def test_newly_in_window_valuation_recovers_at_every_event_boundary():
    t, b, cfg, event = earlier_decision_valuation_inputs()

    def build():
        return MinuteSession(t, b, cfg, policy=Policy(), valuation_events=(event,))

    full = build()
    expected = full.run()
    assert expected.valuation_ledger.event_id.tolist() == ["residual"]
    assert expected.valuation_ledger.time.tolist() == [event.effective_time]
    assert full.simulation.marks == {"A": 3}
    assert full.simulation.valuation_state == {"A": event}
    assert full.simulation.times.count(event.effective_time) == 1
    synchronous = simulate_minute_execution(
        t, b, cfg, decision_policy=Policy(), valuation_events=(event,)
    )
    for name in ("daily", "orders", "fills", "holdings", "valuation_ledger"):
        pd.testing.assert_frame_equal(getattr(expected, name), getattr(synchronous, name))
    for boundary in range(len(full.simulation.times) + 1):
        part = build()
        for _ in range(boundary):
            part.step()
        resumed = restore(part)
        assert resumed.checkpoint() == part.checkpoint()
        result = resumed.run()
        assert resumed.simulation.marks == {"A": 3}
        assert resumed.simulation.valuation_state == {"A": event}
        assert resumed.policy.rows == full.policy.rows
        for name in ("daily", "orders", "fills", "holdings", "valuation_ledger"):
            pd.testing.assert_frame_equal(getattr(result, name), getattr(expected, name))
