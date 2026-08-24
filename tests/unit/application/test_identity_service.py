import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from orchai.application.events import InProcessEventDispatcher
from orchai.application.identity import (
    AccessRoleAssignmentCommand,
    ChangePasswordCommand,
    CreateAccessRoleCommand,
    CreatePermissionCommand,
    CreateUserCommand,
    CreateUserWithRolesCommand,
    IdentityService,
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
from orchai.domain.events import EventType
from orchai.domain.identifiers import AccessRoleId, PermissionId
from orchai.domain.identity import (
    DuplicateUsernameError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserRequiresAccessRoleError,
)
from orchai.infrastructure.identity import (
    Argon2PasswordHasher,
    JWTAccessTokenIssuer,
    Sha256RefreshTokenHasher,
)
from orchai.infrastructure.persistence import (
    InMemoryAccessControlRepository,
    InMemoryAccessRoleRepository,
    InMemoryPermissionRepository,
    InMemoryRefreshTokenRepository,
    InMemoryUserRepository,
)

_SECRET_KEY = "test-secret-key-with-at-least-32-characters"


def _build_service(events: InProcessEventDispatcher | None = None) -> IdentityService:
    return IdentityService(
        user_repository=InMemoryUserRepository(),
        access_role_repository=InMemoryAccessRoleRepository(),
        permission_repository=InMemoryPermissionRepository(),
        refresh_token_repository=InMemoryRefreshTokenRepository(),
        access_control_repository=InMemoryAccessControlRepository(),
        password_hasher=Argon2PasswordHasher(),
        event_publisher=events or InProcessEventDispatcher(),
        access_token_issuer=JWTAccessTokenIssuer(secret_key=_SECRET_KEY),
        refresh_token_hasher=Sha256RefreshTokenHasher(),
    )


def test_create_user_hashes_password_and_publishes_event() -> None:
    async def run() -> None:
        events = InProcessEventDispatcher()
        service = _build_service(events)

        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="correct horse battery")
        )

        assert user.password_hash != "correct horse battery"
        assert events.published_events[0].event_type is EventType.USER_CREATED

        verified = await service.verify_credentials("alice", "correct horse battery")
        assert verified is not None
        assert verified.id == user.id

        wrong = await service.verify_credentials("alice", "wrong password")
        assert wrong is None

    asyncio.run(run())


def test_create_user_rejects_duplicate_username() -> None:
    async def run() -> None:
        service = _build_service()
        await service.create_user(
            CreateUserCommand(username="alice", plain_password="first-password")
        )

        with pytest.raises(DuplicateUsernameError):
            await service.create_user(
                CreateUserCommand(username="alice", plain_password="second-password")
            )

    asyncio.run(run())


def test_deactivated_user_cannot_verify_credentials() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="correct horse battery")
        )
        await service.deactivate_user(user.id)

        verified = await service.verify_credentials("alice", "correct horse battery")
        assert verified is None

    asyncio.run(run())


def test_change_password_updates_verification() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="old-password")
        )

        await service.change_password(
            ChangePasswordCommand(user_id=user.id, new_plain_password="new-password")
        )

        assert await service.verify_credentials("alice", "old-password") is None
        verified = await service.verify_credentials("alice", "new-password")
        assert verified is not None

    asyncio.run(run())


def test_effective_permission_keys_combines_direct_and_role_grants() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="password")
        )
        role = await service.create_access_role(
            CreateAccessRoleCommand(name="operator", description="Operates things.")
        )
        role_permission = await service.create_permission(
            CreatePermissionCommand(key="requests:create")
        )
        direct_permission = await service.create_permission(
            CreatePermissionCommand(key="admin:manage_users")
        )

        await service.add_permission_to_role(
            RolePermissionCommand(role_id=role.id, permission_id=role_permission.id)
        )
        await service.assign_access_role(
            AccessRoleAssignmentCommand(user_id=user.id, role_id=role.id)
        )
        await service.grant_permission(
            PermissionGrantCommand(user_id=user.id, permission_id=direct_permission.id)
        )

        keys = await service.effective_permission_keys(user.id)
        assert keys == frozenset({"requests:create", "admin:manage_users"})

        await service.revoke_access_role(
            AccessRoleAssignmentCommand(user_id=user.id, role_id=role.id)
        )
        keys_after_revoke = await service.effective_permission_keys(user.id)
        assert keys_after_revoke == frozenset({"admin:manage_users"})

    asyncio.run(run())


