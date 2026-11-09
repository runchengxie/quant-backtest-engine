# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355, tests/test_sleeve_allocation.py
from dataclasses import replace
from decimal import Decimal, localcontext

import pandas as pd
import pytest
from test_minute_execution import bars, targets
from test_minute_session import Policy
from test_quantity_locks import notice

from quant_backtest_core.backtest.impact import LinearImpact
from quant_backtest_core.backtest.minute import MinuteExecutionConfig, simulate_minute_execution
from quant_backtest_core.backtest.minute_session import MinuteSession
from quant_backtest_core.evidence.execution_integrity import exit_wealth
from quant_backtest_core.planning.sleeve_allocation import (
    SleeveDemand,
    allocate_external_fills,
    net_sleeve_demands,
)


def demand(sleeve, quantity, **updates):
    return SleeveDemand(
        sleeve=sleeve,
        symbol=updates.pop("symbol", "A"),
        quantity=quantity,
        cash_budget=updates.pop("cash_budget", "1000"),
        inventory=updates.pop("inventory", max(0, -quantity)),
        sellable=updates.pop("sellable", max(0, -quantity)),
        locked=updates.pop("locked", 0),
        max_buy_price=updates.pop("max_buy_price", "10" if quantity > 0 else None),
        fee_budget=updates.pop("fee_budget", "1"),
        **updates,
    )


def plan(*rows, reference="10"):
    return net_sleeve_demands(rows, reference_prices={"A": reference})


def fill(ident="f", quantity=1, price="10", fee="0", side="buy", at=1):
    return {
        "fill_id": ident,
        "ts_ns": at,
        "symbol": "A",
        "side": side,
        "quantity": quantity,
        "price": price,
        "gross_amount": Decimal(price) * quantity,
        "fee": fee,
    }


def rows(allocation):
    return {r.sleeve: r for r in allocation.deltas}


def test_opposing_demands_transfer_reference_value_without_external_fill_or_fee():
    p = plan(demand("buyer", 5), demand("seller", -3))
    assert [(o.symbol, o.side, o.quantity) for o in p.external_orders] == [("A", "buy", 2)]
    a = allocate_external_fills(p, [])
    b, s = rows(a)["buyer"], rows(a)["seller"]
    assert (b.internal_quantity, b.cash_delta, b.residual) == (3, Decimal(-30), 2)
    assert (s.internal_quantity, s.cash_delta, s.residual) == (-3, Decimal(30), 0)
    assert a.pooled_quantities == ()
    assert a.pooled_cash_delta == a.pooled_fee == 0
    assert b.fee == s.fee == 0


def test_partial_fills_conserve_shares_cash_and_fee_cents_with_literal_ties():
    p = plan(demand("b", 3), demand("a", 3))
    a = allocate_external_fills(p, [fill(quantity=3, fee="0.05")])
    r = rows(a)
    assert (r["a"].external_quantity, r["b"].external_quantity) == (2, 1)
    assert (r["a"].fee, r["b"].fee) == (Decimal("0.03"), Decimal("0.02"))
    assert (r["a"].cash_delta, r["b"].cash_delta) == (Decimal("-20.03"), Decimal("-10.02"))
    assert (r["a"].residual, r["b"].residual) == (1, 2)
    assert a.pooled_quantities == (("A", 3),)
    assert a.pooled_cash_delta == Decimal("-30.05")
    assert a.pooled_fee == Decimal("0.05")
    assert sum(x.cash_delta for x in a.deltas) == a.pooled_cash_delta
    assert sum(x.fee for x in a.deltas) == a.pooled_fee


def test_lot_remainders_and_input_order_are_deterministic():
    a, b = (
        demand("a", 300, lot_size=100, cash_budget="4000"),
        demand("b", 300, lot_size=100, cash_budget="4000"),
    )
    reports = [fill("later", 100, at=2), fill("first", 100, at=1)]
    expected = allocate_external_fills(plan(a, b), reports)
    assert expected == allocate_external_fills(plan(b, a), list(reversed(reports)))
    assert [r.external_quantity for r in expected.deltas] == [100, 100]
    one = allocate_external_fills(plan(a, b), [fill(quantity=100)])
    assert [r.external_quantity for r in one.deltas] == [100, 0]


