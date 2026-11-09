"""Supplied-fill event acceptance: delayed knowledge must not alter admission."""

import json

import pandas as pd
import pytest

from quant_backtest_core.backtest.account_events import (
    AccountEvent,
    AccountEventAdapter,
    EventAccountConfig,
)
from quant_backtest_core.backtest.paper_account import PaperState

T = pd.Timestamp("2025-01-01", tz="UTC")


def event(kind, ident, seconds=0, delay=0, **payload):
    at = T + pd.Timedelta(seconds=seconds)
    return AccountEvent(ident, kind, at, at + pd.Timedelta(seconds=delay), payload)


def inputs(seconds=0, price=10, locate=100):
    at = (T + pd.Timedelta(seconds=seconds)).isoformat()
    return {
        "price_basis": "raw",
        "marks": {"A": {"value": price, "available_at": at}},
        "borrow_rates": {"A": {"value": 0.1, "available_at": T.isoformat()}},
        "locate_quantities": {"A": {"value": locate, "available_at": at}},
        "financing_rate": {"value": 0.365, "available_at": T.isoformat()},
    }


def account(cash=100, qty=0):
    return AccountEventAdapter(
        PaperState(T, cash, {"A": qty} if qty else {}, {"A": 10}),
        EventAccountConfig(
            source_binding="synthetic-v1", input_binding="inputs-v1", credit_limit=1000
        ),
    )


def admit(a, ident="o", qty=10, price=10):
    a.admit_order(ident, "A", qty, price, as_of=T, locate_quantity=100, risk_limit=1000)


def test_partial_fill_cancel_race_keeps_reservations_until_delivered():
    a = account()
    admit(a)
    a.request_cancel("o", as_of=T)
    fill = event("fill", "f", delay=10, order_id="o", quantity=4, price=9, inputs=inputs())
    a.apply(fill)
    assert a.actual.cash == 64
    assert a.visible.cash == 100
    assert a.pending["o"]["reserved_cash"] == 100
    a.apply(fill)
    assert a.actual.quantities["A"] == 4
    a.deliver(T + pd.Timedelta(seconds=10))
    assert a.visible.quantities["A"] == 4
    assert a.pending["o"]["reserved_cash"] == 60
    a.apply(event("cancel_ack", "c", 11, delay=4, order_id="o"))
    assert "o" in a.pending
    a.deliver(T + pd.Timedelta(seconds=15))
    assert "o" not in a.pending
    with pytest.raises(ValueError):
        a.apply(event("fill", "late", 16, order_id="o", quantity=1, price=10, inputs=inputs(16)))


def test_reused_ids_and_future_clocks_fail_without_state_change():
    a = account()
    a.apply(event("dividend_record", "record", symbol="A", entitlement_id="d1"))
    e = event("dividend_ex", "d", amount=1, entitlement_id="d1")
    a.apply(e)
    before = a.checkpoint()
    with pytest.raises(ValueError):
        a.apply(event("dividend_ex", "d", amount=2, entitlement_id="d1"))
    assert a.checkpoint() == before
    with pytest.raises(ValueError):
        a.apply(AccountEvent("bad", "recall", T, T - pd.Timedelta(1), {"symbol": "A"}))
    with pytest.raises(ValueError):
        a.deliver(T - pd.Timedelta(1))


@pytest.mark.parametrize("quantity", [4, -4])
def test_dividend_entitlement_survives_close_and_checkpoint(quantity):
    a = account(qty=quantity)
    a.apply(event("dividend_record", "record", symbol="A", entitlement_id="d"))
    a.apply(event("dividend_ex", "ex", amount=2, entitlement_id="d"))
    admit(a, qty=-quantity)
    a.apply(event("fill", "close", order_id="o", quantity=-quantity, price=10, inputs=inputs()))
    a.deliver(T)
    restored = AccountEventAdapter.restore(json.loads(json.dumps(a.checkpoint())), a.config)
    pay = event("dividend_pay", "pay", entitlement_id="d")
    for candidate in (a, restored):
        candidate.apply(pay)
        assert candidate.actual.cash == 100 + quantity * 12
        assert candidate.entitlements["d"]["quantity"] == quantity
    assert restored.checkpoint() == a.checkpoint()