def test_issue_and_revoke_refresh_token() -> None:
    async def run() -> None:
        events = InProcessEventDispatcher()
        service = _build_service(events)
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="password")
        )
        issued_at_boundary = datetime.now(UTC) + timedelta(days=30)

        token = await service.issue_refresh_token(
            IssueRefreshTokenCommand(
                user_id=user.id,
                token_hash="precomputed-hash",
                expires_at=issued_at_boundary,
            )
        )
        assert token.is_active() is True

        revoked = await service.revoke_refresh_token(token.id)
        assert revoked.is_active() is False
        assert any(
            event.event_type is EventType.REFRESH_TOKEN_REVOKED
            for event in events.published_events
        )

    asyncio.run(run())


def test_login_issues_access_and_refresh_tokens() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="correct horse battery")
        )

        result = await service.login(
            LoginCommand(username="alice", plain_password="correct horse battery")
        )

        assert result.user.id == user.id
        assert result.access_token.token
        assert result.raw_refresh_token
        assert result.refresh_token.is_active() is True

    asyncio.run(run())


def test_login_rejects_wrong_password() -> None:
    async def run() -> None:
        service = _build_service()
        await service.create_user(
            CreateUserCommand(username="alice", plain_password="correct horse battery")
        )

        with pytest.raises(InvalidCredentialsError):
            await service.login(
                LoginCommand(username="alice", plain_password="wrong password")
            )

    asyncio.run(run())


def test_login_rejects_inactive_user() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="correct horse battery")
        )
        await service.deactivate_user(user.id)

        with pytest.raises(InvalidCredentialsError):
            await service.login(
                LoginCommand(username="alice", plain_password="correct horse battery")
            )

    asyncio.run(run())


def test_refresh_rotates_token_and_invalidates_previous() -> None:
    async def run() -> None:
        service = _build_service()
        await service.create_user(
            CreateUserCommand(username="alice", plain_password="correct horse battery")
        )
        login_result = await service.login(
            LoginCommand(username="alice", plain_password="correct horse battery")
        )

        refreshed = await service.refresh(
            RefreshCommand(raw_refresh_token=login_result.raw_refresh_token)
        )

        assert refreshed.user.id == login_result.user.id
        assert refreshed.raw_refresh_token != login_result.raw_refresh_token

        with pytest.raises(InvalidRefreshTokenError):
            await service.refresh(
                RefreshCommand(raw_refresh_token=login_result.raw_refresh_token)
            )

    asyncio.run(run())


def test_refresh_rejects_unknown_token() -> None:
    async def run() -> None:
        service = _build_service()

        with pytest.raises(InvalidRefreshTokenError):
            await service.refresh(RefreshCommand(raw_refresh_token="not-a-real-token"))

    asyncio.run(run())


def test_logout_revokes_token_and_is_idempotent() -> None:
    async def run() -> None:
        service = _build_service()
        await service.create_user(
            CreateUserCommand(username="alice", plain_password="correct horse battery")
        )
        login_result = await service.login(
            LoginCommand(username="alice", plain_password="correct horse battery")
        )

        await service.logout(
            LogoutCommand(raw_refresh_token=login_result.raw_refresh_token)
        )

        with pytest.raises(InvalidRefreshTokenError):
            await service.refresh(
                RefreshCommand(raw_refresh_token=login_result.raw_refresh_token)
            )

        # Logging out again (or with an unknown token) is a no-op, not an error.
        await service.logout(
            LogoutCommand(raw_refresh_token=login_result.raw_refresh_token)
        )
        await service.logout(LogoutCommand(raw_refresh_token="never-issued"))

    asyncio.run(run())


