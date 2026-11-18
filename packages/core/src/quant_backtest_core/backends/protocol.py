from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from quant_backtest_engine.product import BackendDescriptor, ProductManifest, ProductResult


@dataclass(frozen=True, slots=True)
class BackendContext:
    """Trusted host configuration; never populated from manifest executable text."""

    artifact_root: Path
    output_root: Path
    rust_executable: Path | None = None
    rust_sha256: str | None = None


class Backend(Protocol):
    def descriptor(self) -> BackendDescriptor: ...
    def validate(self, manifest: ProductManifest, context: BackendContext) -> None: ...
    def run(self, manifest: ProductManifest, context: BackendContext) -> ProductResult: ...
