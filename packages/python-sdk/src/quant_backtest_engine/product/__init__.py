"""Additive immutable product envelopes; importing this module never loads a core."""
from .types import (
    ArtifactRef, BackendDescriptor, ClockSet, EvidenceTable, FailureInfo,
    FrozenJsonValue, JsonValue, NormalizationReceipt, PolicyRef, ProductManifest,
    ProductResult, ProviderIdentity, ScenarioIdentity,
)
from .validation import (
    TABLE_NAMES, loads_manifest, loads_result, manifest_to_json, parse_manifest,
    parse_result, result_to_json, validate_rust_session,
)
from .capabilities import require_capabilities

__all__ = [
    "ArtifactRef", "BackendDescriptor", "ClockSet", "EvidenceTable", "FailureInfo",
    "FrozenJsonValue", "JsonValue", "NormalizationReceipt", "PolicyRef",
    "ProductManifest", "ProductResult", "ProviderIdentity", "ScenarioIdentity",
    "TABLE_NAMES", "loads_manifest", "loads_result", "manifest_to_json",
    "parse_manifest", "parse_result", "result_to_json", "validate_rust_session",
    "require_capabilities",
]
