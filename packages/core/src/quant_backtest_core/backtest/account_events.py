"""Raw integer-share PAPER event adapter over supplied-fill accounting.

Financial reports use conservative causal-prefix delivery: later snapshots wait
for earlier reports. Independent market quotes belong to the caller. No matcher,
broker connection, automatic liquidation, or historical calibration is provided.
"""

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from math import fsum, isfinite
from typing import Literal

import pandas as pd

from ._account_event_types import (
    _AccountData,
    _Order,
    _StateWire,
)
from .paper_account import HouseMargin, Observed, PaperFill, PaperState, project_paper_account


def _clock(value) -> pd.Timestamp:
    if not isinstance(value, pd.Timestamp) or pd.isna(value) or value.tzinfo is None:
        raise ValueError("clocks must be aware pd.Timestamp values")
    return value


def _finite(value, *, minimum=None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("finite number required")
    if minimum is not None and value < minimum:
        raise ValueError("number below permitted minimum")
    return value


def _integer(value, *, nonzero=False) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or abs(value) > 2**53
        or (nonzero and not value)
    ):
        raise ValueError("raw integer shares required")
    return value


def _name(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("nonempty trimmed identifier required")
    return value


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as error:
        raise ValueError("finite JSON-native payload required") from error


def _digest(value):
    return sha256(_json(value).encode()).hexdigest()


def _total(values):
    try:
        return _finite(fsum(values))
    except OverflowError as error:
        raise ValueError("nonfinite aggregate") from error


def _wire(state: PaperState) -> _StateWire:
    return {
        "as_of": state.as_of.isoformat(),
        "cash": state.cash,
        "quantities": {s: _integer(int(q)) for s, q in sorted(state.quantities.items())},
        "marks": dict(sorted(state.marks.items())),
    }


def _state(value: _StateWire):
    return PaperState(
        _clock(pd.Timestamp(value["as_of"])), value["cash"], value["quantities"], value["marks"]
    )


def _receivables(entitlements):
    return _total(
        e["quantity"] * e["amount"] for e in entitlements.values() if e["ex"] and not e["paid"]
    )


def _account_nav(state, entitlements):
    return _total(
        [
            state["cash"],
            _receivables(entitlements),
            *(q * state["marks"][s] for s, q in state["quantities"].items()),
        ]
    )


def _margin_diagnostics(state, entitlements, margin):
    required = _total(
        abs(q) * state["marks"][s] * (margin.long_haircut if q > 0 else margin.short_haircut)
        for s, q in state["quantities"].items()
    )
    excess = _total([_account_nav(state, entitlements), -required])
    return {
        "required": required,
        "excess": excess,
        "breach": excess < 0,
        "equity_basis": "nav_including_signed_receivables",
    }


def _validate_data(data):
    for key, entitlement_key in (("actual", "entitlements"), ("visible", "visible_entitlements")):
        state = data[key]
        _clock(pd.Timestamp(state["as_of"]))
        cash = _finite(state["cash"])
        values = []
        for symbol, quantity in state["quantities"].items():
            _name(symbol)
            _integer(quantity)
            values.append(_finite(quantity * _finite(state["marks"][symbol], minimum=1e-12)))
        _total(abs(v) for v in values)
        _total([cash, *values, _receivables(data[entitlement_key])])
    for key in ("reserved_cash", "reserved_risk", "reserved_locate"):
        _finite(_total(o[key] for o in data["pending"].values()), minimum=0)
    for key in ("settlement", "visible_settlement"):
        _finite(_total(s["amount"] for s in data[key]), minimum=0)


@dataclass(frozen=True)
class EventAccountConfig:
    """Explicit provenance identities and assumed PAPER venue/funding policy.

    Settlement is a calendar-second cash delay, independent of A-share T+1
    inventory restrictions. Explicit per-fill cash_available_at overrides it.
    Fractional split shares are unsupported and reject the complete event.
    """

    source_binding: str
    input_binding: str
    margin: HouseMargin = field(default_factory=lambda: HouseMargin(1.0, 1.0, 1.0))
    financing_basis: Literal["cash", "unrestricted_cash"] = "cash"
    max_age_seconds: float = 864000.0
    credit_limit: float = 0.0
    settlement_delay_seconds: float = 0.0

    def __post_init__(self):
        _name(self.source_binding)
        _name(self.input_binding)
        for value in (
            self.max_age_seconds,
            self.credit_limit,
            self.settlement_delay_seconds,
            self.margin.long_haircut,
            self.margin.short_haircut,
            self.margin.short_proceeds_fraction,
        ):
            _finite(value, minimum=0)
        if self.financing_basis not in ("cash", "unrestricted_cash"):
            raise ValueError("unsupported financing basis")


@dataclass(frozen=True)
class AccountEvent:
    event_id: str
    kind: str
    occurred_at: pd.Timestamp
    available_at: pd.Timestamp
    payload: dict


class AccountEventAdapter:
    """Transactional events, pending reservations and replayable delayed reports.

    Admission sees delivered financial state only. Cash, gross-risk and short
    locate reservations never net opposite orders, expire, or release on cancel
    request. Caller-supplied fills must respect the order limit and remaining
    integer quantity; a cancel acknowledgement terminates further fills.
    """

    _data: _AccountData

    def __init__(self, initial: PaperState, config: EventAccountConfig):
        _clock(initial.as_of)
        _finite(initial.cash)
        for symbol, quantity in initial.quantities.items():
            _name(symbol)
            _integer(quantity)
            _finite(initial.marks[symbol], minimum=0.000000000001)
        for symbol, mark in initial.marks.items():
            _name(symbol)
            _finite(mark, minimum=0.000000000001)
        self.config = config
        self._data = {
            "actual": _wire(initial),
            "visible": _wire(initial),
            "pending": {},
            "orders": {},
            "processed": {},
            "fills": {},
            "entitlements": {},
            "visible_entitlements": {},
            "queue": [],
            "reductions": [],
            "visible_reductions": [],
            "settlement": [],
            "visible_settlement": [],
            "event_clock": initial.as_of.isoformat(),
            "delivery_clock": initial.as_of.isoformat(),
            "control_clock": initial.as_of.isoformat(),
        }
        _validate_data(self._data)
        self.available_cash(initial.as_of)
        self._update_margin(self._data)
        self._data["visible_reductions"] = deepcopy(self._data["reductions"])

    @property
    def actual(self):
        return _state(self._data["actual"])

    @property
    def visible(self):
        return _state(self._data["visible"])

    @property
    def pending(self):
        return deepcopy(self._data["pending"])

    @property
    def entitlements(self):
        return deepcopy(self._data["entitlements"])

    @property
    def reductions(self):
        return deepcopy(self._data["reductions"])

    @property
    def visible_reductions(self):
        return deepcopy(self._data["visible_reductions"])

    @property
    def visible_receivables(self):
        return _receivables(self._data["visible_entitlements"])

    @property
    def actual_nav(self):
        return _account_nav(self._data["actual"], self._data["entitlements"])

    @property
    def visible_nav(self):
        return _account_nav(self._data["visible"], self._data["visible_entitlements"])

    @property
    def actual_margin(self):
        return _margin_diagnostics(
            self._data["actual"], self._data["entitlements"], self.config.margin
        )

    @property
    def visible_margin(self):
        return _margin_diagnostics(
            self._data["visible"], self._data["visible_entitlements"], self.config.margin
        )

    def available_cash(self, as_of):
        """Delivered cash net of unsettled proceeds, short reserve and buy orders."""
        at = _clock(as_of)
        if at < pd.Timestamp(self._data["delivery_clock"]):
            raise ValueError("cash query predates delivered state")
        unsettled, short_reserve, overlap = self._cash_reserves(at)
        reserved = _total(o["reserved_cash"] for o in self._data["pending"].values())
        return _total([self.visible.cash, -unsettled, -reserved, -short_reserve, overlap])

    def _cash_reserves(self, at):
        unsettled = [
            s for s in self._data["visible_settlement"] if pd.Timestamp(s["available_at"]) > at
        ]
        restricted = {
            s: _finite(-q * self.visible.marks[s] * self.config.margin.short_proceeds_fraction)
            for s, q in self.visible.quantities.items()
            if q < 0
        }
        overlap = _total(
            min(
                amount,
                _total(item["short_amount"] for item in unsettled if item["symbol"] == symbol),
            )
            for symbol, amount in restricted.items()
        )
        return (_total(item["amount"] for item in unsettled), _total(restricted.values()), overlap)

    def _mutation_clock(self, as_of):
        at = _clock(as_of)
        if at < pd.Timestamp(self._data["control_clock"]):
            raise ValueError("mutation predates account control clock")
        return at

    def admit_order(
        self,
        order_id,
        symbol,
        quantity,
        limit_price,
        *,
        as_of,
        locate_quantity,
        risk_limit,
        risk_price=None,
        fee_budget=0,
    ):
        """Reserve against delivered state, supplied known locate and gross cap.

        locate_quantity and risk_limit are caller observations at as_of; the
        adapter never consults undelivered truth to decide admission.
        """
        at = self._mutation_clock(as_of)
        if at < pd.Timestamp(self._data["delivery_clock"]):
            raise ValueError("admission predates visible clock")
        _name(order_id)
        _name(symbol)
        _integer(quantity, nonzero=True)
        _integer(locate_quantity)
        _finite(locate_quantity, minimum=0)
        _finite(limit_price, minimum=0.000000000001)
        _finite(risk_limit, minimum=0)
        risk_price = limit_price if risk_price is None else _finite(risk_price, minimum=limit_price)
        _finite(fee_budget, minimum=0)
        if order_id in self._data["orders"]:
            raise ValueError("order id already used")
        pending = self._data["pending"]
        cash = _total([max(quantity, 0) * limit_price, fee_budget])
        risk = _finite(abs(quantity) * risk_price)
        gross = _total(abs(q) * self.visible.marks[s] for s, q in self.visible.quantities.items())
        sales = sum(max(-o["remaining"], 0) for o in pending.values() if o["symbol"] == symbol)
        owned = max(self.visible.quantities.get(symbol, 0) - sales, 0)
        short = max(-quantity - owned, 0)
        located = sum(o["reserved_locate"] for o in pending.values() if o["symbol"] == symbol)
        if cash > _total([self.available_cash(at), self.config.credit_limit]):
            raise ValueError("cash reservation exceeds buying power")
        if _total([gross, risk, *(o["reserved_risk"] for o in pending.values())]) > risk_limit:
            raise ValueError("worst-case gross risk reservation exceeds limit")
        already_short = max(-self.visible.quantities.get(symbol, 0), 0)
        if short and already_short + located + short > locate_quantity:
            raise ValueError("short locate reservation exceeds known units")
        order: _Order = {
            "symbol": symbol,
            "quantity": quantity,
            "remaining": quantity,
            "limit_price": limit_price,
            "locate_quantity": locate_quantity,
            "risk_price": risk_price,
            "fee_remaining": fee_budget,
            "reserved_cash": cash,
            "reserved_risk": risk,
            "reserved_locate": short,
            "admitted_at": at.isoformat(),
            "cancel_requested": False,
            "cancel_requested_at": None,
            "closed": False,
        }
        self._data["pending"][order_id] = deepcopy(order)
        self._data["orders"][order_id] = deepcopy(order)
        self._data["control_clock"] = at.isoformat()

    def request_cancel(self, order_id, *, as_of):
        self._mutation_clock(as_of)
        if _clock(as_of) < pd.Timestamp(self._data["delivery_clock"]):
            raise ValueError("cancel request predates visible clock")
        if order_id not in self._data["pending"]:
            raise ValueError("unknown pending order")
        if as_of < pd.Timestamp(self._data["pending"][order_id]["admitted_at"]):
            raise ValueError("cancel request predates admission")
        for key in ("pending", "orders"):
            order = self._data[key][order_id]
            order["cancel_requested"] = True
            if order["cancel_requested_at"] is None:
                order["cancel_requested_at"] = as_of.isoformat()
        self._data["control_clock"] = as_of.isoformat()

    def apply(self, event: AccountEvent):
        """Apply one ordered actual event atomically; identical replay is a no-op."""
        _name(event.event_id)
        _name(event.kind)
        occurred, available = _clock(event.occurred_at), _clock(event.available_at)
        if available < occurred:
            raise ValueError("report available before occurrence")
        payload = json.loads(_json(event.payload))
        if not isinstance(payload, dict) or "duplicate_fill" in payload:
            raise ValueError("event payload must be an object without reserved fields")
        identity = _digest(
            {
                "kind": event.kind,
                "occurred_at": occurred.isoformat(),
                "available_at": available.isoformat(),
                "payload": payload,
            }
        )
        previous = self._data["processed"].get(event.event_id)
        if previous is not None:
            if previous != identity:
                raise ValueError("event id reused with different payload")
            return
        self._mutation_clock(occurred)
        if occurred < pd.Timestamp(self._data["event_clock"]):
            raise ValueError("event occurrence clock regressed")
        if available < pd.Timestamp(self._data["delivery_clock"]):
            raise ValueError("new event report predates already delivered knowledge")
        candidate = deepcopy(self._data)
        try:
            effects = self._apply_event(candidate, event.kind, payload, occurred, event.event_id)
            self._update_margin(candidate)
        except (KeyError, TypeError, OverflowError) as error:
            raise ValueError("malformed or unknown event reference") from error
        candidate["processed"][event.event_id] = identity
        candidate["event_clock"] = occurred.isoformat()
        candidate["control_clock"] = occurred.isoformat()
        candidate["queue"].append(
            {
                "available_at": available.isoformat(),
                "actual": deepcopy(candidate["actual"]),
                "entitlements": deepcopy(candidate["entitlements"]),
                "settlement": deepcopy(candidate["settlement"]),
                "reductions": deepcopy(candidate["reductions"]),
                "kind": event.kind,
                "payload": payload,
                "effects": effects or {},
            }
        )
        _json(candidate)
        _validate_data(candidate)
        self._data = candidate

    def _apply_event(self, data, kind, payload, at, event_id):
        if kind in ("projection", "fill"):
            self._project(data, payload, at, event_id, fill=kind == "fill")
            return None
        if kind == "cancel_ack":
            self._cancel_ack(data, payload, at)
            return None
        if at != pd.Timestamp(data["actual"]["as_of"]):
            raise ValueError("project to economic event clock first")
        if kind in {"cashflow", "fee_adjustment"}:
            self._cash_adjustment(data, kind, payload)
            return None
        if kind.startswith("dividend_"):
            self._dividend(data, kind, payload)
        elif kind == "split":
            return {"split_order_ids": self._split(data, payload)}
        elif kind == "recall":
            symbol = _name(payload["symbol"])
            quantity = data["actual"]["quantities"].get(symbol, 0)
            if quantity < 0:
                data["reductions"].append(
                    {
                        "symbol": symbol,
                        "quantity": -quantity,
                        "reason": "recall",
                        "status": "required",
                    }
                )
        else:
            raise ValueError("unknown account event kind")
        return None

    def _cash_adjustment(self, data, kind, payload):
        _name(payload["reason"])
        amount = _finite(payload["amount"])
        if kind == "fee_adjustment" and amount < 0:
            raise ValueError("fee adjustment must be a nonnegative cost")
        cash = _total([data["actual"]["cash"], amount if kind == "cashflow" else -amount])
        if cash < -self.config.credit_limit:
            raise ValueError("cash adjustment exceeds configured credit")
        data["actual"]["cash"] = cash

    def _cancel_ack(self, data, payload, at):
        order = data["orders"][payload["order_id"]]
        if not order["cancel_requested"] or at < pd.Timestamp(order["cancel_requested_at"]):
            raise ValueError("cancel acknowledgement predates cancel request")
        if order["closed"] and order["remaining"]:
            raise ValueError("order already closed")
        order["closed"] = True

    def _project(self, data, payload, at, event_id, *, fill):
        inputs = payload["inputs"]
        if inputs.get("price_basis") != "raw":
            raise ValueError("projection requires explicit raw price basis")
        observed = {
            name: {
                s: Observed(v["value"], _clock(pd.Timestamp(v["available_at"])))
                for s, v in inputs[name].items()
            }
            for name in ("marks", "borrow_rates", "locate_quantities")
        }
        rate = inputs["financing_rate"]
        opening = pd.Timestamp(data["actual"]["as_of"])
        for name, values in observed.items():
            clock = opening if name == "borrow_rates" else at
            for observation in values.values():
                _finite(observation.value, minimum=1e-12 if name == "marks" else 0)
                age = clock - _clock(observation.available_at)
                if age < pd.Timedelta(0) or age.total_seconds() > self.config.max_age_seconds:
                    raise ValueError("future or stale supplied observation")
        fills = []
        if fill:
            modeled_fill = self._fill(data, payload, at, event_id)
            if modeled_fill is None:
                return
            fills = [modeled_fill]
        max_age = pd.Timedelta(seconds=self.config.max_age_seconds)
        if not isinstance(max_age, pd.Timedelta):
            raise ValueError("finite max-age duration required")
        projection = project_paper_account(
            _state(data["actual"]),
            as_of=at,
            marks=observed["marks"],
            borrow_rates=observed["borrow_rates"],
            locate_quantities=observed["locate_quantities"],
            financing_rate=Observed(rate["value"], _clock(pd.Timestamp(rate["available_at"]))),
            financing_basis=self.config.financing_basis,
            margin=self.config.margin,
            max_age=max_age,
            fills=fills,
        )
        data["actual"] = _wire(projection.state)
        for symbol in projection.borrow_breaches:
            data["reductions"].append(
                {
                    "symbol": symbol,
                    "quantity": -data["actual"]["quantities"][symbol],
                    "reason": "recall",
                    "status": "required",
                }
            )

    def _update_margin(self, data):
        diagnostics = _margin_diagnostics(data["actual"], data["entitlements"], self.config.margin)
        active = [
            intent
            for intent in data["reductions"]
            if intent["reason"] == "margin" and intent["status"] == "required"
        ]
        if diagnostics["breach"] and not active:
            data["reductions"].append(
                {"symbol": None, "quantity": None, "reason": "margin", "status": "required"}
            )
        elif not diagnostics["breach"]:
            for intent in active:
                intent["status"] = "resolved"

    def _fill(self, data, payload, at, event_id):
        order = data["orders"][payload["order_id"]]
        quantity = _integer(payload["quantity"], nonzero=True)
        price = _finite(payload["price"], minimum=0.000000000001)
        fee = _finite(payload.get("fee", 0), minimum=0)
        fill_id = _name(payload.get("fill_id", event_id))
        economic = _digest({k: v for k, v in payload.items() if k != "fill_id"})
        if fill_id in data["fills"]:
            if data["fills"][fill_id] != economic:
                raise ValueError("fill id reused with different economics")
            payload["duplicate_fill"] = True
            return None
        if order["closed"] or quantity * order["remaining"] <= 0:
            raise ValueError("fill for closed order or wrong side")
        if at < pd.Timestamp(order["admitted_at"]):
            raise ValueError("fill predates order admission")
        _integer(data["actual"]["quantities"].get(order["symbol"], 0) + quantity)
        if abs(quantity) > abs(order["remaining"]):
            raise ValueError("fill exceeds remaining order")
        if (price - order["limit_price"]) * quantity > 0:
            raise ValueError("fill violates order limit")
        self._validate_fill_budget(order, price, fee)
        order["remaining"] -= quantity
        order["fee_remaining"] -= fee
        order["closed"] = not order["remaining"]
        data["fills"][fill_id] = economic
        cash_at = pd.Timestamp(
            payload.get(
                "cash_available_at", at + pd.Timedelta(seconds=self.config.settlement_delay_seconds)
            )
        )
        if _clock(cash_at) < at:
            raise ValueError("cash availability predates fill")
        if quantity < 0:
            before = data["actual"]["quantities"].get(order["symbol"], 0)
            opened_short = max(-(before + quantity), 0) - max(-before, 0)
            proceeds = _finite(max(-quantity * price - fee, 0))
            data["settlement"].append(
                {
                    "symbol": order["symbol"],
                    "available_at": cash_at.isoformat(),
                    "amount": proceeds,
                    "short_amount": proceeds * (opened_short / -quantity),
                }
            )
        return PaperFill(order["symbol"], quantity, price, at, fee)

    def _validate_fill_budget(self, order, price, fee):
        if price > order["risk_price"]:
            raise ValueError("fill exceeds admitted risk price bound")
        if fee > order["fee_remaining"]:
            raise ValueError("fill exceeds admitted fee budget")

    def _dividend(self, data, kind, payload):
        ident = _name(payload["entitlement_id"])
        if kind == "dividend_record":
            if ident in data["entitlements"]:
                raise ValueError("entitlement id reused")
            symbol = _name(payload["symbol"])
            data["entitlements"][ident] = {
                "symbol": symbol,
                "quantity": data["actual"]["quantities"].get(symbol, 0),
                "amount": 0,
                "ex": False,
                "paid": False,
            }
            return
        entitlement = data["entitlements"][ident]
        if kind == "dividend_ex" and not entitlement["ex"]:
            entitlement["amount"] = _finite(payload["amount"], minimum=0)
            entitlement["ex"] = True
        elif kind == "dividend_pay" and entitlement["ex"] and not entitlement["paid"]:
            data["actual"]["cash"] += entitlement["quantity"] * entitlement["amount"]
            entitlement["paid"] = True
        else:
            raise ValueError("invalid dividend lifecycle transition")

    def _split(self, data, payload):
        symbol = _name(payload["symbol"])
        numerator = _integer(payload["numerator"], nonzero=True)
        denominator = _integer(payload["denominator"], nonzero=True)
        if numerator <= 0 or denominator <= 0 or payload["price_basis"] != "raw":
            raise ValueError("positive split ratio and raw prices required")

        def shares(value):
            if value * numerator % denominator:
                raise ValueError("fractional split shares unsupported")
            return _integer(value * numerator // denominator)

        quantities = data["actual"]["quantities"]
        if symbol in quantities:
            quantities[symbol] = shares(quantities[symbol])
        if symbol in data["actual"]["marks"]:
            data["actual"]["marks"][symbol] *= denominator / numerator
        affected = []
        for ident, order in sorted(data["orders"].items()):
            if order["symbol"] == symbol and not order["closed"]:
                self._split_order(order, shares, denominator / numerator)
                affected.append(ident)
        # Recorded entitlements remain in their record-date units. The declared
        # amount at ex must use those same units, even across a subsequent split.
        return affected

    def _split_order(self, order, shares, price_ratio):
        for key in ("quantity", "remaining", "locate_quantity", "reserved_locate"):
            order[key] = _integer(shares(order[key]))
        for key in ("limit_price", "risk_price"):
            order[key] = _finite(order[key] * price_ratio, minimum=1e-12)

    def deliver(self, as_of):
        """Deliver the available causal prefix; never infer an unreceived report."""
        at = self._mutation_clock(as_of)
        if at < pd.Timestamp(self._data["delivery_clock"]):
            raise ValueError("delivery clock regressed")
        data = deepcopy(self._data)
        while data["queue"] and pd.Timestamp(data["queue"][0]["available_at"]) <= at:
            report = data["queue"].pop(0)
            data["visible"] = report["actual"]
            data["visible_entitlements"] = report["entitlements"]
            data["visible_settlement"] = report["settlement"]
            data["visible_reductions"] = report["reductions"]
            self._release_report(data, report)
        self._refresh_locates(data)
        data["delivery_clock"] = at.isoformat()
        data["control_clock"] = at.isoformat()
        _validate_data(data)
        self._data = data

    def _refresh_locates(self, data):
        owned = {s: max(q, 0) for s, q in data["visible"]["quantities"].items()}
        for _, order in sorted(data["pending"].items()):
            symbol = order["symbol"]
            sales = max(-order["remaining"], 0)
            used = min(sales, owned.get(symbol, 0))
            owned[symbol] = owned.get(symbol, 0) - used
            order["reserved_locate"] = sales - used

    def _release_report(self, data, report):
        kind, payload = report["kind"], report["payload"]
        if kind == "fill" and not payload.get("duplicate_fill"):
            order = data["pending"][payload["order_id"]]
            order["remaining"] -= payload["quantity"]
            order["fee_remaining"] -= payload.get("fee", 0)
            remaining = abs(order["remaining"])
            order["reserved_cash"] = _total(
                [max(order["remaining"], 0) * order["limit_price"], order["fee_remaining"]]
            )
            order["reserved_risk"] = remaining * order["risk_price"]
            order["reserved_locate"] = max(-order["remaining"], 0)
            if not remaining:
                del data["pending"][payload["order_id"]]
        elif kind == "cancel_ack":
            data["pending"].pop(payload["order_id"], None)
        elif kind == "split":
            num, den = payload["numerator"], payload["denominator"]
            for ident in report["effects"]["split_order_ids"]:
                if ident in data["pending"]:
                    self._split_order(data["pending"][ident], lambda x: x * num // den, den / num)

    def checkpoint(self):
        """Return deterministic JSON-native state with schema/config/content binding."""
        content = {"schema": 2, "config": asdict(self.config), "state": deepcopy(self._data)}
        return {**content, "digest": _digest(content)}

    @classmethod
    def restore(cls, checkpoint, config):
        """Validate the complete content digest and exact configuration identity."""
        value = json.loads(_json(checkpoint))
        digest = value.pop("digest", None)
        if digest != _digest(value):
            raise ValueError("checkpoint content digest mismatch")
        if value.get("schema") != 2:
            raise ValueError("unsupported checkpoint schema")
        if value.get("config") != asdict(config):
            raise ValueError("checkpoint config/source/input binding mismatch")
        restored = cls(_state(value["state"]["actual"]), config)
        restored._data = value["state"]
        _validate_data(restored._data)
        return restored
