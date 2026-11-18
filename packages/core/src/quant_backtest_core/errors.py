"""Product boundary errors raised before execution."""


class ProductError(ValueError):
    """Invalid or unavailable product configuration."""


class BackendUnavailableError(ProductError):
    """The explicitly selected backend is unavailable; there is no fallback."""
