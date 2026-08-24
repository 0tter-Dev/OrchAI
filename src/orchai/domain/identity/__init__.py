"""Identity domain: users, access roles, permissions, and refresh tokens."""

from orchai.domain.identity.entities import AccessRole, Permission, RefreshToken, User
from orchai.domain.identity.errors import (
    DuplicateAccessRoleNameError,
    DuplicatePermissionKeyError,
    DuplicateUsernameError,
    IdentityError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RefreshTokenAlreadyRevokedError,
    UserAlreadyActiveError,
    UserAlreadyInactiveError,
    UserRequiresAccessRoleError,
)

__all__ = [
    "AccessRole",
    "DuplicateAccessRoleNameError",
    "DuplicatePermissionKeyError",
    "DuplicateUsernameError",
    "IdentityError",
    "InvalidAccessTokenError",
    "InvalidCredentialsError",
    "InvalidRefreshTokenError",
    "Permission",
    "RefreshToken",
    "RefreshTokenAlreadyRevokedError",
    "User",
    "UserAlreadyActiveError",
    "UserAlreadyInactiveError",
    "UserRequiresAccessRoleError",
]
