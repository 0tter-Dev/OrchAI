"""Identity domain errors."""


class IdentityError(ValueError):
    """Base identity domain error."""


class UserAlreadyActiveError(IdentityError):
    """Raised when activating a user that is already active."""


class UserAlreadyInactiveError(IdentityError):
    """Raised when deactivating a user that is already inactive."""


class RefreshTokenAlreadyRevokedError(IdentityError):
    """Raised when revoking a refresh token that is already revoked."""


class DuplicateUsernameError(IdentityError):
    """Raised when a username is already taken by another user."""


class DuplicateAccessRoleNameError(IdentityError):
    """Raised when an access role name is already in use."""


class DuplicatePermissionKeyError(IdentityError):
    """Raised when a permission key is already in use."""


class InvalidCredentialsError(IdentityError):
    """Raised when a username/password pair fails to authenticate."""


class InvalidRefreshTokenError(IdentityError):
    """Raised when a refresh token is unknown, expired, or revoked."""


class InvalidAccessTokenError(IdentityError):
    """Raised when an access token fails signature, expiry, or claim checks."""


class UserRequiresAccessRoleError(IdentityError):
    """Raised when a non-superuser would end up with zero access roles.

    Replaces a "Default AccessRole" system: rather than auto-assigning a
    system-wide default role when none is specified, user creation (and
    any later replace-all of a user's roles) simply requires at least one
    `AccessRoleId` for non-superusers, guaranteeing every non-superuser
    always resolves at least one permission set. Superusers are exempt --
    `is_superuser=True` already bypasses every permission check, so they
    need zero access roles (see `require_permission`/`require_cli_permission`).
    """