def test_split_scales_raw_inventory_orders_locates_and_rejects_fractional():
    a = account(qty=-4)
    admit(a, qty=-2)
    a.apply(event("split", "s", symbol="A", numerator=3, denominator=2, price_basis="raw"))
    assert a.actual.quantities["A"] == -6
    assert a.actual.marks["A"] == pytest.approx(20 / 3)
    a.deliver(T)
    assert a.pending["o"]["quantity"] == -3
    assert a.pending["o"]["limit_price"] == pytest.approx(20 / 3)
    assert a.pending["o"]["locate_quantity"] == 150
    b = account(qty=1)
    before = b.checkpoint()
    with pytest.raises(ValueError, match="fractional"):
        b.apply(event("split", "s", symbol="A", numerator=3, denominator=2, price_basis="raw"))
    assert b.checkpoint() == before


def test_hidden_future_marks_do_not_change_admission_and_restore_pending():
    a, b = account(), account()
    a.apply(event("projection", "m", delay=10, inputs=inputs(price=100)))
    b.apply(event("projection", "m", delay=10, inputs=inputs(price=1)))
    for candidate in (a, b):
        admit(candidate, qty=-5)
    assert a.pending == b.pending
    restored = AccountEventAdapter.restore(a.checkpoint(), a.config)
    restored.deliver(T + pd.Timedelta(seconds=10))
    a.deliver(T + pd.Timedelta(seconds=10))
    assert a.checkpoint() == restored.checkpoint()


def test_funding_recall_margin_reductions_and_settlement_are_explicit():
    a = account(cash=-100, qty=-10)
    a.apply(event("projection", "m", 86400, inputs=inputs(86400, locate=0)))
    assert a.actual.cash == pytest.approx(-100 - 0.1 - 100 * 0.1 / 365)
    assert a.actual.quantities["A"] == -10
    assert a.reductions
    assert all(intent["status"] == "required" for intent in a.reductions)
    b = account(qty=5)
    admit(b, qty=-5)
    b.apply(
        event(
            "fill",
            "sell",
            order_id="o",
            quantity=-5,
            price=10,
            cash_available_at=(T + pd.Timedelta(days=2)).isoformat(),
            inputs=inputs(),
        )
    )
    b.deliver(T)
    assert b.visible.cash == 150
    assert b.available_cash(T) == 100
    assert b.available_cash(T + pd.Timedelta(days=2)) == 150


def test_checkpoint_rejects_tampering_and_config_change():
    a = account()
    snapshot = a.checkpoint()
    snapshot["state"]["actual"]["cash"] = 999
    with pytest.raises(ValueError, match="digest"):
        AccountEventAdapter.restore(snapshot, a.config)
    with pytest.raises(ValueError, match="config"):
        AccountEventAdapter.restore(
            a.checkpoint(), EventAccountConfig(source_binding="other", input_binding="inputs-v1")
        )


def test_owned_long_sales_need_no_locate_and_pending_buys_cannot_supply_it():
    a = account(qty=5)
    a.admit_order("sale", "A", -5, 10, as_of=T, locate_quantity=0, risk_limit=1000)
    with pytest.raises(ValueError, match="locate"):
        a.admit_order("excess", "A", -1, 10, as_of=T, locate_quantity=0, risk_limit=1000)
    b = account()
    admit(b, qty=5)
    with pytest.raises(ValueError, match="locate"):
        b.admit_order("sale", "A", -1, 10, as_of=T, locate_quantity=0, risk_limit=1000)


