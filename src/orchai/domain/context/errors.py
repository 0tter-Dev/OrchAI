"""Context domain errors."""


class ContextError(ValueError):
    """Base context domain error."""


class UnauthorizedContextError(ContextError):
    """Raised when context is requested without authorization."""

