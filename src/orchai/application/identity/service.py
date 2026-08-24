"""Identity application service.

Deliberately isolated (see `docs/TO-DO.md` Priority 1, Phase 1): this
service is not called from any FastAPI route or Typer CLI command, and no
existing execution/action/role/model permission check consults it. It is
a self-contained vertical slice exercised only by its own tests until a
later phase wires enforcement in.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from orchai.application.events.ports import EventPublisher
from orchai.application.identity.commands import (
    AccessRoleAssignmentCommand,
    ChangePasswordCommand,
    CreateAccessRoleCommand,
    CreatePermissionCommand,
    CreateUserCommand,
    CreateUserWithRolesCommand,
    IssueRefreshTokenCommand,
    LoginCommand,
    LogoutCommand,
    PermissionGrantCommand,
    RefreshCommand,
    RolePermissionCommand,
    SetAccessRolesForUserCommand,
    SetPermissionsForRoleCommand,
    UpdateUserProfileCommand,
)
from orchai.application.identity.ports import (
    AccessControlRepository,
    AccessRoleRepository,
    AccessTokenIssuer,
    PasswordHasher,
    PermissionRepository,
    RefreshTokenHasher,
    RefreshTokenRepository,
    UserRepository,
)
from orchai.application.identity.tokens import AuthenticationResult
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.identifiers import AccessRoleId, PermissionId, RefreshTokenId, UserId
from orchai.domain.identity import (
    AccessRole,
    DuplicateAccessRoleNameError,
    DuplicatePermissionKeyError,
    DuplicateUsernameError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    Permission,
    RefreshToken,
    User,
    UserRequiresAccessRoleError,
)


class IdentityService:
    """Coordinates user, access role, permission, and refresh-token use cases."""

    def __init__(
        self,
        *,
        user_repository: UserRepository,
        access_role_repository: AccessRoleRepository,
        permission_repository: PermissionRepository,
        refresh_token_repository: RefreshTokenRepository,
        access_control_repository: AccessControlRepository,
        password_hasher: PasswordHasher,
        event_publisher: EventPublisher,
        access_token_issuer: AccessTokenIssuer,
        refresh_token_hasher: RefreshTokenHasher,
        refresh_token_ttl: timedelta = timedelta(days=30),
    ) -> None:
        self._users = user_repository
        self._access_roles = access_role_repository
        self._permissions = permission_repository
        self._refresh_tokens = refresh_token_repository
        self._access_control = access_control_repository
        self._password_hasher = password_hasher
        self._event_publisher = event_publisher
        self._access_token_issuer = access_token_issuer
        self._refresh_token_hasher = refresh_token_hasher
        self._refresh_token_ttl = refresh_token_ttl

    async def list_users(
        self,
        *,
        is_active: bool | None = None,
        limit: int = 20,
    ) -> tuple[User, ...]:
        """Return user records, optionally filtered by active state.

        Added for the Phase 3 bootstrap-admin path (`docs/TO-DO.md`
        Priority 1 Phase 3, ADR-012 §8), which must check "does any user
        already exist" without reaching into `UserRepository` directly.
        """

        return await self._users.list(is_active=is_active, limit=limit)

    async def get_user(self, user_id: UserId) -> User:
        """Return a single user by id."""

        return await self._users.get(user_id)

    async def create_user(self, command: CreateUserCommand) -> User:
        existing = await self._users.get_by_username(command.username)
        if existing is not None:
            raise DuplicateUsernameError(command.username)
        user = User(
            username=command.username,
            email=command.email,
            password_hash=self._password_hasher.hash(command.plain_password),
            is_superuser=command.is_superuser,
        )
        await self._users.add(user)
        await self._publish_user_event(
            EventType.USER_CREATED,
            user_id=user.id,
            payload={"username": user.username},
        )
        return user

    async def create_user_with_roles(self, command: CreateUserWithRolesCommand) -> User:
        """Create a user and assign its initial access roles (admin-only in practice).

        Enforces the "at least one AccessRole" rule agreed in place of a
        "Default AccessRole" system: a non-superuser must be given at
        least one `AccessRoleId` up front. Every `role_id` must already
        exist -- `AccessRoleRepository.get` raises if not. Superusers may
        be created with an empty `role_ids` since they bypass all
        permission checks.
        """

        if not command.role_ids and not command.is_superuser:
            raise UserRequiresAccessRoleError(
                "creating a non-superuser requires at least one access role"
            )
        for role_id in command.role_ids:
            await self._access_roles.get(role_id)
        user = await self.create_user(
            CreateUserCommand(
                username=command.username,
                plain_password=command.plain_password,
                email=command.email,
                is_superuser=command.is_superuser,
            )
        )
        for role_id in command.role_ids:
            await self._access_control.assign_role(user.id, role_id)
            await self._publish_user_event(
                EventType.ACCESS_ROLE_ASSIGNED,
                user_id=user.id,
                payload={"role_id": str(role_id)},
            )
        return user

    async def update_user_profile(self, command: UpdateUserProfileCommand) -> User:
        """Update a user's own profile (username/email only).

        Never touches `AccessRoleId`s, `is_superuser`, or `id` -- see
        `UpdateUserProfileCommand`'s docstring. `None` fields are left
        unchanged. Raises `DuplicateUsernameError` if `username` is taken
        by a different user.
        """

        user = await self._users.get(command.user_id)
        if command.username is not None:
            normalized = command.username.strip()
            existing = await self._users.get_by_username(normalized)
            if existing is not None and existing.id != user.id:
                raise DuplicateUsernameError(normalized)
        user.update_profile(username=command.username, email=command.email)
        await self._users.save(user)
        await self._publish_user_event(EventType.USER_PROFILE_UPDATED, user_id=user.id)
        return user

    async def activate_user(self, user_id: UserId) -> User:
        user = await self._users.get(user_id)
        user.activate()
        await self._users.save(user)
        await self._publish_user_event(EventType.USER_ACTIVATED, user_id=user.id)
        return user

    async def deactivate_user(self, user_id: UserId) -> User:
        user = await self._users.get(user_id)
        user.deactivate()
        await self._users.save(user)
        await self._publish_user_event(EventType.USER_DEACTIVATED, user_id=user.id)
        return user

    async def change_password(self, command: ChangePasswordCommand) -> User:
        user = await self._users.get(command.user_id)
        user.change_password_hash(
            self._password_hasher.hash(command.new_plain_password)
        )
        await self._users.save(user)
        await self._publish_user_event(EventType.USER_PASSWORD_CHANGED, user_id=user.id)
        return user

    async def verify_credentials(
        self, username: str, plain_password: str
    ) -> User | None:
        """Return the user if `username`/`plain_password` are a valid, active pair.

        Returns None on any failure (unknown username, inactive user, or a
        wrong password) rather than distinguishing the reason, so callers
        cannot use response timing/shape to enumerate valid usernames.
        """

        user = await self._users.get_by_username(username)
        if user is None or not user.is_active:
            return None
        if not self._password_hasher.verify(plain_password, user.password_hash):
            return None
        return user

    async def create_access_role(self, command: CreateAccessRoleCommand) -> AccessRole:
        existing = await self._access_roles.get_by_name(command.name)
        if existing is not None:
            raise DuplicateAccessRoleNameError(command.name)
        role = AccessRole(name=command.name, description=command.description)
        await self._access_roles.add(role)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.ACCESS_ROLE_CREATED,
                source="application.identity",
                payload={"role_id": str(role.id), "name": role.name},
            )
        )
        return role

    async def create_permission(self, command: CreatePermissionCommand) -> Permission:
        existing = await self._permissions.get_by_key(command.key)
        if existing is not None:
            raise DuplicatePermissionKeyError(command.key)
        permission = Permission(key=command.key, description=command.description)
        await self._permissions.add(permission)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.PERMISSION_CREATED,
                source="application.identity",
                payload={"permission_id": str(permission.id), "key": permission.key},
            )
        )
        return permission

    async def list_access_roles(self, *, limit: int = 50) -> tuple[AccessRole, ...]:
        """Return access role records (admin `GET /admin/access-roles`)."""

        return await self._access_roles.list(limit=limit)

    async def get_access_role(self, role_id: AccessRoleId) -> AccessRole:
        """Return a single access role by id."""

        return await self._access_roles.get(role_id)

    async def list_permissions(self, *, limit: int = 100) -> tuple[Permission, ...]:
        """Return permission records (the fixed system catalog)."""

        return await self._permissions.list(limit=limit)

    async def assign_access_role(self, command: AccessRoleAssignmentCommand) -> None:
        await self._users.get(command.user_id)
        await self._access_roles.get(command.role_id)
        await self._access_control.assign_role(command.user_id, command.role_id)
        await self._publish_user_event(
            EventType.ACCESS_ROLE_ASSIGNED,
            user_id=command.user_id,
            payload={"role_id": str(command.role_id)},
        )

    async def revoke_access_role(self, command: AccessRoleAssignmentCommand) -> None:
        await self._access_control.revoke_role(command.user_id, command.role_id)
        await self._publish_user_event(
            EventType.ACCESS_ROLE_REVOKED,
            user_id=command.user_id,
            payload={"role_id": str(command.role_id)},
        )

    async def grant_permission(self, command: PermissionGrantCommand) -> None:
        await self._users.get(command.user_id)
        await self._permissions.get(command.permission_id)
        await self._access_control.grant_permission(
            command.user_id, command.permission_id
        )
        await self._publish_user_event(
            EventType.PERMISSION_GRANTED,
            user_id=command.user_id,
            payload={"permission_id": str(command.permission_id)},
        )

    async def revoke_permission(self, command: PermissionGrantCommand) -> None:
        await self._access_control.revoke_permission(
            command.user_id, command.permission_id
        )
        await self._publish_user_event(
            EventType.PERMISSION_REVOKED,
            user_id=command.user_id,
            payload={"permission_id": str(command.permission_id)},
        )

    async def add_permission_to_role(self, command: RolePermissionCommand) -> None:
        await self._access_roles.get(command.role_id)
        await self._permissions.get(command.permission_id)
        await self._access_control.add_permission_to_role(
            command.role_id, command.permission_id
        )

    async def remove_permission_from_role(self, command: RolePermissionCommand) -> None:
        await self._access_control.remove_permission_from_role(
            command.role_id, command.permission_id
        )

    async def list_roles_for_user(self, user_id: UserId) -> tuple[AccessRole, ...]:
        """Return the access roles assigned to a user (resolved, not just ids)."""

        role_ids = await self._access_control.list_role_ids_for_user(user_id)
        return tuple([await self._access_roles.get(role_id) for role_id in role_ids])

    async def list_users_for_role(self, role_id: AccessRoleId) -> tuple[User, ...]:
        """Return the users a given access role is assigned to (resolved)."""

        user_ids = await self._access_control.list_user_ids_for_role(role_id)
        return tuple([await self._users.get(user_id) for user_id in user_ids])

    async def list_permissions_for_role(
        self, role_id: AccessRoleId
    ) -> tuple[Permission, ...]:
        """Return the permissions bundled into an access role (resolved)."""

        permission_ids = await self._access_control.list_permission_ids_for_role(
            role_id
        )
        return tuple(
            [await self._permissions.get(permission_id) for permission_id in permission_ids]
        )

    async def set_access_roles_for_user(
        self, command: SetAccessRolesForUserCommand
    ) -> tuple[AccessRoleId, ...]:
        """Replace a user's full access-role assignment (admin-only in practice).

        A replace-all: any role currently assigned but absent from
        `command.role_ids` is revoked, and any role present but not yet
        assigned is granted. Enforces the "at least one AccessRole" rule
        for non-superusers agreed in place of a "Default AccessRole"
        system. Every `role_id` must already exist.
        """

        user = await self._users.get(command.user_id)
        desired = tuple(dict.fromkeys(command.role_ids))
        if not desired and not user.is_superuser:
            raise UserRequiresAccessRoleError(
                f"user {user.id} must be assigned at least one access role"
            )
        for role_id in desired:
            await self._access_roles.get(role_id)
        current = set(await self._access_control.list_role_ids_for_user(command.user_id))
        desired_set = set(desired)
        for role_id in current - desired_set:
            await self._access_control.revoke_role(command.user_id, role_id)
        for role_id in desired_set - current:
            await self._access_control.assign_role(command.user_id, role_id)
        await self._publish_user_event(
            EventType.USER_ACCESS_ROLES_REPLACED,
            user_id=command.user_id,
            payload={"role_ids": ",".join(str(role_id) for role_id in desired)},
        )
        return desired

    async def set_permissions_for_role(
        self, command: SetPermissionsForRoleCommand
    ) -> tuple[PermissionId, ...]:
        """Replace an access role's full permission bundle (admin-only in practice).

        A replace-all: any permission currently in the bundle but absent
        from `command.permission_ids` is removed, and any permission
        present but not yet bundled is added. Every `permission_id` must
        already exist. Permissions themselves remain a fixed system
        catalog -- only role<->permission assignment is admin-editable.
        """

        await self._access_roles.get(command.role_id)
        desired = tuple(dict.fromkeys(command.permission_ids))
        for permission_id in desired:
            await self._permissions.get(permission_id)
        current = set(
            await self._access_control.list_permission_ids_for_role(command.role_id)
        )
        desired_set = set(desired)
        for permission_id in current - desired_set:
            await self._access_control.remove_permission_from_role(
                command.role_id, permission_id
            )
        for permission_id in desired_set - current:
            await self._access_control.add_permission_to_role(
                command.role_id, permission_id
            )
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.ROLE_PERMISSIONS_REPLACED,
                source="application.identity",
                payload={
                    "role_id": str(command.role_id),
                    "permission_ids": ",".join(str(pid) for pid in desired),
                },
            )
        )
        return desired

    async def effective_permission_keys(self, user_id: UserId) -> frozenset[str]:
        """Union of direct grants and role-derived grants for a user.

        Reports grants only; it does not special-case `User.is_superuser`.
        Callers needing superuser bypass semantics must check that flag
        themselves -- enforcement is out of scope for this isolated phase
        regardless.
        """

        direct_ids = await self._access_control.list_direct_permission_ids_for_user(
            user_id
        )
        role_ids = await self._access_control.list_role_ids_for_user(user_id)
        permission_ids = set(direct_ids)
        for role_id in role_ids:
            permission_ids.update(
                await self._access_control.list_permission_ids_for_role(role_id)
            )
        keys: set[str] = set()
        for permission_id in permission_ids:
            permission = await self._permissions.get(permission_id)
            keys.add(permission.key)
        return frozenset(keys)

    async def issue_refresh_token(
        self, command: IssueRefreshTokenCommand
    ) -> RefreshToken:
        """Persist a refresh-token record for an already-generated, hashed token.

        Generating the raw token and choosing its hashing scheme is a
        Phase 2 (token lifecycle) concern; see `RefreshToken`'s docstring.
        """

        await self._users.get(command.user_id)
        token = RefreshToken(
            user_id=command.user_id,
            token_hash=command.token_hash,
            expires_at=command.expires_at,
        )
        await self._refresh_tokens.add(token)
        await self._publish_user_event(
            EventType.REFRESH_TOKEN_ISSUED, user_id=command.user_id
        )
        return token

    async def revoke_refresh_token(self, token_id: RefreshTokenId) -> RefreshToken:
        token = await self._refresh_tokens.get(token_id)
        token.revoke()
        await self._refresh_tokens.save(token)
        await self._publish_user_event(
            EventType.REFRESH_TOKEN_REVOKED, user_id=token.user_id
        )
        return token

    async def login(self, command: LoginCommand) -> AuthenticationResult:
        """Authenticate a username/password pair and issue a fresh token pair.

        Raises `InvalidCredentialsError` for any failure (unknown username,
        inactive user, wrong password) without distinguishing the reason --
        see `verify_credentials`'s docstring for why.
        """

        user = await self.verify_credentials(command.username, command.plain_password)
        if user is None:
            raise InvalidCredentialsError(
                f"invalid credentials for username {command.username!r}"
            )
        return await self._issue_tokens_for(user)

    async def refresh(self, command: RefreshCommand) -> AuthenticationResult:
        """Rotate a valid refresh token into a fresh access/refresh token pair.

        The presented token is always revoked as part of this call, whether
        or not rotation succeeds past that point: a refresh token is
        single-use. Raises `InvalidRefreshTokenError` if the token is
        unknown, expired, already revoked, or its owning user is no longer
        active.
        """

        token_hash = self._refresh_token_hasher.hash(command.raw_refresh_token)
        existing = await self._refresh_tokens.get_by_token_hash(token_hash)
        if existing is None or not existing.is_active():
            raise InvalidRefreshTokenError(
                "refresh token is unknown, expired, or revoked"
            )
        existing.revoke()
        await self._refresh_tokens.save(existing)
        await self._publish_user_event(
            EventType.REFRESH_TOKEN_REVOKED, user_id=existing.user_id
        )
        user = await self._users.get(existing.user_id)
        if not user.is_active:
            raise InvalidRefreshTokenError(f"user {user.id} is no longer active")
        return await self._issue_tokens_for(user)

    async def logout(self, command: LogoutCommand) -> None:
        """Revoke a refresh token, ending its session.

        Idempotent: revoking an unknown or already-revoked token is a no-op
        rather than an error, since a caller logging out twice (or with a
        token that already expired/rotated) should not see a failure.
        """

        token_hash = self._refresh_token_hasher.hash(command.raw_refresh_token)
        existing = await self._refresh_tokens.get_by_token_hash(token_hash)
        if existing is None or existing.revoked_at is not None:
            return
        existing.revoke()
        await self._refresh_tokens.save(existing)
        await self._publish_user_event(
            EventType.REFRESH_TOKEN_REVOKED, user_id=existing.user_id
        )

    async def _issue_tokens_for(self, user: User) -> AuthenticationResult:
        """Issue a fresh signed access token and persisted refresh token for `user`."""

        access_token = self._access_token_issuer.issue(user)
        raw_refresh_token = secrets.token_urlsafe(32)
        token_hash = self._refresh_token_hasher.hash(raw_refresh_token)
        refresh_token = await self.issue_refresh_token(
            IssueRefreshTokenCommand(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=datetime.now(UTC) + self._refresh_token_ttl,
            )
        )
        return AuthenticationResult(
            user=user,
            access_token=access_token,
            refresh_token=refresh_token,
            raw_refresh_token=raw_refresh_token,
        )

    async def _publish_user_event(
        self,
        event_type: EventType,
        *,
        user_id: UserId,
        payload: dict[str, str] | None = None,
    ) -> None:
        merged_payload: dict[str, str] = {"user_id": str(user_id)}
        if payload:
            merged_payload.update(payload)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=event_type,
                source="application.identity",
                payload=merged_payload,
            )
        )
