# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_minute_execution.py
import pandas as pd
import pytest

from quant_backtest_core._minute.minute_execution import (
    MinuteExecutionConfig,
    simulate_minute_execution,
)


def targets(times=("2026-01-05 09:30",), weights=(1.0,)):
    return pd.DataFrame(
        [
            {
                "decision_time": pd.Timestamp(t, tz="Asia/Shanghai") - pd.Timedelta(minutes=1),
                "entry_time": pd.Timestamp(t, tz="Asia/Shanghai"),
                "symbol": "A",
                "weight": w,
            }
            for t, w in zip(times, weights, strict=False)
        ]
    )


def bars(
    times=("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:33"), price=10.0, volume=1000
):
    return pd.DataFrame(
        [
            {
                "time": pd.Timestamp(t, tz="Asia/Shanghai"),
                "interval_start": pd.Timestamp(t, tz="Asia/Shanghai") - pd.Timedelta(seconds=30),
                "symbol": "A",
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "amount": price * volume,
                "up_limit": 11.0,
                "down_limit": 9.0,
                "tradable": True,
            }
            for t in times
        ]
    )


def test_participation_cash_and_strict_latency():
    r = simulate_minute_execution(targets(), bars(), MinuteExecutionConfig(10000, 0.1, 10, 10))
    assert r.fills.quantity.tolist() == [100, 100]
    assert r.fills.time.min() == pd.Timestamp("2026-01-05 09:32", tz="Asia/Shanghai")
    assert r.daily.cash.min() >= 0
    assert r.orders.status.tolist() == ["expired"]


def test_future_bar_does_not_change_past_fill():
    b = bars()
    r = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 0.1, 0, 0))
    b.loc[2, ["open", "high", "low", "close"]] = 10.5
    b.loc[2, "amount"] = 10500
    changed = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 0.1, 0, 0))
    pd.testing.assert_series_equal(r.fills.iloc[0], changed.fills.iloc[0])


def test_fee_affordability_and_t_plus_one():
    r = simulate_minute_execution(
        targets(("2026-01-05 09:30", "2026-01-05 09:33"), (1, 0)),
        bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:35")),
        MinuteExecutionConfig(1000, 1, 10, 0),
    )
    assert r.fills.empty  # one lot plus fees cannot be afforded
    r = simulate_minute_execution(
        targets(("2026-01-05 09:30", "2026-01-05 09:33"), (1, 0)),
        bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:35")),
        MinuteExecutionConfig(2000, 1, 0, 0),
    )
    assert r.fills.side.tolist() == ["buy"]
    assert r.orders.iloc[-1].reason == "t_plus_one"


def test_supersedes_pending_and_limit_direction():
    b = bars()
    b.loc[1, "high"] = 11
    r = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 1, 0, 0))
    assert len(r.fills) == 1
    r = simulate_minute_execution(
        targets(("2026-01-05 09:30", "2026-01-05 09:31"), (1, 0)),
        b,
        MinuteExecutionConfig(10000, 1, 0, 0),
    )
    assert r.orders.iloc[0].status == "cancelled"
    assert r.fills.empty


@pytest.mark.parametrize("bad", ["duplicate", "null", "naive"])
def test_invalid_bars_fail(bad):
    b = bars()
    if bad == "duplicate":
        b = pd.concat([b, b.iloc[[0]]])
    elif bad == "null":
        b.loc[0, "amount"] = float("nan")
    else:
        b["time"] = b.time.dt.tz_localize(None)
    with pytest.raises(ValueError):
        simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 0.1, 0, 0))


def test_corporate_actions_require_supported_coverage():
    with pytest.raises(ValueError, match="corporate"):
        simulate_minute_execution(
            targets(), bars(), MinuteExecutionConfig(10000, 0.1, 0, 0), corporate_actions=[object()]
        )


def test_corporate_rights_record_ex_and_payment():
    from quant_backtest_core._minute.corporate_actions import CorporateAction

    action = CorporateAction(
        "div",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-07",
        stock_per_share=0.1,
        stock_tradable_date="2026-01-07",
    )
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32", "2026-01-07 09:32"))
    r = simulate_minute_execution(
        targets(), b, MinuteExecutionConfig(10000, 1, 0, 0), corporate_actions=[action]
    )
    assert r.daily.cash.tolist() == [0, 0, 1000]
    assert r.daily.cash_receivable.tolist() == [0, 1000, 0]
    assert r.daily.stock_receivable_value.tolist() == [0, 1000, 0]
    assert r.daily.positions_value.tolist() == [10000, 10000, 11000]


