"""Capability checks compare one explicit provider, never a backend union."""
from .types import BackendDescriptor, ProductManifest

VALIDATED_INPUT_SCHEMAS = frozenset({"rust-session.v1"})


def require_capabilities(manifest: ProductManifest, descriptor: BackendDescriptor) -> None:
    if manifest.backend_id != descriptor.identity.backend_id:
        raise ValueError("requested backend differs from selected provider")
    if (manifest.input_schema not in VALIDATED_INPUT_SCHEMAS
            or manifest.input_schema not in descriptor.input_schemas):
        raise ValueError("input schema is unsupported or lacks SDK profile validation")
    if "backtest-product-result.v1" not in descriptor.result_schemas:
        raise ValueError("provider cannot produce the requested result schema")
    missing = set(manifest.required_capabilities) - set(descriptor.capabilities)
    if missing:
        raise ValueError(f"provider lacks required capabilities: {sorted(missing)}")
    units = dict(descriptor.units)
    for key, unit in manifest.units:
        if units.get(key) != unit:
            raise ValueError(f"provider does not support unit {key}={unit}")
