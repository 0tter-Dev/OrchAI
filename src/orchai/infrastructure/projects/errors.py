"""Project adapter errors."""


class ProjectAdapterError(RuntimeError):
    """Base project adapter error."""


class ProjectCapabilityError(ProjectAdapterError):
    """Raised when an adapter lacks a required capability."""


class ProjectResourceNotFoundError(ProjectAdapterError):
    """Raised when a project resource cannot be found."""


class ProjectResourceAccessError(ProjectAdapterError):
    """Raised when a project resource is outside the adapter boundary."""


class ProjectWriteError(ProjectAdapterError):
    """Raised when a project write operation fails."""


class ProjectCommandExecutionError(ProjectAdapterError):
    """Raised when a bounded project command cannot be executed."""


class ProjectGitError(ProjectAdapterError):
    """Raised when a Git-bound operation fails."""