def test_locks_inventory_sellability_and_budget_leave_explicit_residuals():
    p = plan(
        demand("buy", 10, cash_budget="41", fee_budget="1"),
        demand("sell", -10, inventory=10, sellable=8, locked=7),
    )
    assert [(o.side, o.quantity) for o in p.external_orders] == [("buy", 3)]
    a = rows(allocate_external_fills(p, [fill(quantity=3)]))
    assert (a["buy"].quantity_delta, a["buy"].residual) == (4, 6)
    assert (a["sell"].quantity_delta, a["sell"].residual) == (-1, -9)
    assert allocate_external_fills(plan(demand("x", 1, blocked=True)), []).deltas[0].residual == 1
    assert plan(demand("x", -2, sellable=0)).external_orders == ()


def test_duplicate_physical_report_is_idempotent_but_conflicts_fail():
    p = plan(demand("a", 3))
    f = fill(quantity=2, fee="0.01")
    assert allocate_external_fills(p, [f, dict(f)]) == allocate_external_fills(p, [f])
    with pytest.raises(ValueError, match="conflicting"):
        allocate_external_fills(p, [f, {**f, "fee": "0.02"}])
    # Pure batch attribution is repeatable, never an implicit lifetime ledger.
    assert allocate_external_fills(p, [f]) == allocate_external_fills(p, [f])


@pytest.mark.parametrize(
    "change",
    [
        {"quantity": 4},
        {"side": "sell"},
        {"symbol": "B"},
        {"price": "11", "gross_amount": "11"},
        {"fee": "1.01"},
        {"fee": "0.001"},
        {"gross_amount": "9.99"},
        {"quantity": True},
        {"ts_ns": 0},
        {"fill_id": ""},
    ],
)
def test_incompatible_actual_fill_rejects_without_mutation(change):
    p = plan(demand("a", 3))
    f = {**fill(), **change}
    before = dict(f)
    with pytest.raises(ValueError):
        allocate_external_fills(p, [f])
    assert f == before
    assert allocate_external_fills(p, []).pooled_cash_delta == 0


def test_actual_fee_allocation_must_fit_each_reservation_without_redistribution():
    p = plan(demand("a", 1, fee_budget="0"), demand("b", 1))
    with pytest.raises(ValueError, match="fee reservation"):
        allocate_external_fills(p, [fill(quantity=2, fee="0.01")])


@pytest.mark.parametrize(
    "change",
    [
        {"inventory": -1},
        {"sellable": 2, "inventory": 1},
        {"locked": True},
        {"quantity": 1.5},
        {"cash_budget": "NaN"},
        {"fee_budget": "0.001"},
        {"max_buy_price": "9"},
        {"max_buy_price": None},
        {"lot_size": 0},
        {"blocked": 1},
        {"sleeve": ""},
    ],
)
def test_invalid_declarations_fail(change):
    with pytest.raises(ValueError):
        plan(replace(demand("a", 1), **change))


def test_unique_rows_common_lots_and_supported_policy_are_explicit():
    with pytest.raises(ValueError, match="unique"):
        plan(demand("a", 1), demand("a", 1))
    with pytest.raises(ValueError, match="lot"):
        plan(demand("a", 100, lot_size=100), demand("b", 100))
    with pytest.raises(ValueError, match="lot"):
        plan(demand("a", 101, lot_size=100))
    with pytest.raises(ValueError, match="policy"):
        net_sleeve_demands([demand("a", 1)], reference_prices={"A": "10"}, policy="broker")


def owner_fills(result):
    # Owner has no physical fill ID: fixture assigns source row identity once.
    return [
        {
            "fill_id": f"owner-row-{i}",
            "ts_ns": int(f.time.value),
            "symbol": f.symbol,
            "side": f.side,
            "quantity": int(f.quantity),
            "price": str(f.price),
            "gross_amount": str(f.gross_amount),
            "fee": str(f.transaction_cost),
        }
        for i, f in enumerate(result.fills.itertuples())
    ]