def test_fixed_release_slices_and_shared_bar_budget():
    b = bars(
        ("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:46", "2026-01-05 09:47"),
        volume=10000,
    )
    r = simulate_minute_execution(
        targets(), b, MinuteExecutionConfig(10000, 1, 0, 0, release_slices=2)
    )
    assert r.fills.quantity.tolist() == [500, 500]
    assert r.fills.time.iloc[-1] == pd.Timestamp("2026-01-05 09:47", tz="Asia/Shanghai")


def test_next_day_sale_funds_buy_even_when_buy_symbol_sorts_first():
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30"), (1, 1))
    t.loc[0, "symbol"] = "Z"
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:29", "2026-01-06 09:32"))
    z = b.copy()
    z["symbol"] = "Z"
    r = simulate_minute_execution(t, pd.concat([b, z]), MinuteExecutionConfig(10000, 1, 0, 0))
    assert r.fills.side.tolist() == ["buy", "sell", "buy"]
    assert r.fills.symbol.tolist() == ["Z", "Z", "A"]
    assert r.daily.cash.min() >= 0


def test_missing_terminal_bar_makes_valuation_missing():
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32"))
    b.loc[2, "symbol"] = "B"
    r = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 1, 0, 0))
    assert pd.isna(r.daily.nav.iloc[-1])
    assert r.daily.stale_mark_symbols.iloc[-1] == ("A",)


def test_odd_integer_bonus_shares_can_be_fully_liquidated():
    from quant_backtest_core._minute.corporate_actions import CorporateAction

    action = CorporateAction(
        "bonus",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        stock_per_share=0.05,
        stock_tradable_date="2026-01-06",
    )
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32"), volume=10000)
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30"), (1, 0))
    r = simulate_minute_execution(
        t, b, MinuteExecutionConfig(10000, 1, 0, 0), corporate_actions=[action]
    )
    assert r.fills.quantity.tolist() == [1000, 1050]
    assert r.daily.positions_value.iloc[-1] == 0


def test_clipped_vwap_is_disclosed():
    b = bars()
    b.loc[1, "amount"] = 5000
    r = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 0.1, 0, 0))
    assert r.summary["clipped_vwap_bars"] == 1


def test_holdings_ledger_tracks_bonus_release_and_liquidation():
    from quant_backtest_core._minute.corporate_actions import CorporateAction

    action = CorporateAction(
        "bonus",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        stock_per_share=0.05,
        stock_tradable_date="2026-01-06",
    )
    b = bars(
        ("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32", "2026-01-07 09:32"),
        volume=10000,
    )
    t = targets(("2026-01-05 09:30", "2026-01-07 09:30"), (1, 0))
    r = simulate_minute_execution(
        t, b, MinuteExecutionConfig(10000, 1, 0, 0), corporate_actions=[action]
    )
    assert r.holdings.quantity.tolist() == [1000, 1050]
    assert r.holdings.date.tolist() == [
        pd.Timestamp("2026-01-05").date(),
        pd.Timestamp("2026-01-06").date(),
    ]
    assert r.holdings.symbol.tolist() == ["A", "A"]
    assert r.orders.reference_price.tolist() == [10, 10]
    assert (r.orders.reference_time < r.orders.entry_time).all()
    assert r.orders.decision_time.tolist() == t.decision_time.tolist()


def test_ex_reference_prevents_prebar_nav_inflation():
    from quant_backtest_core._minute.corporate_actions import CorporateAction

    action = CorporateAction(
        "ex",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-07",
        stock_per_share=0.1,
        stock_tradable_date="2026-01-07",
    )
    b = bars(
        ("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:29", "2026-01-06 09:32"),
        volume=10000,
    )
    b = b[b.time != pd.Timestamp("2026-01-06 09:29", tz="Asia/Shanghai")]
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30"), (1, 1))
    r = simulate_minute_execution(
        t, b, MinuteExecutionConfig(10000, 1, 0, 0), corporate_actions=[action]
    )
    assert r.orders.quantity.tolist() == [1000, 100]
    assert r.orders.reference_price.iloc[-1] == pytest.approx(9 / 1.1)
    assert r.fills.quantity.tolist() == [1000]


