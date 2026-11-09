"""Strict scenario-minute-targets.v1 wire contracts; no numerical dependencies.

The callback is trusted code. Declared consumption and lineage are not proofs of
hidden dependencies or absence of look-ahead. See docs/product/scenarios.md.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Literal, Protocol

from quant_backtest_engine.product import (
    ArtifactRef,
    FailureInfo,
    JsonValue,
    PolicyRef,
    ProductManifest,
    ProductResult,
    ScenarioIdentity,
)
from quant_backtest_engine.product.validation import _decimal, _digest, _nonempty, _ns

from ..artifacts import _constant, _object, json_bytes

TARGET_SCHEMA = "scenario-minute-targets.v1"
MAX_TARGET_BYTES = 16 * 1024 * 1024
INPUT_SCHEMA = "scenario-inputs.v1"
RECEIPT_SCHEMA = "scenario-composition.v1"
# A fixed composition registry, never a dynamic callback/import registry.
PROFILES = frozenset({("python.minute", TARGET_SCHEMA)})
FAMILIES = frozenset({"execution-perturbation", "external-market-path"})
POLICY = {
    "id": "target-weights",
    "version": "v1",
    "state_schema": "target-weights-state.v1",
    "config": {},
}


def plain(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: plain(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, Mapping):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(v) for v in value]
    return value


def digest(value: Any) -> str:
    return hashlib.sha256(json_bytes(value)).hexdigest()


def shape(value: Any, names: tuple[str, ...]) -> None:
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError("scenario object requires exactly: " + ", ".join(names))


def decode(payload: bytes) -> Any:
    return json.loads(payload, object_pairs_hook=_object, parse_constant=_constant)


@dataclass(frozen=True, slots=True)
class ScenarioCase:
    identity: ScenarioIdentity
    manifest: ProductManifest

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ScenarioIdentity) or not isinstance(
            self.manifest, ProductManifest
        ):
            raise ValueError("ScenarioCase requires typed identity and manifest")


@dataclass(frozen=True, slots=True)
class PredictionArtifacts:
    forecast: ArtifactRef | None
    risk: ArtifactRef | None
    policy: PolicyRef | None
    provider_id: str
    provider_version: str
    available_ns: str
    input_sha256: str

    def __post_init__(self) -> None:
        for name in ("forecast", "risk"):
            if getattr(self, name) is not None and not isinstance(getattr(self, name), ArtifactRef):
                raise ValueError(name + " must be ArtifactRef or null")
        if self.policy is not None and not isinstance(self.policy, PolicyRef):
            raise ValueError("policy must be PolicyRef or null")
        _nonempty(self.provider_id, "provider_id")
        _nonempty(self.provider_version, "provider_version")
        _ns(self.available_ns, "available_ns")
        _digest(self.input_sha256, "input_sha256")


class PredictionProvider(Protocol):
    def recompute(
        self, case: ScenarioCase, inputs: Mapping[str, JsonValue]
    ) -> PredictionArtifacts: ...


@dataclass(frozen=True, slots=True)
class ScenarioAttempt:
    identity: ScenarioIdentity
    status: Literal["completed", "failed"]
    result: ProductResult | None
    failure: FailureInfo | None
    composition: ArtifactRef | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, ScenarioIdentity):
            raise ValueError("identity must be ScenarioIdentity")
        if self.status not in ("completed", "failed"):
            raise ValueError("invalid attempt status")
        if self.status == "completed" and (self.result is None or self.failure is not None):
            raise ValueError("completed attempt requires result and no failure")
        if self.status == "failed" and not isinstance(self.failure, FailureInfo):
            raise ValueError("failed attempt requires original failure")
        if self.result is not None and not isinstance(self.result, ProductResult):
            raise ValueError("result must be ProductResult or null")
        if self.composition is not None and not isinstance(self.composition, ArtifactRef):
            raise ValueError("composition must be ArtifactRef or null")


def validate_policy(value: Any) -> None:
    if value != POLICY:
        raise ValueError(
            "scenario profile requires exact empty-config target-weights/v1/target-weights-state.v1"
        )


def validate_inputs(value: dict[str, Any]) -> None:
    shape(
        value,
        (
            "schema",
            "scenario",
            "prediction_request_sha256",
            "resolved_manifest",
            "calendar",
            "sources",
        ),
    )
    if value["schema"] != INPUT_SCHEMA:
        raise ValueError("unsupported callback input schema")
    _digest(value["prediction_request_sha256"], "prediction_request_sha256")
    if digest(value["resolved_manifest"]) != value["prediction_request_sha256"]:
        raise ValueError("prediction view digest mismatch")
    for source in value["sources"]:
        shape(source, ("pointer", "reference", "snapshot", "sha256"))
        _digest(source["sha256"], "source sha256")


def pointer(value: Any, path: str) -> Any:
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("consumed input must be an absolute JSON Pointer")
    for token in path.split("/")[1:]:
        # Reject noncanonical escape and array aliases.
        if "~" in token.replace("~0", "").replace("~1", ""):
            raise ValueError("invalid JSON Pointer escape")
        token = token.replace("~1", "/").replace("~0", "~")
        if isinstance(value, list):
            if not token.isdecimal() or str(int(token)) != token:
                raise ValueError("invalid JSON Pointer index")
            value = value[int(token)]
        elif isinstance(value, dict):
            value = value[token]
        else:
            raise ValueError("JSON Pointer does not resolve")
    return value


def validate_targets(
    payload: Any, prediction: PredictionArtifacts, case: ScenarioCase, envelope: dict[str, Any]
) -> list[dict[str, Any]]:
    shape(
        payload,
        (
            "schema",
            "scenario",
            "provider_id",
            "provider_version",
            "available_ns",
            "input_sha256",
            "targets",
            "source_records",
            "consumed_inputs",
        ),
    )
    if (case.manifest.backend_id, payload["schema"]) not in PROFILES:
        raise ValueError("unsupported scenario composition profile")
    bound_identity = ScenarioIdentity(**payload["scenario"])
    if plain(bound_identity) != plain(case.identity):
        raise ValueError("target scenario identity mismatch")
    for name in ("provider_id", "provider_version", "available_ns", "input_sha256"):
        if payload[name] != getattr(prediction, name):
            raise ValueError("target prediction binding mismatch: " + name)
    if prediction.input_sha256 != digest(envelope):
        raise ValueError("callback input hash mismatch")
    available = int(prediction.available_ns)
    clocks = envelope["resolved_manifest"]["clocks"]
    if prediction.available_ns != clocks["available_ns"]:
        raise ValueError("target availability differs from explicit requested clock")
    if not isinstance(payload["source_records"], list) or not payload["source_records"]:
        raise ValueError("explicit declared source records required")
    ids: set[str] = set()
    for source in payload["source_records"]:
        shape(source, ("id", "kind", "sha256"))
        _nonempty(source["id"], "source id")
        _digest(source["sha256"], "source sha256")
        if (
            source["kind"] not in ("implementation", "dependency", "artifact")
            or source["id"] in ids
        ):
            raise ValueError("invalid or duplicate declared source")
        ids.add(source["id"])
    if not isinstance(payload["consumed_inputs"], list) or not payload["consumed_inputs"]:
        raise ValueError("explicit consumed input records required")
    pointers: set[str] = set()
    for consumed in payload["consumed_inputs"]:
        shape(consumed, ("pointer", "sha256", "available_ns"))
        _ns(consumed["available_ns"], "consumed available_ns")
        _digest(consumed["sha256"], "consumed sha256")
        path = consumed["pointer"]
        value = pointer(envelope, path)
        if path in pointers or digest(value) != consumed["sha256"]:
            raise ValueError("duplicate or mismatched consumed source pointer/hash")
        pointers.add(path)
        if int(consumed["available_ns"]) > available:
            raise ValueError("consumed source is unavailable at prediction time")
        # v1 verifies event-time equality only; availability is a synthetic convention.
        parts = path.split("/")
        if len(parts) != 5 or parts[1:4] != ["resolved_manifest", "inline_inputs", "bars"]:
            raise ValueError("v1 consumed pointers must identify complete minute bar rows")
        if value["time"] != consumed["available_ns"]:
            raise ValueError("consumed bar availability differs from its observed close clock")
    rows = payload["targets"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonempty execution-ready targets required")
    for row in rows:
        required = {"information_time", "decision_time", "entry_time", "symbol", "weight"}
        if (
            not isinstance(row, dict)
            or not required <= row.keys()
            or set(row) - required - {"order_type"}
        ):
            raise ValueError("strict target row with explicit clocks required")
        _nonempty(row["symbol"], "symbol")
        _decimal(row["weight"], "weight")
        for key in ("information_time", "decision_time", "entry_time"):
            _ns(row[key], key)
        if (
            not int(row["information_time"])
            <= available
            <= int(row["decision_time"])
            <= int(row["entry_time"])
        ):
            raise ValueError("target information/availability/decision/entry ordering mismatch")
        for field_name, clock_name in (
            ("information_time", "information_ns"),
            ("decision_time", "decision_ns"),
            ("entry_time", "entry_ns"),
        ):
            if row[field_name] != clocks[clock_name]:
                raise ValueError("v1 target clocks differ from the requested single decision cut")
    return rows


RECEIPT_FIELDS = (
    "schema",
    "identity",
    "status",
    "stage",
    "original_manifest",
    "original_manifest_sha256",
    "requested_manifest",
    "requested_manifest_sha256",
    "prediction_request_manifest",
    "prediction_request_sha256",
    "input_view_projection",
    "source_artifacts",
    "callback_inputs",
    "callback_input_sha256",
    "prediction",
    "target_artifact",
    "callback_source",
    "lineage",
    "projection",
    "adapter",
    "executed_manifest",
    "executed_manifest_sha256",
    "owner_call",
    "owner_result",
    "failure",
    "last_successful_checkpoint",
    "checkpoint_scope",
    "trust",
)


def validate_receipt(value: dict[str, Any]) -> None:
    shape(value, RECEIPT_FIELDS)
    if value["schema"] != RECEIPT_SCHEMA or value["status"] not in ("completed", "failed"):
        raise ValueError("invalid composition receipt")
    for name in ("original_manifest", "requested_manifest", "executed_manifest"):
        if value[name] is not None and digest(value[name]) != value[name + "_sha256"]:
            raise ValueError("receipt manifest identity mismatch")
    if value["callback_inputs"] is not None:
        validate_inputs(value["callback_inputs"])
        if value["prediction_request_manifest"] != value["callback_inputs"][
            "resolved_manifest"
        ] or value["prediction_request_sha256"] != digest(value["prediction_request_manifest"]):
            raise ValueError("receipt prediction view identity mismatch")
        if digest(value["callback_inputs"]) != value["callback_input_sha256"]:
            raise ValueError("receipt callback input identity mismatch")
