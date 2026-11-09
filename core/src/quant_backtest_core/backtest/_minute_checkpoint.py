# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/backtest/_minute_checkpoint.py
# Original SHA256: f75937e47a26eacc2d0ec3ef228669580a0e6cdb156af0c4841aa0212dd43542
"""Lossless, source-bound wire contract for recoverable minute accounts."""

import hashlib
import inspect
import json
import math
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pandas as pd

from quant_backtest_core._minute.capital_flows import CapitalFlow
from quant_backtest_core._minute.corporate_actions import CorporateAction
from quant_backtest_core._minute.minute_execution import _MinuteSimulation
from quant_backtest_core._minute.valuation_events import ValuationEvent

from .impact import LinearImpact
from .quantity_locks import QuantityLock

_EVENT_TYPES = {cls.__name__: cls for cls in (CorporateAction, ValuationEvent, CapitalFlow)}

_FIELDS = [
    "rights",
    "valuation_state",
    "valuation_ledger",
    "capital_flow_ledger",
    "applied_capital_flow_ids",
    "cumulative_capital_flow",
    "return_factor",
    "return_anchor",
    "cash",
    "holdings",
    "bought",
    "marks",
    "orders",
    "fills",
    "daily",
    "costs",
    "mark_days",
    "mark_times",
    "mark_source_times",
    "mark_basis",
    "adjusted_ex_dates",
    "holdings_ledger",
    "clipped_vwap_bars",
    "current_day",
    "day_has_events",
    "current_time",
    "policy_snapshots",
    "execution_locked_symbols",
    "bar_execution_locked_symbols",
]


def _wire(value):
    if type(value) in (CorporateAction, ValuationEvent, CapitalFlow):
        return {"type": type(value).__name__, "value": _wire(asdict(value))}
    if isinstance(value, pd.Timestamp):
        return {
            "type": "timestamp",
            "value": value.isoformat(),
            "zone": str(value.tz) if value.tz else None,
        }
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if isinstance(value, pd.DataFrame):
        return {"type": "frame", "value": _wire(value.to_dict("list"))}
    if isinstance(value, dict):
        return {"type": "dict", "value": [[_wire(k), _wire(v)] for k, v in value.items()]}
    if isinstance(value, (set, tuple)):
        return {
            "type": "set" if isinstance(value, set) else "tuple",
            "value": [_wire(v) for v in sorted(value) if isinstance(value, set)]
            if isinstance(value, set)
            else [_wire(v) for v in value],
        }
    if isinstance(value, list):
        return [_wire(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return {"type": "nonfinite", "value": repr(value)}
    return value


def _nonfinite(data):
    if data not in {"nan", "inf", "-inf"}:
        raise ValueError("invalid nonfinite encoding")
    return float(data)


def _unwire(value):
    if isinstance(value, list):
        return [_unwire(v) for v in value]
    if not isinstance(value, dict):
        return value
    kind, data = value["type"], value["value"]
    if kind in _EVENT_TYPES:
        return _EVENT_TYPES[kind](**_unwire(data))
    if kind == "dict":
        return {_unwire(k): _unwire(v) for k, v in data}
    if kind == "timestamp":
        return (
            pd.Timestamp(data).tz_convert(value["zone"])
            if value.get("zone")
            else pd.Timestamp(data)
        )
    if kind == "date":
        return date.fromisoformat(data)
    if kind == "frame":
        return pd.DataFrame(_unwire(data))
    if kind == "nonfinite":
        return _nonfinite(data)
    if kind in {"set", "tuple"}:
        return set(_unwire(data)) if kind == "set" else tuple(_unwire(data))
    raise ValueError("unknown checkpoint type")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def _frame_binding(frame):
    # Python JSON floats round-trip exactly; pandas.to_json defaults to 10 digits.
    return _wire(
        {
            "columns": frame.columns.tolist(),
            "index": frame.index.tolist(),
            "dtypes": [str(dtype) for dtype in frame.dtypes],
            "data": frame.to_dict("list"),
        }
    )


def _binding(targets, bars, config, policy, locks, tapes):
    owner_dir = Path(inspect.getfile(_MinuteSimulation)).parent
    sources = [
        Path(__file__),
        Path(__file__).with_name("minute_session.py"),
        Path(__file__).with_name("minute.py"),
        Path(inspect.getfile(LinearImpact)),
        Path(inspect.getfile(QuantityLock)),
        *[
            owner_dir / name
            for name in (
                "minute_execution.py",
                "_minute_validation.py",
                "_minute_state.py",
                "corporate_actions.py",
                "valuation_events.py",
                "capital_flows.py",
            )
        ],
    ]
    return _digest(
        {
            "targets": _frame_binding(targets),
            "bars": _frame_binding(bars),
            "config": _wire(asdict(config)),
            "quantity_locks": _wire([asdict(lock) for lock in locks]),
            "tapes": _wire(tapes),
            "tape_contract": "minute-financial-tapes.v1",
            "policy_type": type(policy).__module__ + "." + type(policy).__qualname__,
            "policy_source": hashlib.sha256(
                Path(inspect.getfile(type(policy))).read_bytes()
            ).hexdigest(),
            "source": {
                path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sources
            },
        }
    )
