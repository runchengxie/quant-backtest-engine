# Extracted from quant-platform/tests/test_execution_integrity.py at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355.
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
from decimal import Decimal

import pytest

from quant_backtest_core.evidence.execution_integrity import (
    compare_prefixes,
    exit_wealth,
    fill_prefixes,
)


def fill(ident="f", at=10, side="buy", quantity="100", price="10", fee="1"):
    return {
        "fill_id": ident,
        "ts_ns": at,
        "symbol": "A",
        "side": side,
        "quantity": quantity,
        "price": price,
        "fee": fee,
    }


def test_prefix_detects_interior_difference_even_when_final_cash_and_shares_match():
    left = fill_prefixes([fill(), fill("s", 20, "sell", price="12")], "10000")
    right = fill_prefixes([fill(price="10.01"), fill("s", 20, "sell", price="12.01")], "10000")
    assert left[-1] == right[-1]
    differences = compare_prefixes(left, right)
    assert differences[0]["ts_ns"] == 10
    assert differences[0]["left"]["cash"] == Decimal("8999")
    assert differences[0]["right"]["cash"] == Decimal("8998")


def test_simultaneous_fills_compare_after_entire_clock_and_duplicate_ids_fail():
    rows = [fill(), fill("second", side="sell", price="11")]
    assert fill_prefixes(rows, "10000") == fill_prefixes(list(reversed(rows)), "10000")
    with pytest.raises(ValueError, match="identity"):
        fill_prefixes([fill(), fill()], "10000")


@pytest.mark.parametrize(
    "updates", [{"quantity": "1.5"}, {"price": "NaN"}, {"fee": "-1"}, {"ts_ns": True}]
)
def test_invalid_fill_contract_is_rejected(updates):
    with pytest.raises(ValueError):
        fill_prefixes([{**fill(), **updates}], "10000")


def test_unsold_inventory_is_never_reported_as_cash_and_stale_marks_are_unknown():
    marks = {"A": {"price": "10", "ts_ns": 90}}
    report = exit_wealth("100", {"A": 20}, marks, as_of_ns=100, max_mark_age_ns=10)
    assert report["marked_wealth"] == Decimal("300")
    assert report["cash_realized_wealth"] is None
    stale = exit_wealth("100", {"A": 20}, marks, as_of_ns=101, max_mark_age_ns=10)
    assert stale["marked_wealth"] is None
    assert stale["unpriced_symbols"] == ["A"]
    assert exit_wealth("300", {}, {}, as_of_ns=100, max_mark_age_ns=10)[
        "cash_realized_wealth"
    ] == Decimal("300")
    assert (
        exit_wealth("300", {}, {}, as_of_ns=100, max_mark_age_ns=10, receivable="1")[
            "cash_realized_wealth"
        ]
        is None
    )


def test_accounting_ignores_ambient_precision_and_rejects_inexact_extremes():
    from decimal import localcontext

    with localcontext() as context:
        context.prec = 4
        left = fill_prefixes([fill(fee="1")], "100000")
        right = fill_prefixes([fill(fee="2")], "100000")
        assert compare_prefixes(left, right)[0]["right"]["cash"] == Decimal("98998")
        marked = exit_wealth(
            "100000",
            {"A": 1},
            {"A": {"price": "1.01", "ts_ns": 10}},
            as_of_ns=10,
            max_mark_age_ns=0,
        )
        assert marked["marked_wealth"] == Decimal("100001.01")
    a = fill_prefixes([fill(quantity="1", price="1", fee="0")], "1e29")
    b = fill_prefixes([fill(quantity="1", price="2", fee="0")], "1e29")
    assert compare_prefixes(a, b)
    with pytest.raises(ValueError, match="exact"):
        fill_prefixes([fill()], "1e100")


def test_exit_report_retains_mark_prices_clocks_and_freshness_contract():
    result = exit_wealth(
        "1", {"A": 1}, {"A": {"price": "2", "ts_ns": 90}}, as_of_ns=100, max_mark_age_ns=10
    )
    assert result["as_of_ns"] == 100
    assert result["max_mark_age_ns"] == 10
    assert result["mark_evidence"] == {"A": {"price": Decimal("2"), "ts_ns": 90}}
