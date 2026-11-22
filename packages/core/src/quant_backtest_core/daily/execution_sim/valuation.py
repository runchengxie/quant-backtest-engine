"""Endpoint coverage from the live owner ledger; never price or reconstruct NAV."""

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .capacity import _price_at

VALUATION_MARK_COLUMNS = [
    "trade_date",
    "held_symbols",
    "held_count",
    "stock_receivable_symbols",
    "required_marks",
    "current_marks",
    "missing_symbols",
    "cash_complete",
    "receivables_complete",
    "endpoint_complete",
    "reason",
]


def endpoint_marks(
    *,
    day: pd.Timestamp,
    shares: Mapping[str, float],
    cash: float,
    price_table: pd.DataFrame,
    stock_receivables: Mapping[str, float] | None = None,
    cash_receivable: float = 0.0,
    stock_receivable_value: float = 0.0,
) -> dict[str, Any]:
    """Attest current marks for positive holdings/stock rights at this endpoint.

    The supplied amounts come from the existing cash/rights ledger. A carried
    valuation remains untouched but cannot satisfy current-price evidence.
    """
    stock = stock_receivables or {}
    held = tuple(sorted(symbol for symbol, quantity in shares.items() if quantity > 0))
    rights = tuple(sorted(symbol for symbol, quantity in stock.items() if quantity > 0))
    required = set(held) | set(rights)
    missing = tuple(
        sorted(
            symbol for symbol in required if not np.isfinite(_price_at(symbol, day, price_table))
        )
    )
    quantities_ok = all(np.isfinite(q) and q >= 0 for q in (*shares.values(), *stock.values()))
    cash_ok = bool(np.isfinite(cash))
    rights_ok = bool(np.isfinite(cash_receivable) and np.isfinite(stock_receivable_value))
    reasons = []
    if missing:
        reasons.append("missing_current_price")
    if not quantities_ok:
        reasons.append("invalid_position_quantity")
    if not cash_ok:
        reasons.append("nonfinite_cash")
    if not rights_ok:
        reasons.append("nonfinite_receivable")
    if not reasons:
        reasons.append(
            "current_marks"
            if required
            else "cash_and_receivables"
            if cash_receivable
            else "cash_only"
        )
    return {
        "trade_date": day.strftime("%Y%m%d"),
        "held_symbols": held,
        "held_count": len(held),
        "stock_receivable_symbols": rights,
        "required_marks": len(required),
        "current_marks": len(required) - len(missing),
        "missing_symbols": missing,
        "cash_complete": cash_ok,
        "receivables_complete": rights_ok,
        "endpoint_complete": bool(not missing and quantities_ok and cash_ok and rights_ok),
        "reason": ";".join(reasons),
    }