def test_event_cannot_predate_admission_cancel_request_or_delivered_knowledge():
    a = account()
    a.admit_order(
        "o", "A", 1, 10, as_of=T + pd.Timedelta(seconds=5), locate_quantity=0, risk_limit=1000
    )
    before = a.checkpoint()
    with pytest.raises(ValueError):
        a.apply(event("fill", "early", order_id="o", quantity=1, price=10, inputs=inputs()))
    assert a.checkpoint() == before
    a.request_cancel("o", as_of=T + pd.Timedelta(seconds=8))
    with pytest.raises(ValueError):
        a.apply(event("cancel_ack", "early_ack", 7, order_id="o"))
    a.deliver(T + pd.Timedelta(seconds=9))
    with pytest.raises(ValueError):
        a.apply(event("cancel_ack", "past_report", 8, order_id="o"))


def test_overflow_entitlement_is_rejected_atomically_and_nav_sees_receivables():
    a = account(qty=-4)
    a.apply(event("dividend_record", "r", symbol="A", entitlement_id="d"))
    before = a.checkpoint()
    with pytest.raises(ValueError):
        a.apply(event("dividend_ex", "overflow", amount=1e308, entitlement_id="d"))
    assert a.checkpoint() == before
    a.apply(event("dividend_ex", "ex", amount=2, entitlement_id="d"))
    assert a.actual_nav == 52
    assert a.visible_nav == 60
    a.deliver(T)
    assert a.visible_receivables == -8
    assert a.visible_nav == 52


def test_full_fill_cancel_ack_race_and_economic_fill_id_deduplication():
    a = account()
    admit(a, qty=2)
    a.request_cancel("o", as_of=T)
    payload = {
        "order_id": "o",
        "quantity": 2,
        "price": 10,
        "fill_id": "economic-fill",
        "inputs": inputs(),
    }
    a.apply(event("fill", "one", **payload))
    a.apply(event("fill", "duplicate-report", delay=1, **payload))
    a.apply(event("cancel_ack", "ack", order_id="o"))
    a.deliver(T + pd.Timedelta(seconds=1))
    assert a.visible.quantities["A"] == 2
    assert not a.pending
    assert a.visible.cash == 80


def test_projection_requires_raw_prices_and_rejects_future_observations_atomically():
    a = account(qty=-2)
    for changes in (
        {"price_basis": "adjusted"},
        {"marks": {"A": {"value": 10, "available_at": (T + pd.Timedelta(seconds=1)).isoformat()}}},
    ):
        before = a.checkpoint()
        with pytest.raises(ValueError):
            a.apply(event("projection", "bad", inputs={**inputs(), **changes}))
        assert a.checkpoint() == before


def test_failed_cover_keeps_exposure_and_successful_cover_needs_no_locate():
    a = account(qty=-4)
    a.admit_order("cover", "A", 4, 10, as_of=T, locate_quantity=0, risk_limit=1000)
    before = a.checkpoint()
    with pytest.raises(ValueError):
        a.apply(
            event(
                "fill", "failure", order_id="cover", quantity=4, price=11, inputs=inputs(locate=0)
            )
        )
    assert a.checkpoint() == before
    assert a.actual.quantities["A"] == -4
    a.apply(
        event("fill", "success", order_id="cover", quantity=4, price=10, inputs=inputs(locate=0))
    )
    assert not a.actual.quantities


def test_long_sale_partial_reports_do_not_create_phantom_short_locate_reservation():
    a = account(qty=5)
    a.admit_order("sale", "A", -5, 10, as_of=T, locate_quantity=0, risk_limit=1000)
    a.apply(event("fill", "f", order_id="sale", quantity=-2, price=10, inputs=inputs(locate=0)))
    a.deliver(T)
    assert a.visible.quantities["A"] == 3
    assert a.pending["sale"]["reserved_locate"] == 0


