"""Optional public-owner exporter. Not an Engine or docs runtime dependency.

All financial execution comes from pinned owners. The selection illustration is
an exhaustive permutation of the public null scenario, not a research campaign.
Decimal strings retain owner precision; UTC nanoseconds are strings for JS.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from decimal import Decimal
from fractions import Fraction
import hashlib
import json
from pathlib import Path

PLATFORM = "c211d36167acf7a81fd0c034beb14317e2036b7e"
RUNTIME = "01ed4c34f955ef6cd39d13aa073b6d61b610d321"
ENGINE = "ad0895f1c2015eb31bd364b40741b0f7cd6e0048"
ROOT = Path(__file__).resolve().parents[1]


def number(value):
    if value is None:
        return None
    value = (
        Decimal(str(float(value)))
        if isinstance(value, Fraction)
        else Decimal(str(value))
    )
    if not value.is_finite():
        return None
    return (
        format(value, "f").rstrip("0").rstrip(".")
        if "." in format(value, "f")
        else format(value, "f")
    )


def wire(value):
    if is_dataclass(value):
        return wire(asdict(value))
    if isinstance(value, dict):
        return {str(k): wire(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [wire(v) for v in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, (float, Decimal, Fraction)):
        return number(value)
    if hasattr(value, "item"):
        return wire(value.item())
    return value


def digest(value):
    data = (
        value
        if isinstance(value, bytes)
        else json.dumps(wire(value), sort_keys=True, allow_nan=False).encode()
    )
    return hashlib.sha256(data).hexdigest()


def scenario(ident, states, inputs, source, *, owner_name="core", **extra):
    return {
        "id": ident,
        "owner": owner_name,
        "source": source,
        "evidence": "synthetic",
        "status": "synthetic_mechanism",
        "evidence_boundary": "Synthetic acceptance only; no real-market calibration or performance claim",
        "input_sha256": digest(inputs),
        "config_sha256": digest(inputs),
        "configuration_scope": "complete synthetic inputs; typed owner-call definitions include resolved arguments and dataclass defaults",
        "run_sha256": {
            name: digest(run) for name, run in inputs.get("runs", {}).items()
        },
        "inputs": wire(inputs),
        "units": {
            "money": "CNY unless explicitly USD",
            "price": "currency/share",
            "quantity": "shares",
            "offset": "price displacement",
            "score": "return fraction",
        },
        "clocks": {
            "event": "explicit fixture clock; UTC nanoseconds encoded as decimal strings",
            "decision": "strictly prior eligible information",
            "report": "receipt clock; may lag economic fill",
        },
        "states": wire(states),
        **wire(extra),
    }


class Policy:
    """A documented feedback rule: preserve pending; optionally hold actual shares."""

    def __init__(self, hold=False):
        self.rows = []
        self.hold = hold

    def __call__(self, state, proposed):
        chosen = (
            {"A": state.holdings["A"] * state.marks["A"] / state.nav}
            if self.hold and state.holdings
            else (None if state.pending_orders else proposed)
        )
        self.rows.append(
            {
                "cash": number(state.cash),
                "quantity": number(state.holdings.get("A", 0)),
                "pending": bool(state.pending_orders),
                "next_target": None if chosen is None else number(chosen.get("A", 0)),
                "clock": str(state.time.value),
            }
        )
        return chosen

    def checkpoint(self):
        return {"rows": self.rows.copy(), "hold": self.hold}


def targets(times=("2026-01-05 09:30",), weights=(1,)):
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "decision_time": pd.Timestamp(t, tz="Asia/Shanghai")
                - pd.Timedelta(minutes=1),
                "entry_time": pd.Timestamp(t, tz="Asia/Shanghai"),
                "symbol": "A",
                "weight": w,
            }
            for t, w in zip(times, weights, strict=True)
        ]
    )


def bars(
    times=("2026-01-05 09:29", "2026-01-05 09:32", "2026-01-05 09:36"),
    price=10.0,
    volume=1000,
):
    import pandas as pd

    return pd.DataFrame(
        [
            {
                "time": pd.Timestamp(t, tz="Asia/Shanghai"),
                "interval_start": pd.Timestamp(t, tz="Asia/Shanghai")
                - pd.Timedelta(seconds=30),
                "symbol": "A",
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
                "amount": price * volume,
                "up_limit": 20,
                "down_limit": 1,
                "tradable": True,
            }
            for t in times
        ]
    )


def records(frame):
    return wire(frame.to_dict("records"))
