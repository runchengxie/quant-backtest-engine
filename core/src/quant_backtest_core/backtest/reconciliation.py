"""Read-only comparison of caller-supplied, aligned normalized account evidence."""

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType


def _name(value):
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("trimmed nonempty evidence identity required")


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise ValueError("finite evidence amount required")


def _shares(value):
    if type(value) is not int or abs(value) > 2**53:
        raise ValueError("raw integer evidence shares required")


@dataclass(frozen=True)
class OrderEvidence:
    symbol: str
    signed_remaining: int
    limit_price: float | None

    def __post_init__(self):
        _name(self.symbol)
        _shares(self.signed_remaining)
        if not self.signed_remaining:
            raise ValueError("open order remaining must be nonzero")
        if self.limit_price is not None:
            _number(self.limit_price)
            if self.limit_price <= 0:
                raise ValueError("positive limit price required")


@dataclass(frozen=True)
class AccountEvidence:
    account_id: str
    currency: str
    as_of_ns: int
    available_ns: int
    complete: bool
    source_binding: str
    cash: float
    quantities: Mapping[str, int]
    orders: Mapping[str, OrderEvidence]
    fill_ids: tuple[str, ...]
    cash_receivable: float = 0.0
    fill_window_start_ns: int = 0

    def __post_init__(self):
        for value in (self.account_id, self.currency, self.source_binding):
            _name(value)
        if type(self.as_of_ns) is not int or type(self.available_ns) is not int:
            raise ValueError("integer evidence clocks required")
        if type(self.fill_window_start_ns) is not int or self.fill_window_start_ns > self.as_of_ns:
            raise ValueError("integer fill window must precede snapshot")
        if self.available_ns < self.as_of_ns or type(self.complete) is not bool:
            raise ValueError("invalid report clock/completeness")
        _number(self.cash)
        _number(self.cash_receivable)
        for symbol, quantity in self.quantities.items():
            _name(symbol)
            _shares(quantity)
        for ident, order in self.orders.items():
            _name(ident)
            if not isinstance(order, OrderEvidence):
                raise ValueError("normalized OrderEvidence required")
        for ident in self.fill_ids:
            _name(ident)
        if len(set(self.fill_ids)) != len(self.fill_ids):
            raise ValueError("physical fill IDs must be unique")
        object.__setattr__(self, "quantities", MappingProxyType(dict(self.quantities)))
        object.__setattr__(self, "orders", MappingProxyType(dict(self.orders)))
        object.__setattr__(self, "fill_ids", tuple(self.fill_ids))


def reconcile_evidence(local, external, *, decision_ns, cash_atol=0.01):
    _number(cash_atol)
    if cash_atol < 0 or type(decision_ns) is not int:
        raise ValueError("nonnegative tolerance and integer decision clock required")
    aligned = (
        local.account_id == external.account_id
        and local.currency == external.currency
        and local.as_of_ns == external.as_of_ns
        and local.fill_window_start_ns == external.fill_window_start_ns
        and local.complete
        and external.complete
        and max(local.available_ns, external.available_ns) <= decision_ns
    )
    if not aligned:
        return {
            "schema": "account-reconciliation.v1",
            "status": "blocked_evidence",
            "action": "halt_new_orders",
            "reason": "unaligned_incomplete_or_unavailable_evidence",
        }
    shares = {
        s: external.quantities.get(s, 0) - local.quantities.get(s, 0)
        for s in set(local.quantities) | set(external.quantities)
        if external.quantities.get(s, 0) != local.quantities.get(s, 0)
    }
    order_ids = sorted(
        k
        for k in set(local.orders) | set(external.orders)
        if local.orders.get(k) != external.orders.get(k)
    )
    unknown_fills = sorted(set(external.fill_ids) - set(local.fill_ids))
    missing_fills = sorted(set(local.fill_ids) - set(external.fill_ids))
    cash = external.cash - local.cash
    receivable = external.cash_receivable - local.cash_receivable
    if not isfinite(cash) or not isfinite(receivable):
        return {
            "schema": "account-reconciliation.v1",
            "status": "blocked_evidence",
            "action": "halt_new_orders",
            "reason": "amount_difference_overflow",
        }
    mismatch = bool(
        shares
        or order_ids
        or unknown_fills
        or missing_fills
        or abs(cash) > cash_atol
        or abs(receivable) > cash_atol
    )
    return {
        "schema": "account-reconciliation.v1",
        "status": "blocked_mismatch" if mismatch else "matched",
        "action": "halt_new_orders" if mismatch else "retain_local_state",
        "cash_delta": cash,
        "receivable_delta": receivable,
        "share_delta": shares,
        "order_mismatches": order_ids,
        "unknown_external_fills": unknown_fills,
        "missing_external_fills": missing_fills,
        "cash_atol": cash_atol,
        "source_bindings": [local.source_binding, external.source_binding],
        "authority": "caller_supplied_evidence_no_venue_access_no_book_mutation",
    }