def test_prefix_delivery_withholds_newer_snapshot_until_older_report_arrives():
    a = account()
    admit(a, qty=2)
    a.apply(event("fill", "old", delay=10, order_id="o", quantity=1, price=10, inputs=inputs()))
    a.apply(event("projection", "new", 1, inputs=inputs(1, price=20)))
    a.deliver(T + pd.Timedelta(seconds=5))
    assert a.visible.cash == 100
    assert not a.visible.quantities
    a.deliver(T + pd.Timedelta(seconds=10))
    assert a.visible.cash == 90
    assert a.visible.quantities["A"] == 1
    assert a.visible.marks["A"] == 20


def test_record_before_close_ex_after_close_still_books_signed_receivable():
    a = account(qty=-2)
    a.apply(event("dividend_record", "record", symbol="A", entitlement_id="d"))
    admit(a, qty=2)
    a.apply(event("fill", "close", order_id="o", quantity=2, price=10, inputs=inputs()))
    a.apply(event("dividend_ex", "ex", entitlement_id="d", amount=3))
    assert not a.actual.quantities
    assert a.actual_nav == 74
    a.apply(event("dividend_pay", "pay", entitlement_id="d"))
    assert a.actual.cash == 74
    assert a.actual_nav == 74


def test_unused_future_input_and_nonfinite_initial_aggregate_fail_closed():
    a = account()
    bad = inputs()
    bad["marks"]["UNHELD"] = {"value": 5, "available_at": (T + pd.Timedelta(seconds=1)).isoformat()}
    before = a.checkpoint()
    with pytest.raises(ValueError):
        a.apply(event("projection", "future", inputs=bad))
    assert a.checkpoint() == before
    with pytest.raises(ValueError):
        AccountEventAdapter(PaperState(T, 1e308, {"A": 2}, {"A": 1e308}), a.config)


def test_sorted_json_resume_preserves_boundary_risk_admission():
    cfg = EventAccountConfig(source_binding="s", input_binding="i", credit_limit=1e20)
    a = AccountEventAdapter(PaperState(T, 0, {}, {}), cfg)
    for name, price in (("z", 1e16), ("b", 1), ("a", 1)):
        a.admit_order(name, "A", 1, price, as_of=T, locate_quantity=0, risk_limit=1e20)
    b = AccountEventAdapter.restore(json.loads(json.dumps(a.checkpoint(), sort_keys=True)), cfg)
    for candidate in (a, b):
        with pytest.raises(ValueError, match="risk"):
            candidate.admit_order("extra", "A", 1, 1, as_of=T, locate_quantity=0, risk_limit=1e16)


def test_supplied_short_fill_cannot_exceed_reserved_adverse_price_bound():
    a = account()
    a.admit_order(
        "short", "A", -2, 10, as_of=T, locate_quantity=100, risk_limit=1000, risk_price=12
    )
    assert a.pending["short"]["reserved_risk"] == 24
    before = a.checkpoint()
    with pytest.raises(ValueError, match="risk"):
        a.apply(
            event("fill", "bad", order_id="short", quantity=-1, price=13, inputs=inputs(price=13))
        )
    assert a.checkpoint() == before
    a.apply(event("fill", "good", order_id="short", quantity=-1, price=11, inputs=inputs(price=11)))
    a.deliver(T)
    assert a.pending["short"]["reserved_risk"] == 12


def test_fee_budget_reservation_stays_until_partial_report_and_rejects_overrun():
    a = account()
    a.admit_order("buy", "A", 2, 10, as_of=T, locate_quantity=0, risk_limit=1000, fee_budget=3)
    assert a.pending["buy"]["reserved_cash"] == 23
    before = a.checkpoint()
    with pytest.raises(ValueError, match="fee"):
        a.apply(event("fill", "bad", order_id="buy", quantity=1, price=10, fee=4, inputs=inputs()))
    assert a.checkpoint() == before
    a.apply(
        event("fill", "good", delay=1, order_id="buy", quantity=1, price=10, fee=1, inputs=inputs())
    )
    assert a.pending["buy"]["reserved_cash"] == 23
    a.deliver(T + pd.Timedelta(seconds=1))
    assert a.pending["buy"]["reserved_cash"] == 12


