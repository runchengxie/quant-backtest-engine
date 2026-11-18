"""Strict supplied-depth audit for limit-order feeds whose orders imply trades.

This is a diagnostic, not a ProductManifest backend or exchange certification.
Initial aggregate depth supplies no historical order IDs or true queue position.
Trade rows are observations, not additional book debits. Zero/default order_type
is the caller-declared ordinary limit convention; other encodings are unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .matching import LimitOrderBook
from .pack import SimulatorPack

Levels = tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class DepthAudit:
    status: Literal["matched", "mismatched", "not_comparable"]
    reason: str
    bid_differences: tuple[tuple[int, int, int], ...] = ()
    ask_differences: tuple[tuple[int, int, int], ...] = ()
    processed_events: int = 0
    scope: str = "supplied_snapshot_depth_orders_imply_trades"
    initial_order_identity_available: bool = False
    queue_position_calibrated: bool = False
    trade_rows_reconciled: bool = False
    sequence_evidence: str = "unknown"


def _levels(rows: Levels, side: int) -> Levels:
    for price, volume in rows:
        if type(price) is not int or type(volume) is not int:
            raise ValueError("depth price and volume must be integers")
        if price <= 0 or volume <= 0:
            raise ValueError("depth price and volume must be positive")
    prices = [p for p, _ in rows]
    if len(set(prices)) != len(prices) or prices != sorted(prices, reverse=side == 1):
        raise ValueError("depth must have unique best-to-worst prices")
    return rows


def _difference(actual: Levels, expected: Levels) -> tuple[tuple[int, int, int], ...]:
    # A snapshot certifies only its supplied top N levels. Extra deeper levels
    # are outside scope; extra levels *inside* that prefix cause a mismatch.
    observed = dict(actual[: len(expected)] if expected else actual)
    wanted = dict(expected)
    return tuple(
        (p, observed.get(p, 0), wanted.get(p, 0))
        for p in sorted(observed.keys() | wanted.keys())
        if observed.get(p, 0) != wanted.get(p, 0)
    )


def audit_depth(
    pack: SimulatorPack, init_snapshot_idx: int = 0, target_snapshot_idx: int = 1
) -> DepthAudit:
    """Replay strictly inside two clocks; reject ambiguous boundary events.

    Input must already be ordered. Observed contiguous channel sequences do not
    prove feed completeness; snapshot matches never certify calibration.
    """
    if not 0 <= init_snapshot_idx < target_snapshot_idx < len(pack.snapshots):
        raise ValueError("snapshot indices must be ordered and in range")
    start, end = pack.snapshots[init_snapshot_idx], pack.snapshots[target_snapshot_idx]
    if any(type(x.time_ms) is not int for x in [start, end, *pack.events]):
        raise ValueError("time_ms must be an integer")
    if start.kind != "snapshot" or end.kind != "snapshot":
        raise ValueError("snapshot list must contain snapshots")
    if start.time_ms >= end.time_ms:
        raise ValueError("snapshot clocks must be strictly ordered")
    if any(a.time_ms > b.time_ms for a, b in zip(pack.events, pack.events[1:])):
        raise ValueError("events must already be ordered")
    if any(x is None for x in (start.bid_levels, start.ask_levels, end.bid_levels, end.ask_levels)):
        return DepthAudit("not_comparable", "missing_snapshot_depth")
    assert start.bid_levels is not None and start.ask_levels is not None
    assert end.bid_levels is not None and end.ask_levels is not None
    for snapshot in (start, end):
        snapshot_bids = _levels(snapshot.bid_levels, 1)  # type: ignore[arg-type]
        snapshot_asks = _levels(snapshot.ask_levels, -1)  # type: ignore[arg-type]
        if snapshot_bids and snapshot_asks and snapshot_bids[0][0] >= snapshot_asks[0][0]:
            raise ValueError("crossed snapshot depth is unsupported")
    events = [
        e for e in pack.events if e.kind != "snapshot" and start.time_ms <= e.time_ms <= end.time_ms
    ]
    if any(e.time_ms in (start.time_ms, end.time_ms) for e in events):
        return DepthAudit("not_comparable", "snapshot_boundary_ambiguous")
    book = LimitOrderBook()
    seen = set()
    for side, rows in ((1, start.bid_levels), (-1, start.ask_levels)):
        for price, volume in rows:
            oid = f"__depth_seed_{side}_{price}"
            seen.add(oid)
            book.seed_level(side, price, volume, oid)
    sequences: dict[str, int] = {}
    ties: dict[int, set[str]] = {}
    for e in events:
        ties.setdefault(e.time_ms, set()).add(e.channel)
    if any(len(channels) > 1 for channels in ties.values()):
        return DepthAudit("not_comparable", "cross_channel_tie")
    for index, e in enumerate(events):
        if e.sequence is not None:
            if not e.channel or type(e.sequence) is not int:
                return DepthAudit(
                    "not_comparable", "invalid_channel_sequence", processed_events=index
                )
            previous = sequences.get(e.channel)
            if previous is not None and e.sequence != previous + 1:
                return DepthAudit(
                    "not_comparable", "channel_sequence_discontinuity", processed_events=index
                )
            sequences[e.channel] = e.sequence
        if e.kind == "order":
            if e.order_type != 0:
                return DepthAudit(
                    "not_comparable", "unsupported_order_type", processed_events=index
                )
            if not e.order_id or e.order_id in seen:
                raise ValueError("missing or duplicate order id")
            if type(e.side) is not int or e.side not in (1, -1):
                raise ValueError("order side must be 1 or -1")
            _levels(((e.price, e.volume),), e.side)
            seen.add(e.order_id)
            book.apply_order(e.order_id, e.side, e.price, e.volume)
        elif e.kind == "cancel":
            if e.volume != 0:
                return DepthAudit(
                    "not_comparable", "partial_cancel_unsupported", processed_events=index
                )
            if not book.has_order(e.order_id):
                return DepthAudit("not_comparable", "unknown_cancel_id", processed_events=index)
            # Existing pack cancellation convention is full cancellation by ID.
            book.cancel_order(e.order_id)
        elif e.kind != "trade":
            raise ValueError("unsupported event kind")
    bids = _difference(book.depth(1), end.bid_levels)
    asks = _difference(book.depth(-1), end.ask_levels)
    return DepthAudit(
        "mismatched" if bids or asks else "matched",
        "depth_comparison",
        bids,
        asks,
        len(events),
        sequence_evidence=(
            "observed_contiguous"
            if events and all(e.channel and e.sequence is not None for e in events)
            else "unknown"
        ),
    )
