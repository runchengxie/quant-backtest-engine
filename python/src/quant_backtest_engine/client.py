"""Opt-in subprocess boundary to the independent engine; no sizing or matching logic."""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
import tempfile
from collections import defaultdict
from datetime import UTC, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Any

from zoneinfo import ZoneInfo


class EngineProtocolError(ValueError):
    """The selected engine failed or returned inconsistent wire evidence."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EngineProtocolError(message)


def _number(value: Any, *, integer: bool = False) -> Decimal:
    _require(
        isinstance(value, str) and bool(re.fullmatch(r"-?\d+(?:\.\d+)?", value)),
        "expected finite decimal string",
    )
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise EngineProtocolError("invalid decimal") from exc
    _require(result.is_finite() and result >= 0, "expected nonnegative finite decimal")
    _require(not integer or result == result.to_integral_value(), "expected integer quantity")
    return result


def _unique(rows: list[dict], key: str) -> dict:
    result = {row[key]: row for row in rows}
    _require(len(result) == len(rows), f"duplicate {key}")
    return result


def _equal(left: Decimal, right: Decimal) -> None:
    _require(left == right, "inconsistent monetary evidence")


class EngineClient:
    """Explicit content-pinned executable client. Wire requests stay engine-owned.

    ``size`` produces estimates; execution independently checks actual cash.
    ``run_sessions`` only accepts raw-price v2 sessions. No default registration.
    """

    def __init__(
        self,
        executable: Path,
        sha256: str,
        *,
        timeout: float = 30,
        source_revision: str | None = None,
    ) -> None:
        executable = Path(executable)
        if not executable.is_absolute() or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("select an absolute executable and lowercase SHA256 digest")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be finite and positive")
        self.executable = executable
        self.sha256 = sha256
        self.timeout = timeout
        self.source_revision = source_revision

    def _invoke(self, command: str, request: dict, schema: str) -> dict:
        try:
            _require(request["schema_version"] == schema, "unsupported request schema")
            payload = json.dumps(request, allow_nan=False)
            executable_bytes = self.executable.read_bytes()
            _require(
                hashlib.sha256(executable_bytes).hexdigest() == self.sha256,
                "executable digest mismatch",
            )
            with tempfile.TemporaryDirectory(prefix="quant-engine-") as directory:
                snapshot = Path(directory) / "verified-engine"
                snapshot.write_bytes(executable_bytes)
                snapshot.chmod(0o700)
                path = Path(directory) / "request.json"
                path.write_text(payload, encoding="utf-8")
                process = subprocess.run(
                    [str(snapshot), command, str(path)],
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    check=False,
                    cwd=directory,
                )
            _require(process.returncode == 0, f"engine failed: {process.stderr.strip()}")
            result = json.loads(
                process.stdout, parse_constant=_reject_constant, object_pairs_hook=_json_object
            )
            _require(isinstance(result, dict), "expected result object")
            return result
        except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, EngineProtocolError):
                raise
            raise EngineProtocolError(f"engine protocol failure: {exc}") from exc

    def size(self, request: dict) -> dict:
        """Return validated engine-owned sizing wire output, never execution evidence."""
        result = self._invoke("size", request, "sizing_request.v1")
        try:
            _sizing_shape(result)
            _require(result["schema_version"] == "sizing_result.v1", "unsupported sizing result")
            _require(result["currency"] == request["currency"], "currency mismatch")
            _number(result["marked_equity"])
            _number(result["projected_cash"])
            assets = _unique(request["assets"], "symbol")
            targets = _unique(result["targets"], "symbol")
            _require(set(targets) == set(assets), "sizing target coverage mismatch")
            changes = {}
            for symbol, target in targets.items():
                _number(target["desired_quantity"], integer=True)
                planned = _number(target["planned_quantity"], integer=True)
                changes[symbol] = planned - _number(assets[symbol]["held_quantity"], integer=True)
            _unique(result["orders"], "id")
            seen = set()
            for order in result["orders"]:
                symbol = order["symbol"]
                _require(symbol in assets and symbol not in seen, "invalid sizing order symbol")
                seen.add(symbol)
                quantity = _number(order["quantity"], integer=True)
                _require(quantity > 0 and order["side"] in ("buy", "sell"), "invalid sizing order")
                _require(
                    order["information_ts_ns"] == request["information_ts_ns"],
                    "sizing information timestamp mismatch",
                )
                signed = quantity if order["side"] == "buy" else -quantity
                _require(signed == changes[symbol], "sizing quantities do not reconcile")
                if order["side"] == "buy":
                    _require(quantity % assets[symbol]["buy_lot"] == 0, "invalid buy lot")
            _require(seen == {s for s, q in changes.items() if q}, "missing sizing orders")
        except (KeyError, TypeError, ArithmeticError, IndexError, AttributeError) as exc:
            raise EngineProtocolError(f"malformed sizing result: {exc}") from exc
        return result

    def run_sessions(self, request: dict) -> dict:
        """Return validated v2 wire evidence, preserving decimal strings and timestamps."""
        result = self._invoke("run", request, "engine_request.v2")
        try:
            with localcontext() as context:
                context.prec = 64
                return self._validate_sessions(request, result)
        except (
            KeyError,
            TypeError,
            ArithmeticError,
            ValueError,
            IndexError,
            AttributeError,
        ) as exc:
            if isinstance(exc, EngineProtocolError):
                raise
            raise EngineProtocolError(f"malformed session result: {exc}") from exc

    def _validate_sessions(self, request: dict, result: dict) -> dict:
        _session_shape(result)
        _require(result["schema_version"] == "engine_result.v2", "unsupported session result")
        for key in ("currency", "initial_cash", "price_basis", "enforce_t1"):
            _require(result[key] == request[key], f"{key} mismatch")
        zone = "Asia/Shanghai" if request["currency"] == "CNY" else "UTC"
        _require(result["valuation_timezone"] == zone, "valuation timezone mismatch")
        _require(request["price_basis"] == "raw", "raw prices required")
        _require(
            set(request["required_capabilities"]) <= set(result["capabilities"]),
            "missing requested capabilities",
        )
        sessions = _unique(request["sessions"], "session_date")
        daily = _unique(result["daily_ledger"], "session_date")
        _require(list(daily) == list(sessions), "session ledger coverage/order mismatch")
        fills_by_date, _, _ = _order_evidence(request, result, sessions, zone)
        _ledger_evidence(request, result, sessions, daily, fills_by_date, zone)
        return result


def _ledger_evidence(
    request: dict, result: dict, sessions: dict, daily: dict, fills_by_date, zone: str
):
    quantities = defaultdict(Decimal)
    cash = _number(result["initial_cash"])
    commission = Decimal(0)
    positions = {}
    for position in result["daily_positions"]:
        key = (position["session_date"], position["symbol"])
        _require(
            key not in positions
            and key[0] in daily
            and key[1] in {i["symbol"] for i in request["instruments"]},
            "invalid position identity",
        )
        positions[key] = position
        quantity = _number(position["quantity"], integer=True)
        _require(
            _number(position["mark_price"]) == _valuation_mark(sessions[key[0]], key[1]),
            "valuation mark mismatch",
        )
        _equal(_number(position["market_value"]), quantity * _number(position["mark_price"]))
    for day, balance in daily.items():
        session = sessions[day]
        _require(
            balance["valuation_ts_ns"] == session["valuation_ts_ns"],
            "valuation timestamp mismatch",
        )
        _require(
            datetime.fromtimestamp(session["valuation_ts_ns"] // 1_000_000_000, UTC)
            .astimezone(ZoneInfo(zone))
            .date()
            .isoformat()
            == day,
            "invalid local session date",
        )
        if request["enforce_t1"]:
            sold = defaultdict(Decimal)
            for fill in fills_by_date[day]:
                if fill["side"] == "sell":
                    sold[fill["symbol"]] += _number(fill["quantity"])
            _require(all(qty <= quantities[symbol] for symbol, qty in sold.items()),
                     "session sells violate T+1 eligibility")
        day_fee = Decimal(0)
        for fill in fills_by_date[day]:
            qty, price, fee = (_number(fill[k]) for k in ("quantity", "price", "commission"))
            signed = qty if fill["side"] == "buy" else -qty
            quantities[fill["symbol"]] += signed
            notional = (qty * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
            cash -= (notional if signed > 0 else -notional) + fee
            day_fee += fee
        commission += day_fee
        _equal(_number(balance["cash"]), cash)
        _equal(_number(balance["commission"]), day_fee)
        value = Decimal(0)
        for symbol, qty in quantities.items():
            position = positions.get((day, symbol))
            _require(qty >= 0 and (position is not None or qty == 0), "missing position")
            if position is not None:
                _require(_number(position["quantity"]) == qty, "position quantity mismatch")
        for (position_day, symbol), position in positions.items():
            if position_day != day:
                continue
            _require(
                _number(position["quantity"]) == quantities[symbol],
                "unexpected position quantity",
            )
            market_value = _number(position["market_value"])
            value += market_value
        _equal(_number(balance["positions_value"]), value)
        _equal(_number(balance["nav"]), _number(balance["cash"]) + value)
    _equal(_number(result["final_cash"]), _number(result["daily_ledger"][-1]["cash"]))
    _equal(_number(result["final_nav"]), _number(result["daily_ledger"][-1]["nav"]))
    _equal(_number(result["total_commission"]), commission)


def _valuation_mark(session: dict, symbol: str) -> Decimal:
    quotes = [
        quote
        for quote in session["quotes"]
        if quote["symbol"] == symbol and quote["ts_ns"] == session["valuation_ts_ns"]
    ]
    _require(len(quotes) == 1, "missing or duplicate valuation mark quote")
    quote = quotes[0]
    return (_number(quote["bid"]) + _number(quote["ask"])) / Decimal(2)


def _order_evidence(request: dict, result: dict, sessions: dict, zone: str):
    intents = _unique([o for s in sessions.values() for o in s["orders"]], "id")
    orders = _unique(result["orders"], "id")
    _require(set(orders) == set(intents), "order coverage mismatch")
    filled = defaultdict(Decimal)
    fills_by_date = defaultdict(list)
    for fill in result["fills"]:
        intent = intents[fill["order_id"]]
        _require(
            fill["symbol"] == intent["symbol"] and fill["side"] == intent["side"],
            "fill identity mismatch",
        )
        quantity = _number(fill["quantity"], integer=True)
        _require(quantity > 0, "zero fill quantity")
        price = _number(fill["price"])
        _require(price > 0, "zero fill price")
        _number(fill["commission"])
        stamp = datetime.fromtimestamp(fill["ts_ns"] // 1_000_000_000, UTC)
        day = stamp.astimezone(ZoneInfo(zone)).date().isoformat()
        _require(
            day in sessions
            and sessions[day]["open_ts_ns"] <= fill["ts_ns"] <= sessions[day]["valuation_ts_ns"]
            and fill["ts_ns"] > intent["information_ts_ns"],
            "fill outside session",
        )
        _require(
            any(o["id"] == fill["order_id"] for o in sessions[day]["orders"]),
            "fill in incorrect order session",
        )
        filled[fill["order_id"]] += quantity
        fills_by_date[day].append(fill)
    rejections = _unique(result["rejections"], "order_id")
    for order_id, order in orders.items():
        intent = intents[order_id]
        _require(order["symbol"] == intent["symbol"], "order symbol mismatch")
        _require(
            _number(order["filled_quantity"], integer=True)
            == filled[order_id]
            <= _number(intent["quantity"], integer=True),
            "filled quantity mismatch",
        )
        status = order["status"]
        _require(
            status in ("FILLED", "DENIED", "REJECTED", "CANCELED", "NOT_SUBMITTED", "EXPIRED"),
            "unsupported order status",
        )
        if status == "FILLED":
            _require(filled[order_id] == _number(intent["quantity"]), "incomplete filled order")
        if status == "NOT_SUBMITTED":
            _require(filled[order_id] == 0, "unsubmitted order has fills")
        if status in ("DENIED", "REJECTED"):
            _require(order_id in rejections and filled[order_id] == 0, "missing rejection")
    _require(set(rejections) <= set(orders), "unknown rejected order")
    for rejection in rejections.values():
        _require(
            bool(rejection["reason"]) and rejection["event_type"] in ("denied", "rejected"),
            "invalid rejection",
        )
        _require(
            orders[rejection["order_id"]]["status"] == rejection["event_type"].upper(),
            "rejection status mismatch",
        )
    return fills_by_date, orders, rejections


def _record(
    value: Any, strings: str = "", integers: str = "", lists: str = "", booleans: str = ""
) -> None:
    fields = {
        **dict.fromkeys(strings.split(), str),
        **dict.fromkeys(integers.split(), int),
        **dict.fromkeys(lists.split(), list),
        **dict.fromkeys(booleans.split(), bool),
    }
    _require(type(value) is dict and set(value) == set(fields), "invalid wire fields")
    for key, kind in fields.items():
        _require(type(value[key]) is kind, f"invalid wire type: {key}")


def _sizing_shape(result: dict) -> None:
    _record(result, "schema_version currency marked_equity projected_cash", lists="orders targets")
    for order in result["orders"]:
        _record(order, "id symbol side quantity", "information_ts_ns")
    for target in result["targets"]:
        _record(target, "symbol desired_quantity planned_quantity")


def _session_shape(result: dict) -> None:
    _record(
        result,
        "initial_cash price_basis valuation_timezone schema_version backend "
        "backend_version currency final_cash final_nav total_commission",
        lists="rejections capabilities orders fills daily_ledger daily_positions",
        booleans="enforce_t1",
    )
    _require(
        result["backend"] == "nautilus" and result["backend_version"] == "0.66.0",
        "unsupported engine backend/version",
    )
    _require(
        all(type(c) is str for c in result["capabilities"])
        and len(set(result["capabilities"])) == len(result["capabilities"]),
        "invalid engine capabilities",
    )
    for row in result["rejections"]:
        _record(row, "order_id reason event_type")
    for row in result["orders"]:
        _record(row, "id symbol status filled_quantity")
    for row in result["fills"]:
        _record(row, "order_id symbol side quantity price commission", "ts_ns")
    for row in result["daily_ledger"]:
        _record(row, "session_date cash positions_value nav commission", "valuation_ts_ns")
    for row in result["daily_positions"]:
        _record(row, "session_date symbol quantity mark_price market_value")


def _reject_constant(value: str) -> None:
    raise EngineProtocolError(f"nonfinite JSON constant: {value}")


def _json_object(pairs: list[tuple[str, Any]]) -> dict:
    result = dict(pairs)
    _require(len(result) == len(pairs), "duplicate JSON field")
    return result