def test_real_owner_consumes_one_capacity_and_impact_budget_then_allocates_once():
    p = plan(
        demand("a", 500, cash_budget="6000", max_buy_price="11", lot_size=100),
        demand("b", 500, cash_budget="6000", max_buy_price="11", lot_size=100),
    )
    assert len(p.external_orders) == 1
    impact = LinearImpact(permanent=0.002)
    result = simulate_minute_execution(
        targets(weights=(5 / 6,)),
        bars(("2026-01-05 09:29", "2026-01-05 09:32")),
        MinuteExecutionConfig(12000, 0.1, 0, 0, commission_minimum_cny=1),
        impact_model=impact,
    )
    assert result.orders.quantity.tolist() == [p.external_orders[0].quantity]
    assert result.fills.quantity.tolist() == [100]  # 10% of one 1000-share bar
    assert result.fills.price.tolist() == [10.1]  # half of 0.002 * 100
    assert impact.checkpoint()["states"]["A"]["permanent"] == 0.2
    supplied = owner_fills(result)
    assert supplied[0]["gross_amount"] == "1010.0"
    assert supplied[0]["fee"] == "1.0"
    a = allocate_external_fills(p, supplied + supplied)
    assert [r.external_quantity for r in a.deltas] == [100, 0]
    assert a.pooled_cash_delta == Decimal("-1011")
    assert a.pooled_fee == 1
    assert sum(r.quantity_delta for r in a.deltas) == result.fills.quantity.sum()
    assert Decimal(str(result.daily.iloc[-1].cash)) == Decimal(12000) + a.pooled_cash_delta
    assert impact.checkpoint()["states"]["A"]["permanent"] == 0.2


def test_restricted_finite_exit_reuses_real_owner_cash_residuals_and_exit_wealth():
    t = targets(("2026-01-05 09:30", "2026-01-06 09:30", "2026-01-07 09:30"), (0.5, 0, 0))
    b = bars(tuple(f"2026-01-{d:02} {m}" for d in (5, 6, 7) for m in ("09:29", "09:32")))
    b.loc[b.time.dt.day == 7, "volume"] = 200
    b["amount"] = b.volume * 10
    result = MinuteSession(
        t,
        b,
        MinuteExecutionConfig(10000, 0.5, 0, 0),
        policy=Policy(),
        quantity_locks=(notice("2026-01-06 09:00", "2026-01-06 15:00"),),
    ).run()
    assert result.fills.side.tolist() == ["buy", "sell"]
    assert result.fills.quantity.tolist() == [500, 100]
    sale = owner_fills(result)[1]
    p = plan(demand("exit", -500, inventory=500, sellable=500))
    a = allocate_external_fills(p, [sale])
    assert (a.deltas[0].quantity_delta, a.deltas[0].residual) == (-100, -400)
    assert a.pooled_cash_delta == 1000
    cash = Decimal(str(result.daily.iloc[-1].cash))
    assert cash == 6000
    assert result.holdings.iloc[-1].quantity == 400
    clock = int(pd.Timestamp("2026-01-07 09:32", tz="Asia/Shanghai").value)
    marks = {"A": {"price": "10", "ts_ns": clock}}
    report = exit_wealth(cash, {"A": 400}, marks, as_of_ns=clock, max_mark_age_ns=0)
    assert report["marked_wealth"] == 10000
    assert report["residual_marked_value"] == 4000
    assert report["cash_realized_wealth"] is None
    assert (
        exit_wealth(cash, {"A": 400}, marks, as_of_ns=clock + 1, max_mark_age_ns=0)["marked_wealth"]
        is None
    )
    assert (
        exit_wealth(cash, {}, {}, as_of_ns=clock, max_mark_age_ns=0, receivable="1")[
            "cash_realized_wealth"
        ]
        is None
    )


def test_decimal_context_is_exact_and_extremes_fail_explicitly():
    with localcontext() as c:
        c.prec = 2
        a = allocate_external_fills(plan(demand("a", 3)), [fill(quantity=3, fee="0.05")])
        assert a.pooled_cash_delta == Decimal("-30.05")
    with pytest.raises(ValueError, match="exact"):
        plan(demand("a", 1, cash_budget="1e100"))


