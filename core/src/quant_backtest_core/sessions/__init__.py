"""Explicit financial sessions; importing the contracts never imports pandas."""

from quant_backtest_engine.product import ProductManifest

from ..backends.protocol import BackendContext
from .protocol import FinancialSession, LocalPolicy, SessionObservation


def open_session(
    manifest: ProductManifest, *, context: BackendContext, policy: LocalPolicy | None = None
) -> FinancialSession:
    if manifest.backend_id != "python.minute":
        raise ValueError("financial sessions require python.minute")
    from .minute import MinuteFinancialSession

    return MinuteFinancialSession(manifest, context, policy)


def restore_session(
    manifest: ProductManifest,
    checkpoint: bytes,
    *,
    context: BackendContext,
    policy: LocalPolicy | None = None,
) -> FinancialSession:
    if manifest.backend_id != "python.minute":
        raise ValueError("financial sessions require python.minute")
    from .minute import MinuteFinancialSession

    session = MinuteFinancialSession(manifest, context, policy)
    session.restore(checkpoint)
    return session


__all__ = [
    "FinancialSession",
    "LocalPolicy",
    "SessionObservation",
    "open_session",
    "restore_session",
]
