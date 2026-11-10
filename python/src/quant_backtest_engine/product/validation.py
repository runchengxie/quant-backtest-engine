"""Strict codecs and profile-specific validation, without execution or imports.

A Mapping has already lost duplicate JSON keys. Use loads_manifest/loads_result
at a raw JSON boundary to reject them before constructing DTOs.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date
import json
import math
import re
from types import MappingProxyType, UnionType
from typing import Literal, Union, get_args, get_origin, get_type_hints
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import types as t

TABLE_NAMES = (
    "intents", "admissions", "cancellations", "fills", "fees", "cash",
    "positions", "reservations", "reports", "rights", "receivables",
    "valuations", "capital_flows", "daily",
)
# Named economic columns in generic JSON evidence/configuration. Backend row
# schemas additionally define allowed columns and their financial semantics.
DECIMAL_FIELDS = frozenset((
    "amount", "cash", "initial_cash", "final_cash", "nav", "final_nav", "equity",
    "price", "fill_price", "mark_price", "reference_price", "bid", "ask",
    "quantity", "held_quantity", "available_quantity", "reserved_quantity",
    "bid_size", "ask_size", "fee", "fees", "fee_bps", "commission", "cost",
    "notional", "pnl", "realized_pnl", "unrealized_pnl", "cash_delta",
    "cash_before", "cash_after", "balance", "reservation", "receivable",
    "dividend", "capital_flow", "deposit", "withdrawal",
))
_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
_NS = re.compile(r"(?:0|-?[1-9][0-9]*)\Z")
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_KEY = re.compile(r"[a-z][a-z0-9_-]*(?:\.[a-z][a-z0-9_-]*)*\Z")


def _nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")
    return value


def _ns(value, name):
    if not isinstance(value, str) or not _NS.fullmatch(value):
        raise ValueError(f"{name} must be a canonical string UTC nanosecond integer")


def _decimal(value, name):
    if not isinstance(value, str) or not _DECIMAL.fullmatch(value):
        raise ValueError(f"{name} must be an explicit finite decimal string")


def _digest(value, name):
    if not isinstance(value, str) or not _DIGEST.fullmatch(value):
        raise ValueError(f"{name} must be a lowercase SHA256 digest")


def _freeze(value, name="JSON", active=None):
    active = set() if active is None else active
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{name} cannot be nonfinite")
        return value
    if not isinstance(value, (Mapping, list, tuple)):
        raise ValueError(f"{name} must contain JSON values")
    if id(value) in active:
        raise ValueError(f"{name} cannot contain a cycle")
    active.add(id(value))
    try:
        if isinstance(value, Mapping):
            out = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"{name} object keys must be strings")
                if key in DECIMAL_FIELDS and item is not None:
                    _decimal(item, f"{name}.{key}")
                if key.endswith("_ns") and item is not None:
                    _ns(item, f"{name}.{key}")
                out[key] = _freeze(item, f"{name}.{key}", active)
            return MappingProxyType(out)
        return tuple(_freeze(item, name, active) for item in value)
    finally:
        active.remove(id(value))


def _json_object(value, name):
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be an object")
    return _freeze(value, name)


def _convert(value, annotation, name, wire=False):
    origin, args = get_origin(annotation), get_args(annotation)
    if origin in (Union, UnionType):
        for option in args:
            try:
                return _convert(value, option, name, wire)
            except ValueError:
                pass
        raise ValueError(f"{name} has an invalid value or type")
    if annotation is type(None):
        if value is not None:
            raise ValueError(f"{name} must be null")
        return None
    if origin is Literal:
        if not any(type(value) is type(a) and value == a for a in args):
            raise ValueError(f"{name} must be one of {args}")
        return value
    if origin is tuple:
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"{name} must be an array")
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_convert(v, args[0], name, wire) for v in value)
        if len(value) != len(args):
            raise ValueError(f"{name} has wrong arity")
        return tuple(_convert(v, a, name, wire) for v, a in zip(value, args))
    if isinstance(annotation, type) and is_dataclass(annotation):
        if type(value) is annotation:
            return value
        if wire:
            return _construct(annotation, value)
        raise ValueError(f"{name} must be {annotation.__name__}")
    if annotation is str:
        return _nonempty(value, name)
    if annotation in (int, bool):
        if type(value) is not annotation:
            raise ValueError(f"{name} must be {annotation.__name__}")
        return value
    raise ValueError(f"{name} has unsupported type")


def _pair_items(value, name, wire):
    if wire:
        if not isinstance(value, Mapping):
            raise ValueError(f"{name} must be a JSON object")
        items = tuple(value.items())
    else:
        if not isinstance(value, (tuple, list)):
            raise ValueError(f"{name} must be name/value pairs")
        items = tuple(value)
    keys = set()
    for pair in items:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(f"{name} must contain pairs")
        key = _nonempty(pair[0], name)
        if key in keys:
            raise ValueError(f"{name} has duplicate key {key}")
        keys.add(key)
    return items


def _field(value, field, annotation, wire):
    name = field.name
    if field.metadata.get("json_object"):
        return _json_object(value, name)
    if field.metadata.get("json_rows"):
        if not isinstance(value, (tuple, list)):
            raise ValueError(f"{name} must be an array")
        return tuple(_json_object(row, name) for row in value)
    if field.metadata.get("tapes"):
        out = []
        for key, item in _pair_items(value, name, wire):
            if isinstance(item, t.ArtifactRef):
                parsed = item
            elif isinstance(item, Mapping) and wire:
                parsed = _construct(t.ArtifactRef, item)
            elif isinstance(item, (list, tuple)):
                parsed = _freeze(item, key)
            else:
                raise ValueError(f"tape {key} must be an artifact or array")
            out.append((key, parsed))
        return tuple(out)
    if field.metadata.get("pairs"):
        value = _pair_items(value, name, wire)
    return _convert(value, annotation, name, wire)


def _construct(cls, value):
    if not isinstance(value, Mapping):
        raise ValueError(f"{cls.__name__} must be an object")
    expected = {f.name for f in fields(cls)}
    if set(value) != expected:
        raise ValueError(f"{cls.__name__} missing/unknown fields: {sorted(expected ^ set(value), key=str)}")
    hints = get_type_hints(cls)
    try:
        return cls(**{f.name: _field(value[f.name], f, hints[f.name], True) for f in fields(cls)})
    except (TypeError, OverflowError) as exc:
        raise ValueError(f"invalid {cls.__name__}: {exc}") from exc


def _snapshot(obj):
    hints = get_type_hints(type(obj))
    for f in fields(obj):
        object.__setattr__(obj, f.name, _field(getattr(obj, f.name), f, hints[f.name], False))
    _validate(obj)


def _unique(values, name):
    if len(values) != len(set(values)):
        raise ValueError(f"{name} cannot contain duplicates")


def _validate(obj):
    if isinstance(obj, t.ClockSet):
        for f in fields(obj):
            value = getattr(obj, f.name)
            if value is not None:
                _ns(value, f.name)
    elif isinstance(obj, t.ArtifactRef):
        _digest(obj.sha256, "artifact.sha256")
    elif isinstance(obj, t.ProviderIdentity):
        if not _KEY.fullmatch(obj.backend_id):
            raise ValueError("backend_id must be a registry key")
        if obj.source_revision is not None and not re.fullmatch(r"[0-9a-f]{40}", obj.source_revision):
            raise ValueError("source_revision must be a full Git revision or null")
        for name in ("source_sha256", "artifact_sha256"):
            if getattr(obj, name) is not None:
                _digest(getattr(obj, name), name)
        if obj.source_sha256 is None and obj.artifact_sha256 is None:
            raise ValueError("executed source or artifact digest is required")
    elif isinstance(obj, t.BackendDescriptor):
        for name in ("input_schemas", "result_schemas", "checkpoint_schemas", "capabilities"):
            _unique(getattr(obj, name), name)
    elif isinstance(obj, t.PolicyRef):
        if not re.fullmatch(r"[a-z][a-z0-9_-]*", obj.id):
            raise ValueError("policy id must be a fixed registry key, not an import")
    elif isinstance(obj, t.ScenarioIdentity):
        _digest(obj.base_input_sha256, "base_input_sha256")
        _digest(obj.transformation_sha256, "transformation_sha256")
    elif isinstance(obj, t.ProductManifest):
        if not _KEY.fullmatch(obj.backend_id):
            raise ValueError("backend_id must be a registry key")
        _unique(obj.required_capabilities, "required_capabilities")
        if set(dict(obj.inputs)) & set(obj.inline_inputs):
            raise ValueError("inputs cannot be both inline and artifact-backed")
        if not re.fullmatch(r"[A-Z]{3}", obj.currency):
            raise ValueError("currency must be a three-letter uppercase code")
        try:
            ZoneInfo(obj.timezone)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone must identify an installed IANA zone") from exc
        if obj.input_schema == "rust-session.v1":
            validate_rust_session(obj)
        elif obj.input_schema == "minute-input.v1":
            from .minute import validate_minute_input
            validate_minute_input(obj)
        elif obj.input_schema == "daily-input.v1":
            from .daily import validate_daily_input
            validate_daily_input(obj)
    elif isinstance(obj, t.EvidenceTable):
        if obj.name not in TABLE_NAMES:
            raise ValueError("unknown economic table")
        if obj.status == "unavailable":
            if not obj.reason or obj.rows:
                raise ValueError("unavailable evidence requires a reason and no rows")
        elif obj.reason is not None:
            raise ValueError("available evidence cannot carry an unavailable reason")
    elif isinstance(obj, t.NormalizationReceipt):
        _digest(obj.source_sha256, "normalization.source_sha256")
        _unique(obj.unavailable_fields, "unavailable_fields")
    elif isinstance(obj, t.FailureInfo):
        if obj.last_successful_cursor is not None and obj.last_successful_cursor < 0:
            raise ValueError("last_successful_cursor must be nonnegative or null")
    elif isinstance(obj, t.ProductResult):
        _digest(obj.manifest_sha256, "manifest_sha256")
        _unique(tuple(table.name for table in obj.tables), "tables")
        if (obj.status == "completed") != (obj.failure is None):
            raise ValueError("completed results have no failure; failed/partial results require failure")


def _shape(value, required, optional=()):
    if not isinstance(value, Mapping) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise ValueError(f"profile object requires {required}; optional {optional}")
    return value


def _array(value, name):
    if not isinstance(value, (tuple, list)):
        raise ValueError(f"{name} must be an array")
    return value


def _ordered(left, right, name):
    if left is not None and right is not None and int(left) > int(right):
        raise ValueError(f"{name} has reversed clocks")


def validate_rust_session(manifest: t.ProductManifest) -> None:
    """Validate inline rust-session.v1 data, never dereference artifacts.

    Call again with verified artifact contents substituted by the trusted
    adapter before execution. Native eligibility/accounting remain native.
    """
    clocks = manifest.clocks
    _ordered(clocks.information_ns, clocks.decision_ns, "information/decision")
    _ordered(clocks.decision_ns, clocks.entry_ns, "decision/entry")
    _ordered(clocks.available_ns, clocks.decision_ns, "available/decision")
    _shape(manifest.initial_account, ("cash",))
    _decimal(manifest.initial_account["cash"], "cash")
    _shape(manifest.settings, ("fee_bps", "enforce_t1"))
    _decimal(manifest.settings["fee_bps"], "fee_bps")
    _convert(manifest.settings["enforce_t1"], bool, "enforce_t1")
    combined = set(dict(manifest.inputs)) | set(manifest.inline_inputs)
    if combined != {"instruments"}:
        raise ValueError("rust-session.v1 requires instruments input only")
    if "instruments" in manifest.inline_inputs:
        instruments = _array(manifest.inline_inputs["instruments"], "instruments")
        symbols = []
        for item in instruments:
            _shape(item, ("symbol", "price_precision", "buy_lot"))
            symbols.append(_nonempty(item["symbol"], "symbol"))
            for key in ("price_precision", "buy_lot"):
                _convert(item[key], int, key)
            if not 0 <= item["price_precision"] <= 4 or not 1 <= item["buy_lot"] <= 1_000_000:
                raise ValueError("invalid instrument precision/lot")
        _unique(tuple(symbols), "instrument symbols")
    tapes = dict(manifest.tapes)
    if set(tapes) != {"sessions"}:
        raise ValueError("rust-session.v1 requires an explicit sessions tape only")
    if isinstance(tapes["sessions"], t.ArtifactRef):
        return
    for session in tapes["sessions"]:
        _shape(session, ("session_date", "open_ts_ns", "valuation_ts_ns", "quotes", "orders"))
        try:
            date.fromisoformat(session["session_date"])
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid session_date") from exc
        for key in ("open_ts_ns", "valuation_ts_ns"):
            _ns(session[key], key)
        _ordered(session["open_ts_ns"], session["valuation_ts_ns"], "open/valuation")
        for quote in _array(session["quotes"], "quotes"):
            _shape(quote, ("symbol", "ts_ns", "bid", "ask", "bid_size", "ask_size", "tradable", "limit_up", "limit_down"))
            _nonempty(quote["symbol"], "symbol")
            _ns(quote["ts_ns"], "ts_ns")
            for key in ("bid", "ask", "bid_size", "ask_size"):
                _decimal(quote[key], key)
            for key in ("tradable", "limit_up", "limit_down"):
                _convert(quote[key], bool, key)
        for order in _array(session["orders"], "orders"):
            _shape(order, ("id", "symbol", "information_ts_ns", "side", "quantity"))
            for key in ("id", "symbol"):
                _nonempty(order[key], key)
            _ns(order["information_ts_ns"], "information_ts_ns")
            _decimal(order["quantity"], "quantity")
            if order["side"] not in ("buy", "sell"):
                raise ValueError("side must be buy or sell")


def _to_json(value):
    if is_dataclass(value):
        out = {}
        for f in fields(value):
            item = getattr(value, f.name)
            if f.metadata.get("pairs") or f.metadata.get("tapes"):
                out[f.name] = {key: _to_json(v) for key, v in item}
            else:
                out[f.name] = _to_json(item)
        return out
    if isinstance(value, Mapping):
        return {key: _to_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_json(item) for item in value]
    return value


def parse_manifest(value: Mapping[str, t.JsonValue]) -> t.ProductManifest:
    return _construct(t.ProductManifest, value)


def manifest_to_json(manifest: t.ProductManifest) -> dict[str, t.JsonValue]:
    if type(manifest) is not t.ProductManifest:
        raise ValueError("expected ProductManifest")
    return _to_json(manifest)


def parse_result(value: Mapping[str, t.JsonValue]) -> t.ProductResult:
    return _construct(t.ProductResult, value)


def result_to_json(result: t.ProductResult) -> dict[str, t.JsonValue]:
    if type(result) is not t.ProductResult:
        raise ValueError("expected ProductResult")
    return _to_json(result)


def _strict_loads(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError(f"duplicate JSON field {key}")
            result[key] = item
        return result

    def reject_constant(value):
        raise ValueError(f"nonfinite JSON value {value}")

    try:
        return json.loads(value, object_pairs_hook=pairs, parse_constant=reject_constant)
    except (TypeError, UnicodeError, RecursionError) as exc:
        raise ValueError("invalid product JSON") from exc


def loads_manifest(value: str | bytes) -> t.ProductManifest:
    return parse_manifest(_strict_loads(value))


def loads_result(value: str | bytes) -> t.ProductResult:
    return parse_result(_strict_loads(value))
