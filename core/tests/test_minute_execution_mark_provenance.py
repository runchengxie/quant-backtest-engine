# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_minute_execution_mark_provenance.py
"""Temporary nontrading marks retain observation provenance and permit reopening."""

import pandas as pd
import pytest

from quant_backtest_core._minute.minute_execution import (
    MinuteExecutionConfig,
    simulate_minute_execution,
)


def inputs():
    rows = []
    for day, price in (("2026-06-30", 10.0), ("2026-07-01", 10.0), ("2026-07-03", 11.0)):
        for clock in ("09:30", "09:31", "09:32", "09:33", "09:34", "09:35", "15:00"):
            stamp = pd.Timestamp(f"{day} {clock}", tz="Asia/Shanghai")
            rows.append(
                {
                    "symbol": "S0",
                    "time": stamp,
                    "open": price,
                    "high": price,
                    "low": price,
                    "close": price,
                    "volume": 100000.0,
                    "amount": price * 100000,
                    "up_limit": 12.0,
                    "down_limit": 8.0,
                    "tradable": True,
                    "mark_source_time": stamp,
                    "mark_basis": "raw",
                }
            )
    source = pd.Timestamp("2026-07-01 15:00", tz="Asia/Shanghai")
    rows.append(
        {
            "symbol": "S0",
            "time": pd.Timestamp("2026-07-02 15:00", tz="Asia/Shanghai"),
            "open": 10.0,
            "high": 10.0,
            "low": 10.0,
            "close": 10.0,
            "volume": 0.0,
            "amount": 0.0,
            "up_limit": 12.0,
            "down_limit": 8.0,
            "tradable": False,
            "mark_source_time": source,
            "mark_basis": "declared_nontrading",
        }
    )
    bars = pd.DataFrame(rows).sort_values("time").reset_index(drop=True)
    targets = pd.DataFrame(
        [
            {
                "symbol": "S0",
                "decision_time": pd.Timestamp("2026-06-30 15:00", tz="Asia/Shanghai"),
                "entry_time": pd.Timestamp("2026-07-01 09:30", tz="Asia/Shanghai"),
                "weight": 0.5,
            },
            {
                "symbol": "S0",
                "decision_time": pd.Timestamp("2026-07-02 15:00", tz="Asia/Shanghai"),
                "entry_time": pd.Timestamp("2026-07-03 09:30", tz="Asia/Shanghai"),
                "weight": 0.0,
            },
        ]
    )
    return targets, bars


def run(targets, bars):
    return simulate_minute_execution(
        targets,
        bars,
        MinuteExecutionConfig(
            initial_cash=100000.0,
            participation_rate=0.05,
            buy_fee_bp=3.0,
            sell_fee_bp=8.0,
            lot_size=100,
            latency_minutes=0,
        ),
    )


def test_halt_mark_keeps_source_time_and_allows_reopening():
    targets, bars = inputs()
    result = run(targets, bars)
    sale = result.orders.loc[result.orders.side.eq("sell")].iloc[0]
    assert sale.reference_basis == "declared_nontrading"
    assert sale.reference_time == pd.Timestamp("2026-07-02 15:00", tz="Asia/Shanghai")
    assert sale.reference_source_time == pd.Timestamp("2026-07-01 15:00", tz="Asia/Shanghai")
    assert result.fills.side.eq("sell").any()
    assert not result.daily.stale_mark_symbols.map(bool).any()
    assert result.daily.iloc[-1].positions_value == 0


@pytest.mark.parametrize(
    "mutation", ["future", "tradable", "volume", "missing_column", "raw_stale"]
)
def test_invalid_mark_declarations_fail_closed(mutation):
    targets, bars = inputs()
    held = bars.mark_basis.eq("declared_nontrading")
    if mutation == "future":
        bars.loc[held, "mark_source_time"] = pd.Timestamp("2026-07-03 15:00", tz="Asia/Shanghai")
    elif mutation == "tradable":
        bars.loc[held, "tradable"] = True
    elif mutation == "volume":
        bars.loc[held, "volume"] = 100.0
    elif mutation == "missing_column":
        bars = bars.drop(columns="mark_source_time")
    else:
        bars.loc[held, "mark_basis"] = "raw"
    with pytest.raises(ValueError, match="mark"):
        run(targets, bars)


def test_raw_metadata_preserves_legacy_financial_results():
    targets, bars = inputs()
    bars = bars.loc[bars.mark_basis.eq("raw")].copy()
    enriched = run(targets, bars)
    legacy = run(targets, bars.drop(columns=["mark_source_time", "mark_basis"]))
    for name in ("daily", "orders", "fills", "holdings"):
        pd.testing.assert_frame_equal(getattr(enriched, name), getattr(legacy, name))