def test_ex_reference_applies_without_entitlement_and_is_disclosed():
    from quant_backtest_core._minute.corporate_actions import CorporateAction

    action = CorporateAction(
        "ex",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-07",
    )
    b = bars(("2026-01-05 09:29", "2026-01-06 09:32"), volume=10000)
    t = targets(("2026-01-06 09:30",), (1,))
    r = simulate_minute_execution(
        t, b, MinuteExecutionConfig(10000, 1, 0, 0), corporate_actions=[action]
    )
    assert r.orders.reference_price.tolist() == [9]
    assert r.orders.reference_basis.tolist() == ["synthetic_ex_reference"]
    assert r.orders.reference_time.iloc[0] == pd.Timestamp("2026-01-06", tz="Asia/Shanghai")
    assert r.orders.reference_source_time.iloc[0] == pd.Timestamp(
        "2026-01-05 09:29", tz="Asia/Shanghai"
    )


def test_whole_bar_must_follow_release_latency():
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:33"))
    b = b.drop(columns="interval_start")
    r = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 0.1, 0, 0))
    assert r.fills.time.tolist() == [pd.Timestamp("2026-01-05 09:33", tz="Asia/Shanghai")]
    b["interval_start"] = b.time - pd.Timedelta(minutes=5)
    r = simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 0.1, 0, 0))
    assert r.fills.empty
    b.loc[b.index[-1], "interval_start"] = b.time.iloc[-1]
    with pytest.raises(ValueError, match="interval_start"):
        simulate_minute_execution(targets(), b, MinuteExecutionConfig(10000, 0.1, 0, 0))


def test_unreleased_bonus_rights_prevent_duplicate_target_buy():
    from quant_backtest_core._minute.corporate_actions import CorporateAction

    action = CorporateAction(
        "bonus",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        stock_per_share=0.1,
        stock_tradable_date="2026-01-07",
    )
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32"), volume=10000)
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30"), (1, 1))
    r = simulate_minute_execution(
        t, b, MinuteExecutionConfig(10000, 1, 0, 0), corporate_actions=[action]
    )
    assert r.orders.quantity.tolist() == [1000]
    assert r.holdings.quantity.tolist() == [1000, 1000]
    assert r.daily.stock_receivable_value.iloc[-1] == 1000


def test_fresh_ex_bar_replaces_synthetic_reference():
    from quant_backtest_core._minute.corporate_actions import CorporateAction

    action = CorporateAction(
        "ex",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        cash_per_share=1,
        cash_pay_date="2026-01-07",
    )
    b = bars(("2026-01-05 09:29", "2026-01-06 09:29", "2026-01-06 09:32"), volume=10000)
    b.loc[b.index[1], ["open", "high", "low", "close"]] = 9.5
    b.loc[b.index[1], "amount"] = 95000
    r = simulate_minute_execution(
        targets(("2026-01-06 09:30",)),
        b,
        MinuteExecutionConfig(10000, 1, 0, 0),
        corporate_actions=[action],
    )
    assert r.orders.reference_price.tolist() == [9.5]
    assert r.orders.reference_basis.tolist() == ["raw"]
    assert r.orders.reference_time.iloc[0] == pd.Timestamp("2026-01-06 09:29", tz="Asia/Shanghai")


def test_missing_bar_time_fails_contract_validation():
    with pytest.raises(ValueError, match="missing required"):
        simulate_minute_execution(
            targets(),
            bars().drop(columns=["time", "interval_start"]),
            MinuteExecutionConfig(10000, 0.1, 0, 0),
        )