def test_unsettled_short_proceeds_and_collateral_are_reserved_once():
    a = account()
    admit(a, qty=-5)
    a.apply(
        event(
            "fill",
            "short",
            order_id="o",
            quantity=-5,
            price=10,
            cash_available_at=(T + pd.Timedelta(days=2)).isoformat(),
            inputs=inputs(),
        )
    )
    a.deliver(T)
    assert a.visible.cash == 150
    assert a.available_cash(T) == 100
    assert a.available_cash(T + pd.Timedelta(days=2)) == 100


def test_other_symbol_collateral_does_not_overlap_closed_short_sale_settlement():
    cfg = EventAccountConfig(source_binding="s", input_binding="i", credit_limit=1000)
    a = AccountEventAdapter(PaperState(T, 100, {"A": -5}, {"A": 10, "B": 10}), cfg)
    observed = inputs()
    for key in ("marks", "borrow_rates", "locate_quantities"):
        observed[key]["B"] = observed[key]["A"].copy()
    a.admit_order("short", "B", -5, 10, as_of=T, locate_quantity=100, risk_limit=1000)
    a.apply(
        event(
            "fill",
            "sell",
            order_id="short",
            quantity=-5,
            price=10,
            cash_available_at=(T + pd.Timedelta(days=2)).isoformat(),
            inputs=observed,
        )
    )
    a.deliver(T)
    assert a.available_cash(T) == 50
    a.admit_order("cover", "B", 5, 10, as_of=T, locate_quantity=0, risk_limit=1000)
    a.apply(event("fill", "buy", order_id="cover", quantity=5, price=10, inputs=observed))
    a.deliver(T)
    assert a.visible.cash == 100
    assert a.available_cash(T) == 0
    assert a.available_cash(T + pd.Timedelta(days=2)) == 50


def test_future_control_action_prevents_retroactive_corporate_transform():
    a = account(qty=2)
    a.admit_order(
        "future", "A", 2, 10, as_of=T + pd.Timedelta(seconds=10), locate_quantity=0, risk_limit=1000
    )
    before = a.checkpoint()
    with pytest.raises(ValueError):
        a.apply(event("split", "past", symbol="A", numerator=3, denominator=2, price_basis="raw"))
    assert a.checkpoint() == before
    for mutation in (
        lambda: a.deliver(T + pd.Timedelta(seconds=9)),
        lambda: a.request_cancel("future", as_of=T + pd.Timedelta(seconds=9)),
    ):
        with pytest.raises(ValueError):
            mutation()
        assert a.checkpoint() == before


def test_delayed_split_report_never_scales_an_order_admitted_after_occurrence():
    a = account()
    a.apply(
        event("split", "s", delay=10, symbol="A", numerator=2, denominator=1, price_basis="raw")
    )
    a.deliver(T + pd.Timedelta(seconds=1))
    a.admit_order(
        "new", "A", 2, 10, as_of=T + pd.Timedelta(seconds=1), locate_quantity=0, risk_limit=1000
    )
    a.apply(event("fill", "f", 2, order_id="new", quantity=2, price=10, inputs=inputs(2)))
    a.deliver(T + pd.Timedelta(seconds=10))
    assert a.actual.quantities["A"] == 2
    assert a.visible.quantities["A"] == 2
    assert not a.pending


