"""Hand-calculated raw-share ledger cases; all prices and events are synthetic."""

from dataclasses import FrozenInstanceError, replace

import pandas as pd
import pytest

from quant_backtest_core.daily.execution_sim import (
    CorporateAction,
    ExecutionSimConfig,
    prepare_execution_tables,
    simulate_execution_adjusted_nav,
)

SESSIONS = ["20260904", "20260908", "20260909", "20260910", "20260911"]


def action(**overrides):
    values = {
        "event_id": "dividend",
        "symbol": "AAA",
        "available_date": "20260903",
        "record_date": SESSIONS[0],
        "ex_date": SESSIONS[1],
        "cash_per_share": 1.0,
        "cash_pay_date": SESSIONS[3],
    }
    return CorporateAction(**(values | overrides))


def positions(*targets):
    return pd.DataFrame(
        [
            {"rebalance_date": date, "entry_date": date, "symbol": symbol, "weight": weight}
            for date, symbol, weight in (targets or [(SESSIONS[0], "AAA", 1.0)])
        ]
    )


def prices(aaa=(10, 9, 9, 9, 9)):
    return pd.DataFrame(
        [
            {
                "trade_date": date,
                "symbol": symbol,
                "raw": price,
                "amount": 10000.0,
                "tradable": True,
            }
            for date, price_a in zip(SESSIONS, aaa, strict=True)
            for symbol, price in [("AAA", price_a), ("BBB", 10.0)]
        ]
    )


def run(events, *, targets=None, quotes=None, config=None, **kwargs):
    return simulate_execution_adjusted_nav(
        positions() if targets is None else targets,
        prices() if quotes is None else quotes,
        config
        or ExecutionSimConfig(
            enabled=True,
            portfolio_value=1000,
            participation_rate=1,
            liquidity_cols=("amount",),
            buy_max_days=5,
            enforce_t1=True,
        ),
        price_col="raw",
        tradable_col="tradable",
        corporate_actions=events,
        **({"price_basis": "raw"} | kwargs),
    )


def test_cash_right_recognized_at_ex_and_payment_transfers_without_return():
    result = run([action()])
    assert result.daily.portfolio_value.tolist() == pytest.approx([1000] * 5)
    assert result.daily.invested_value.tolist() == pytest.approx([1000, 900, 900, 900, 900])
    assert result.daily.cash_receivable.tolist() == pytest.approx([0, 100, 100, 0, 0])
    assert result.daily.cash.tolist() == pytest.approx([0, 0, 0, 100, 100])
    assert result.daily.executed_return.tolist() == pytest.approx([0] * 5)
    assert result.actions.stage.tolist() == ["record", "ex", "cash_payment"]
    assert result.actions.record_shares.tolist() == pytest.approx([100] * 3)
    assert result.holdings.shares.tolist() == pytest.approx([100] * 5)
    pd.testing.assert_frame_equal(result.daily, run([action()]).daily)


def test_new_target_sizes_on_rights_but_cannot_spend_unpaid_cash():
    result = run(
        [action()],
        targets=positions(
            (SESSIONS[0], "AAA", 1),
            (SESSIONS[2], "AAA", 0.9),
            (SESSIONS[2], "BBB", 0.1),
        ),
    )
    bbb = result.fills.loc[result.fills.symbol.eq("BBB")]
    assert bbb.trade_date.tolist() == [SESSIONS[3]]
    assert bbb.filled_notional.tolist() == pytest.approx([100])
    assert result.orders.loc[result.orders.symbol.eq("BBB"), "requested_notional"].tolist() == [100]
    assert result.daily.loc[2, "cash"] == 0
    assert result.daily.portfolio_value.tolist() == pytest.approx([1000] * 5)


def test_selling_after_record_retains_cash_rights():
    result = run(
        [action()],
        targets=positions(
            (SESSIONS[0], "AAA", 1),
            (SESSIONS[1], "__CASH__", 0),
        ),
    )
    assert result.daily.cash.tolist() == pytest.approx([0, 900, 900, 1000, 1000])
    assert result.daily.cash_receivable.tolist() == pytest.approx([0, 100, 100, 0, 0])


def test_record_date_sells_exclude_rights():
    result = run(
        [action(record_date=SESSIONS[1], ex_date=SESSIONS[2])],
        quotes=prices((10, 10, 9, 9, 9)),
        targets=positions((SESSIONS[0], "AAA", 1), (SESSIONS[1], "__CASH__", 0)),
    )
    assert result.daily.cash_receivable.tolist() == [0] * 5
    assert result.daily.portfolio_value.tolist() == pytest.approx([1000] * 5)


def test_buys_after_record_and_pre_run_record_get_no_rights():
    for targets in [
        positions((SESSIONS[1], "AAA", 1)),
        positions(
            (SESSIONS[0], "__CASH__", 0),
            (SESSIONS[1], "AAA", 1),
        ),
    ]:
        result = run([action()], targets=targets)
        assert result.daily.cash_receivable.sum() == 0
        assert result.daily.portfolio_value.tolist() == pytest.approx([1000] * len(result.daily))


