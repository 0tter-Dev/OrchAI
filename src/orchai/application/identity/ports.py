"""Identity application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.application.identity.tokens import AccessTokenClaims, IssuedAccessToken
from orchai.domain.identifiers import AccessRoleId, PermissionId, RefreshTokenId, UserId
from orchai.domain.identity import AccessRole, Permission, RefreshToken, User


class UserRepository(Protocol):
    """Persistence boundary for user records."""

    async def add(self, user: User) -> None:
        """Persist a newly created user."""

    async def get(self, user_id: UserId) -> User:
        """Return a user by id."""

    async def get_by_username(self, username: str) -> User | None:
        """Return a user by username, or None if no such user exists."""

    async def save(self, user: User) -> None:
        """Persist changes to a user record."""

    async def list(
        self,
        *,
        is_active: bool | None = None,
        limit: int = 20,
    ) -> tuple[User, ...]:
        """Return user records, optionally filtered by active state."""


class AccessRoleRepository(Protocol):
    """Persistence boundary for access-role records."""

    async def add(self, role: AccessRole) -> None:
        """Persist a newly created access role."""

    async def get(self, role_id: AccessRoleId) -> AccessRole:
        """Return an access role by id."""

    async def get_by_name(self, name: str) -> AccessRole | None:
        """Return an access role by name, or None if no such role exists."""

    async def list(self, *, limit: int = 50) -> tuple[AccessRole, ...]:
        """Return access role records."""


class PermissionRepository(Protocol):
    """Persistence boundary for permission records."""

    async def add(self, permission: Permission) -> None:
        """Persist a newly created permission."""

    async def get(self, permission_id: PermissionId) -> Permission:
        """Return a permission by id."""

    async def get_by_key(self, key: str) -> Permission | None:
        """Return a permission by key, or None if no such permission exists."""

    async def list(self, *, limit: int = 100) -> tuple[Permission, ...]:
        """Return permission records."""


class RefreshTokenRepository(Protocol):
    """Persistence boundary for refresh-token records."""

    async def add(self, token: RefreshToken) -> None:
        """Persist a newly issued refresh token record."""

    async def get(self, token_id: RefreshTokenId) -> RefreshToken:
        """Return a refresh token record by id."""

    async def save(self, token: RefreshToken) -> None:
        """Persist changes (e.g. revocation) to a refresh token record."""

    async def list_for_user(
        self,
        user_id: UserId,
        *,
        active_only: bool = False,
    ) -> tuple[RefreshToken, ...]:
        """Return refresh token records issued to a user."""

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        """Return the refresh token record matching `token_hash`, if any."""


class AccessControlRepository(Protocol):
    """Persistence boundary for the many-to-many grant relationships.

    Covers `UserRole`, `RolePermission`, and `UserPermission` from
    `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §1 -- grouped in one
    port since they are pure join-table operations with no independent
    entity identity of their own.
    """

    async def assign_role(self, user_id: UserId, role_id: AccessRoleId) -> None:
        """Assign an access role to a user (idempotent)."""

    async def revoke_role(self, user_id: UserId, role_id: AccessRoleId) -> None:
        """Revoke an access role from a user (idempotent)."""

    async def grant_permission(
        self, user_id: UserId, permission_id: PermissionId
    ) -> None:
        """Grant a permission directly to a user (idempotent)."""

    async def revoke_permission(
        self,
        user_id: UserId,
        permission_id: PermissionId,
    ) -> None:
        """Revoke a direct permission grant from a user (idempotent)."""

    async def add_permission_to_role(
        self,
        role_id: AccessRoleId,
        permission_id: PermissionId,
    ) -> None:
        """Add a permission to an access role's bundle (idempotent)."""

    async def remove_permission_from_role(
        self,
        role_id: AccessRoleId,
        permission_id: PermissionId,
    ) -> None:
        """Remove a permission from an access role's bundle (idempotent)."""

    async def list_role_ids_for_user(self, user_id: UserId) -> tuple[AccessRoleId, ...]:
        """Return the access roles assigned to a user."""

    async def list_user_ids_for_role(self, role_id: AccessRoleId) -> tuple[UserId, ...]:
        """Return the users a given access role is assigned to (reverse lookup)."""

    async def list_direct_permission_ids_for_user(
        self,
        user_id: UserId,
    ) -> tuple[PermissionId, ...]:
        """Return the permissions granted directly to a user."""

    async def list_permission_ids_for_role(
        self,
        role_id: AccessRoleId,
    ) -> tuple[PermissionId, ...]:
        """Return the permissions bundled into an access role."""


class PasswordHasher(Protocol):
    """Port for one-way password hashing, kept out of the domain layer."""

    def hash(self, plain_password: str) -> str:
        """Return a salted, one-way hash of `plain_password`."""

    def verify(self, plain_password: str, password_hash: str) -> bool:
        """Return whether `plain_password` matches `password_hash`."""


class RefreshTokenHasher(Protocol):
    """Port for one-way hashing of high-entropy refresh tokens.

    Deliberately distinct from `PasswordHasher`: refresh tokens are
    generated as high-entropy random strings, not low-entropy secrets a
    person chooses, so a fast one-way hash (e.g. SHA-256) is an
    appropriate and much cheaper fit than a memory-hard scheme like
    Argon2 -- see `docs/TO-DO.md` Priority 1, Phase 2.
    """

    def hash(self, raw_token: str) -> str:
        """Return a one-way hash of `raw_token` suitable for storage/lookup."""


class AccessTokenIssuer(Protocol):
    """Port for issuing and validating signed, short-lived access tokens."""

    def issue(self, user: User) -> IssuedAccessToken:
        """Return a freshly signed access token for `user`."""

    def decode(self, token: str) -> AccessTokenClaims:
        """Return the claims encoded in `token`.

        Raises `InvalidAccessTokenError` (`domain.identity`) if `token`
        fails signature verification, is expired, or is malformed.
        """