def test_delayed_split_transforms_preexisting_partial_order_only():
    a = account()
    admit(a, ident="old", qty=4, price=20)
    a.apply(
        event("fill", "partial", delay=5, order_id="old", quantity=1, price=10, inputs=inputs())
    )
    a.apply(
        event("split", "s", delay=10, symbol="A", numerator=2, denominator=1, price_basis="raw")
    )
    a.deliver(T + pd.Timedelta(seconds=1))
    a.admit_order(
        "new", "A", 2, 10, as_of=T + pd.Timedelta(seconds=1), locate_quantity=0, risk_limit=1000
    )
    a.apply(event("fill", "new-full", 2, order_id="new", quantity=2, price=10, inputs=inputs(2)))
    a.deliver(T + pd.Timedelta(seconds=10))
    assert set(a.pending) == {"old"}
    assert a.pending["old"]["quantity"] == 8
    assert a.pending["old"]["remaining"] == 6
    assert a.pending["old"]["limit_price"] == 10
    assert a.pending["old"]["reserved_cash"] == 60
    assert a.visible.quantities["A"] == 4


def test_sorted_json_resume_preserves_split_report_membership_order():
    a = account()
    admit(a, ident="z", qty=2)
    admit(a, ident="a", qty=2)
    b = AccountEventAdapter.restore(
        json.loads(json.dumps(a.checkpoint(), sort_keys=True)), a.config
    )
    split = event("split", "s", delay=10, symbol="A", numerator=2, denominator=1, price_basis="raw")
    a.apply(split)
    b.apply(split)
    assert a.checkpoint() == b.checkpoint()


def test_short_dividend_payable_triggers_margin_at_ex_and_cover_before_pay_can_resolve():
    a = account(qty=-4)
    assert not a.actual_margin["breach"]
    a.apply(event("dividend_record", "r", symbol="A", entitlement_id="d"))
    a.apply(event("dividend_ex", "ex", delay=1, entitlement_id="d", amount=6))
    assert a.actual_nav == 36
    assert a.actual_margin == {
        "required": 40,
        "excess": -4,
        "breach": True,
        "equity_basis": "nav_including_signed_receivables",
    }
    assert not a.visible_margin["breach"]
    assert a.actual.quantities["A"] == -4
    assert any(i["reason"] == "margin" and i["status"] == "required" for i in a.reductions)
    a.deliver(T + pd.Timedelta(seconds=1))
    assert a.visible_margin["breach"]
    a.admit_order(
        "cover", "A", 2, 10, as_of=T + pd.Timedelta(seconds=1), locate_quantity=0, risk_limit=1000
    )
    a.apply(event("fill", "cover", 1, order_id="cover", quantity=2, price=10, inputs=inputs(1)))
    assert a.actual_nav == pytest.approx(36 - 4 / 86400 / 365)
    assert not a.actual_margin["breach"]
    assert a.actual.quantities["A"] == -2
    assert a.visible_margin["breach"]
    assert all(i["status"] == "resolved" for i in a.reductions if i["reason"] == "margin")
    a.apply(event("dividend_pay", "pay", 1, entitlement_id="d"))
    a.deliver(T + pd.Timedelta(seconds=1))
    assert not a.visible_margin["breach"]
    assert a.visible_margin["required"] == 20


def test_cashflows_and_late_fee_are_atomic_delayed_and_event_idempotent():
    a = account(cash=100, qty=0)
    deposit = event("cashflow", "deposit", delay=5, amount=50, reason="declared_deposit")
    a.apply(deposit)
    a.apply(deposit)
    assert a.actual.cash == 150 and a.visible.cash == 100
    a.deliver(T + pd.Timedelta(seconds=5))
    assert a.visible.cash == 150
    before = a.checkpoint()
    with pytest.raises(ValueError, match="project"):
        a.apply(event("cashflow", "future", 6, amount=1, reason="deposit"))
    assert a.checkpoint() == before
    # Same economic clock is behind delivery now, so use a separate account probe.
    b = account(cash=100, qty=0)
    b.apply(event("fee_adjustment", "fee", amount=7, reason="supplementary_commission"))
    assert b.actual.cash == 93
    with pytest.raises(ValueError):
        b.apply(event("fee_adjustment", "credit", amount=-7, reason="invalid_fee_credit"))
    assert b.actual.cash == 93
    restored = AccountEventAdapter.restore(b.checkpoint(), b.config)
    restored.deliver(T)
    assert restored.visible.cash == 93
