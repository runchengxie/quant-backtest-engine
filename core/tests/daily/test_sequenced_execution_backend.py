"""Original sequenced financial cases adapted to the neutral request."""

from dataclasses import replace

import pandas as pd
import pytest
from quant_backtest_engine.product import ClockSet

from quant_backtest_core.daily.contracts import (
    DailyDecisionTiming,
    DailyInputLayout,
    DailyReplayRequest,
    ExecutionCalendar,
    utc_ns,
)
from quant_backtest_core.daily.execution_sim import ExecutionSimConfig
from quant_backtest_core.daily.runner import run_daily


def neutral_request(
    *, positions, pricing, decision_clocks, config, tradable_col, limit_up_col, limit_down_col
):
    clocks, timing = {}, {}

    def ns(v):
        return utc_ns(pd.Timestamp(v)) if v is not None else None

    for day, c in decision_clocks.items():
        clocks[day] = ClockSet(
            None,
            ns(c["information_cutoff_at"]),
            ns(c["decision_at"]),
            ns(c["earliest_order_at"]),
            None,
            None,
            ns(c["valuation_at"]),
        )
        timing[day] = DailyDecisionTiming(
            ns(c["signal_at"]),
            ns(c["earliest_order_at"]),
            ns(c["execution_window_start_at"]),
            ns(c["execution_window_end_at"]),
            c["timing_policy_id"],
            c["trading_calendar_ref"],
        )
    return DailyReplayRequest(
        positions,
        pricing,
        ExecutionCalendar.from_dates("Asia/Shanghai", tuple(pricing.trade_date)),
        clocks,
        config,
        "sequenced",
        "raw",
        (),
        layout=DailyInputLayout(
            "close",
            "close",
            tradable_col,
            None,
            None,
            "CNY",
            "raw_share",
            "CNY/raw_share",
            {"amount": "CNY"},
        ),
        decision_timing=timing,
    )


def _clock(day: str, entry: str) -> dict[str, str]:
    date = pd.Timestamp(day).strftime("%Y-%m-%d")
    next_date = pd.Timestamp(entry).strftime("%Y-%m-%d")
    return {
        "schema_version": "research.clock.v1",
        "timezone": "Asia/Shanghai",
        "information_cutoff_at": f"{date}T18:00:00+08:00",
        "signal_at": f"{date}T18:01:00+08:00",
        "decision_at": f"{date}T18:02:00+08:00",
        "earliest_order_at": f"{next_date}T09:30:00+08:00",
        "execution_window_start_at": f"{next_date}T09:30:00+08:00",
        "execution_window_end_at": f"{next_date}T15:00:00+08:00",
        "valuation_at": "2020-01-08T16:00:00+08:00",
        "timing_policy_id": "test.after_close_next_session",
        "trading_calendar_ref": "synthetic-calendar",
    }


def _request():
    positions = pd.DataFrame(
        {
            "rebalance_date": ["2020-01-02", "2020-01-06"],
            "entry_date": ["2020-01-03", "2020-01-07"],
            "symbol": ["A", "B"],
            "weight": [1.0, 1.0],
        }
    )
    pricing = pd.DataFrame(
        [
            {
                "trade_date": day,
                "symbol": symbol,
                "close": 10.0,
                "amount": 1_000_000.0,
                "tradable": True,
                "limit_up": symbol == "B" and day == "2020-01-07",
                "limit_down": False,
            }
            for day in ("2020-01-03", "2020-01-06", "2020-01-07", "2020-01-08")
            for symbol in ("A", "B")
        ]
    )
    return neutral_request(
        positions=positions,
        pricing=pricing,
        decision_clocks={
            "2020-01-02": _clock("2020-01-02", "2020-01-03"),
            "2020-01-06": _clock("2020-01-06", "2020-01-07"),
        },
        config=ExecutionSimConfig(
            enabled=True,
            portfolio_value=10_000.0,
            participation_rate=1.0,
            liquidity_cols=("amount",),
            buy_max_days=2,
            sell_max_days=2,
            enforce_price_limits=True,
            limit_up_col="limit_up",
            limit_down_col="limit_down",
        ),
        tradable_col="tradable",
        limit_up_col="limit_up",
        limit_down_col="limit_down",
    )


def test_sequence_uses_one_clock_per_decision_and_shared_market_rules():
    request = _request()
    result = run_daily(request)
    assert len(request.decision_clocks) == 2
    assert result.daily.shape[0] == 4
    assert result.to_unified_ledger() is not None
    b_fills = result.fills.loc[result.fills["symbol"].eq("B")]
    assert "20200107" not in set(b_fills["trade_date"].astype(str))
    assert "20200108" in set(b_fills["trade_date"].astype(str))


def test_sequence_rejects_missing_clock_and_early_entry():
    request = _request()
    with pytest.raises(ValueError, match="decision clocks"):
        replace(request, decision_clocks={"2020-01-02": request.decision_clocks["2020-01-02"]})
    request = _request()
    request.positions.loc[0, "entry_date"] = "2020-01-02"
    with pytest.raises(ValueError):
        run_daily(request)


def test_sequence_rejects_future_pricing_and_overweight_target():
    request = _request()
    request.pricing.loc[0, "trade_date"] = "2020-01-09"
    with pytest.raises(ValueError):
        run_daily(request)
    request = _request()
    request.positions.loc[0, "weight"] = 1.2
    with pytest.raises(ValueError, match="exceed full investment"):
        run_daily(request)
