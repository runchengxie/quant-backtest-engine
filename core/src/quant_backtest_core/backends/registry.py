from ..errors import BackendUnavailableError, ProductError
from .protocol import Backend, BackendContext


def get_backend(backend_id: str, context: BackendContext) -> Backend:
    if backend_id == "rust.nautilus.sessions":
        from .rust import RustBackend

        return RustBackend(context)
    if backend_id == "python.minute":
        from .minute import MinuteBackend

        return MinuteBackend(context)
    if backend_id == "python.daily":
        raise BackendUnavailableError(
            f"{backend_id} is not implemented in core 0.2.0; installing its extra does not enable it"
        )
    raise ProductError(f"unknown backend: {backend_id}")
