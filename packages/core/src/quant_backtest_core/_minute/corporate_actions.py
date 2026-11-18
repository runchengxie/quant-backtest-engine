# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/_portfolio/corporate_actions.py
# Original SHA256: 2c6fd0e45636c15c37bebee7b5037f0607b8a4cf169d6cf20fe5da54e1b64eaa
"""Caller-normalized corporate actions for opt-in raw-share accounting."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from math import isfinite

import pandas as pd


def _action_date(value: object, name: str) -> pd.Timestamp:
    if not isinstance(value, (str, date, pd.Timestamp)):
        raise ValueError(f"{name} must be a calendar date")
    try:
        result = pd.Timestamp(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name}: {value!r}") from exc
    if not isinstance(result, pd.Timestamp):
        raise ValueError(f"invalid {name}: {value!r}")
    if result.tzinfo is not None or result != result.normalize():
        raise ValueError(f"{name} must be a timezone-naive calendar date without a time")
    return result


def _validate_action_numbers(event: CorporateAction) -> None:
    for name in ("cash_per_share", "stock_per_share", "withholding_rate"):
        try:
            value = float(getattr(event, name))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be finite and nonnegative") from exc
        if not isfinite(value) or value < 0:
            raise ValueError(f"{name} must be finite and nonnegative")
        object.__setattr__(event, name, value)
    if event.withholding_rate > 1:
        raise ValueError("withholding_rate must be between zero and one")
    if event.cash_per_share == 0 and event.stock_per_share == 0:
        raise ValueError("an action must distribute cash or additional shares")


def _validate_action_dates(event: CorporateAction) -> None:
    for name in ("available_date", "record_date", "ex_date"):
        object.__setattr__(event, name, _action_date(getattr(event, name), name))
    available_date = _action_date(event.available_date, "available_date")
    record_date = _action_date(event.record_date, "record_date")
    ex_date = _action_date(event.ex_date, "ex_date")
    if not available_date <= record_date < ex_date:
        raise ValueError("require available_date <= record_date < ex_date")
    for amount, name in (
        (event.cash_per_share, "cash_pay_date"),
        (event.stock_per_share, "stock_tradable_date"),
    ):
        value = getattr(event, name)
        if value is None:
            if amount > 0:
                raise ValueError(f"{name} is required for a positive distribution")
            continue
        value = _action_date(value, name)
        if value < ex_date:
            raise ValueError(f"{name} must be on or after ex_date")
        object.__setattr__(event, name, value)


@dataclass(frozen=True)
class CorporateAction:
    """Additional cash/shares per record-date closing share; no inferred adjustments.

    ``withholding_rate`` is an explicit flat analytical rate, not a historical
    holding-period tax model. Zero means no withholding has been modeled.
    """

    event_id: str
    symbol: str
    available_date: str | date | pd.Timestamp
    record_date: str | date | pd.Timestamp
    ex_date: str | date | pd.Timestamp
    cash_per_share: float = 0.0
    cash_pay_date: str | date | pd.Timestamp | None = None
    stock_per_share: float = 0.0
    stock_tradable_date: str | date | pd.Timestamp | None = None
    withholding_rate: float = 0.0

    def __post_init__(self) -> None:
        for name in ("event_id", "symbol"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or value != value.strip():
                raise ValueError(f"{name} must be a nonempty normalized string")
        _validate_action_numbers(self)
        _validate_action_dates(self)


def normalize_corporate_actions(
    actions: Iterable[CorporateAction] | None,
    price_basis: str | None,
) -> tuple[CorporateAction, ...] | None:
    if actions is None:
        return None
    if price_basis != "raw":
        raise ValueError("corporate_actions require price_basis='raw', including empty actions")
    events = tuple(actions)
    seen: set[str] = set()
    for event in events:
        if not isinstance(event, CorporateAction):
            raise TypeError("corporate_actions must contain CorporateAction events")
        if event.event_id in seen:
            raise ValueError(f"duplicate corporate action event_id: {event.event_id}")
        seen.add(event.event_id)
    return tuple(sorted(events, key=lambda event: (event.record_date, event.event_id)))
