"""Neutral executable boundary: original owner arithmetic, explicit inputs."""

import sys
from dataclasses import replace
from unittest.mock import patch

import pandas as pd
import pytest
from quant_backtest_engine.product import ClockSet

from quant_backtest_core.daily.contracts import (
    DailyInputLayout,
    DailyReplayRequest,
    ExecutionCalendar,
    utc_ns,
)
from quant_backtest_core.daily.execution_sim import ExecutionSimConfig, simulate_capacity_execution
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


@pytest.mark.parametrize(
    "control",
    [
        "enforce_price_limits",
        "enforce_listing_status",
        "enforce_t1",
        "round_lot",
        "sell_round_lot",
        "unfilled_buy_action",
        "unfilled_sell_action",
    ],
)
def test_capacity_rejects_unsupported_rules_before_owner_dispatch(control):
    r = request("capacity")
    config = {
        control: (
            "cancel"
            if control.startswith("unfilled_")
            else 100
            if control in ("round_lot", "sell_round_lot")
            else True
        )
    }
    if control == "enforce_price_limits":
        config.update(limit_up_col="limit_up", limit_down_col="limit_down")
        r.pricing["limit_up"], r.pricing["limit_down"] = True, False
    elif control == "enforce_listing_status":
        config["listing_status_col"] = "listing_status"
        r.pricing["listing_status"] = "delisted"
    r = replace(r, config=replace(r.config, **config))
    before = r.pricing.copy(deep=True)
    with patch(
        "quant_backtest_core.daily.runner.simulate_capacity_execution",
        wraps=simulate_capacity_execution,
    ) as owner:
        with pytest.raises(ValueError, match=f"capacity.*{control}"):
            run_daily(r)
        owner.assert_not_called()
    pd.testing.assert_frame_equal(r.pricing, before)


@pytest.mark.parametrize("selector", ["tradable_col", "buy_tradable_col"])
def test_capacity_supported_liquidity_and_tradability_controls_execute(selector):
    r = request("capacity")
    r.pricing["amount"] = 100.0
    r.pricing["allowed"] = r.pricing.trade_date.ne("2020-01-03")
    r = replace(
        r,
        positions=r.positions.iloc[:1].copy(),
        decision_clocks={"2020-01-02": r.decision_clocks["2020-01-02"]},
        config=replace(r.config, participation_rate=0.1),
        layout=replace(r.layout, sell_tradable_col=None, **{selector: "allowed"}),
    )
    result = run_daily(r)
    assert result.summary["status"] == "ok"
    assert result.fills.trade_date.tolist() == ["20200106", "20200107"]
    assert result.fills.filled_notional.tolist() == [10.0, 10.0]
    assert not hasattr(result, "daily")
