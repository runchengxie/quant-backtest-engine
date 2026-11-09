# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_minute_execution_feedback.py
"""Account feedback must follow the strategy clock, not the entry clock."""

import pandas as pd
import pytest
from test_minute_execution import bars, targets

from quant_backtest_core._minute.minute_execution import (
    MinuteExecutionConfig,
    simulate_minute_execution,
)


def test_partial_fill_and_pending_are_visible_without_duplicate_submission():
    seen = []

    def policy(state, proposed):
        seen.append(state)
        if len(seen) == 2:
            return None  # preserve outstanding quantity rather than resubmit it
        return proposed

    t = targets(("2026-01-05 09:30", "2026-01-05 09:34"), (1, 1))
    result = simulate_minute_execution(
        t, bars(), MinuteExecutionConfig(10000, 0.1, 0, 0), decision_policy=policy
    )
    assert seen[1].holdings == {"A": 100}
    assert seen[1].cash == 9000
    assert seen[1].pending_orders[0]["remaining_quantity"] == 900
    assert len(result.orders) == 1
    assert result.fills.quantity.sum() == 200


def test_decision_uses_strictly_prior_marks_and_snapshot_is_immutable():
    seen = []

    def policy(state, proposed):
        seen.append(state)
        with pytest.raises(TypeError):
            state.holdings["A"] = 100000
        return proposed

    t = targets(("2026-01-05 09:34",), (1,))
    t["decision_time"] = pd.Timestamp("2026-01-05 09:30", tz="Asia/Shanghai")
    b = bars()
    simulate_minute_execution(t, b, MinuteExecutionConfig(10000, 1, 0, 0), decision_policy=policy)
    assert seen[0].marks["A"] == 10
    assert seen[0].time == t.decision_time.iloc[0]
    b.loc[b.time > seen[0].time, ["open", "high", "low", "close"]] = 10.5
    b.loc[b.time > seen[0].time, "amount"] = 10500
    simulate_minute_execution(t, b, MinuteExecutionConfig(10000, 1, 0, 0), decision_policy=policy)
    assert seen[0] == seen[1]


def test_feedback_can_hold_actual_inventory_instead_of_unfilled_target():
    def policy(state, proposed):
        return proposed if not state.holdings else {"A": state.holdings["A"] * 10 / state.nav}

    result = simulate_minute_execution(
        targets(("2026-01-05 09:30", "2026-01-05 09:34"), (1, 1)),
        bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:36")),
        MinuteExecutionConfig(10000, 0.1, 0, 0),
        decision_policy=policy,
    )
    assert result.fills.quantity.sum() == 100
    assert result.orders.iloc[0].reason == "superseded"


@pytest.mark.parametrize("weight", [-0.1, float("nan"), 1.1])
def test_invalid_policy_weights_fail(weight):
    with pytest.raises(ValueError, match="weight"):
        simulate_minute_execution(
            targets(),
            bars(),
            MinuteExecutionConfig(10000, 1, 0, 0),
            decision_policy=lambda state, proposed: {"A": weight},
        )


def test_impact_changes_later_fills_and_is_not_a_cash_fee():
    from quant_backtest_core.backtest.impact import LinearImpact

    result = simulate_minute_execution(
        targets(),
        bars(),
        MinuteExecutionConfig(10000, 0.1, 0, 0),
        impact_model=LinearImpact(permanent=0.001),
    )
    assert result.fills.price.tolist() == pytest.approx([10.05, 10.15])
    assert result.daily.iloc[-1].transaction_cost == 0
    assert result.daily.iloc[-1].cash == pytest.approx(7980)
    assert result.summary["impact_checkpoint"]["states"]["A"]["permanent"] == pytest.approx(0.2)


def test_impact_affordability_uses_affected_price():
    from quant_backtest_core.backtest.impact import LinearImpact

    result = simulate_minute_execution(
        targets(),
        bars(),
        MinuteExecutionConfig(1000, 1, 0, 0),
        impact_model=LinearImpact(permanent=0.001),
    )
    assert result.fills.empty  # even a single lot costs more than initial cash


def test_next_session_decision_sees_paid_dividend_and_ex_reference():
    from quant_backtest_core._minute.corporate_actions import CorporateAction

    seen = []

    def policy(state, proposed):
        seen.append(state)
        return proposed

    action = CorporateAction(
        "div",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-06",
    )
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30"), (0.1, 0.1))
    result = simulate_minute_execution(
        t,
        bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32")),
        MinuteExecutionConfig(10000, 1, 0, 0),
        corporate_actions=[action],
        decision_policy=policy,
    )
    assert seen[1].cash == 9100
    assert seen[1].marks["A"] == 9
    assert seen[1].cash_receivable == 0
    assert len(result.daily) == 2
