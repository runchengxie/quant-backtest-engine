from ..errors import ProductError
from .protocol import Backend, BackendContext


def get_backend(backend_id: str, context: BackendContext) -> Backend:
    if backend_id == "rust.nautilus.sessions":
        from .rust import RustBackend

        return RustBackend(context)
    if backend_id == "python.minute":
        from .minute import MinuteBackend

        return MinuteBackend(context)
    if backend_id == "python.daily":
        from .daily import DailyBackend

        return DailyBackend(context)
    raise ProductError(f"unknown backend: {backend_id}")