def test_lock_is_subset_of_prelock_sellable_inventory_not_an_unknown_overlap():
    with pytest.raises(ValueError, match="inventory"):
        plan(demand("a", -10, inventory=10, sellable=2, locked=3))


def test_multiple_symbols_and_sell_fees_reconcile_full_initial_economic_state():
    ds = [
        demand("buyer", 5),
        demand("seller", -8),
        demand("buyer", 2, symbol="B"),
        demand("seller", 2, symbol="B"),
    ]
    p = net_sleeve_demands(ds, reference_prices={"A": "10", "B": "10"})
    sale = fill("sale", 2, price="9", fee="0.03", side="sell")
    purchase = {**fill("purchase", 3, fee="0.01"), "symbol": "B"}
    a = allocate_external_fills(p, [sale, purchase])
    assert [(o.symbol, o.side, o.quantity) for o in p.external_orders] == [
        ("A", "sell", 3),
        ("B", "buy", 4),
    ]
    assert a.pooled_quantities == (("A", -2), ("B", 3))
    assert a.pooled_cash_delta == Decimal("-12.04")
    assert a.pooled_fee == Decimal("0.04")
    assert sum(d.cash_delta for d in a.deltas) == Decimal("-12.04")
    assert sum(d.fee for d in a.deltas) == Decimal("0.04")
    assert sum(d.quantity_delta for d in a.deltas if d.symbol == "A") == -2
    assert sum(d.quantity_delta for d in a.deltas if d.symbol == "B") == 3
    seller = next(d for d in a.deltas if d.sleeve == "seller" and d.symbol == "A")
    assert (seller.quantity_delta, seller.cash_delta, seller.residual) == (-7, Decimal("67.97"), -1)
    # Initial cash2000 and inventory A8 -> cash1987.96 and inventory A6+B3.
    assert Decimal(2000) + sum(d.cash_delta for d in a.deltas) == Decimal("1987.96")
    assert 8 + sum(d.quantity_delta for d in a.deltas if d.symbol == "A") == 6


def test_partial_parent_fee_is_not_recomputed_and_fee_reservation_is_cumulative():
    p = plan(demand("a", 4, fee_budget="0.03"))
    reports = [fill("first", 1, fee="0.03"), fill("second", 1, at=2)]
    a = allocate_external_fills(p, [*reports, reports[0]])
    assert (a.pooled_fee, a.pooled_cash_delta, a.deltas[0].residual) == (
        Decimal("0.03"),
        Decimal("-20.03"),
        2,
    )
    with pytest.raises(ValueError, match="fee reservation"):
        allocate_external_fills(p, [*reports, fill("third", 1, fee="0.01", at=3)])


def test_declared_maximum_price_reserves_slippage_and_preserves_raw_decimal_provenance():
    p = plan(demand("a", 5, cash_budget="45", fee_budget="1", max_buy_price="11"))
    assert p.external_orders[0].quantity == 4
    a = allocate_external_fills(p, [fill(quantity=4, price="11", fee="1")])
    assert a.deltas[0].cash_delta == Decimal("-45")
    assert a.deltas[0].residual == 1
    assert a.fills[0].gross_amount == Decimal("44")
    # No independent per-sleeve penny rounding: subcent raw prices remain exact.
    a = allocate_external_fills(
        plan(demand("a", 1), demand("b", 1)), [fill(quantity=2, price="9.999", fee="0.01")]
    )
    assert [d.cash_delta for d in a.deltas] == [Decimal("-10.009"), Decimal("-9.999")]
    assert a.pooled_cash_delta == Decimal("-20.008")


def test_fractional_external_lots_and_binary_gross_inconsistency_are_rejected():
    p = plan(demand("a", 200, cash_budget="3000", lot_size=100))
    with pytest.raises(ValueError, match="lot"):
        allocate_external_fills(p, [fill(quantity=1)])
    # Caller must not silently round away a raw owner's inconsistent gross.
    p = plan(demand("a", 3))
    f = fill(quantity=3, price="0.1")
    with pytest.raises(ValueError, match="gross"):
        allocate_external_fills(p, [{**f, "price": 0.1, "gross_amount": 3 * 0.1}])
