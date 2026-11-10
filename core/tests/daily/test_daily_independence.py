"""Neutral executable boundary: original owner arithmetic, explicit inputs."""

import sys
from dataclasses import replace

import pandas as pd
import pytest
from quant_backtest_engine.product import ClockSet

from quant_backtest_core.daily.contracts import (
    DailyInputLayout,
    DailyReplayRequest,
    ExecutionCalendar,
    utc_ns,
)
from quant_backtest_core.daily.execution_sim import ExecutionSimConfig
from quant_backtest_core.daily.runner import run_daily


def request(mode="adjusted"):
    days = ("2020-01-03", "2020-01-06", "2020-01-07")

    def ns(x):
        return utc_ns(pd.Timestamp(x, tz="Asia/Shanghai"))

    return DailyReplayRequest(
        pd.DataFrame(
            {
                "rebalance_date": ["2020-01-02", "2020-01-06"],
                "entry_date": ["2020-01-03", "2020-01-07"],
                "symbol": ["A", "B"],
                "weight": [1.0, 1.0],
            }
        ),
        pd.DataFrame(
            [
                {
                    "trade_date": d,
                    "symbol": s,
                    "close": 10.0,
                    "amount": 1000000.0,
                    "sell": not (s == "A" and d == "2020-01-07"),
                }
                for d in days
                for s in ("A", "B")
            ]
        ),
        ExecutionCalendar.from_dates("Asia/Shanghai", days),
        {
            d: ClockSet(
                None,
                ns(d + " 18:00"),
                ns(d + " 18:01"),
                ns(e + " 09:30"),
                None,
                None,
                ns("2020-01-07 16:00"),
            )
            for d, e in (("2020-01-02", "2020-01-03"), ("2020-01-06", "2020-01-07"))
        },
        ExecutionSimConfig(
            enabled=True, portfolio_value=1000.0, participation_rate=1.0, liquidity_cols=("amount",)
        ),
        mode,
        "raw",
        (),
        layout=DailyInputLayout(
            "close",
            "close",
            None,
            None,
            "sell",
            "CNY",
            "raw_share",
            "CNY/raw_share",
            {"amount": "CNY"},
        ),
        decision_timing={},
    )


def test_unfilled_sales_cannot_fund_buys_and_inputs_are_immutable():
    r = request()
    positions, pricing = r.positions.copy(deep=True), r.pricing.copy(deep=True)
    result = run_daily(r)
    assert result.fills.symbol.tolist() == ["A"]
    assert result.daily.cash.tolist() == [0.0, 0.0, 0.0]
    assert result.daily.portfolio_value.tolist() == [1000.0, 1000.0, 1000.0]
    pd.testing.assert_frame_equal(r.positions, positions)
    pd.testing.assert_frame_equal(r.pricing, pricing)


def test_repeated_runs_have_independent_accounts():
    a, b = run_daily(request()), run_daily(request())
    for name in ("daily", "orders", "fills"):
        pd.testing.assert_frame_equal(getattr(a, name), getattr(b, name))
        assert getattr(a, name) is not getattr(b, name)


@pytest.mark.parametrize(
    "change", ["missing_session", "missing_entry", "overweight", "duplicate", "future_valuation"]
)
def test_invalid_admission_does_not_silently_drop_targets(change):
    r = request()
    if change == "missing_session":
        r = replace(
            r, calendar=ExecutionCalendar.from_dates("Asia/Shanghai", ("2020-01-03", "2020-01-07"))
        )
    elif change == "missing_entry":
        r.positions.loc[0, "entry_date"] = "2020-01-04"
    elif change == "overweight":
        r.positions.loc[0, "weight"] = 1.2
    elif change == "duplicate":
        r = replace(r, positions=pd.concat([r.positions, r.positions.iloc[:1]], ignore_index=True))
    else:
        clocks = {
            d: replace(c, valuation_ns=utc_ns(pd.Timestamp("2020-01-06 16:00", tz="Asia/Shanghai")))
            for d, c in r.decision_clocks.items()
        }
        r = replace(r, decision_clocks=clocks)
    with pytest.raises(ValueError):
        run_daily(r)


def test_execution_closure_has_no_research_or_provider_dependency():
    run_daily(request())
    assert not any(
        n.split(".")[0]
        in {
            "quant_platform",
            "portfolio_backtester",
            "quant_backtest_runtime",
            "research_contracts",
            "rqdatac",
            "torch",
            "qlib",
        }
        for n in sys.modules
    )
