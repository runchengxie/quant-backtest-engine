# Extracted from quant-platform/packages/platform/src/quant_platform/analytics/execution_integrity.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Recorded-fill reconciliation and conditional exit wealth; never a matcher."""

from collections import defaultdict
from decimal import Decimal
from itertools import pairwise

from ._exact import _clock, _decimal, _exact


def _shares(value):
    number = _decimal(value, minimum=0)
    if number != number.to_integral_value():
        raise ValueError("raw integer shares required")
    return number


def _quantities(values):
    if any(not isinstance(s, str) or not s.strip() for s in values):
        raise ValueError("nonempty symbol required")
    return {s: _shares(q) for s, q in values.items() if _shares(q)}


@_exact
def fill_prefixes(fills, initial_cash, initial_quantities=None):
    """Group fills at identical clocks; reconstruct balances, not hidden venue state.

    Fill identities must be assigned from actual source evidence. This audit does
    not prove cash admission, T+1, queue order or fees beyond supplied fill rows.
    """
    cash = _decimal(initial_cash, minimum=0)
    quantities = _quantities(initial_quantities or {})
    rows = [{"ts_ns": 0, "cash": cash, "quantities": dict(quantities)}]
    groups = defaultdict(list)
    seen = set()
    for fill in fills:
        ident = fill["fill_id"]
        if not isinstance(ident, str) or not ident.strip() or ident in seen:
            raise ValueError("unique recorded fill identity required")
        seen.add(ident)
        groups[_clock(fill["ts_ns"])].append(fill)
    for time, group in sorted(groups.items()):
        for fill in group:
            symbol, side = fill["symbol"], fill["side"]
            if not isinstance(symbol, str) or not symbol.strip() or side not in {"buy", "sell"}:
                raise ValueError("valid symbol and side required")
            quantity, price, fee = (
                _shares(fill["quantity"]),
                _decimal(fill["price"], minimum=0),
                _decimal(fill["fee"], minimum=0),
            )
            if not quantity or not price:
                raise ValueError("positive quantity and price required")
            signed = quantity if side == "buy" else -quantity
            cash -= signed * price + fee
            quantities[symbol] = quantities.get(symbol, Decimal(0)) + signed
        if any(q < 0 for q in quantities.values()):
            raise ValueError("long-only fill prefix oversells holdings")
        quantities = {s: q for s, q in quantities.items() if q}
        rows.append({"ts_ns": time, "cash": cash, "quantities": dict(sorted(quantities.items()))})
    return rows


@_exact
def compare_prefixes(left, right, *, cash_atol="0.00000001"):
    """Retain divergent clock states, including first divergence and convergence."""
    tolerance = _decimal(cash_atol, minimum=0)
    for rows in (left, right):
        if (
            not rows
            or rows[0]["ts_ns"] != 0
            or any(a["ts_ns"] >= b["ts_ns"] for a, b in pairwise(rows))
        ):
            raise ValueError("ordered unique prefixes with initial state required")
    a, b = left[0], right[0]
    ai, bi = 0, 0
    differences = []
    for time in sorted({r["ts_ns"] for r in left + right}):
        while ai + 1 < len(left) and left[ai + 1]["ts_ns"] <= time:
            ai += 1
            a = left[ai]
        while bi + 1 < len(right) and right[bi + 1]["ts_ns"] <= time:
            bi += 1
            b = right[bi]
        if abs(a["cash"] - b["cash"]) > tolerance or a["quantities"] != b["quantities"]:
            differences.append({"ts_ns": time, "left": a, "right": b})
    return differences


@_exact
def exit_wealth(cash, quantities, marks, *, as_of_ns, max_mark_age_ns, receivable="0"):
    """Mark residual shares explicitly; only an empty settled book is realized cash."""
    _clock(as_of_ns)
    if type(max_mark_age_ns) is not int or max_mark_age_ns < 0:
        raise ValueError("nonnegative integer mark age required")
    cash, receivable = _decimal(cash), _decimal(receivable, minimum=0)
    quantities = _quantities(quantities)
    missing, value, evidence = [], Decimal(0), {}
    for symbol, quantity in sorted(quantities.items()):
        mark = marks.get(symbol)
        if mark is None:
            missing.append(symbol)
            continue
        time = _clock(mark["ts_ns"])
        price = _decimal(mark["price"], minimum=0)
        evidence[symbol] = {"price": price, "ts_ns": time}
        if not price or not 0 <= as_of_ns - time <= max_mark_age_ns:
            missing.append(symbol)
            continue
        value += quantity * price
    return {
        "as_of_ns": as_of_ns,
        "max_mark_age_ns": max_mark_age_ns,
        "mark_evidence": evidence,
        "cash": cash,
        "receivable": receivable,
        "residual_quantities": quantities,
        "unpriced_symbols": missing,
        "residual_marked_value": None if missing else value,
        "marked_wealth": None if missing else cash + value + receivable,
        "cash_realized_wealth": cash if not quantities and not receivable else None,
        "basis": "supplied_raw_marks_not_executable_liquidation_quote",
    }
