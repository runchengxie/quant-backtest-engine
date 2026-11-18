"""Internal wire shapes for supplied account events; no financial behavior."""

from typing import Any, TypedDict


class _StateWire(TypedDict):
    as_of: str
    cash: float
    quantities: dict[str, int]
    marks: dict[str, float]


class _Order(TypedDict):
    symbol: str
    quantity: int
    remaining: int
    limit_price: float
    locate_quantity: int
    risk_price: float
    fee_remaining: float
    reserved_cash: float
    reserved_risk: float
    reserved_locate: int
    admitted_at: str
    cancel_requested: bool
    cancel_requested_at: str | None
    closed: bool


class _Entitlement(TypedDict):
    symbol: str
    quantity: int
    amount: float
    ex: bool
    paid: bool


class _Settlement(TypedDict):
    symbol: str
    available_at: str
    amount: float
    short_amount: float


class _Reduction(TypedDict):
    symbol: str | None
    quantity: int | None
    reason: str
    status: str


class _Report(TypedDict):
    available_at: str
    actual: _StateWire
    entitlements: dict[str, _Entitlement]
    settlement: list[_Settlement]
    reductions: list[_Reduction]
    kind: str
    payload: dict[str, Any]
    effects: dict[str, list[str]]


class _AccountData(TypedDict):
    actual: _StateWire
    visible: _StateWire
    pending: dict[str, _Order]
    orders: dict[str, _Order]
    processed: dict[str, str]
    fills: dict[str, str]
    entitlements: dict[str, _Entitlement]
    visible_entitlements: dict[str, _Entitlement]
    queue: list[_Report]
    reductions: list[_Reduction]
    visible_reductions: list[_Reduction]
    settlement: list[_Settlement]
    visible_settlement: list[_Settlement]
    event_clock: str
    delivery_clock: str
    control_clock: str
