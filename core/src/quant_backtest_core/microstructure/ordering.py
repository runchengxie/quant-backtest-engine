"""Deterministic L2 event ordering without inventing a cross-channel exchange order."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from itertools import pairwise
from typing import Any

CHANNEL_COLUMNS = ("ChannelNo", "Channel", "channel_no", "channel")
SEQUENCE_COLUMNS = (
    "ApplSeqNum",
    "BizIndex",
    "SeqNum",
    "SeqNo",
    "Sequence",
    "seq_num",
    "sequence",
)


def _first_present(columns: set[str], aliases: tuple[str, ...]) -> str | None:
    return next((name for name in aliases if name in columns), None)


def detect_ordering_columns(columns: Iterable[str]) -> dict[str, Any]:
    """Resolve optional raw channel/sequence columns from known aliases."""
    names = {str(column) for column in columns}
    channel = _first_present(names, CHANNEL_COLUMNS)
    sequence = _first_present(names, SEQUENCE_COLUMNS)
    return {
        "channel_column": channel,
        "sequence_column": sequence,
        "exchange_sequence_available": sequence is not None,
    }


def _timestamp_bucket(events: list[Any]) -> list[Any]:
    non_snapshots = [event for event in events if event.kind != "snapshot"]
    snapshots = [event for event in events if event.kind == "snapshot"]
    sequenced = [event for event in non_snapshots if event.sequence is not None]
    channels = {event.channel for event in sequenced if event.channel}

    if non_snapshots and len(sequenced) == len(non_snapshots) and len(channels) <= 1:
        non_snapshots = sorted(
            non_snapshots,
            key=lambda event: (int(event.sequence), event.source_index),
        )
    else:
        non_snapshots = sorted(non_snapshots, key=lambda event: event.source_index)
    snapshots = sorted(snapshots, key=lambda event: event.source_index)
    return [*non_snapshots, *snapshots]


def sort_simulator_events(events: Iterable[Any], *, backend: str = "python") -> list[Any]:
    """Sort by time; use sequence only where it does not fabricate cross-channel order."""
    if backend == "rust":
        from _microstructure_rs import sort_event_indices

        rows = list(events)
        indices = sort_event_indices(
            [
                (
                    int(event.time_ms),
                    event.kind,
                    event.channel,
                    event.sequence,
                    event.source_index,
                )
                for event in rows
            ]
        )
        return [rows[index] for index in indices]
    if backend != "python":
        raise ValueError(f"unknown ordering backend: {backend}")
    buckets: dict[int, list[Any]] = defaultdict(list)
    for event in events:
        buckets[int(event.time_ms)].append(event)
    ordered: list[Any] = []
    for time_ms in sorted(buckets):
        ordered.extend(_timestamp_bucket(buckets[time_ms]))
    return ordered


def ordering_provenance(
    events: Iterable[Any],
    *,
    channel_column: str | None = None,
    sequence_column: str | None = None,
) -> dict[str, Any]:
    """Describe how a loaded event stream can be ordered without overstating precision."""
    rows = list(events)
    sequenced = [event for event in rows if getattr(event, "sequence", None) is not None]
    channels = {str(event.channel) for event in sequenced if getattr(event, "channel", "")}
    if not sequenced:
        mode = "timestamp_fallback"
    elif len(channels) <= 1:
        mode = "timestamp_then_channel_sequence"
    else:
        mode = "timestamp_then_source_order_cross_channel"
    return {
        "exchange_sequence_available": bool(sequenced),
        "channel_column": channel_column,
        "sequence_column": sequence_column,
        "ordering_mode": mode,
        "cross_channel_total_order": False,
        "cross_channel_fallback": "source_order",
        **_sequence_integrity(rows),
    }


def _sequence_integrity(events: list[Any]) -> dict[str, Any]:
    """Observed channel gaps are evidence, not proof of a complete exchange feed."""
    sequences: dict[str, set[int]] = defaultdict(set)
    unknown = False
    for event in events:
        if event.kind == "snapshot":
            continue
        channel, sequence = getattr(event, "channel", None), getattr(event, "sequence", None)
        if not channel or sequence is None:
            unknown = True
            continue
        sequences[str(channel)].add(int(sequence))
    gap_count = 0
    for values in sequences.values():
        ordered = sorted(values)
        gap_count += sum(right - left - 1 for left, right in pairwise(ordered))
    status = (
        "gaps_observed"
        if gap_count
        else ("unknown" if unknown or not sequences else "observed_contiguous")
    )
    return {"sequence_gap_count": gap_count, "sequence_completeness": status}
