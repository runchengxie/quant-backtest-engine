"""Immutable, standard-library product DTOs (Python 3.11+).

Wire objects are accepted at the boundary; every JSON subtree is copied into
read-only mappings and tuples. Financial execution belongs to an explicit backend.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Mapping, TypeAlias, Union

JsonValue: TypeAlias = Union[None, bool, int, float, str, list["JsonValue"], dict[str, "JsonValue"]]
FrozenJsonValue: TypeAlias = Union[None, bool, int, float, str, tuple["FrozenJsonValue", ...], Mapping[str, "FrozenJsonValue"]]


class _DTO:
    __slots__ = ()

    def __post_init__(self) -> None:
        from .validation import _snapshot
        _snapshot(self)


def _json_object():
    return field(metadata={"json_object": True})


def _pairs():
    return field(metadata={"pairs": True})


@dataclass(frozen=True, slots=True)
class ClockSet(_DTO):
    available_ns: str | None
    information_ns: str | None
    decision_ns: str | None
    entry_ns: str | None
    effective_ns: str | None
    report_ns: str | None
    valuation_ns: str | None


@dataclass(frozen=True, slots=True)
class ArtifactRef(_DTO):
    uri: str
    sha256: str
    media_type: str


@dataclass(frozen=True, slots=True)
class ProviderIdentity(_DTO):
    backend_id: str
    distribution: str
    version: str
    source_revision: str | None
    source_sha256: str | None
    dependencies: tuple[tuple[str, str], ...] = _pairs()
    artifact_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class BackendDescriptor(_DTO):
    identity: ProviderIdentity
    input_schemas: tuple[str, ...]
    result_schemas: tuple[str, ...]
    checkpoint_schemas: tuple[str, ...]
    capabilities: tuple[str, ...]
    units: tuple[tuple[str, str], ...] = _pairs()
    restrictions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PolicyRef(_DTO):
    id: str
    version: str
    state_schema: str
    config: Mapping[str, FrozenJsonValue] = _json_object()


@dataclass(frozen=True, slots=True)
class ScenarioIdentity(_DTO):
    id: str
    family: str
    seed: int
    base_input_sha256: str
    transformation_sha256: str
    forecast_mode: Literal["fixed", "recomputed"]


@dataclass(frozen=True, slots=True)
class ProductManifest(_DTO):
    backend_id: str
    required_capabilities: tuple[str, ...]
    model_versions: tuple[tuple[str, str], ...] = _pairs()
    input_schema: str
    inputs: tuple[tuple[str, ArtifactRef], ...] = _pairs()
    inline_inputs: Mapping[str, FrozenJsonValue] = _json_object()
    currency: str
    share_basis: Literal["raw", "adjusted"]
    calendar: ArtifactRef
    timezone: str
    units: tuple[tuple[str, str], ...] = _pairs()
    clocks: ClockSet
    initial_account: Mapping[str, FrozenJsonValue] = _json_object()
    settings: Mapping[str, FrozenJsonValue] = _json_object()
    tapes: tuple[tuple[str, ArtifactRef | tuple[FrozenJsonValue, ...]], ...] = field(metadata={"tapes": True})
    policy: PolicyRef | None
    forecast: ArtifactRef | None
    risk: ArtifactRef | None
    scenario: ScenarioIdentity | None
    output_uri: str
    schema: Literal["backtest-product.v1"] = field(default="backtest-product.v1", kw_only=True)


@dataclass(frozen=True, slots=True)
class EvidenceTable(_DTO):
    name: str
    status: Literal["available", "unavailable"]
    rows: tuple[Mapping[str, FrozenJsonValue], ...] = field(metadata={"json_rows": True})
    reason: str | None


@dataclass(frozen=True, slots=True)
class NormalizationReceipt(_DTO):
    adapter_version: str
    source_schema: str
    source_sha256: str
    unavailable_fields: tuple[str, ...]
    schema: Literal["backtest-normalization.v1"] = field(default="backtest-normalization.v1", kw_only=True)


@dataclass(frozen=True, slots=True)
class FailureInfo(_DTO):
    code: str
    message: str
    stage: str
    last_successful_cursor: int | None


@dataclass(frozen=True, slots=True)
class ProductResult(_DTO):
    status: Literal["completed", "failed", "partial"]
    manifest_sha256: str
    provider: ProviderIdentity
    tables: tuple[EvidenceTable, ...]
    summary: Mapping[str, FrozenJsonValue] = _json_object()
    raw_result: ArtifactRef | None
    normalization: NormalizationReceipt
    failure: FailureInfo | None
    scenario: ScenarioIdentity | None
    schema: Literal["backtest-product-result.v1"] = field(default="backtest-product-result.v1", kw_only=True)