def test_future_event_terms_do_not_change_pre_ex_daily_rows():
    first = run([action()])
    changed = run([action(cash_per_share=2)])
    pd.testing.assert_frame_equal(first.daily.iloc[:1], changed.daily.iloc[:1])


def test_explicit_withholding_recognizes_net_80_and_discloses_flat_rate():
    result = run([action(withholding_rate=0.2)])
    assert result.daily.portfolio_value.tolist() == pytest.approx([1000, 980, 980, 980, 980])
    assert result.daily.cash_receivable.tolist() == pytest.approx([0, 80, 80, 0, 0])
    ex = result.actions.loc[result.actions.stage.eq("ex")].iloc[0]
    assert ex.gross_cash == 100
    assert ex.withheld_cash == 20
    assert ex.withholding_rate == 0.2


def bonus(**overrides):
    return action(
        **(
            {
                "cash_per_share": 0,
                "cash_pay_date": None,
                "stock_per_share": 1,
                "stock_tradable_date": SESSIONS[3],
            }
            | overrides
        )
    )


def test_bonus_receivable_marks_at_current_raw_price_then_releases_once():
    result = run([bonus()], quotes=prices((10, 5, 6, 6, 6)))
    assert result.daily.portfolio_value.tolist() == pytest.approx([1000, 1000, 1200, 1200, 1200])
    assert result.daily.stock_receivable_value.tolist() == pytest.approx([0, 500, 600, 0, 0])
    assert result.holdings.shares.tolist() == pytest.approx([100, 100, 100, 200, 200])
    assert result.holdings.stock_receivable_shares.tolist() == pytest.approx([0, 100, 100, 0, 0])
    assert result.actions.stage.tolist() == ["record", "ex", "stock_release"]


def test_bonus_only_original_shares_sell_before_release_across_holiday_sessions():
    result = run(
        [bonus()],
        quotes=prices((10, 5, 5, 5, 5)),
        targets=positions(
            (SESSIONS[0], "AAA", 1),
            (SESSIONS[1], "__CASH__", 0),
            (SESSIONS[3], "__CASH__", 0),
        ),
    )
    sells = result.fills.loc[result.fills.side.eq("sell")]
    assert sells.trade_date.tolist() == [SESSIONS[1], SESSIONS[3]]
    assert sells.filled_notional.tolist() == pytest.approx([500, 500])
    assert result.daily.cash.tolist() == pytest.approx([0, 500, 500, 1000, 1000])
    assert result.daily.portfolio_value.tolist() == pytest.approx([1000] * 5)
    assert result.holdings.loc[0, "sellable_shares"] == 0  # record-day buys are T+1


def test_bonus_counts_toward_target_exposure_without_duplicate_buy():
    result = run(
        [bonus()],
        quotes=prices((10, 5, 5, 5, 5)),
        targets=positions(
            (SESSIONS[0], "AAA", 0.5),
            (SESSIONS[1], "AAA", 0.5),
        ),
    )
    assert result.fills.filled_notional.tolist() == pytest.approx([500])
    assert result.daily.cash.tolist() == pytest.approx([500] * 5)


def test_fractional_bonus_is_retained_without_cash_in_lieu():
    result = run([bonus(stock_per_share=0.003)], quotes=prices((10, 10, 10, 10, 10)))
    assert result.holdings.shares.tolist() == pytest.approx([100, 100, 100, 100.3, 100.3])
    assert result.daily.cash.tolist() == [0] * 5


def test_settlement_outside_window_stays_receivable():
    result = run(
        [action(cash_pay_date="20261001", stock_per_share=1, stock_tradable_date="20261001")],
        quotes=prices((10, 4.5, 4.5, 4.5, 4.5)),
    )
    assert result.daily.loc[4, "cash_receivable"] == 100
    assert result.daily.loc[4, "stock_receivable_value"] == 450
    assert result.daily.loc[4, "portfolio_value"] == 1000
    assert result.actions.stage.tolist() == ["record", "ex"]


def test_same_ex_settlement_recognizes_and_transfers_before_orders():
    result = run([action(cash_pay_date=SESSIONS[1])])
    assert result.daily.cash_receivable.tolist() == [0] * 5
    assert result.daily.cash.tolist() == [0, 100, 100, 100, 100]
    assert result.daily.portfolio_value.tolist() == pytest.approx([1000] * 5)


@pytest.mark.parametrize("basis", [None, "adjusted", "qfq", "RAW"])
def test_raw_basis_required_even_for_explicit_empty_events(basis):
    with pytest.raises(ValueError, match="price_basis"):
        run([], price_basis=basis)


def test_duplicate_event_identity_rejected():
    event = action()
    with pytest.raises(ValueError, match="duplicate"):
        run([event, replace(event, symbol="BBB")])