# ---------------------------------------------------------------------------
# User-configuration CRUD (admin + self-service, ADR-012)
# ---------------------------------------------------------------------------


def test_create_user_with_roles_requires_at_least_one_role_for_non_superuser() -> None:
    async def run() -> None:
        service = _build_service()

        with pytest.raises(UserRequiresAccessRoleError):
            await service.create_user_with_roles(
                CreateUserWithRolesCommand(
                    username="norole", plain_password="correct horse battery"
                )
            )

    asyncio.run(run())


def test_create_user_with_roles_allows_empty_roles_for_superuser() -> None:
    async def run() -> None:
        service = _build_service()

        user = await service.create_user_with_roles(
            CreateUserWithRolesCommand(
                username="root",
                plain_password="correct horse battery",
                is_superuser=True,
            )
        )

        assert user.is_superuser is True
        assert await service.list_roles_for_user(user.id) == ()

    asyncio.run(run())


def test_create_user_with_roles_assigns_every_given_role() -> None:
    async def run() -> None:
        service = _build_service()
        role_a = await service.create_access_role(CreateAccessRoleCommand(name="A"))
        role_b = await service.create_access_role(CreateAccessRoleCommand(name="B"))

        user = await service.create_user_with_roles(
            CreateUserWithRolesCommand(
                username="alice",
                plain_password="correct horse battery",
                role_ids=(role_a.id, role_b.id),
            )
        )

        roles = await service.list_roles_for_user(user.id)
        assert {role.name for role in roles} == {"A", "B"}
        users_for_role_a = await service.list_users_for_role(role_a.id)
        assert [u.id for u in users_for_role_a] == [user.id]

    asyncio.run(run())


def test_create_user_with_roles_rejects_unknown_role_id() -> None:
    async def run() -> None:
        service = _build_service()

        with pytest.raises(LookupError):
            await service.create_user_with_roles(
                CreateUserWithRolesCommand(
                    username="alice",
                    plain_password="correct horse battery",
                    role_ids=(AccessRoleId.new(),),
                )
            )

    asyncio.run(run())


def test_get_user_returns_the_persisted_record() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="password")
        )

        fetched = await service.get_user(user.id)

        assert fetched.id == user.id
        assert fetched.username == "alice"

    asyncio.run(run())


def test_update_user_profile_changes_username_and_email() -> None:
    async def run() -> None:
        events = InProcessEventDispatcher()
        service = _build_service(events)
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="password")
        )

        updated = await service.update_user_profile(
            UpdateUserProfileCommand(
                user_id=user.id, username="alicia", email="alicia@example.com"
            )
        )

        assert updated.username == "alicia"
        assert updated.email == "alicia@example.com"
        assert any(
            event.event_type is EventType.USER_PROFILE_UPDATED
            for event in events.published_events
        )

    asyncio.run(run())


def test_update_user_profile_rejects_username_taken_by_another_user() -> None:
    async def run() -> None:
        service = _build_service()
        await service.create_user(
            CreateUserCommand(username="alice", plain_password="password")
        )
        bob = await service.create_user(
            CreateUserCommand(username="bob", plain_password="password")
        )

        with pytest.raises(DuplicateUsernameError):
            await service.update_user_profile(
                UpdateUserProfileCommand(user_id=bob.id, username="alice")
            )

    asyncio.run(run())


def test_update_user_profile_allows_renaming_to_ones_own_current_username() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="password")
        )

        updated = await service.update_user_profile(
            UpdateUserProfileCommand(user_id=user.id, username="alice")
        )

        assert updated.username == "alice"

    asyncio.run(run())


def test_update_user_profile_leaves_unspecified_fields_unchanged() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(
                username="alice", plain_password="password", email="alice@example.com"
            )
        )

        updated = await service.update_user_profile(
            UpdateUserProfileCommand(user_id=user.id, username="alicia")
        )

        assert updated.username == "alicia"
        assert updated.email == "alice@example.com"

    asyncio.run(run())


