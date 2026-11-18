from quant_backtest_engine.product import ProductManifest, ProductResult

from .backends.protocol import BackendContext
from .backends.registry import get_backend


def run_manifest(manifest: ProductManifest, *, context: BackendContext) -> ProductResult:
    """Select exactly one registered owner; validation/failures never trigger fallback."""
    backend = get_backend(manifest.backend_id, context)
    return backend.run(manifest, context)
