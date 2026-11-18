"""Optional explicit product execution; base imports only stdlib and the SDK."""

from .backends.protocol import BackendContext
from .runner import run_manifest

__all__ = ["BackendContext", "run_manifest"]
__version__ = "0.2.0"
