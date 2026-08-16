"""Project adapter errors."""


class ProjectAdapterError(RuntimeError):
    """Base project adapter error."""


class ProjectCapabilityError(ProjectAdapterError):
    """Raised when an adapter lacks a required capability."""


class ProjectResourceNotFoundError(ProjectAdapterError):
    """Raised when a project resource cannot be found."""


class ProjectResourceAccessError(ProjectAdapterError):
    """Raised when a project resource is outside the adapter boundary."""

