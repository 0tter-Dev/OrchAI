"""In-memory identity repositories for tests and local bootstrap."""

from __future__ import annotations

from orchai.application.identity.ports import (
    AccessControlRepository,
    AccessRoleRepository,
    PermissionRepository,
    RefreshTokenRepository,
    UserRepository,
)
from orchai.domain.identifiers import AccessRoleId, PermissionId, RefreshTokenId, UserId
from orchai.domain.identity import AccessRole, Permission, RefreshToken, User


class UserNotFoundError(LookupError):
    """Raised when a user is not present in the repository."""


class AccessRoleNotFoundError(LookupError):
    """Raised when an access role is not present in the repository."""


class PermissionNotFoundError(LookupError):
    """Raised when a permission is not present in the repository."""


class RefreshTokenNotFoundError(LookupError):
    """Raised when a refresh token is not present in the repository."""


class InMemoryUserRepository(UserRepository):
    """Simple non-durable user repository."""

    def __init__(self) -> None:
        self._users: dict[UserId, User] = {}

    async def add(self, user: User) -> None:
        self._users[user.id] = user

    async def get(self, user_id: UserId) -> User:
        try:
            return self._users[user_id]
        except KeyError as exc:
            raise UserNotFoundError(str(user_id)) from exc

    async def get_by_username(self, username: str) -> User | None:
        normalized = username.strip()
        for user in self._users.values():
            if user.username == normalized:
                return user
        return None

    async def save(self, user: User) -> None:
        if user.id not in self._users:
            raise UserNotFoundError(str(user.id))
        self._users[user.id] = user

    async def list(
        self,
        *,
        is_active: bool | None = None,
        limit: int = 20,
    ) -> tuple[User, ...]:
        users = tuple(
            user
            for user in self._users.values()
            if is_active is None or user.is_active == is_active
        )
        return users[: max(1, min(limit, 100))]


class InMemoryAccessRoleRepository(AccessRoleRepository):
    """Simple non-durable access-role repository."""

    def __init__(self) -> None:
        self._roles: dict[AccessRoleId, AccessRole] = {}

    async def add(self, role: AccessRole) -> None:
        self._roles[role.id] = role

    async def get(self, role_id: AccessRoleId) -> AccessRole:
        try:
            return self._roles[role_id]
        except KeyError as exc:
            raise AccessRoleNotFoundError(str(role_id)) from exc

    async def get_by_name(self, name: str) -> AccessRole | None:
        normalized = name.strip()
        for role in self._roles.values():
            if role.name == normalized:
                return role
        return None

    async def list(self, *, limit: int = 50) -> tuple[AccessRole, ...]:
        return tuple(self._roles.values())[: max(1, min(limit, 200))]


class InMemoryPermissionRepository(PermissionRepository):
    """Simple non-durable permission repository."""

    def __init__(self) -> None:
        self._permissions: dict[PermissionId, Permission] = {}

    async def add(self, permission: Permission) -> None:
        self._permissions[permission.id] = permission

    async def get(self, permission_id: PermissionId) -> Permission:
        try:
            return self._permissions[permission_id]
        except KeyError as exc:
            raise PermissionNotFoundError(str(permission_id)) from exc

    async def get_by_key(self, key: str) -> Permission | None:
        normalized = key.strip()
        for permission in self._permissions.values():
            if permission.key == normalized:
                return permission
        return None

    async def list(self, *, limit: int = 100) -> tuple[Permission, ...]:
        return tuple(self._permissions.values())[: max(1, min(limit, 500))]


class InMemoryRefreshTokenRepository(RefreshTokenRepository):
    """Simple non-durable refresh-token repository."""

    def __init__(self) -> None:
        self._tokens: dict[RefreshTokenId, RefreshToken] = {}

    async def add(self, token: RefreshToken) -> None:
        self._tokens[token.id] = token

    async def get(self, token_id: RefreshTokenId) -> RefreshToken:
        try:
            return self._tokens[token_id]
        except KeyError as exc:
            raise RefreshTokenNotFoundError(str(token_id)) from exc

    async def save(self, token: RefreshToken) -> None:
        if token.id not in self._tokens:
            raise RefreshTokenNotFoundError(str(token.id))
        self._tokens[token.id] = token

    async def list_for_user(
        self,
        user_id: UserId,
        *,
        active_only: bool = False,
    ) -> tuple[RefreshToken, ...]:
        return tuple(
            token
            for token in self._tokens.values()
            if token.user_id == user_id
            if not active_only or token.is_active()
        )

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        for token in self._tokens.values():
            if token.token_hash == token_hash:
                return token
        return None


class InMemoryAccessControlRepository(AccessControlRepository):
    """Simple non-durable store for the identity many-to-many grants."""

    def __init__(self) -> None:
        self._user_roles: set[tuple[UserId, AccessRoleId]] = set()
        self._user_permissions: set[tuple[UserId, PermissionId]] = set()
        self._role_permissions: set[tuple[AccessRoleId, PermissionId]] = set()

    async def assign_role(self, user_id: UserId, role_id: AccessRoleId) -> None:
        self._user_roles.add((user_id, role_id))

    async def revoke_role(self, user_id: UserId, role_id: AccessRoleId) -> None:
        self._user_roles.discard((user_id, role_id))

    async def grant_permission(
        self, user_id: UserId, permission_id: PermissionId
    ) -> None:
        self._user_permissions.add((user_id, permission_id))

    async def revoke_permission(
        self,
        user_id: UserId,
        permission_id: PermissionId,
    ) -> None:
        self._user_permissions.discard((user_id, permission_id))

    async def add_permission_to_role(
        self,
        role_id: AccessRoleId,
        permission_id: PermissionId,
    ) -> None:
        self._role_permissions.add((role_id, permission_id))

    async def remove_permission_from_role(
        self,
        role_id: AccessRoleId,
        permission_id: PermissionId,
    ) -> None:
        self._role_permissions.discard((role_id, permission_id))

    async def list_role_ids_for_user(self, user_id: UserId) -> tuple[AccessRoleId, ...]:
        return tuple(role_id for (uid, role_id) in self._user_roles if uid == user_id)

    async def list_user_ids_for_role(self, role_id: AccessRoleId) -> tuple[UserId, ...]:
        return tuple(uid for (uid, rid) in self._user_roles if rid == role_id)

    async def list_direct_permission_ids_for_user(
        self,
        user_id: UserId,
    ) -> tuple[PermissionId, ...]:
        return tuple(
            permission_id
            for (uid, permission_id) in self._user_permissions
            if uid == user_id
        )

    async def list_permission_ids_for_role(
        self,
        role_id: AccessRoleId,
    ) -> tuple[PermissionId, ...]:
        return tuple(
            permission_id
            for (rid, permission_id) in self._role_permissions
            if rid == role_id
        )
