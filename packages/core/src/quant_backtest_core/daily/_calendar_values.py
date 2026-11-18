"""Legacy calendar labels/parsers only; never resolves or fetches sessions."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

MARKET_CALENDAR = "market"
HK_CONNECT_CALENDAR = "hk_connect"

_MARKET_ALIASES = {
    "",
    "market",
    "hk_market",
    "trading",
    "trading_calendar",
    "data",
}
_HK_CONNECT_ALIASES = {
    "hk_connect",
    "stock_connect",
    "southbound",
    "southbound_connect",
    "connect",
}


def normalize_execution_calendar(value: object | None) -> str:
    text = str(value or MARKET_CALENDAR).strip().lower().replace("-", "_")
    if text in _MARKET_ALIASES:
        return MARKET_CALENDAR
    if text in _HK_CONNECT_ALIASES:
        return HK_CONNECT_CALENDAR
    raise ValueError("execution.calendar must be one of: market, hk_connect.")


def coerce_date_set(values: object | None) -> tuple[pd.Timestamp, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, pd.Timestamp)):
        raw_values: Iterable[object] = [values]
    elif isinstance(values, Iterable):
        raw_values = values
    else:
        raw_values = [values]

    dates: list[pd.Timestamp] = []
    for value in raw_values:
        text = str(value).strip()
        if not text:
            continue
        compact = text.replace("-", "")
        parsed = (
            pd.to_datetime(compact, format="%Y%m%d", errors="coerce")
            if compact.isdigit() and len(compact) == 8
            else pd.to_datetime(text, errors="coerce")
        )
        if pd.isna(parsed):
            raise ValueError(f"Invalid execution calendar date: {value}")
        dates.append(parsed.normalize())
    return tuple(sorted(set(dates)))
