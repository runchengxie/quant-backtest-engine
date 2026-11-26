"""Read-only financial components captured from the live adjusted daily owner."""

from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np

SYMBOL_ATTRIBUTION_COLUMNS = [
    "trade_date",
    "symbol",
    "opening_value",
    "closing_value",
    "buy_principal",
    "sell_principal",
    "fees",
    "net_pnl",
    "policy_valued",
    "status",
]
DAILY_ATTRIBUTION_COLUMNS = [
    "trade_date",
    "opening_equity",
    "closing_equity",
    "symbol_net_pnl",
    "cash_pnl",
    "receivable_pnl",
    "residual",
    "status",
]


def endpoint_attribution(
    *,
    opening_values: Mapping[str, float],
    closing_values: Mapping[str, float],
    fills: Sequence[Mapping[str, Any]],
    opening_equity: float,
    closing_equity: float,
    opening_complete: bool,
    marks: Mapping[str, Any],
    corporate_actions: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Decompose a completed owner interval; never mutate/reconstruct financial state.

    The caller supplies actual owner endpoint values and this session's fills.
    No cash flows, interest or separate corporate-action cash/rights are supported.
    A residual remains evidence, never a balancing allocation.
    """
    status = (
        "unsupported_corporate_actions"
        if corporate_actions
        else "incomplete_valuation"
        if not opening_complete or not marks["endpoint_complete"]
        else "complete"
    )
    components: dict[str, dict[str, float]] = {}
    for fill in fills:
        symbol = fill["symbol"]
        item = components.setdefault(symbol, {"buy": 0.0, "sell": 0.0, "fees": 0.0})
        item[fill["side"]] += float(fill["filled_notional"])
        item["fees"] += float(fill["transaction_cost"])
    rows = []
    for symbol in sorted(set(opening_values) | set(closing_values) | set(components)):
        item = components.get(symbol, {"buy": 0.0, "sell": 0.0, "fees": 0.0})
        opening, closing = opening_values.get(symbol, 0.0), closing_values.get(symbol, 0.0)
        rows.append(
            {
                "trade_date": marks["trade_date"],
                "symbol": symbol,
                "opening_value": opening,
                "closing_value": closing,
                "buy_principal": item["buy"],
                "sell_principal": item["sell"],
                "fees": item["fees"],
                "net_pnl": closing - opening - item["buy"] + item["sell"] - item["fees"],
                "policy_valued": symbol in marks["policy_valued_symbols"],
                "status": status,
            }
        )
    total = sum(row["net_pnl"] for row in rows)
    residual = closing_equity - opening_equity - total if status == "complete" else np.nan
    if status == "complete" and (
        not np.isfinite(residual)
        or abs(residual) > 1e-8 + 1e-10 * max(abs(opening_equity), abs(closing_equity), 1.0)
    ):
        status = "unreconciled"
    for row in rows:
        row["status"] = status
        if status != "complete":
            row["net_pnl"] = np.nan
    return rows, {
        "trade_date": marks["trade_date"],
        "opening_equity": opening_equity,
        "closing_equity": closing_equity,
        "symbol_net_pnl": total if status == "complete" else np.nan,
        "cash_pnl": 0.0 if status == "complete" else np.nan,
        "receivable_pnl": 0.0 if status == "complete" else np.nan,
        "residual": residual,
        "status": status,
    }
