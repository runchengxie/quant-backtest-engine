"""Lazy, immutable public session contracts; no numerical imports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from quant_backtest_engine.product import JsonValue, ProductResult


def freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(freeze(item) for item in value)
    if value is None or type(value) in (bool, int, float, str):
        return value
    raise TypeError("observation requires JSON values")


@dataclass(frozen=True, slots=True)
class SessionObservation:
    cursor: int
    as_of_ns: str
    account: Mapping[str, JsonValue]
    reports: tuple[Mapping[str, JsonValue], ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "account", freeze(self.account))
        object.__setattr__(self, "reports", freeze(self.reports))


class LocalPolicy(Protocol):
    policy_id: str
    version: str
    state_schema: str

    def decide(self, observation: SessionObservation) -> Mapping[str, str]: ...
    def state(self) -> JsonValue: ...
    def restore_state(self, state: JsonValue) -> None: ...


class FinancialSession(Protocol):
    def step(self) -> SessionObservation | None: ...
    def observe(self) -> SessionObservation: ...
    def checkpoint(self) -> bytes: ...
    def finish(self) -> ProductResult: ...
