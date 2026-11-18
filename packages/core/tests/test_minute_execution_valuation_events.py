# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_minute_execution_valuation_events.py
import pandas as pd
import pytest
from test_minute_execution import bars, targets

from quant_backtest_core._minute.corporate_actions import CorporateAction
from quant_backtest_core._minute.minute_execution import (
    MinuteExecutionConfig,
    ValuationEvent,
    simulate_minute_execution,
)


def ts(value):
    return pd.Timestamp(value, tz="Asia/Shanghai")


def event(value=0, effective="2026-01-06 09:30", event_id="impair", **extra):
    return ValuationEvent(
        event_id=event_id,
        symbol="A",
        effective_time=ts(effective),
        available_time=ts(effective) - pd.Timedelta(days=1),
        value_per_share=value,
        basis="declared_impairment",
        source="synthetic_test_policy",
        **extra,
    )


def input_bars():
    b = bars(
        ("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32", "2026-01-07 09:32"),
        volume=10000,
    )
    b.loc[b.index[2:], "symbol"] = "B"
    return b


@pytest.mark.parametrize("value", [0, 3])
def test_event_preserves_cash_shares_and_explicit_value_persists(value):
    b = input_bars()
    base = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 1, 0, 0))
    r = simulate_minute_execution(
        targets(), b, MinuteExecutionConfig(10000, 1, 0, 0), valuation_events=[event(value)]
    )
    pd.testing.assert_frame_equal(r.fills, base.fills)
    pd.testing.assert_frame_equal(r.holdings, base.holdings)
    assert r.daily.cash.tolist() == base.daily.cash.tolist()
    assert r.daily.nav.tolist() == [10000, 1000 * value, 1000 * value]
    assert r.daily.stale_mark_symbols.iloc[-1] == ()
    assert r.valuation_ledger.quantity.tolist() == [1000]
    assert r.valuation_ledger.previous_value_per_share.tolist() == [10]
    assert r.valuation_ledger.delta_value.tolist() == [1000 * (value - 10)]
    assert r.valuation_ledger.cash_before.equals(r.valuation_ledger.cash_after)
    mark = r.daily.valuation_marks.iloc[-1][0]
    assert mark["effective_time"] == ts("2026-01-06 09:30")
    assert mark["available_time"] == ts("2026-01-05 09:30")
    assert mark["event_age_seconds"] > 86400
    assert mark["source"] == "synthetic_test_policy"


def test_event_cancels_pending_and_blocks_positive_weight_without_zero_division():
    b = bars(volume=1000)
    b.loc[b.index[-1], "tradable"] = False
    t = targets(("2026-01-05 09:30", "2026-01-05 09:33"), (1, 1))
    r = simulate_minute_execution(
        t,
        b,
        MinuteExecutionConfig(10000, 0.1, 0, 0),
        valuation_events=[event(effective="2026-01-05 09:33")],
    )
    assert r.fills.quantity.tolist() == [100]
    assert r.orders.status.tolist() == ["cancelled", "expired"]
    assert r.orders.reason.tolist() == ["nontrading_valuation", "nontrading_valuation"]
    assert r.daily.nav.tolist() == [9000]


def test_event_own_instant_precedes_sizing_and_only_new_events_change_mark():
    b = input_bars()
    late_quote = bars(("2026-01-06 09:31",))
    late_quote["tradable"] = False
    b = pd.concat([b, late_quote])
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30"), (1, 1))
    r = simulate_minute_execution(
        t,
        b,
        MinuteExecutionConfig(10000, 1, 0, 0),
        valuation_events=[event(), event(2, "2026-01-07 09:00", "update")],
    )
    assert r.orders.iloc[-1].reason == "nontrading_valuation"
    assert r.daily.nav.tolist() == [10000, 0, 2000]
    assert r.valuation_ledger.time.tolist() == [ts("2026-01-06 09:30"), ts("2026-01-07 09:00")]


def test_unaffected_missing_marks_remain_missing():
    b = input_bars()
    b.loc[b.index[0:2], "symbol"] = "C"
    t = targets()
    t["symbol"] = "C"
    r = simulate_minute_execution(
        t, b, MinuteExecutionConfig(10000, 1, 0, 0), valuation_events=[event()]
    )
    assert pd.isna(r.daily.nav.iloc[-1])
    assert r.daily.stale_mark_symbols.iloc[-1] == ("C",)


def test_event_marks_stock_rights_without_destroying_cash_entitlement():
    action = CorporateAction(
        "bonus",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-07",
        stock_per_share=0.1,
        stock_tradable_date="2026-01-09",
    )
    r = simulate_minute_execution(
        targets(),
        input_bars(),
        MinuteExecutionConfig(10000, 1, 0, 0),
        corporate_actions=[action],
        valuation_events=[event()],
    )
    assert r.daily.nav.tolist() == [10000, 1000, 1000]
    assert r.daily.cash.tolist() == [0, 0, 1000]
    assert r.daily.stock_receivable_value.tolist() == [0, 0, 0]
    assert r.valuation_ledger.stock_receivable_quantity.tolist() == [100]