def test_missing_bar_for_unreleased_stock_rights_makes_nav_missing():
    from quant_backtest_core._minute.corporate_actions import CorporateAction

    action = CorporateAction(
        "bonus",
        "A",
        "2026-01-05",
        "2026-01-05",
        "2026-01-06",
        stock_per_share=0.1,
        stock_tradable_date="2026-01-09",
    )
    b = bars(
        ("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32", "2026-01-07 09:32"),
        volume=10000,
    )
    b.loc[b.index[-1], "symbol"] = "B"
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30"), (1, 0))
    r = simulate_minute_execution(
        t, b, MinuteExecutionConfig(10000, 1, 0, 0), corporate_actions=[action]
    )
    assert r.fills.quantity.tolist() == [1000, 1000]
    assert r.holdings.date.tolist() == [pd.Timestamp("2026-01-05").date()]
    assert r.daily.stale_mark_symbols.iloc[-1] == ("A",)
    assert pd.isna(r.daily.stock_receivable_value.iloc[-1])
    assert pd.isna(r.daily.nav.iloc[-1])


def test_parent_minimum_is_charged_once_and_then_crossed_incrementally():
    b = bars(
        (
            "2026-01-05 09:29",
            "2026-01-05 09:32",
            "2026-01-05 09:33",
            "2026-01-05 09:34",
            "2026-01-05 09:35",
            "2026-01-05 09:36",
            "2026-01-05 09:37",
        )
    )
    r = simulate_minute_execution(
        targets(), b, MinuteExecutionConfig(10000, 0.1, 10, 10, commission_minimum_cny=5)
    )
    assert r.fills.transaction_cost.tolist() == [5, 0, 0, 0, 0, 1]
    assert r.orders.executed_notional.iloc[0] == 6000
    assert r.orders.commission_paid.iloc[0] == 6


def test_minimum_changes_buy_affordability_and_zero_fills_pay_nothing():
    r = simulate_minute_execution(
        targets(),
        bars(volume=10000),
        MinuteExecutionConfig(2004, 1, 1, 6, commission_minimum_cny=5, sell_tax_bp=5),
    )
    assert r.fills.quantity.tolist() == [100]
    assert r.daily.cash.min() == 999
    zero = simulate_minute_execution(
        targets(),
        bars(),
        MinuteExecutionConfig(1004, 1, 1, 6, commission_minimum_cny=5, sell_tax_bp=5),
    )
    assert zero.fills.empty
    assert zero.summary["transaction_cost"] == 0
    cancelled = simulate_minute_execution(
        targets(("2026-01-05 09:30", "2026-01-05 09:31"), (1, 0)),
        bars(),
        MinuteExecutionConfig(10000, 1, 1, 6, commission_minimum_cny=5, sell_tax_bp=5),
    )
    assert cancelled.summary["transaction_cost"] == 0
    assert cancelled.orders.commission_paid.iloc[0] == 0


def test_sell_tax_is_separate_from_parent_commission_minimum():
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32"), volume=10000)
    r = simulate_minute_execution(
        targets(("2026-01-05 09:30", "2026-01-06 09:30"), (1, 0)),
        b,
        MinuteExecutionConfig(10005, 1, 1, 6, commission_minimum_cny=5, sell_tax_bp=5),
    )
    assert r.fills.transaction_cost.tolist() == [5, 10]
    assert r.fills.commission.tolist() == [5, 5]
    assert r.fills.sell_tax.tolist() == [0, 5]
    assert r.orders.tax_paid.tolist() == [0, 5]


def test_sell_minimum_cannot_make_cash_negative():
    b = bars(("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-06 09:32"), volume=10000)
    b.loc[b.index[-1], ["open", "high", "low", "close", "amount", "down_limit", "up_limit"]] = [
        0.01,
        0.01,
        0.01,
        0.01,
        100,
        0.001,
        0.02,
    ]
    r = simulate_minute_execution(
        targets(("2026-01-05 09:30", "2026-01-06 09:30"), (1, 0)),
        b,
        MinuteExecutionConfig(1005, 1, 1, 6, commission_minimum_cny=5, sell_tax_bp=5),
    )
    assert r.fills.side.tolist() == ["buy"]
    assert r.daily.cash.min() == 0
    assert r.orders.reason.iloc[-1] == "fee_cash"


def test_sell_tax_cannot_exceed_combined_sell_fee():
    with pytest.raises(ValueError, match="sell_tax"):
        MinuteExecutionConfig(1000, 1, 1, 6, sell_tax_bp=7)
