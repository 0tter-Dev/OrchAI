import asyncio
from datetime import UTC, datetime, timedelta

from orchai.application.events import InProcessEventDispatcher
from orchai.application.identity import (
    AccessRoleAssignmentCommand,
    CreateAccessRoleCommand,
    CreatePermissionCommand,
    CreateUserCommand,
    IdentityService,
    IssueRefreshTokenCommand,
    PermissionGrantCommand,
    RolePermissionCommand,
)
from orchai.infrastructure.identity import (
    Argon2PasswordHasher,
    JWTAccessTokenIssuer,
    Sha256RefreshTokenHasher,
)
from orchai.bootstrap.runtime import PERMISSION_CATALOG
from orchai.domain.identifiers import ProjectId, UserId
from orchai.infrastructure.persistence import (
    SQLAlchemyAccessControlRepository,
    SQLAlchemyAccessRoleRepository,
    SQLAlchemyDatabase,
    SQLAlchemyPermissionRepository,
    SQLAlchemyProjectConnectionRepository,
    SQLAlchemyRefreshTokenRepository,
    SQLAlchemyUserRepository,
)

_SECRET_KEY = "test-secret-key-with-at-least-32-characters"


def test_identity_tables_survive_application_restart(tmp_path) -> None:
    async def run() -> None:
        database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
        database = SQLAlchemyDatabase(database_url)
        database.migrate()

        service = IdentityService(
            user_repository=SQLAlchemyUserRepository(database),
            access_role_repository=SQLAlchemyAccessRoleRepository(database),
            permission_repository=SQLAlchemyPermissionRepository(database),
            refresh_token_repository=SQLAlchemyRefreshTokenRepository(database),
            access_control_repository=SQLAlchemyAccessControlRepository(database),
            password_hasher=Argon2PasswordHasher(),
            event_publisher=InProcessEventDispatcher(),
            access_token_issuer=JWTAccessTokenIssuer(secret_key=_SECRET_KEY),
            refresh_token_hasher=Sha256RefreshTokenHasher(),
        )

        user = await service.create_user(
            CreateUserCommand(username="alice", plain_password="correct horse battery")
        )
        role = await service.create_access_role(
            CreateAccessRoleCommand(name="operator", description="Operates things.")
        )
        permission = await service.create_permission(
            CreatePermissionCommand(key="requests:create")
        )
        direct_permission = await service.create_permission(
            CreatePermissionCommand(key="admin:manage_users")
        )
        await service.add_permission_to_role(
            RolePermissionCommand(role_id=role.id, permission_id=permission.id)
        )
        await service.assign_access_role(
            AccessRoleAssignmentCommand(user_id=user.id, role_id=role.id)
        )
        await service.grant_permission(
            PermissionGrantCommand(user_id=user.id, permission_id=direct_permission.id)
        )
        token = await service.issue_refresh_token(
            IssueRefreshTokenCommand(
                user_id=user.id,
                token_hash="precomputed-hash",
                expires_at=datetime.now(UTC) + timedelta(days=30),
            )
        )

        restarted_database = SQLAlchemyDatabase(database_url)
        restarted_database.migrate()
        restarted_service = IdentityService(
            user_repository=SQLAlchemyUserRepository(restarted_database),
            access_role_repository=SQLAlchemyAccessRoleRepository(restarted_database),
            permission_repository=SQLAlchemyPermissionRepository(restarted_database),
            refresh_token_repository=SQLAlchemyRefreshTokenRepository(
                restarted_database
            ),
            access_control_repository=SQLAlchemyAccessControlRepository(
                restarted_database
            ),
            password_hasher=Argon2PasswordHasher(),
            event_publisher=InProcessEventDispatcher(),
            access_token_issuer=JWTAccessTokenIssuer(secret_key=_SECRET_KEY),
            refresh_token_hasher=Sha256RefreshTokenHasher(),
        )

        verified = await restarted_service.verify_credentials(
            "alice", "correct horse battery"
        )
        assert verified is not None
        assert verified.id == user.id

        keys = await restarted_service.effective_permission_keys(user.id)
        assert keys == frozenset({"requests:create", "admin:manage_users"})

        role_users = await SQLAlchemyAccessControlRepository(
            restarted_database
        ).list_user_ids_for_role(role.id)
        assert role_users == (user.id,)

        persisted_token = await SQLAlchemyRefreshTokenRepository(
            restarted_database
        ).get(token.id)
        assert persisted_token.is_active() is True

        by_hash = await SQLAlchemyRefreshTokenRepository(
            restarted_database
        ).get_by_token_hash("precomputed-hash")
        assert by_hash is not None
        assert by_hash.id == token.id

        missing = await SQLAlchemyRefreshTokenRepository(
            restarted_database
        ).get_by_token_hash("no-such-hash")
        assert missing is None

    asyncio.run(run())


def test_project_connections_survive_application_restart(tmp_path) -> None:
    async def run() -> None:
        database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
        database = SQLAlchemyDatabase(database_url)
        database.migrate()

        project_id = ProjectId.new()
        user_id = UserId.new()
        other_user_id = UserId.new()
        repository = SQLAlchemyProjectConnectionRepository(database)
        await repository.link(project_id, user_id)
        await repository.link(project_id, other_user_id)
        # Linking the same pair twice is idempotent, not an error/duplicate.
        await repository.link(project_id, user_id)

        restarted_database = SQLAlchemyDatabase(database_url)
        restarted_database.migrate()
        restarted_repository = SQLAlchemyProjectConnectionRepository(
            restarted_database
        )

        assert await restarted_repository.list_project_ids_for_user(user_id) == (
            project_id,
        )
        user_ids = set(
            await restarted_repository.list_user_ids_for_project(project_id)
        )
        assert user_ids == {user_id, other_user_id}
        assert await restarted_repository.list_project_ids_for_user(
            UserId.new()
        ) == ()

    asyncio.run(run())


def test_permission_catalog_seed_is_idempotent_and_survives_restart(tmp_path) -> None:
    async def run() -> None:
        database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
        database = SQLAlchemyDatabase(database_url)
        database.migrate()
        repository = SQLAlchemyPermissionRepository(database)

        repository.seed_catalog(PERMISSION_CATALOG)
        first_pass = await repository.list(limit=100)
        assert {p.key for p in first_pass} == set(PERMISSION_CATALOG)

        # Re-seeding does not duplicate the existing catalog rows.
        repository.seed_catalog(PERMISSION_CATALOG)
        second_pass = await repository.list(limit=100)
        assert len(second_pass) == len(first_pass)

        restarted_database = SQLAlchemyDatabase(database_url)
        restarted_database.migrate()
        restarted_repository = SQLAlchemyPermissionRepository(restarted_database)
        restarted_repository.seed_catalog(PERMISSION_CATALOG)
        after_restart = await restarted_repository.list(limit=100)
        assert {p.key for p in after_restart} == set(PERMISSION_CATALOG)
        assert len(after_restart) == len(first_pass)

    asyncio.run(run())
