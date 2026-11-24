"""Endpoint coverage from the live owner ledger; never price or reconstruct NAV."""

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from .capacity import _price_at
from .config import ExecutionSimConfig

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
    "valuation_policy",
    "policy_valued_symbols",
    "policy_quote_dates",
    "policy_quote_ages",
    "unresolved_symbols",
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
    config: ExecutionSimConfig | None = None,
    last_prices: Mapping[str, float] | None = None,
    suspension_table: pd.DataFrame | None = None,
    trade_dates: list[pd.Timestamp] | None = None,
) -> dict[str, Any]:
    """Attest current marks for positive holdings/stock rights at this endpoint.

    Amounts come from the existing ledger. Carried prices never become current
    evidence; explicit adjusted suspension policy may certify them separately.
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
    policy = config.valuation_policy if config is not None else "current_mark_only"
    quote_dates: dict[str, str] = {}
    quote_ages: dict[str, int] = {}
    if (
        policy == "suspended_last_quote"
        and suspension_table is not None
        and trade_dates is not None
    ):
        # Only actual strictly prior quotes matching the live financial owner's
        # price qualify. Never fill the executable table or search future rows.
        sessions = {date: index for index, date in enumerate(trade_dates)}
        for symbol in missing:
            if day not in suspension_table.index or symbol not in suspension_table.columns:
                continue
            flag = suspension_table.at[day, symbol]
            if not (isinstance(flag, (bool, np.bool_)) and bool(flag)):
                continue
            held_price = (last_prices or {}).get(symbol, np.nan)
            if not np.isfinite(held_price) or held_price <= 0:
                continue
            if day not in sessions or config is None or config.valuation_max_stale_sessions is None:
                continue
            index = sessions[day]
            earliest = max(0, index - config.valuation_max_stale_sessions)
            source = next(
                (
                    date
                    for date in reversed(trade_dates[earliest:index])
                    if date < day and np.isfinite(_price_at(symbol, date, price_table))
                ),
                None,
            )
            if source is None or _price_at(symbol, source, price_table) != held_price:
                continue
            age = index - sessions[source]
            if age <= 0:
                continue
            quote_dates[symbol] = source.strftime("%Y-%m-%d")
            quote_ages[symbol] = age
    unresolved = tuple(symbol for symbol in missing if symbol not in quote_dates)
    quantities_ok = all(np.isfinite(q) and q >= 0 for q in (*shares.values(), *stock.values()))
    cash_ok = bool(np.isfinite(cash))
    rights_ok = bool(np.isfinite(cash_receivable) and np.isfinite(stock_receivable_value))
    reasons = []
    if unresolved:
        reasons.append("missing_current_price")
    if quote_dates:
        reasons.append("suspended_last_quote")
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
        "endpoint_complete": bool(not unresolved and quantities_ok and cash_ok and rights_ok),
        "reason": ";".join(reasons),
        "valuation_policy": policy,
        "policy_valued_symbols": tuple(sorted(quote_dates)),
        "policy_quote_dates": tuple(quote_dates[symbol] for symbol in sorted(quote_dates)),
        "policy_quote_ages": tuple(quote_ages[symbol] for symbol in sorted(quote_dates)),
        "unresolved_symbols": unresolved,
    }
