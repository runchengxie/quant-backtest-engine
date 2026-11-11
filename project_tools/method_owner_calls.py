"""Typed, fully resolved public-owner calls. Serialization is not simulation.

An owner is called only after decoding its stored definition. Float hex strings,
frame dtypes, timezone-aware clocks, dataclass defaults and stateful policy/model
initial states survive JSON round trips. Missing resolved fields fail closed.
"""

from dataclasses import fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from fractions import Fraction
from importlib import import_module
import inspect
import json
import math

_APIS = {
    "minute": ("quant_backtest_core.backtest.minute", "simulate_minute_execution"),
    "session": ("quant_backtest_core.backtest.minute_session", "MinuteSession"),
    "discrete": (
        "quant_backtest_core.planning.discrete_inventory",
        "solve_discrete_inventory",
    ),
    "risk_audit": (
        "quant_platform.analytics.risk_calibration",
        "audit_risk_calibration",
    ),
    "net_sleeves": (
        "quant_backtest_core.planning.sleeve_allocation",
        "net_sleeve_demands",
    ),
    "allocate": (
        "quant_backtest_core.planning.sleeve_allocation",
        "allocate_external_fills",
    ),
    "exit_wealth": ("quant_backtest_core.evidence.execution_integrity", "exit_wealth"),
    "null_scenario": ("quant_platform.scenarios", "build_scenario"),
    "impact": ("quant_backtest_core.backtest.impact", "LinearImpact"),
    "matching": ("quant_backtest_core.microstructure.matching", "MatchingEngine"),
}


_DATACLASSES = frozenset(
    {
        "quant_backtest_core._minute.minute_execution.MinuteExecutionConfig",
        "quant_backtest_core._minute.capital_flows.CapitalFlow",
        "quant_backtest_core._minute.corporate_actions.CorporateAction",
        "quant_backtest_core._minute.valuation_events.ValuationEvent",
        "quant_backtest_core.backtest.quantity_locks.QuantityLock",
        "quant_backtest_core.planning.discrete_inventory.DiscreteInventoryRequest",
        "quant_backtest_core.planning.sleeve_allocation.SleeveDemand",
        "quant_backtest_core.planning.sleeve_allocation.ExternalOrder",
        "quant_backtest_core.planning.sleeve_allocation.SleeveNetPlan",
    }
)


def _api(name):
    module, attribute = _APIS[name]
    return getattr(import_module(module), attribute)


def encode(value):
    from method_fixture_common import Policy
    import pandas as pd
    from quant_backtest_core.backtest.impact import LinearImpact

    if isinstance(value, Policy):
        return {"type": "method-policy.v1", "state": encode(value.checkpoint())}
    if type(value) is LinearImpact:
        return {"type": "linear-impact.v1", "state": encode(value.checkpoint())}
    if isinstance(value, pd.DataFrame):
        return {
            "type": "frame.v1",
            "columns": value.columns.tolist(),
            "dtypes": [str(dtype) for dtype in value.dtypes],
            "rows": encode(value.to_dict("records")),
        }
    if isinstance(value, pd.Timestamp):
        return {"type": "timestamp", "value": value.isoformat()}
    if isinstance(value, datetime):
        return {"type": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"type": "date", "value": value.isoformat()}
    if is_dataclass(value):
        if type(value).__module__ + "." + type(value).__name__ not in _DATACLASSES:
            raise ValueError("unregistered public owner dataclass")
        return {
            "type": "dataclass",
            "class": type(value).__module__ + "." + type(value).__name__,
            "fields": {
                field.name: encode(getattr(value, field.name))
                for field in fields(value)
                if field.init
            },
        }
    if isinstance(value, tuple):
        return {"type": "tuple", "items": [encode(item) for item in value]}
    if isinstance(value, list):
        return [encode(item) for item in value]
    if isinstance(value, dict):
        return {key: encode(item) for key, item in value.items()}
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("finite input float required")
        return {"type": "float", "hex": value.hex()}
    if isinstance(value, Decimal):
        return {"type": "decimal", "value": str(value)}
    if isinstance(value, Fraction):
        return {
            "type": "fraction",
            "numerator": value.numerator,
            "denominator": value.denominator,
        }
    if isinstance(value, int) and abs(value) > 2**53 - 1:
        return {"type": "integer", "value": str(value)}
    if hasattr(value, "item"):
        return encode(value.item())
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise TypeError(f"unsupported run-definition type {type(value).__name__}")


def decode(value):
    if isinstance(value, list):
        return [decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    kind = value.get("type")
    if kind == "float":
        return float.fromhex(value["hex"])
    if kind == "integer":
        return int(value["value"])
    if kind == "decimal":
        return Decimal(value["value"])
    if kind == "fraction":
        return Fraction(value["numerator"], value["denominator"])
    if kind == "tuple":
        return tuple(decode(item) for item in value["items"])
    if kind in {"timestamp", "frame.v1"}:
        import pandas as pd

        if kind == "timestamp":
            return pd.Timestamp(value["value"])
        frame = pd.DataFrame(decode(value["rows"]), columns=value["columns"])
        return frame.astype(dict(zip(value["columns"], value["dtypes"], strict=True)))
    if kind == "datetime":
        return datetime.fromisoformat(value["value"])
    if kind == "date":
        return date.fromisoformat(value["value"])
    if kind == "dataclass":
        identity = value["class"]
        if identity not in _DATACLASSES:
            raise ValueError("unregistered public owner dataclass")
        module, name = identity.rsplit(".", 1)
        cls = getattr(import_module(module), name)
        if set(value["fields"]) != {field.name for field in fields(cls) if field.init}:
            raise ValueError("all resolved dataclass fields are required")
        return cls(**decode(value["fields"]))
    if kind == "method-policy.v1":
        from method_fixture_common import Policy

        state = decode(value["state"])
        policy = Policy(state["hold"])
        policy.rows = state["rows"]
        return policy
    if kind == "linear-impact.v1":
        return _api("impact").restore(decode(value["state"]))
    if kind is not None:
        raise ValueError("unknown serialized owner type")
    return {key: decode(item) for key, item in value.items()}


def define_call(api, *args, **kwargs):
    bound = inspect.signature(_api(api)).bind(*args, **kwargs)
    bound.apply_defaults()
    # JSON is the execution boundary, not merely a later annotation of a live call.
    return json.loads(
        json.dumps(
            {
                "schema": "public-owner-call.v1",
                "api": api,
                "arguments": encode(dict(bound.arguments)),
            },
            allow_nan=False,
        )
    )


def execute_call(definition, *, return_policy=False):
    if definition["schema"] != "public-owner-call.v1":
        raise ValueError("unsupported owner call")
    api = _api(definition["api"])
    arguments = decode(definition["arguments"])
    if set(arguments) != set(inspect.signature(api).parameters):
        raise ValueError("all resolved owner arguments are required")
    result = api(**arguments)
    return (result, arguments["decision_policy"]) if return_policy else result


def restore_session(definition, checkpoint):
    arguments = decode(definition["arguments"])
    policy = arguments["policy"]
    policy.rows = checkpoint["policy"]["rows"]
    policy.hold = checkpoint["policy"]["hold"]
    return _api("session").restore(
        arguments["targets"],
        arguments["bars"],
        arguments["config"],
        checkpoint,
        policy=policy,
    )
