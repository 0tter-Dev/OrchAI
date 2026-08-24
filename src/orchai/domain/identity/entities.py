"""Identity entities: users, access roles, permissions, and refresh tokens.

Part of the isolated Phase 1 identity slice (ADR-012,
`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`, `docs/TO-DO.md` Priority 1).
Nothing here is consulted by any existing execution/action/role/model
permission check yet -- see the module docstring on
`application.identity.service.IdentityService` for the isolation boundary.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from orchai.domain.identifiers import AccessRoleId, PermissionId, RefreshTokenId, UserId
from orchai.domain.identity.errors import (
    RefreshTokenAlreadyRevokedError,
    UserAlreadyActiveError,
    UserAlreadyInactiveError,
)


@dataclass(slots=True)
class User:
    """A person or service identity able to authenticate against OrchAI."""

    username: str
    email: str | None
    password_hash: str
    id: UserId = field(default_factory=UserId.new)
    is_superuser: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        username = self.username.strip()
        if not username:
            raise ValueError("user username must not be empty")
        email = self.email.strip() if self.email is not None else None
        password_hash = self.password_hash.strip()
        if not password_hash:
            raise ValueError("user password_hash must not be empty")
        self.username = username
        self.email = email or None
        self.password_hash = password_hash

    def deactivate(self, *, at: datetime | None = None) -> None:
        if not self.is_active:
            raise UserAlreadyInactiveError(f"user {self.id} is already inactive")
        self.is_active = False
        self.updated_at = at or datetime.now(UTC)

    def activate(self, *, at: datetime | None = None) -> None:
        if self.is_active:
            raise UserAlreadyActiveError(f"user {self.id} is already active")
        self.is_active = True
        self.updated_at = at or datetime.now(UTC)

    def change_password_hash(
        self,
        password_hash: str,
        *,
        at: datetime | None = None,
    ) -> None:
        normalized = password_hash.strip()
        if not normalized:
            raise ValueError("user password_hash must not be empty")
        self.password_hash = normalized
        self.updated_at = at or datetime.now(UTC)

    def update_profile(
        self,
        *,
        username: str | None = None,
        email: str | None = None,
        at: datetime | None = None,
    ) -> None:
        """Update self-service profile fields (username/email).

        Deliberately excludes `AccessRoleId`s, `is_superuser`, and `id` --
        those are admin-only or immutable, never part of a user's own
        profile update (see `application.identity.commands
        .UpdateUserProfileCommand`). `None` leaves a field unchanged.
        """

        if username is not None:
            normalized_username = username.strip()
            if not normalized_username:
                raise ValueError("user username must not be empty")
            self.username = normalized_username
        if email is not None:
            self.email = email.strip() or None
        self.updated_at = at or datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class AccessRole:
    """A named bundle of permissions grantable to users.

    Distinct from `RoleName` (`domain.roles`), which names a *task* role
    (e.g. DEVELOPER, REVIEWER) consumed by the existing `Authorization`
    aggregate. `AccessRole` is unrelated: it names an *access* grouping
    for the identity/authentication layer -- see `AccessRoleId`'s
    docstring in `domain.identifiers`.
    """

    name: str
    id: AccessRoleId = field(default_factory=AccessRoleId.new)
    description: str = ""

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name:
            raise ValueError("access role name must not be empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "description", self.description.strip())


@dataclass(frozen=True, slots=True)
class Permission:
    """A coarse, string-named capability that can be required or granted."""

    key: str
    id: PermissionId = field(default_factory=PermissionId.new)
    description: str = ""

    def __post_init__(self) -> None:
        key = self.key.strip()
        if not key:
            raise ValueError("permission key must not be empty")
        object.__setattr__(self, "key", key)
        object.__setattr__(self, "description", self.description.strip())


@dataclass(slots=True)
class RefreshToken:
    """A revocable, hashed refresh token issued to a user.

    Generating the raw token and choosing its hashing scheme is a Phase 2
    (token lifecycle) concern; this entity only models the persisted
    record -- see `docs/TO-DO.md` Priority 1, Phase 2.
    """

    user_id: UserId
    token_hash: str
    expires_at: datetime
    id: RefreshTokenId = field(default_factory=RefreshTokenId.new)
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        token_hash = self.token_hash.strip()
        if not token_hash:
            raise ValueError("refresh token_hash must not be empty")
        if self.expires_at <= self.issued_at:
            raise ValueError("refresh token expires_at must be after issued_at")
        self.token_hash = token_hash

    def is_active(self, *, at: datetime | None = None) -> bool:
        checked_at = at or datetime.now(UTC)
        return self.revoked_at is None and checked_at < self.expires_at

    def revoke(self, *, at: datetime | None = None) -> None:
        if self.revoked_at is not None:
            raise RefreshTokenAlreadyRevokedError(
                f"refresh token {self.id} already revoked"
            )
        self.revoked_at = at or datetime.now(UTC)
