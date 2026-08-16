"""Authorization domain errors."""


class AuthorizationError(ValueError):
    """Base authorization domain error."""


class AuthorizationAlreadyDecidedError(AuthorizationError):
    """Raised when a terminal authorization decision would be changed."""


class AuthorizationMismatchError(AuthorizationError):
    """Raised when authorization details do not match an operation."""


class AuthorizationNotGrantedError(AuthorizationError):
    """Raised when a protected operation lacks valid authorization."""

