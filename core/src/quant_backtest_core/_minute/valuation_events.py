# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/_portfolio/valuation_events.py
# Original SHA256: 57feba201db8f16b6397e7e9ad1051b9f2b112a50afc28aa8e9bd3f629edaab9
"""Explicit permanent nontrading valuation declarations, separate from bars."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from math import isfinite
from typing import cast

import pandas as pd

VALUATION_LEDGER_COLUMNS = (
    "time",
    "event_id",
    "symbol",
    "effective_time",
    "available_time",
    "value_per_share",
    "previous_value_per_share",
    "basis",
    "source",
    "quantity",
    "stock_receivable_quantity",
    "delta_value",
    "cash_before",
    "cash_after",
)


@dataclass(frozen=True)
class ValuationEvent:
    """A declared mark and permanent trading prohibition, never a disposal.

    Later events can change the mark but cannot reopen trading. ``available_time``
    is the declaration/source availability, not a fresh executable quote time.
    """

    event_id: str
    symbol: str
    effective_time: str | datetime | pd.Timestamp
    available_time: str | datetime | pd.Timestamp
    value_per_share: float
    basis: str
    source: str

    def __post_init__(self):
        self._validate_strings()
        self._validate_times()
        try:
            value = float(self.value_per_share)
        except (TypeError, ValueError) as exc:
            raise ValueError("value_per_share must be finite and nonnegative") from exc
        if not isfinite(value) or value < 0:
            raise ValueError("value_per_share must be finite and nonnegative")
        object.__setattr__(self, "value_per_share", value)

    def _validate_strings(self):
        for name in ("event_id", "symbol", "basis", "source"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be a nonempty normalized string")

    def _validate_times(self):
        for name in ("effective_time", "available_time"):
            try:
                value = pd.Timestamp(getattr(self, name))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"invalid {name}") from exc
            if pd.isna(value) or value.tzinfo is None:
                raise ValueError(f"{name} must be timezone aware")
            object.__setattr__(self, name, value)
        if cast(pd.Timestamp, self.available_time) > cast(pd.Timestamp, self.effective_time):
            raise ValueError("available_time must not follow effective_time")


def _market_timezone(bars: pd.DataFrame, targets: pd.DataFrame):
    inputs = [bars.time, targets.entry_time, targets.decision_time]
    if "interval_start" in bars:
        inputs.append(bars.interval_start)
    names = {str(t.tz) for values in inputs for t in values}
    if len(names) != 1:
        raise ValueError(
            "valuation_events require one declared market timezone in bars and targets"
        )
    return next(t.tz for values in inputs for t in values)


def normalize_valuation_events(
    events: Iterable[ValuationEvent], bars: pd.DataFrame, targets: pd.DataFrame
):
    """Validate unique declarations and prohibit later executable bar conflicts."""
    normalized = tuple(events)
    if not normalized:
        return ()
    timezone = _market_timezone(bars, targets)
    identities, keys = set(), set()
    converted = []
    for event in normalized:
        if not isinstance(event, ValuationEvent):
            raise ValueError("valuation_events must contain ValuationEvent objects")
        event = replace(
            event,
            effective_time=cast(pd.Timestamp, event.effective_time).tz_convert(timezone),
            available_time=cast(pd.Timestamp, event.available_time).tz_convert(timezone),
        )
        key = (event.symbol, event.effective_time)
        if event.event_id in identities or key in keys:
            raise ValueError("duplicate valuation event identity or symbol/effective_time")
        converted.append(event)
        identities.add(event.event_id)
        keys.add(key)
        conflict = (
            (bars.symbol == event.symbol) & (bars.time >= event.effective_time) & bars.tradable
        )
        if conflict.any():
            raise ValueError("tradable bars conflict with permanent nontrading valuation event")
    return tuple(sorted(converted, key=lambda e: (e.effective_time, e.symbol, e.event_id)))


def minute_valuation_provenance(sim):
    time = cast(pd.Timestamp, sim.current_time)
    return tuple(
        {
            "symbol": symbol,
            "event_id": event.event_id,
            "value_per_share": event.value_per_share,
            "basis": event.basis,
            "source": event.source,
            "effective_time": event.effective_time,
            "available_time": event.available_time,
            "event_age_seconds": (time - cast(pd.Timestamp, event.effective_time)).total_seconds(),
            "source_age_seconds": (time - cast(pd.Timestamp, event.available_time)).total_seconds(),
            "observed_quote": False,
        }
        for symbol, event in sorted(sim.valuation_state.items())
    )
