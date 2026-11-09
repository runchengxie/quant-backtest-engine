"""Synthetic CNY minute account; execute with installed quant-backtest-core[minute]."""

import json

import pandas as pd
from quant_backtest_core.backtest.impact import LinearImpact
from quant_backtest_core.backtest.minute import (
    CapitalFlow,
    CorporateAction,
    MinuteExecutionConfig,
    ValuationEvent,
)
from quant_backtest_core.backtest.minute_session import MinuteSession
from quant_backtest_core.backtest.quantity_locks import QuantityLock


class Policy:
    """Wait for pending financial reports; preserve policy state for recovery."""

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


def make_session(*, delay=600, locked=True, valuation=False):
    def clock(value):
        return pd.Timestamp(value, tz="Asia/Shanghai")

    targets = pd.DataFrame(
        [
            {
                "decision_time": clock(f"2026-01-{day:02} 09:29"),
                "entry_time": clock(f"2026-01-{day:02} 09:30"),
                "symbol": "A",
                "weight": weight,
            }
            for day, weight in ((5, 1.0), (6, 0.0), (7, 0.0))
        ]
    )
    bars = pd.DataFrame(
        [
            {
                "time": clock(f"2026-01-{day:02} {time}"),
                "interval_start": clock(f"2026-01-{day:02} {time}")
                - pd.Timedelta(seconds=30),
                "symbol": "A",
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": 1000,
                "amount": price * 1000,
                "up_limit": 11.0,
                "down_limit": 1.0,
                "tradable": not (valuation and day >= 6),
            }
            for day, price in ((5, 10.0), (6, 4.5), (7, 4.5))
            for time in ("09:29", "09:32", "09:33")
        ]
    )
    actions = (
        CorporateAction(
            "distribution",
            "A",
            "2026-01-04",
            "2026-01-05",
            "2026-01-06",
            cash_per_share=1,
            cash_pay_date="2026-01-07",
            stock_per_share=1,
            stock_tradable_date="2026-01-07",
        ),
    )
    locks = (
        (
            QuantityLock(
                clock("2026-01-06 00:00").value,
                clock("2026-01-06 00:00").value,
                clock("2026-01-07 09:30").value,
                ("A",),
                "synthetic-lock",
            ),
        )
        if locked
        else ()
    )
    events = (
        (
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
        if valuation
        else ()
    )
    flows = (
        CapitalFlow(
            "deposit",
            "2026-01-05 09:29+08:00",
            "2026-01-05 09:33+08:00",
            100,
            "synthetic",
        ),
        CapitalFlow(
            "withdrawal",
            "2026-01-07 09:29+08:00",
            "2026-01-07 09:30+08:00",
            -50,
            "synthetic",
        ),
    )
    return MinuteSession(
        targets,
        bars,
        MinuteExecutionConfig(
            10000, 0.1, 3, 8, commission_minimum_cny=5, sell_tax_bp=5
        ),
        policy=Policy(),
        report_delay_seconds=delay,
        impact=LinearImpact(permanent=0.0001),
        corporate_actions=actions,
        valuation_events=events,
        capital_flows=flows,
        quantity_locks=locks,
    )


def main():
    expected = make_session().run()
    session = make_session()
    for _ in range(4):
        session.step()
    checkpoint = json.loads(json.dumps(session.checkpoint(), allow_nan=False))
    policy = Policy()
    policy.rows = checkpoint["policy"]
    restored = MinuteSession.restore(
        session.targets,
        session.bars,
        session.config,
        checkpoint,
        policy=policy,
        **session.tapes,
    )
    actual = restored.run()
    for table in (
        "daily",
        "orders",
        "fills",
        "holdings",
        "valuation_ledger",
        "capital_flow_ledger",
    ):
        pd.testing.assert_frame_equal(getattr(actual, table), getattr(expected, table))
    assert not actual.fills.empty
    assert not actual.holdings.empty
    assert actual.summary == expected.summary
    assert actual.capital_flow_ledger.amount.sum() == 50
    print(
        json.dumps(
            {
                "currency": "CNY",
                "schema": checkpoint["schema"],
                "fills": len(actual.fills),
                "external_capital": 50,
                "recovery": "complete ledgers equal",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