def test_list_and_get_access_roles_and_permissions() -> None:
    async def run() -> None:
        service = _build_service()
        role = await service.create_access_role(CreateAccessRoleCommand(name="Ops"))
        permission = await service.create_permission(
            CreatePermissionCommand(key="requests:create")
        )

        assert [r.id for r in await service.list_access_roles()] == [role.id]
        assert await service.get_access_role(role.id) == role
        assert [p.id for p in await service.list_permissions()] == [permission.id]

    asyncio.run(run())


def test_set_access_roles_for_user_replaces_the_full_set() -> None:
    async def run() -> None:
        events = InProcessEventDispatcher()
        service = _build_service(events)
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="password")
        )
        role_a = await service.create_access_role(CreateAccessRoleCommand(name="A"))
        role_b = await service.create_access_role(CreateAccessRoleCommand(name="B"))
        await service.assign_access_role(
            AccessRoleAssignmentCommand(user_id=user.id, role_id=role_a.id)
        )

        result = await service.set_access_roles_for_user(
            SetAccessRolesForUserCommand(user_id=user.id, role_ids=(role_b.id,))
        )

        assert result == (role_b.id,)
        roles = await service.list_roles_for_user(user.id)
        assert {role.id for role in roles} == {role_b.id}
        assert any(
            event.event_type is EventType.USER_ACCESS_ROLES_REPLACED
            for event in events.published_events
        )

    asyncio.run(run())


def test_set_access_roles_for_user_rejects_emptying_for_non_superuser() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="password")
        )
        role = await service.create_access_role(CreateAccessRoleCommand(name="A"))
        await service.assign_access_role(
            AccessRoleAssignmentCommand(user_id=user.id, role_id=role.id)
        )

        with pytest.raises(UserRequiresAccessRoleError):
            await service.set_access_roles_for_user(
                SetAccessRolesForUserCommand(user_id=user.id, role_ids=())
            )

    asyncio.run(run())


def test_set_access_roles_for_user_allows_emptying_for_superuser() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(
                username="root", plain_password="password", is_superuser=True
            )
        )
        role = await service.create_access_role(CreateAccessRoleCommand(name="A"))
        await service.assign_access_role(
            AccessRoleAssignmentCommand(user_id=user.id, role_id=role.id)
        )

        result = await service.set_access_roles_for_user(
            SetAccessRolesForUserCommand(user_id=user.id, role_ids=())
        )

        assert result == ()
        assert await service.list_roles_for_user(user.id) == ()

    asyncio.run(run())


def test_set_access_roles_for_user_rejects_unknown_role_id() -> None:
    async def run() -> None:
        service = _build_service()
        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="password")
        )

        with pytest.raises(LookupError):
            await service.set_access_roles_for_user(
                SetAccessRolesForUserCommand(
                    user_id=user.id, role_ids=(AccessRoleId.new(),)
                )
            )

    asyncio.run(run())


def test_set_permissions_for_role_replaces_the_full_bundle() -> None:
    async def run() -> None:
        service = _build_service()
        role = await service.create_access_role(CreateAccessRoleCommand(name="Ops"))
        perm_a = await service.create_permission(
            CreatePermissionCommand(key="requests:create")
        )
        perm_b = await service.create_permission(
            CreatePermissionCommand(key="projects:read")
        )
        await service.add_permission_to_role(
            RolePermissionCommand(role_id=role.id, permission_id=perm_a.id)
        )

        result = await service.set_permissions_for_role(
            SetPermissionsForRoleCommand(role_id=role.id, permission_ids=(perm_b.id,))
        )

        assert result == (perm_b.id,)
        permissions = await service.list_permissions_for_role(role.id)
        assert {p.id for p in permissions} == {perm_b.id}

    asyncio.run(run())


def test_set_permissions_for_role_rejects_unknown_permission_id() -> None:
    async def run() -> None:
        service = _build_service()
        role = await service.create_access_role(CreateAccessRoleCommand(name="Ops"))

        with pytest.raises(LookupError):
            await service.set_permissions_for_role(
                SetPermissionsForRoleCommand(
                    role_id=role.id, permission_ids=(PermissionId.new(),)
                )
            )

    asyncio.run(run())