@pytest.mark.parametrize(
    "changes",
    [
        {"event_id": ""},
        {"symbol": " "},
        {"record_date": "bad"},
        {"available_date": "20260905"},
        {"ex_date": SESSIONS[0]},
        {"cash_pay_date": None},
        {"cash_pay_date": SESSIONS[0]},
        {"stock_per_share": 1},
        {"stock_per_share": 1, "stock_tradable_date": SESSIONS[0]},
        {"cash_per_share": -1},
        {"cash_per_share": float("nan")},
        {"stock_per_share": float("inf")},
        {"withholding_rate": 1.1},
        {"withholding_rate": -0.1},
        {"withholding_rate": float("nan")},
        {"record_date": None},
        {"record_date": "2026-09-04T12:00"},
        {"record_date": "2026-09-04T00:00Z"},
        {"cash_per_share": 0, "cash_pay_date": None},
    ],
)
def test_invalid_events_rejected(changes):
    with pytest.raises(ValueError):
        action(**changes)


def test_event_is_immutable_and_dates_normalize():
    event = action()
    assert event.record_date == pd.Timestamp("2026-09-04")
    with pytest.raises(FrozenInstanceError):
        event.cash_per_share = 2


@pytest.mark.parametrize(
    "changes",
    [
        {"record_date": "20260907"},
        {"ex_date": "20260907"},
        {"cash_pay_date": "20260912"},
    ],
)
def test_in_window_action_dates_require_exact_session_coverage(changes):
    # Include a later session so September 12 is inside the run, not after it.
    quotes = pd.concat([prices(), prices().iloc[-2:].assign(trade_date="20260914")])
    with pytest.raises(ValueError, match="calendar"):
        run([action(**changes)], quotes=quotes)


@pytest.mark.parametrize("mark", [float("nan"), 0, -1, float("inf")])
def test_missing_or_invalid_ex_mark_fails_even_when_suspended(mark):
    quotes = prices()
    quotes.loc[quotes.trade_date.eq(SESSIONS[1]) & quotes.symbol.eq("AAA"), ["raw", "tradable"]] = [
        mark,
        False,
    ]
    with pytest.raises(ValueError, match="raw mark"):
        run([action()], quotes=quotes)


def test_suspension_with_explicit_raw_mark_can_value_rights():
    quotes = prices()
    quotes.loc[quotes.trade_date.eq(SESSIONS[1]), "tradable"] = False
    assert run([action()], quotes=quotes).daily.loc[1, "portfolio_value"] == 1000


def test_missing_stock_receivable_mark_after_original_shares_sold_fails():
    quotes = prices((10, 5, float("nan"), 5, 5))
    with pytest.raises(ValueError, match="raw mark"):
        run(
            [bonus()],
            quotes=quotes,
            targets=positions((SESSIONS[0], "AAA", 1), (SESSIONS[1], "__CASH__", 0)),
        )


def test_ex_cancels_only_affected_outstanding_orders():
    quotes = prices()
    quotes.loc[quotes.trade_date.eq(SESSIONS[0]), "amount"] = 100
    result = run(
        [action()],
        quotes=quotes,
        targets=positions((SESSIONS[0], "AAA", 0.5), (SESSIONS[0], "BBB", 0.5)),
    )
    aaa = result.orders.loc[result.orders.symbol.eq("AAA")].iloc[0]
    bbb = result.orders.loc[result.orders.symbol.eq("BBB")].iloc[0]
    assert aaa.status == "cancelled_corporate_action"
    assert aaa.filled_notional == 100
    assert bbb.status == "filled"
    assert bbb.filled_notional == 500


def test_no_action_calls_are_exactly_equivalent_and_opt_in_empty_adds_only_receipts():
    config = ExecutionSimConfig(enabled=True, portfolio_value=1000, liquidity_cols=("amount",))
    legacy = simulate_execution_adjusted_nav(
        positions(), prices(), config, price_col="raw", tradable_col="tradable"
    )
    explicit_none = run(None, config=config, price_basis=None)
    empty = run([], config=config)
    for field in ["daily", "orders", "fills"]:
        pd.testing.assert_frame_equal(getattr(legacy, field), getattr(explicit_none, field))
    assert legacy.summary == explicit_none.summary
    assert legacy.actions is None and legacy.holdings is None
    pd.testing.assert_frame_equal(legacy.daily, empty.daily[legacy.daily.columns])
    pd.testing.assert_frame_equal(legacy.orders, empty.orders)
    pd.testing.assert_frame_equal(legacy.fills, empty.fills)
    assert empty.actions.empty
    assert not empty.holdings.empty


def test_prepared_tables_use_same_run_calendar_and_accounting():
    config = ExecutionSimConfig(
        enabled=True,
        portfolio_value=1000,
        participation_rate=1,
        liquidity_cols=("amount",),
        enforce_t1=True,
    )
    tables = prepare_execution_tables(prices(), config, price_col="raw", tradable_col="tradable")
    actual = run([action()], config=config, prepared_tables=tables)
    pd.testing.assert_frame_equal(actual.daily, run([action()], config=config).daily)