def test_future_events_do_not_extend_window_or_change_earlier_fills():
    b = bars(volume=10000)
    base = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 1, 0, 0))
    r = simulate_minute_execution(
        targets(), b, MinuteExecutionConfig(10000, 1, 0, 0), valuation_events=[event()]
    )
    pd.testing.assert_frame_equal(r.fills, base.fills)
    assert r.daily.date.tolist() == base.daily.date.tolist()
    assert r.valuation_ledger.empty
    assert r.summary["ignored_future_event_ids"] == ["impair"]


def test_pre_window_event_blocks_existing_tradable_bars():
    with pytest.raises(ValueError, match=r"tradable.*valuation"):
        simulate_minute_execution(
            targets(),
            bars(),
            MinuteExecutionConfig(10000, 1, 0, 0),
            valuation_events=[event(effective="2026-01-04 09:30")],
        )


@pytest.mark.parametrize(
    "invalid", ["id", "basis", "source", "symbol", "naive", "nan", "negative", "future_available"]
)
def test_invalid_event_contract_fails(invalid):
    data = {
        "event_id": "e",
        "symbol": "A",
        "effective_time": ts("2026-01-06 09:30"),
        "available_time": ts("2026-01-05 09:30"),
        "value_per_share": 0,
        "basis": "policy",
        "source": "test",
    }
    if invalid in {"id", "basis", "source", "symbol"}:
        data["event_id" if invalid == "id" else invalid] = ""
    elif invalid == "naive":
        data["effective_time"] = pd.Timestamp("2026-01-06 09:30")
    elif invalid == "future_available":
        data["available_time"] = ts("2026-01-07 09:30")
    else:
        data["value_per_share"] = float("nan") if invalid == "nan" else -1
    with pytest.raises(ValueError):
        ValuationEvent(**data)


def test_duplicate_id_and_symbol_effective_time_fail():
    for events in (
        [event(), event(2, "2026-01-07 09:30")],
        [event(), event(2, event_id="different")],
    ):
        with pytest.raises(ValueError, match="duplicate"):
            simulate_minute_execution(
                targets(),
                input_bars(),
                MinuteExecutionConfig(10000, 1, 0, 0),
                valuation_events=events,
            )


def test_conflicting_tradable_bar_at_event_time_fails():
    with pytest.raises(ValueError, match=r"tradable.*valuation"):
        simulate_minute_execution(
            targets(),
            bars(),
            MinuteExecutionConfig(10000, 1, 0, 0),
            valuation_events=[event(effective="2026-01-05 09:32")],
        )


def test_pre_window_nontrade_state_preserves_original_source_age():
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32"))
    b["tradable"] = False
    r = simulate_minute_execution(
        targets(),
        b,
        MinuteExecutionConfig(10000, 1, 0, 0),
        valuation_events=[event(0, "2026-01-04 09:30")],
    )
    assert r.fills.empty
    assert r.valuation_ledger.time.tolist() == [ts("2026-01-05 09:29")]
    assert r.valuation_ledger.effective_time.tolist() == [ts("2026-01-04 09:30")]
    assert r.daily.valuation_marks.iloc[0][0]["event_age_seconds"] > 86400
    assert r.valuation_ledger.delta_value.tolist() == [0]


def test_impairment_before_ex_date_keeps_dividend_entitlement():
    action = CorporateAction(
        "cash",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-07",
    )
    r = simulate_minute_execution(
        targets(),
        input_bars(),
        MinuteExecutionConfig(10000, 1, 0, 0),
        corporate_actions=[action],
        valuation_events=[event(0, "2026-01-05 10:00")],
    )
    assert r.daily.nav.tolist() == [0, 1000, 1000]
    assert r.daily.cash.tolist() == [0, 0, 1000]
    assert r.holdings.quantity.tolist() == [1000, 1000, 1000]


def test_utc_event_uses_declared_market_calendar_without_prior_day_impairment():
    foreign = ValuationEvent(
        "utc",
        "A",
        pd.Timestamp("2026-01-05 17:00", tz="UTC"),
        pd.Timestamp("2026-01-05 16:00", tz="UTC"),
        0,
        "impairment",
        "public_test",
    )
    r = simulate_minute_execution(
        targets(), input_bars(), MinuteExecutionConfig(10000, 1, 0, 0), valuation_events=[foreign]
    )
    assert r.daily.nav.tolist() == [10000, 0, 0]
    assert r.valuation_ledger.time.tolist() == [ts("2026-01-06 01:00")]
    assert str(r.valuation_ledger.effective_time.iloc[0].tz) == "Asia/Shanghai"
    assert r.valuation_ledger.effective_time.iloc[0] == foreign.effective_time


def test_opt_in_rejects_mixed_market_timezones():
    t = targets()
    t["decision_time"] = t.decision_time.dt.tz_convert("UTC")
    with pytest.raises(ValueError, match="market timezone"):
        simulate_minute_execution(
            t, input_bars(), MinuteExecutionConfig(10000, 1, 0, 0), valuation_events=[event()]
        )
