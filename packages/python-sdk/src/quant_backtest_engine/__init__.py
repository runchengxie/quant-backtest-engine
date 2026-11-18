"""Standard-library-only client for the independent engine wire contract."""

from .client import EngineClient, EngineProtocolError

__all__ = ["EngineClient", "EngineProtocolError"]
