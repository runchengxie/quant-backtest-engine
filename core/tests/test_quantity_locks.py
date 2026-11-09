# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_quantity_locks.py
import json
from dataclasses import replace

import pandas as pd
import pytest
from test_minute_execution import bars, targets
from test_minute_session import Policy

from quant_backtest_core.backtest.minute import MinuteExecutionConfig
from quant_backtest_core.backtest.minute_session import MinuteSession
from quant_backtest_core.backtest.quantity_locks import QuantityLock


def at(value):
    return pd.Timestamp(value, tz="Asia/Shanghai")


def notice(start, end, symbols=("A",), available=None):
    return QuantityLock(
        available_ns=int(at(available or start).value),
        start_ns=int(at(start).value),
        end_ns=int(at(end).value),
        symbols=symbols,
        source_binding="synthetic-notice-v1",
    )


class RecordingPolicy(Policy):
    def __call__(self, state, proposed):
        self.rows.append({"holdings": dict(state.holdings), "locked": list(state.locked_symbols)})
        return proposed


def two_assets():
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30", "2026-01-07 09:30"), (0.3, 0, 0))
    t = pd.concat([t, t.assign(symbol="B", weight=[0.3, 0.5, 0.5])], ignore_index=True)
    frames = []
    for day in (5, 6, 7):
        times = tuple(f"2026-01-{day:02} {m}" for m in ("09:28", "09:32", "09:33"))
        a = bars(times, price=10 if day == 5 else 20, volume=10000).assign(up_limit=100)
        frames.extend([a, bars(times, volume=10000).assign(symbol="B")])
    return t, pd.concat(frames, ignore_index=True)


def test_locked_shares_survive_repricing_while_other_symbols_trade_and_release():
    t, b = two_assets()
    session = MinuteSession(
        t,
        b,
        MinuteExecutionConfig(10000, 1, 0, 0),
        policy=RecordingPolicy(),
        quantity_locks=(notice("2026-01-06 09:00", "2026-01-06 15:00"),),
    )
    result = session.run()
    holdings = result.holdings.set_index(["date", "symbol"]).quantity
    assert holdings.loc[(at("2026-01-06").date(), "A")] == 300
    assert session.policy.rows[1]["locked"] == ["A"]
    day2 = result.fills.loc[result.fills.time.dt.day == 6]
    assert day2.symbol.tolist() == ["B"]
    assert day2.quantity.sum() == 300
    assert result.fills.loc[
        (result.fills.symbol == "A") & (result.fills.side == "sell"), "time"
    ].dt.day.tolist() == [7]


def partial(delay=0):
    t = targets(("2026-01-05 09:30", "2026-01-05 09:34"), (0.8, 0.8))
    b = bars(tuple(f"2026-01-05 {m}" for m in ("09:29", "09:32", "09:33", "09:35", "09:36")))
    return MinuteSession(
        t,
        b,
        MinuteExecutionConfig(10000, 0.1, 0, 0),
        policy=RecordingPolicy(),
        report_delay_seconds=delay,
        quantity_locks=(
            notice("2026-01-05 09:31", "2026-01-05 09:35", available="2026-01-05 09:32:30"),
        ),
    )


def test_receipt_cancels_only_remaining_partial_order_and_inclusive_end_blocks_entry():
    result = partial().run()
    assert result.fills.quantity.tolist() == [100]
    assert result.orders.iloc[0].filled_quantity == 100
    assert result.orders.iloc[0].status == "cancelled"
    assert result.orders.iloc[0].reason == "quantity_lock"
    assert len(result.orders) == 1  # end does not resurrect the cancelled parent


@pytest.mark.parametrize("delay", [0, 600])
def test_every_boundary_recovery_preserves_locks_cancellation_and_deliveries(delay):
    full = partial(delay)
    expected = full.run()
    for boundary in range(len(full.simulation.times) + 1):
        session = partial(delay)
        for _ in range(boundary):
            session.step()
        wire = json.loads(json.dumps(session.checkpoint(), allow_nan=False))
        policy = RecordingPolicy()
        policy.rows = wire["policy"]
        restored = MinuteSession.restore(
            session.targets, session.bars, session.config, wire, policy=policy
        )
        result = restored.run()
        for table in ("daily", "orders", "fills", "holdings"):
            pd.testing.assert_frame_equal(
                getattr(result, table), getattr(expected, table), check_exact=True
            )
        assert restored.trace == full.trace
        assert restored.policy.rows == full.policy.rows


def test_overlap_and_zero_holdings_are_blocked_until_last_notice_ends():
    t = targets(("2026-01-05 09:30", "2026-01-05 09:34"), (1, 1))
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:36"))
    first = notice("2026-01-05 09:28", "2026-01-05 09:31")
    second = notice("2026-01-05 09:30", "2026-01-05 09:35")
    result = MinuteSession(
        t,
        b,
        MinuteExecutionConfig(10000, 1, 0, 0),
        policy=RecordingPolicy(),
        quantity_locks=(first, second),
    ).run()
    assert result.fills.empty
    assert result.orders.empty


@pytest.mark.parametrize(
    "changes",
    [
        {"available_ns": True},
        {"end_ns": 0},
        {"symbols": ()},
        {"symbols": ("A", "A")},
        {"symbols": ("",)},
        {"source_binding": ""},
    ],
)
def test_invalid_notices_are_rejected(changes):
    with pytest.raises(ValueError):
        replace(notice("2026-01-05 09:30", "2026-01-05 15:00"), **changes)


def test_bar_overlapping_lock_end_cannot_fill_after_release():
    t = targets(("2026-01-05 09:34",), (1,))
    b = bars(("2026-01-05 09:29", "2026-01-05 09:35", "2026-01-05 09:36"))
    lock = notice("2026-01-05 09:30", "2026-01-05 09:34:45")
    t["decision_time"] = at("2026-01-05 09:33")
    # Entry is blocked, so this parent is never created, even after release.
    result = MinuteSession(
        t,
        b,
        MinuteExecutionConfig(10000, 1, 0, 0),
        policy=RecordingPolicy(),
        quantity_locks=(lock,),
    ).run()
    assert result.fills.empty
    # A new entry after release is eligible only on a completely unlocked bar.
    t["entry_time"] = at("2026-01-05 09:34:50")
    t["decision_time"] = at("2026-01-05 09:34:46")
    session = MinuteSession(
        t,
        b,
        MinuteExecutionConfig(10000, 1, 0, 0, latency_minutes=0),
        policy=RecordingPolicy(),
        quantity_locks=(lock,),
    )
    result = session.run()
    assert result.fills.time.tolist() == [at("2026-01-05 09:36")]


def test_policy_sees_received_future_notice_without_future_receipt_leak():
    class Reader(Policy):
        def __call__(self, state, proposed):
            self.rows.append([lock.source_binding for lock in state.quantity_locks])
            return proposed

    first = notice("2026-01-05 09:31", "2026-01-05 09:35", available="2026-01-05 09:28")
    future = replace(first, available_ns=int(at("2026-01-05 09:32").value), source_binding="later")
    policy = Reader()
    MinuteSession(
        targets(),
        bars(),
        MinuteExecutionConfig(10000, 1, 0, 0),
        policy=policy,
        quantity_locks=(first, future),
    ).run()
    assert policy.rows == [["synthetic-notice-v1"]]


def test_empty_session_without_notices_retains_empty_owner_result():
    session = MinuteSession(
        targets().iloc[:0], bars().iloc[:0], MinuteExecutionConfig(10000, 1, 0, 0), policy=Policy()
    )
    result = session.run()
    assert result.daily.empty
    assert result.orders.empty
    assert result.fills.empty
