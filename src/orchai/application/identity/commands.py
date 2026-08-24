"""Identity use-case commands."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from orchai.domain.identifiers import AccessRoleId, PermissionId, UserId


@dataclass(frozen=True, slots=True)
class CreateUserCommand:
    """Command for creating a new user."""

    username: str
    plain_password: str
    email: str | None = None
    is_superuser: bool = False


@dataclass(frozen=True, slots=True)
class CreateUserWithRolesCommand:
    """Command for creating a new user together with its initial access roles.

    The admin-facing "create user" use case (`docs/TO-DO.md` user-config
    CRUD layer): wraps `CreateUserCommand` with the mandatory-role rule
    settled on in place of a "Default AccessRole" system -- creating a
    non-superuser requires at least one `AccessRoleId` so every
    non-superuser always resolves at least one permission set. Superusers
    bypass all permission checks (`is_superuser=True`), so they may be
    created with an empty `role_ids`.
    """

    username: str
    plain_password: str
    role_ids: tuple[AccessRoleId, ...] = ()
    email: str | None = None
    is_superuser: bool = False


@dataclass(frozen=True, slots=True)
class UpdateUserProfileCommand:
    """Command for updating a user's own profile.

    Deliberately excludes `AccessRoleId`s and `is_superuser`: a caller can
    never change their own access roles or superuser status through this
    command (see the self-service `/me` scope in
    `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`). `None` fields are
    left unchanged.
    """

    user_id: UserId
    username: str | None = None
    email: str | None = None


@dataclass(frozen=True, slots=True)
class SetAccessRolesForUserCommand:
    """Command to replace the full set of access roles assigned to a user.

    A replace-all, not an incremental add/remove: `role_ids` becomes the
    user's complete role set. Admin-only in practice (§4
    `admin:manage_users`).
    """

    user_id: UserId
    role_ids: tuple[AccessRoleId, ...]


@dataclass(frozen=True, slots=True)
class SetPermissionsForRoleCommand:
    """Command to replace the full set of permissions bundled into a role.

    A replace-all, not an incremental add/remove: `permission_ids` becomes
    the role's complete permission bundle. Admin-only in practice (§4
    `admin:manage_users`).
    """

    role_id: AccessRoleId
    permission_ids: tuple[PermissionId, ...]


@dataclass(frozen=True, slots=True)
class ChangePasswordCommand:
    """Command for changing a user's password."""

    user_id: UserId
    new_plain_password: str


@dataclass(frozen=True, slots=True)
class CreateAccessRoleCommand:
    """Command for creating a new access role."""

    name: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class CreatePermissionCommand:
    """Command for creating a new permission."""

    key: str
    description: str = ""


@dataclass(frozen=True, slots=True)
class AccessRoleAssignmentCommand:
    """Command for assigning or revoking an access role on a user."""

    user_id: UserId
    role_id: AccessRoleId


@dataclass(frozen=True, slots=True)
class PermissionGrantCommand:
    """Command for granting or revoking a direct permission on a user."""

    user_id: UserId
    permission_id: PermissionId


@dataclass(frozen=True, slots=True)
class RolePermissionCommand:
    """Command for adding or removing a permission from an access role."""

    role_id: AccessRoleId
    permission_id: PermissionId


@dataclass(frozen=True, slots=True)
class IssueRefreshTokenCommand:
    """Command for persisting an already-generated, hashed refresh token."""

    user_id: UserId
    token_hash: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class LoginCommand:
    """Command for authenticating a user and issuing a fresh token pair."""

    username: str
    plain_password: str


@dataclass(frozen=True, slots=True)
class RefreshCommand:
    """Command for rotating a refresh token into a fresh token pair."""

    raw_refresh_token: str


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    """Command for revoking a refresh token, ending its session (idempotent)."""

    raw_refresh_token: str
