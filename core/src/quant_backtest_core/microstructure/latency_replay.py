"""Deterministic limit/cancel arrival replay under explicitly supplied latency.

This diagnostic owns matching only. It creates no cash account and does not fit
latency distributions or infer historical queue identities from aggregate depth.
All nanosecond clocks are bounded signed-64-bit integers. Equal arrivals use the
caller's explicit sequence, never lexical event IDs or list input order.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Literal

from .matching import Fill, LimitOrderBook

MAX_NS = 2**63 - 1


@dataclass(frozen=True)
class Command:
    event_id: str
    kind: Literal["order", "cancel"]
    send_ns: int
    latency_ns: int
    response_ns: int
    sequence: int
    order_id: str
    side: int = 0
    price: int = 0
    quantity: int | None = None


@dataclass(frozen=True)
class BookEvent:
    event_id: str
    order_id: str
    kind: str
    effective_ns: int
    sequence: int
    status: str
    cancelled_quantity: int
    fills: tuple[Fill, ...]
    bids: tuple[tuple[int, int], ...]
    asks: tuple[tuple[int, int], ...]
    queue: tuple[tuple[str, int, int, int], ...]


@dataclass(frozen=True)
class Report:
    event_id: str
    effective_ns: int
    delivered_ns: int
    event: BookEvent


@dataclass(frozen=True)
class ReplayResult:
    schema: str
    input_sha256: str
    commands: tuple[Command, ...]
    events: tuple[BookEvent, ...]
    reports: tuple[Report, ...]


def _integer(value: object, name: str, minimum: int = 0) -> None:
    if type(value) is not int or not minimum <= value <= MAX_NS:
        raise ValueError(f"{name} must be an integer in [{minimum}, {MAX_NS}]")


def replay_commands(commands: list[Command], *, max_commands: int = 1_000) -> ReplayResult:
    """Replay a complete, bounded supplied command set from an empty Python book.

    A resting order can fill before its acknowledgement is delivered. Each
    report retains the exchange event it describes, even when reports reorder.
    Unknown/overlarge cancellations return explicit outcomes without changing
    the book. Order IDs are unique for the entire run, including filled orders.
    Cancel quantity=None means full cancellation, otherwise exact partial cancel.
    """
    _integer(max_commands, "max_commands", 1)
    if max_commands > 1_000:
        raise ValueError("snapshot replay supports at most 1000 commands")
    if type(commands) is not list or len(commands) > max_commands:
        raise ValueError("commands must be a bounded list")
    ids: set[str] = set()
    order_ids: set[str] = set()
    arrivals: set[tuple[int, int]] = set()
    for c in commands:
        if not isinstance(c, Command):
            raise ValueError("each command must be a Command")
        if not isinstance(c.event_id, str) or not c.event_id.strip() or c.event_id in ids:
            raise ValueError("event_id must be nonempty and unique")
        ids.add(c.event_id)
        if not isinstance(c.order_id, str) or not c.order_id.strip():
            raise ValueError("order_id must be nonempty")
        for name in ("send_ns", "latency_ns", "response_ns", "sequence"):
            _integer(getattr(c, name), name)
        arrival = c.send_ns + c.latency_ns
        _integer(arrival + c.response_ns, "delivery_ns")
        if (arrival, c.sequence) in arrivals:
            raise ValueError("equal arrivals require a unique explicit sequence")
        arrivals.add((arrival, c.sequence))
        if c.kind == "order":
            if type(c.side) is not int or c.side not in (-1, 1):
                raise ValueError("order side must be 1 or -1")
            _integer(c.price, "price", 1)
            _integer(c.quantity, "quantity", 1)
            if c.order_id in order_ids:
                raise ValueError("order identities must be unique for the full run")
            order_ids.add(c.order_id)
        elif c.kind == "cancel":
            if type(c.side) is not int or c.side != 0 or type(c.price) is not int or c.price != 0:
                raise ValueError("cancel side and price must be zero")
            if c.quantity is not None:
                _integer(c.quantity, "quantity", 1)
        else:
            raise ValueError("supported commands are order and cancel")
    scheduled = tuple(sorted(commands, key=lambda c: (c.send_ns + c.latency_ns, c.sequence)))
    raw = json.dumps(
        {"schema": "command-latency.v1", "commands": [asdict(c) for c in scheduled]},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode()
    book = LimitOrderBook()
    events: list[BookEvent] = []
    reports: list[Report] = []
    for c in scheduled:
        cancelled = 0
        fills: tuple[Fill, ...] = ()
        if c.kind == "order":
            assert c.quantity is not None
            trade = book.apply_order(c.order_id, c.side, c.price, c.quantity)
            fills = trade.fills if trade else ()
            status = (
                "resting" if not fills else "partial" if book.has_order(c.order_id) else "filled"
            )
        else:
            before = next((v for oid, _, _, v in book.orders() if oid == c.order_id), None)
            if before is None:
                status = "not_resting"
            elif book.cancel_order(c.order_id, c.quantity):
                cancelled = before if c.quantity is None else c.quantity
                status = "cancelled"
            else:
                status = "cancel_rejected"
        arrival = c.send_ns + c.latency_ns
        event = BookEvent(
            c.event_id,
            c.order_id,
            c.kind,
            arrival,
            c.sequence,
            status,
            cancelled,
            fills,
            book.depth(1),
            book.depth(-1),
            book.orders(),
        )
        events.append(event)
        reports.append(Report(c.event_id, arrival, arrival + c.response_ns, event))
    reports.sort(key=lambda r: (r.delivered_ns, r.event.effective_ns, r.event.sequence))
    return ReplayResult(
        "command-latency.v1",
        hashlib.sha256(raw).hexdigest(),
        scheduled,
        tuple(events),
        tuple(reports),
    )
