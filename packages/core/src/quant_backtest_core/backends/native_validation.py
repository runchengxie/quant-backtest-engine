"""Preflight native v2 semantics, not an execution or accounting implementation.

Mirrors src/session_contract.rs validation. Rust validates the request again
before constructing its financial owner; this adapter never repairs inputs.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from ..errors import ProductError


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ProductError(message)


def _amount(value: str, precision: int, maximum: int, positive: bool = False) -> Decimal:
    number = Decimal(value)
    scale = max(0, -int(number.as_tuple().exponent))
    _require(
        scale <= precision and 0 <= number <= maximum and (not positive or number > 0),
        "decimal outside native supported range or precision",
    )
    return number


def _identifier(value: str) -> bool:
    return re.fullmatch(r"[A-Za-z0-9_-]{1,40}", value) is not None


def _timestamp(value: int) -> None:
    _require(0 < value <= 4_102_444_800_000_000_000, "timestamp outside native range")


def validate_native(request: dict[str, Any], zone_name: str) -> None:
    _require(request["currency"] in {"CNY", "USD"}, "unsupported native currency")
    _require(request["price_basis"] == "raw", "native sessions require raw share basis")
    expected_zone = "Asia/Shanghai" if request["currency"] == "CNY" else "UTC"
    _require(zone_name == expected_zone, "timezone differs from native valuation timezone")
    zone = ZoneInfo(zone_name)
    _amount(request["initial_cash"], 2, 1_000_000_000_000, True)
    _amount(request["fee_bps"], 4, 10000)
    instruments = {row["symbol"]: row for row in request["instruments"]}
    _require(
        bool(instruments) and bool(request["sessions"]), "sessions and instruments are required"
    )
    for symbol in instruments:
        _require(_identifier(symbol), "invalid native instrument identifier")
    previous_close = 0
    last_date = ""
    ids: set[str] = set()
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    for session in request["sessions"]:
        opened, closed = session["open_ts_ns"], session["valuation_ts_ns"]
        _timestamp(opened)
        _timestamp(closed)
        _require(session["session_date"] > last_date, "session dates must increase")
        _require(opened > previous_close and closed >= opened, "overlapping session boundaries")
        for clock in (opened, closed):
            # Integer division retains the date without a floating-point timestamp conversion.
            date = (epoch + timedelta(seconds=clock // 1_000_000_000)).astimezone(zone).date()
            _require(date.isoformat() == session["session_date"], "session local date mismatch")
        last: dict[str, int] = {}
        global_clock = opened
        for quote in session["quotes"]:
            symbol, clock = quote["symbol"], quote["ts_ns"]
            _require(symbol in instruments, "unknown quote instrument")
            _require(
                global_clock <= clock <= closed and clock > last.get(symbol, -1),
                "unordered or duplicate quotes",
            )
            precision = instruments[symbol]["price_precision"]
            bid = _amount(quote["bid"], precision, 1_000_000, True)
            ask = _amount(quote["ask"], precision, 1_000_000, True)
            _require(bid <= ask, "crossed quote")
            _amount(quote["bid_size"], 0, 1_000_000)
            _amount(quote["ask_size"], 0, 1_000_000)
            last[symbol] = global_clock = clock
        _require(
            set(last) == set(instruments) and all(t == closed for t in last.values()),
            "every instrument requires a fresh valuation quote",
        )
        for order in session["orders"]:
            _require(
                _identifier(order["id"])
                and order["id"] not in ids
                and order["symbol"] in instruments,
                "invalid or duplicate order",
            )
            ids.add(order["id"])
            _timestamp(order["information_ts_ns"])
            _require(
                previous_close <= order["information_ts_ns"] <= closed,
                "order information outside decision window",
            )
            _amount(order["quantity"], 0, 1_000_000, True)
        previous_close, last_date = closed, session["session_date"]
