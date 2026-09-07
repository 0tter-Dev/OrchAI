"""Minimal OrchAI CLI."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import typer
import uvicorn

from orchai.application.authorization import (
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.context import ResolveExecutionContextCommand
from orchai.application.executions import (
    CompleteExecutionCommand,
    RequestExecutionCommand,
    TransitionExecutionCommand,
)
from orchai.application.identity import (
    AccessTokenClaims,
    CreateAccessRoleCommand,
    CreateUserCommand,
    CreateUserWithRolesCommand,
    LoginCommand,
    LogoutCommand,
    SetAccessRolesForUserCommand,
    SetPermissionsForRoleCommand,
    UpdateUserProfileCommand,
)
from orchai.application.modules import list_modules
from orchai.application.orchestration import (
    TaskWorkflowStage,
    run_local_flow,
    run_project_operation,
    run_task_workflow_stage,
)
from orchai.application.policies import AutomaticExecutionPolicy, PolicyOperation
from orchai.application.projects import (
    RegisterProjectCommand,
    UpdateProjectSecurityCommand,
)
from orchai.application.tasks import CreateTaskCommand, TransitionTaskCommand
from orchai.bootstrap import (
    build_identity_runtime_from_settings,
    build_local_flow_dependencies_from_settings,
    build_sqlalchemy_runtime,
    collect_runtime_status,
    collect_task_snapshot,
    provider_from_settings,
)
from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.context import ContextSource
from orchai.domain.events import EventType
from orchai.domain.executions import (
    ExecutionState,
    ExecutionStateMachine,
    ResourceUsage,
)
from orchai.domain.identifiers import (
    AccessRoleId,
    AuditRecordId,
    AuthorizationId,
    ExecutionId,
    ModelId,
    PermissionId,
    ProjectId,
    SuggestionId,
    TaskId,
    UserId,
)
from orchai.domain.identity import (
    DuplicateAccessRoleNameError,
    DuplicateUsernameError,
    InvalidAccessTokenError,
    InvalidCredentialsError,
    UserRequiresAccessRoleError,
)
from orchai.domain.projects import (
    ProjectOperation,
    ProjectReadinessLevel,
    ProjectSecurityProfile,
    ProviderSharingLevel,
    ProviderTarget,
)
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import SuggestionStatus
from orchai.domain.tasks import ExecutionMode, TaskState, TaskStateMachine
from orchai.infrastructure.configuration import DatabaseSettings, load_settings
from orchai.infrastructure.identity import JWTAccessTokenIssuer
from orchai.infrastructure.persistence import (
    SQLAlchemyDatabase,
    SQLAlchemyProjectConnectionRepository,
)
from orchai.infrastructure.persistence.db import DatabaseAdmin
from orchai.infrastructure.projects import LocalFilesystemProjectAdapter
from orchai.interfaces.api import app as api_application

app = typer.Typer(help="OrchAI orchestration CLI.")
db_app = typer.Typer(help="Database operations.")
tasks_app = typer.Typer(help="Task state operations.")
authorizations_app = typer.Typer(help="Authorization record operations.")
executions_app = typer.Typer(help="Execution state operations.")
policies_app = typer.Typer(help="Policy evaluation operations.")
automatic_policy_app = typer.Typer(help="Automatic-mode execution policy configuration.")
audit_app = typer.Typer(help="Audit history operations.")
events_app = typer.Typer(help="Event history operations.")
metrics_app = typer.Typer(help="Operational metrics operations.")
suggestions_app = typer.Typer(help="Suggestion operations.")
projects_app = typer.Typer(help="Project adapter operations.")
modules_app = typer.Typer(help="Module registry operations (ADR-015).")
providers_app = typer.Typer(help="AI provider runtime operations.")
runtime_app = typer.Typer(help="Consolidated runtime operational checks.")
api_app = typer.Typer(help="HTTP API operations.")
auth_app = typer.Typer(help="Authentication operations (ADR-012).")
users_app = typer.Typer(help="Admin-only user configuration operations (ADR-012).")
access_roles_app = typer.Typer(
    help="Admin-only access-role configuration operations (ADR-012)."
)
me_app = typer.Typer(help="Self-service: the logged-in user's own profile (ADR-012).")
app.add_typer(db_app, name="db")
app.add_typer(auth_app, name="auth")
app.add_typer(users_app, name="users")
app.add_typer(access_roles_app, name="access-roles")
app.add_typer(me_app, name="me")
app.add_typer(tasks_app, name="tasks")
app.add_typer(authorizations_app, name="authorizations")
app.add_typer(executions_app, name="executions")
app.add_typer(policies_app, name="policies")
policies_app.add_typer(automatic_policy_app, name="automatic")
app.add_typer(audit_app, name="audit")
app.add_typer(events_app, name="events")
app.add_typer(metrics_app, name="metrics")
app.add_typer(suggestions_app, name="suggestions")
app.add_typer(projects_app, name="projects")
app.add_typer(modules_app, name="modules")
app.add_typer(providers_app, name="providers")
app.add_typer(runtime_app, name="runtime")
app.add_typer(api_app, name="api")

# Chat-first request command is registered directly on the root app (orchai request ...)
# It provides the CLI counterpart to POST /requests.


def _credentials_path() -> Path:
    """Local, user-only-readable credentials file written by `orchai auth login`.

    Deliberately a per-user home-directory path (not project-relative like
    the SQLite default), since a login session is a property of the person
    running the CLI, not of any one project checkout.
    """

    return Path.home() / ".orchai" / "credentials.json"


def _read_credentials() -> dict[str, Any] | None:
    path = _credentials_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def _write_credentials(data: dict[str, Any]) -> None:
    path = _credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def _clear_credentials() -> None:
    path = _credentials_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def require_cli_permission(permission_key: str | None = None) -> None:
    """Enforce a CLI permission (ADR-012, `docs/TO-DO.md` Priority 1 Phase 3).

    Called as the first statement of every command that is not part of the
    `auth login` / `auth bootstrap-admin` bootstrap path. This is the CLI
    counterpart to `interfaces.api.main.require_permission`: same rollout
    behavior (inert unless `ORCHAI_AUTH_ENFORCED` is true), same superuser
    bypass, same permission-key semantics (`None` = authenticated only).

    Implemented as a plain function called explicitly, not a decorator:
    Typer/Click builds each command's argument parser by introspecting the
    command function's own signature, and a decorator that changes the
    call shape (e.g. to `*args, **kwargs`) risks silently breaking that
    parsing. A one-line call at the top of the function body is exactly as
    declarative and carries none of that risk.

    Resolves the bearer token from `ORCHAI_TOKEN` or the local credentials
    file (`orchai auth login`'s output) -- not from a per-command `--token`
    option, which would require touching every command's signature just
    like a decorator would; that refinement is left for a follow-up if it
    turns out to be needed in practice.

    On any failure, prints an error to stderr and exits with status 1,
    matching Typer's convention for fatal CLI errors.
    """

    settings = load_settings()
    if not settings.auth.enforced:
        return

    claims = _resolve_cli_claims(settings)
    if claims.is_superuser or permission_key is None:
        return

    identity_runtime = build_identity_runtime_from_settings(settings)
    effective_keys = asyncio.run(
        identity_runtime.identity_service.effective_permission_keys(claims.user_id)
    )
    if permission_key not in effective_keys:
        typer.echo(
            f"Error: missing required permission: {permission_key}",
            err=True,
        )
        raise typer.Exit(code=1)


def _resolve_cli_claims(settings) -> AccessTokenClaims:
    """Resolve and decode the caller's bearer access token, unconditionally.

    Factored out of `require_cli_permission` so `require_authenticated_cli_user`
    (the CLI counterpart of `interfaces.api.main.require_authenticated_user`,
    used by the `orchai me *` self-service commands, which need to know
    which user "me" refers to regardless of `ORCHAI_AUTH_ENFORCED`) can
    reuse the exact same token resolution/decode path without duplicating
    it. Exits with status 1 on any failure, matching `require_cli_permission`.
    """

    token = os.environ.get("ORCHAI_TOKEN")
    if not token:
        credentials = _read_credentials()
        token = credentials.get("access_token") if credentials else None
    if not token:
        typer.echo(
            "Error: not authenticated. Run 'orchai auth login' first, "
            "or set ORCHAI_TOKEN.",
            err=True,
        )
        raise typer.Exit(code=1)

    issuer = JWTAccessTokenIssuer(
        secret_key=settings.auth.secret_key,
        ttl=timedelta(minutes=settings.auth.access_token_ttl_minutes),
    )
    try:
        return issuer.decode(token)
    except InvalidAccessTokenError as exc:
        typer.echo(
            f"Error: invalid or expired access token ({exc}). "
            "Run 'orchai auth login' again.",
            err=True,
        )
        raise typer.Exit(code=1) from exc


def require_authenticated_cli_user() -> AccessTokenClaims:
    """CLI counterpart of `interfaces.api.main.require_authenticated_user`.

    Always resolves and returns the caller's claims, ignoring
    `ORCHAI_AUTH_ENFORCED` -- the `orchai me *` commands need to know which
    user "me" refers to unconditionally, the same way `/me` always
    requires a real bearer token on the API side (there is no meaningful
    "no-op" reading of "show my own profile").
    """

    return _resolve_cli_claims(load_settings())


@auth_app.command("login")
def auth_login(
    username: str = typer.Option(..., "--username", prompt=True),
    password: str = typer.Option(
        ..., "--password", prompt=True, hide_input=True, confirmation_prompt=False
    ),
) -> None:
    """Authenticate and persist the resulting token pair for later commands."""

    settings = load_settings()
    identity_runtime = build_identity_runtime_from_settings(settings)
    try:
        result = asyncio.run(
            identity_runtime.identity_service.login(
                LoginCommand(username=username, plain_password=password)
            )
        )
    except InvalidCredentialsError as exc:
        typer.echo("Error: invalid username or password.", err=True)
        raise typer.Exit(code=1) from exc

    _write_credentials(
        {
            "username": result.user.username,
            "access_token": result.access_token.token,
            "access_token_expires_at": result.access_token.expires_at.isoformat(),
            "refresh_token": result.raw_refresh_token,
            "refresh_token_expires_at": result.refresh_token.expires_at.isoformat(),
        }
    )
    typer.echo(f"Logged in as {result.user.username}.")
    typer.echo(f"Credentials saved to {_credentials_path()}.")


@auth_app.command("logout")
def auth_logout() -> None:
    """Revoke the persisted refresh token and clear local credentials."""

    require_cli_permission()
    settings = load_settings()
    credentials = _read_credentials()
    if credentials and credentials.get("refresh_token"):
        identity_runtime = build_identity_runtime_from_settings(settings)
        asyncio.run(
            identity_runtime.identity_service.logout(
                LogoutCommand(raw_refresh_token=credentials["refresh_token"])
            )
        )
    _clear_credentials()
    typer.echo("Logged out.")


@auth_app.command("bootstrap-admin")
def auth_bootstrap_admin(
    username: str | None = typer.Option(
        None,
        "--username",
        help="Defaults to ORCHAI_ADMIN_USERNAME.",
    ),
    password: str | None = typer.Option(
        None,
        "--password",
        help="Defaults to ORCHAI_ADMIN_PASSWORD.",
    ),
) -> None:
    """Create the first superuser (ADR-012 §8).

    Only succeeds when zero users exist yet -- this is the one path that
    creates a user without requiring an already-authenticated caller,
    resolving the chicken-and-egg problem of bootstrapping the very first
    account. Refuses once any user exists; use the (not yet implemented)
    user-management surface, or a direct `IdentityService.create_user`
    call, to add further users afterward.
    """

    settings = load_settings()
    resolved_username = username or settings.auth.admin_username
    resolved_password = password or settings.auth.admin_password
    if not resolved_username or not resolved_password:
        typer.echo(
            "Error: an admin username and password are required, via "
            "--username/--password or ORCHAI_ADMIN_USERNAME/"
            "ORCHAI_ADMIN_PASSWORD.",
            err=True,
        )
        raise typer.Exit(code=1)

    identity_runtime = build_identity_runtime_from_settings(settings)
    existing_users = asyncio.run(identity_runtime.identity_service.list_users(limit=1))
    if existing_users:
        typer.echo(
            "Error: bootstrap-admin only runs when zero users exist yet; "
            "at least one user is already present.",
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        user = asyncio.run(
            identity_runtime.identity_service.create_user(
                CreateUserCommand(
                    username=resolved_username,
                    plain_password=resolved_password,
                    is_superuser=True,
                )
            )
        )
    except DuplicateUsernameError as exc:
        typer.echo(f"Error: username {resolved_username!r} is already taken.", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Created superuser {user.username!r}.")


@users_app.command("list")
def list_users(
    is_active: bool | None = typer.Option(
        None, "--is-active", help="Filter by active state."
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
) -> None:
    """List every user in the system with full admin details (admin-only)."""

    require_cli_permission("admin:manage_users")
    settings = load_settings()
    identity_runtime = build_identity_runtime_from_settings(settings)
    service = identity_runtime.identity_service
    users = asyncio.run(service.list_users(is_active=is_active, limit=limit))
    # Connections are descriptive project-DB metadata, resolved against the
    # default primary database -- see `ProjectConnectionRepository`'s
    # module docstring, and `interfaces.api.main.admin_list_users`.
    project_runtime = build_sqlalchemy_runtime(settings.database.sqlalchemy_url)
    connection_repository = SQLAlchemyProjectConnectionRepository(
        project_runtime.database
    )
    typer.echo(f"users={len(users)}")
    for user in users:
        roles = asyncio.run(service.list_roles_for_user(user.id))
        connected = asyncio.run(
            connection_repository.list_project_ids_for_user(user.id)
        )
        typer.echo(
            " ".join(
                (
                    f"user_id={user.id}",
                    f"username={user.username}",
                    f"email={user.email or ''}",
                    f"is_superuser={str(user.is_superuser).lower()}",
                    f"is_active={str(user.is_active).lower()}",
                    "access_roles=" + ",".join(role.name for role in roles),
                    "connected_project_ids="
                    + ",".join(str(project_id) for project_id in connected),
                )
            )
        )


@users_app.command("create")
def create_user(
    username: str = typer.Option(..., "--username"),
    password: str = typer.Option(
        ..., "--password", prompt=True, hide_input=True, confirmation_prompt=True
    ),
    role_id: list[str] = typer.Option(
        [],
        "--role-id",
        help=(
            "Access role id to assign (repeatable). At least one is "
            "required unless --superuser."
        ),
    ),
    email: str | None = typer.Option(None, "--email"),
    superuser: bool = typer.Option(
        False,
        "--superuser",
        help="Create as superuser (bypasses all permission checks; no access role required).",
    ),
) -> None:
    """Create a new user together with its initial access roles (admin-only)."""

    require_cli_permission("admin:manage_users")
    identity_runtime = build_identity_runtime_from_settings(load_settings())
    service = identity_runtime.identity_service
    try:
        user = asyncio.run(
            service.create_user_with_roles(
                CreateUserWithRolesCommand(
                    username=username,
                    plain_password=password,
                    role_ids=tuple(AccessRoleId(rid) for rid in role_id),
                    email=email,
                    is_superuser=superuser,
                )
            )
        )
    except DuplicateUsernameError as exc:
        typer.echo(f"Error: username {username!r} is already taken.", err=True)
        raise typer.Exit(code=1) from exc
    except UserRequiresAccessRoleError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except LookupError as exc:
        typer.echo(f"Error: unknown access role: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    roles = asyncio.run(service.list_roles_for_user(user.id))
    typer.echo(f"user_id={user.id}")
    typer.echo(f"username={user.username}")
    typer.echo(f"is_superuser={str(user.is_superuser).lower()}")
    typer.echo("access_roles=" + ",".join(role.name for role in roles))


@users_app.command("set-access-roles")
def set_user_access_roles(
    user_id: str = typer.Argument(..., help="User id to update."),
    role_id: list[str] = typer.Option(
        [],
        "--role-id",
        help=(
            "Replace-all: the user's complete access-role set (repeatable). "
            "At least one is required unless the user is a superuser."
        ),
    ),
) -> None:
    """Replace the full set of access roles assigned to a user (admin-only)."""

    require_cli_permission("admin:manage_users")
    identity_runtime = build_identity_runtime_from_settings(load_settings())
    service = identity_runtime.identity_service
    try:
        asyncio.run(
            service.set_access_roles_for_user(
                SetAccessRolesForUserCommand(
                    user_id=UserId(user_id),
                    role_ids=tuple(AccessRoleId(rid) for rid in role_id),
                )
            )
        )
    except UserRequiresAccessRoleError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except LookupError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    user = asyncio.run(service.get_user(UserId(user_id)))
    roles = asyncio.run(service.list_roles_for_user(user.id))
    typer.echo(f"user_id={user.id}")
    typer.echo("access_roles=" + ",".join(role.name for role in roles))


@access_roles_app.command("list")
def list_access_roles(
    limit: int = typer.Option(50, "--limit", min=1, max=200),
) -> None:
    """List every access role with its linked users and permissions (admin-only)."""

    require_cli_permission("admin:manage_users")
    identity_runtime = build_identity_runtime_from_settings(load_settings())
    service = identity_runtime.identity_service
    roles = asyncio.run(service.list_access_roles(limit=limit))
    typer.echo(f"access_roles={len(roles)}")
    for role in roles:
        permissions = asyncio.run(service.list_permissions_for_role(role.id))
        users = asyncio.run(service.list_users_for_role(role.id))
        typer.echo(
            " ".join(
                (
                    f"role_id={role.id}",
                    f"name={role.name}",
                    "permissions=" + ",".join(p.key for p in permissions),
                    "users=" + ",".join(u.username for u in users),
                )
            )
        )


@access_roles_app.command("create")
def create_access_role(
    name: str = typer.Option(..., "--name"),
    description: str = typer.Option("", "--description"),
) -> None:
    """Create a new access role (admin-only)."""

    require_cli_permission("admin:manage_users")
    identity_runtime = build_identity_runtime_from_settings(load_settings())
    service = identity_runtime.identity_service
    try:
        role = asyncio.run(
            service.create_access_role(
                CreateAccessRoleCommand(name=name, description=description)
            )
        )
    except DuplicateAccessRoleNameError as exc:
        typer.echo(f"Error: access role name {name!r} is already taken.", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"role_id={role.id}")
    typer.echo(f"name={role.name}")


@access_roles_app.command("set-permissions")
def set_role_permissions(
    role_id: str = typer.Argument(..., help="Access role id to update."),
    permission_id: list[str] = typer.Option(
        [],
        "--permission-id",
        help="Replace-all: the role's complete permission bundle (repeatable).",
    ),
) -> None:
    """Replace the full set of permissions bundled into an access role (admin-only)."""

    require_cli_permission("admin:manage_users")
    identity_runtime = build_identity_runtime_from_settings(load_settings())
    service = identity_runtime.identity_service
    try:
        asyncio.run(
            service.set_permissions_for_role(
                SetPermissionsForRoleCommand(
                    role_id=AccessRoleId(role_id),
                    permission_ids=tuple(PermissionId(pid) for pid in permission_id),
                )
            )
        )
    except LookupError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    role = asyncio.run(service.get_access_role(AccessRoleId(role_id)))
    permissions = asyncio.run(service.list_permissions_for_role(role.id))
    typer.echo(f"role_id={role.id}")
    typer.echo("permissions=" + ",".join(p.key for p in permissions))


@me_app.command("show")
def show_me() -> None:
    """Show the logged-in user's own profile."""

    claims = require_authenticated_cli_user()
    settings = load_settings()
    identity_runtime = build_identity_runtime_from_settings(settings)
    service = identity_runtime.identity_service
    user = asyncio.run(service.get_user(claims.user_id))
    roles = asyncio.run(service.list_roles_for_user(user.id))
    project_runtime = build_sqlalchemy_runtime(settings.database.sqlalchemy_url)
    connection_repository = SQLAlchemyProjectConnectionRepository(
        project_runtime.database
    )
    connected = asyncio.run(connection_repository.list_project_ids_for_user(user.id))
    typer.echo(f"user_id={user.id}")
    typer.echo(f"username={user.username}")
    typer.echo(f"email={user.email or ''}")
    typer.echo(f"is_superuser={str(user.is_superuser).lower()}")
    typer.echo(f"is_active={str(user.is_active).lower()}")
    typer.echo("access_roles=" + ",".join(role.name for role in roles))
    typer.echo(
        "connected_project_ids="
        + ",".join(str(project_id) for project_id in connected)
    )


@me_app.command("update")
def update_me(
    username: str | None = typer.Option(None, "--username"),
    email: str | None = typer.Option(None, "--email"),
) -> None:
    """Update the logged-in user's own profile (username/email only)."""

    claims = require_authenticated_cli_user()
    identity_runtime = build_identity_runtime_from_settings(load_settings())
    service = identity_runtime.identity_service
    try:
        user = asyncio.run(
            service.update_user_profile(
                UpdateUserProfileCommand(
                    user_id=claims.user_id,
                    username=username,
                    email=email,
                )
            )
        )
    except DuplicateUsernameError as exc:
        typer.echo(f"Error: username {username!r} is already taken.", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"user_id={user.id}")
    typer.echo(f"username={user.username}")
    typer.echo(f"email={user.email or ''}")


@me_app.command("projects")
def list_me_projects() -> None:
    """List the projects the logged-in user has connected to OrchAI."""

    claims = require_authenticated_cli_user()
    settings = load_settings()
    project_runtime = build_sqlalchemy_runtime(settings.database.sqlalchemy_url)
    connection_repository = SQLAlchemyProjectConnectionRepository(
        project_runtime.database
    )
    project_ids = asyncio.run(
        connection_repository.list_project_ids_for_user(claims.user_id)
    )
    projects = [
        asyncio.run(project_runtime.project_service.get_project(project_id))
        for project_id in project_ids
    ]
    typer.echo(f"projects={len(projects)}")
    for project in projects:
        typer.echo(
            " ".join(
                (
                    f"project_id={project.id}",
                    f"name={project.name}",
                    f"effective_readiness_level={project.readiness_level.value}",
                )
            )
        )


@db_app.command("sync")
def sync_database(
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
    maintenance_database: str = typer.Option(
        "postgres",
        "--maintenance-database",
        help="Existing database used to create the target database, when applicable.",
    ),
) -> None:
    """Create the database if needed (PostgreSQL only), then apply migrations.

    This is the single, standard database administration command: create the
    target database when it does not exist yet (a no-op, not an error, for a
    local-flow/SQLite target, which does not need a database created up
    front), then apply migrations unconditionally.
    """

    require_cli_permission("admin:db")
    settings = load_settings()
    url = database_url or settings.database.url
    normalized = DatabaseSettings(url=url)
    message = ""
    if normalized.is_postgresql:
        created = DatabaseAdmin(
            url,
            maintenance_database=maintenance_database,
        ).create_database()
        create_status = "created" if created else "already_exists"
    else:
        create_status = "skipped_non_postgresql"
        message = (
            "Database creation only applies to PostgreSQL; the currently "
            "selected database is a local-flow/SQLite target, which does "
            "not need a database created up front, so that step was "
            "skipped. Migrations were still applied."
        )

    SQLAlchemyDatabase(normalized.sqlalchemy_url).migrate()
    typer.echo(f"database={_safe_database_label(url)}")
    typer.echo(f"create_status={create_status}")
    typer.echo("migrations=applied")
    if message:
        typer.echo(message)


@app.command("local-flow")
def local_flow(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the project adapter.",
    ),
    context_path: str = typer.Argument(
        ...,
        help="Relative file path to authorize and resolve as execution context.",
    ),
    title: str = typer.Option("CLI local flow", help="Task title."),
    model: str | None = typer.Option(
        None,
        help="Provider-independent model id. Defaults to configured provider model.",
    ),
    provider_target: ProviderTarget = typer.Option(
        ProviderTarget.LOCAL,
        "--provider-target",
        case_sensitive=False,
        help="Treat the execution as local or cloud for project security policy.",
    ),
    execution_mode: ExecutionMode = typer.Option(
        ExecutionMode.SUGGESTED,
        "--execution-mode",
        case_sensitive=False,
        help="Execution mode enforced by the Orchestrator.",
    ),
    approve_suggestion: bool = typer.Option(
        False,
        "--approve-suggestion/--no-approve-suggestion",
        help="Explicitly approve the generated suggestion in SUGGESTED mode.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Run a minimal authorized task/execution/context flow."""

    require_cli_permission("requests:create")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    effective_settings = settings.model_copy(
        update={
            "database": settings.database.model_copy(update={"url": url}),
        }
    )
    result = asyncio.run(
        run_local_flow(
            project_root=project_root,
            context_path=context_path,
            title=title,
            model=model or effective_settings.ai_provider.model or "local-demo",
            provider_target=provider_target,
            dependencies=build_local_flow_dependencies_from_settings(effective_settings),
            storage_label=_safe_database_label(url),
            execution_mode=execution_mode,
            approve_suggestion=approve_suggestion,
        )
    )
    typer.echo(f"project_id={result['project_id']}")
    typer.echo(f"task_id={result['task_id']}")
    typer.echo(f"authorization_id={result['authorization_id']}")
    typer.echo(f"execution_id={result['execution_id']}")
    typer.echo(f"task_state={result['task_state']}")
    typer.echo(f"execution_state={result['execution_state']}")
    typer.echo(f"suggestion_id={result['suggestion_id']}")
    typer.echo(f"suggested_role={result['suggested_role']}")
    typer.echo(f"suggested_action={result['suggested_action']}")
    typer.echo(f"suggestion_status={result['suggestion_status']}")
    typer.echo(f"blocked_reason={result['blocked_reason']}")
    typer.echo(f"context_items={result['context_items']}")
    typer.echo(f"events={result['events']}")
    typer.echo(f"audit_records={result['audit_records']}")
    typer.echo(f"database={result['database']}")


@app.command("request")
def chat_request(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Project folder to connect to OrchAI.",
    ),
    prompt: str = typer.Argument(
        ...,
        help="Natural language description of what you want OrchAI to do.",
    ),
    role: RoleName | None = typer.Option(
        None,
        "--role",
        case_sensitive=False,
        help="Orchestration role (DEVELOPER, QUALITY_AGENT, PLANNER, …).",
    ),
    action: ActionName | None = typer.Option(
        None,
        "--action",
        case_sensitive=False,
        help="Operation to perform (IMPLEMENT, REVIEW, PLAN, …).",
    ),
    model: str | None = typer.Option(
        None,
        help="AI model identifier. Defaults to configured provider model.",
    ),
    provider_target: ProviderTarget = typer.Option(
        ProviderTarget.LOCAL,
        "--provider-target",
        case_sensitive=False,
        help="LOCAL (e.g. Ollama via litellm) or CLOUD (configured cloud provider).",
    ),
    execution_mode: ExecutionMode = typer.Option(
        ExecutionMode.SUGGESTED,
        "--execution-mode",
        case_sensitive=False,
        help="MANUAL | SUGGESTED (default) | AUTOMATIC.",
    ),
    context_path: str | None = typer.Option(
        None,
        "--context",
        help="Optional file path to include as execution context.",
    ),
    title: str | None = typer.Option(
        None,
        "--title",
        help="Task title. Defaults to first line of the prompt.",
    ),
    approve_suggestion: bool = typer.Option(
        False,
        "--approve/--no-approve",
        help="Auto-approve the generated suggestion in SUGGESTED mode.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Submit a request to OrchAI using a natural language prompt (chat-first interface).

    This is the CLI counterpart to POST /requests.  OrchAI connects to the
    project, creates a Task from your prompt, and orchestrates the full flow.

    Example:
        orchai request . "Review the authentication module for security issues" --role QUALITY_AGENT --approve
    """
    require_cli_permission("requests:create")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    effective_settings = settings.model_copy(
        update={
            "database": settings.database.model_copy(update={"url": url}),
        }
    )

    # Derive title from first line of prompt if not explicitly provided
    prompt_lines = prompt.strip().splitlines()
    derived_title = title or (prompt_lines[0][:120] if prompt_lines else "Untitled request")

    # Use provided context_path or fall back to project root (".") as context
    effective_context_path = context_path or "."

    typer.echo(f"role={role.value if role else '(from orchestrator)'}")
    typer.echo(f"action={action.value if action else '(from orchestrator)'}")
    typer.echo(f"execution_mode={execution_mode.value}")
    typer.echo(f"provider_target={provider_target.value}")
    typer.echo(f"title={derived_title!r}")
    typer.echo("")

    result = asyncio.run(
        run_local_flow(
            project_root=project_root,
            context_path=effective_context_path,
            title=derived_title,
            model=model or effective_settings.ai_provider.model or "local-demo",
            provider_target=provider_target,
            dependencies=build_local_flow_dependencies_from_settings(effective_settings),
            storage_label=_safe_database_label(url),
            execution_mode=execution_mode,
            approve_suggestion=approve_suggestion,
        )
    )

    request_id = result.get("task_id", "")
    typer.echo(f"request_id={request_id}")
    typer.echo(f"task_state={result['task_state']}")
    typer.echo(f"execution_state={result['execution_state']}")
    typer.echo(f"suggestion_status={result['suggestion_status']}")
    typer.echo(f"suggestion_id={result['suggestion_id']}")
    typer.echo(f"suggested_role={result['suggested_role']}")
    typer.echo(f"suggested_action={result['suggested_action']}")
    typer.echo(f"blocked_reason={result['blocked_reason']}")
    typer.echo(f"project_id={result['project_id']}")
    typer.echo(f"authorization_id={result['authorization_id']}")
    typer.echo(f"execution_id={result['execution_id']}")
    typer.echo(f"context_items={result['context_items']}")
    typer.echo(f"events={result['events']}")
    typer.echo(f"audit_records={result['audit_records']}")
    typer.echo(f"database={result['database']}")
    if request_id:
        typer.echo("")
        typer.echo(f"flow: GET /requests/{request_id}/flow")


@audit_app.command("list")
def list_audit_records(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter audit records by task id.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Filter audit records by project id.",
    ),
    execution_id: str | None = typer.Option(
        None,
        "--execution-id",
        help="Filter audit records by execution id.",
    ),
    authorization_id: str | None = typer.Option(
        None,
        "--authorization-id",
        help="Filter audit records by authorization id.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List persisted audit records."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    records = asyncio.run(
        runtime.audit_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            project_id=ProjectId(project_id) if project_id is not None else None,
            execution_id=ExecutionId(execution_id) if execution_id is not None else None,
            authorization_id=(
                AuthorizationId(authorization_id)
                if authorization_id is not None
                else None
            ),
            limit=limit,
        )
    )
    for record in records:
        typer.echo(
            " ".join(
                (
                    f"audit_id={record.id}",
                    f"occurred_at={record.occurred_at.isoformat()}",
                    f"operation={record.operation}",
                    f"outcome={record.outcome}",
                    f"actor={record.actor}",
                    f"task_id={record.task_id or ''}",
                    f"project_id={record.project_id or ''}",
                    f"execution_id={record.execution_id or ''}",
                    f"authorization_id={record.authorization_id or ''}",
                    f"event_id={record.event_id or ''}",
                    f"correlation_id={record.correlation_id or ''}",
                    f"causation_id={record.causation_id or ''}",
                )
            )
        )


@audit_app.command("show")
def show_audit_record(
    audit_id: str = typer.Argument(..., help="Persisted audit record id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Show one persisted audit record."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    record = asyncio.run(runtime.audit_repository.get(AuditRecordId(audit_id)))
    typer.echo(f"audit_id={record.id}")
    typer.echo(f"occurred_at={record.occurred_at.isoformat()}")
    typer.echo(f"operation={record.operation}")
    typer.echo(f"outcome={record.outcome}")
    typer.echo(f"actor={record.actor}")
    typer.echo(f"task_id={record.task_id or ''}")
    typer.echo(f"project_id={record.project_id or ''}")
    typer.echo(f"execution_id={record.execution_id or ''}")
    typer.echo(f"authorization_id={record.authorization_id or ''}")
    typer.echo(f"event_id={record.event_id or ''}")
    typer.echo(f"correlation_id={record.correlation_id or ''}")
    typer.echo(f"causation_id={record.causation_id or ''}")
    typer.echo(f"metadata={dict(record.metadata)}")


@tasks_app.command("list")
def list_tasks(
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Filter tasks by project id.",
    ),
    state: TaskState | None = typer.Option(
        None,
        "--state",
        case_sensitive=False,
        help="Filter tasks by task state.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List persisted tasks."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    tasks = asyncio.run(
        runtime.task_service.list_tasks(
            project_id=ProjectId(project_id) if project_id is not None else None,
            state=state,
            limit=limit,
        )
    )
    typer.echo(f"tasks={len(tasks)}")
    for task in tasks:
        typer.echo(
            " ".join(
                (
                    f"task_id={task.id}",
                    f"project_id={task.project_id or ''}",
                    f"state={task.state.value}",
                    "available_transitions="
                    + ",".join(_task_available_transitions(task.state)),
                    f"execution_mode={task.execution_mode.value}",
                    f"title={task.title}",
                )
            )
        )


@tasks_app.command("create")
def create_task(
    title: str = typer.Option(..., "--title", help="Task title."),
    description: str = typer.Option(..., "--description", help="Task description."),
    requested_change: str = typer.Option(
        ...,
        "--requested-change",
        help="Requested change description.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Optional persisted project id.",
    ),
    execution_mode: ExecutionMode = typer.Option(
        ExecutionMode.SUGGESTED,
        "--execution-mode",
        case_sensitive=False,
        help="Execution mode for the task.",
    ),
    acceptance_criteria: str = typer.Option(
        "",
        "--acceptance-criteria",
        help="Comma-separated acceptance criteria.",
    ),
    constraints: str = typer.Option(
        "",
        "--constraints",
        help="Comma-separated constraints.",
    ),
    exclusions: str = typer.Option(
        "",
        "--exclusions",
        help="Comma-separated exclusions.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Create one task directly through the task service."""

    require_cli_permission("requests:create")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    task = asyncio.run(
        runtime.task_service.create_task(
            CreateTaskCommand(
                title=title,
                description=description,
                requested_change=requested_change,
                project_id=ProjectId(project_id) if project_id else None,
                execution_mode=execution_mode,
                acceptance_criteria=_parse_csv_tuple(acceptance_criteria) or (),
                constraints=_parse_csv_tuple(constraints) or (),
                exclusions=_parse_csv_tuple(exclusions) or (),
            )
        )
    )
    typer.echo(f"task_id={task.id}")
    typer.echo(f"project_id={task.project_id or ''}")
    typer.echo(f"state={task.state.value}")
    typer.echo("available_transitions=" + ",".join(_task_available_transitions(task.state)))
    typer.echo(f"execution_mode={task.execution_mode.value}")
    typer.echo(f"title={task.title}")


@tasks_app.command("show")
def show_task(
    task_id: str = typer.Argument(..., help="Persisted task id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Show one persisted task."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    task = asyncio.run(runtime.task_service.get_task(TaskId(task_id)))
    typer.echo(f"task_id={task.id}")
    typer.echo(f"project_id={task.project_id or ''}")
    typer.echo(f"title={task.title}")
    typer.echo(f"description={task.description}")
    typer.echo(f"state={task.state.value}")
    typer.echo("available_transitions=" + ",".join(_task_available_transitions(task.state)))
    typer.echo(f"execution_mode={task.execution_mode.value}")
    typer.echo(f"requested_change={task.scope.requested_change}")
    typer.echo("acceptance_criteria=" + ",".join(task.scope.acceptance_criteria))
    typer.echo("constraints=" + ",".join(task.scope.constraints))
    typer.echo("exclusions=" + ",".join(task.scope.exclusions))


@tasks_app.command("snapshot")
def task_snapshot(
    task_id: str = typer.Argument(..., help="Persisted task id."),
    history_limit: int = typer.Option(100, "--history-limit", min=1, max=500),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Show one consolidated task-centric operational snapshot."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    snapshot = asyncio.run(
        collect_task_snapshot(
            runtime=runtime,
            task_id=TaskId(task_id),
            history_limit=history_limit,
        )
    )
    task = snapshot["task"]
    typer.echo(f"task_id={task.id}")
    typer.echo(f"project_id={task.project_id or ''}")
    typer.echo(f"state={task.state.value}")
    typer.echo("available_transitions=" + ",".join(_task_available_transitions(task.state)))
    typer.echo(f"execution_mode={task.execution_mode.value}")
    typer.echo(f"history_limit={snapshot['history_limit']}")
    typer.echo(f"authorizations={len(snapshot['authorizations'])}")
    typer.echo(f"executions={len(snapshot['executions'])}")
    typer.echo(f"suggestions={len(snapshot['suggestions'])}")
    typer.echo(f"events={len(snapshot['events'])}")
    typer.echo(f"audit_records={len(snapshot['audit_records'])}")
    typer.echo(f"metric_records={len(snapshot['metric_records'])}")
    typer.echo(f"context_records={len(snapshot['context_records'])}")
    for authorization in snapshot["authorizations"]:
        typer.echo(
            " ".join(
                (
                    "snapshot_authorization=true",
                    f"authorization_id={authorization.id}",
                    "status="
                    + (
                        authorization.status.value
                        if authorization.status is not None
                        else ""
                    ),
                    f"role={authorization.request.operation.role.value}",
                    f"action={authorization.request.operation.action.value}",
                )
            )
        )
    for execution in snapshot["executions"]:
        typer.echo(
            " ".join(
                (
                    "snapshot_execution=true",
                    f"execution_id={execution.id}",
                    f"state={execution.state.value}",
                    "available_transitions="
                    + ",".join(_execution_available_transitions(execution.state)),
                    f"role={execution.role.value}",
                    f"action={execution.action.value}",
                )
            )
        )


@tasks_app.command("advance")
def advance_task(
    task_id: str = typer.Argument(..., help="Persisted task id."),
    stage: TaskWorkflowStage | None = typer.Option(
        None,
        "--stage",
        case_sensitive=False,
        help="Explicit workflow stage. Defaults to the next suggested stage.",
    ),
    context_paths: list[str] = typer.Option(
        [],
        "--context-path",
        help="Repeatable authorized context resource for AI-backed stages.",
    ),
    documentation_path: str = typer.Option(
        "",
        "--documentation-path",
        help="Documentation target path required by DOCUMENT stage.",
    ),
    test_args: list[str] = typer.Option(
        [],
        "--test-arg",
        help="Repeatable pytest argument for TEST stage.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Provider-independent model id. Defaults to configured model.",
    ),
    provider_target: ProviderTarget = typer.Option(
        ProviderTarget.LOCAL,
        "--provider-target",
        case_sensitive=False,
        help="Target provider boundary.",
    ),
    execution_mode: ExecutionMode | None = typer.Option(
        None,
        "--execution-mode",
        case_sensitive=False,
        help="Optional execution mode override. Defaults to the task mode.",
    ),
    approve_stage: bool = typer.Option(
        False,
        "--approve-stage",
        help="Approve the stage when SUGGESTED mode requires it.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Advance one persisted task through a task-centric workflow stage."""

    require_cli_permission("requests:advance")
    settings = load_settings()
    effective_settings = (
        settings
        if database_url is None
        else settings.model_copy(
            update={
                "database": settings.database.model_copy(update={"url": database_url}),
            }
        )
    )
    url = effective_settings.database.sqlalchemy_url
    result = asyncio.run(
        run_task_workflow_stage(
            task_id=task_id,
            dependencies=build_local_flow_dependencies_from_settings(effective_settings),
            storage_label=url,
            model=model or effective_settings.ai_provider.model or "local-task-stage",
            stage=stage,
            context_paths=tuple(context_paths),
            documentation_path=documentation_path,
            test_args=tuple(test_args),
            provider_target=provider_target,
            execution_mode=execution_mode,
            approve_stage=approve_stage,
            requester="cli",
            decider="cli",
        )
    )
    for key in (
        "project_id",
        "task_id",
        "stage",
        "task_state",
        "authorization_id",
        "execution_id",
        "execution_state",
        "resource",
        "blocked_reason",
        "suggestion_id",
        "suggested_role",
        "suggested_action",
        "suggestion_status",
    ):
        typer.echo(f"{key}={result[key]}")
    typer.echo(f"events={result['events']}")
    typer.echo(f"audit_records={result['audit_records']}")
    typer.echo(f"database={result['database']}")
    output = result["output"].replace("\r", " ").replace("\n", " ").strip()
    typer.echo(f"output={output}")


@tasks_app.command("transition")
def transition_task(
    task_id: str = typer.Argument(..., help="Persisted task id."),
    target_state: TaskState = typer.Option(
        ...,
        "--target-state",
        case_sensitive=False,
        help="Target task state.",
    ),
    source: str = typer.Option(
        "cli.tasks",
        "--source",
        help="Transition source label.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Transition one task directly through the task service."""

    require_cli_permission("requests:advance")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    task = asyncio.run(
        runtime.task_service.transition_task(
            TransitionTaskCommand(
                task_id=TaskId(task_id),
                target_state=target_state,
                source=source,
            )
        )
    )
    typer.echo(f"task_id={task.id}")
    typer.echo(f"state={task.state.value}")
    typer.echo("available_transitions=" + ",".join(_task_available_transitions(task.state)))
    typer.echo(f"execution_mode={task.execution_mode.value}")


@authorizations_app.command("list")
def list_authorizations(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter authorizations by task id.",
    ),
    status: AuthorizationDecisionStatus | None = typer.Option(
        None,
        "--status",
        help="Filter by the most recent decision status (GRANTED, REJECTED, EXPIRED, REVOKED).",
    ),
    pending_only: bool = typer.Option(
        False,
        "--pending-only",
        help="Only show authorizations with no decision recorded yet.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List persisted authorizations."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    authorizations = asyncio.run(
        runtime.authorization_service.list_authorizations(
            task_id=TaskId(task_id) if task_id is not None else None,
            status=status,
            pending_only=pending_only,
            limit=limit,
        )
    )
    typer.echo(f"authorizations={len(authorizations)}")
    for authorization in authorizations:
        operation = authorization.request.operation
        typer.echo(
            " ".join(
                (
                    f"authorization_id={authorization.id}",
                    f"task_id={authorization.task_id}",
                    "status="
                    + (
                        authorization.status.value
                        if authorization.status is not None
                        else ""
                    ),
                    f"role={operation.role.value}",
                    f"action={operation.action.value}",
                    f"execution_mode={authorization.request.execution_mode.value}",
                )
            )
        )


@authorizations_app.command("show")
def show_authorization(
    authorization_id: str = typer.Argument(..., help="Persisted authorization id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Show one persisted authorization."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    authorization = asyncio.run(
        runtime.authorization_service.get_authorization(
            AuthorizationId(authorization_id)
        )
    )
    operation = authorization.request.operation
    typer.echo(f"authorization_id={authorization.id}")
    typer.echo(f"task_id={authorization.task_id}")
    typer.echo(f"status={authorization.status.value if authorization.status is not None else ''}")
    typer.echo(f"role={operation.role.value}")
    typer.echo(f"action={operation.action.value}")
    typer.echo(
        "model_id=" + (str(operation.model_id) if operation.model_id is not None else "")
    )
    typer.echo("context_scope=" + ",".join(operation.context_scope))
    typer.echo(
        "proposed_state="
        + (operation.proposed_state.value if operation.proposed_state is not None else "")
    )
    typer.echo(f"reason={authorization.request.reason}")
    typer.echo(f"requester={authorization.request.requester}")
    typer.echo(f"execution_mode={authorization.request.execution_mode.value}")
    typer.echo(f"created_at={authorization.request.created_at.isoformat()}")
    typer.echo(
        "expires_at="
        + (
            authorization.request.expires_at.isoformat()
            if authorization.request.expires_at is not None
            else ""
        )
    )
    if authorization.current_decision is not None:
        typer.echo(f"current_decision_status={authorization.current_decision.status.value}")
        typer.echo(f"current_decision_by={authorization.current_decision.decided_by}")
        typer.echo(f"current_decision_reason={authorization.current_decision.reason}")
        typer.echo(
            f"current_decision_at={authorization.current_decision.decided_at.isoformat()}"
        )
    typer.echo(f"decisions={len(authorization.decisions)}")


@authorizations_app.command("request")
def request_authorization(
    task_id: str = typer.Argument(..., help="Persisted task id."),
    role: RoleName = typer.Option(..., "--role", case_sensitive=False, help="Requested role."),
    action: ActionName = typer.Option(..., "--action", case_sensitive=False, help="Requested action."),
    reason: str = typer.Option(..., "--reason", help="Why the authorization is being requested."),
    requester: str = typer.Option(..., "--requester", help="Actor requesting the authorization."),
    execution_mode: ExecutionMode = typer.Option(
        ...,
        "--execution-mode",
        case_sensitive=False,
        help="Execution mode associated with the request.",
    ),
    model_id: str | None = typer.Option(
        None,
        "--model-id",
        help="Optional provider-independent model id.",
    ),
    context_scope: str = typer.Option(
        "",
        "--context-scope",
        help="Comma-separated requested context resources.",
    ),
    proposed_state: TaskState | None = typer.Option(
        None,
        "--proposed-state",
        case_sensitive=False,
        help="Optional proposed task state.",
    ),
    expires_at: str | None = typer.Option(
        None,
        "--expires-at",
        help="Optional ISO-8601 expiration timestamp.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Request one explicit authorization."""

    require_cli_permission("authorizations:decide")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    authorization = asyncio.run(
        runtime.authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=TaskId(task_id),
                role=role,
                action=action,
                reason=reason,
                requester=requester,
                execution_mode=execution_mode,
                model_id=ModelId(model_id) if model_id else None,
                context_scope=_parse_csv_tuple(context_scope) or (),
                proposed_state=proposed_state,
                expires_at=datetime.fromisoformat(expires_at) if expires_at else None,
            )
        )
    )
    typer.echo(f"authorization_id={authorization.id}")
    typer.echo(f"task_id={authorization.task_id}")
    typer.echo("status=" + (authorization.status.value if authorization.status is not None else ""))
    typer.echo(f"role={authorization.request.operation.role.value}")
    typer.echo(f"action={authorization.request.operation.action.value}")
    typer.echo(f"execution_mode={authorization.request.execution_mode.value}")


@authorizations_app.command("decide")
def decide_authorization(
    authorization_id: str = typer.Argument(..., help="Persisted authorization id."),
    status: AuthorizationDecisionStatus = typer.Option(
        ...,
        "--status",
        case_sensitive=False,
        help="Decision status to record.",
    ),
    decided_by: str = typer.Option(..., "--decided-by", help="Actor deciding the request."),
    reason: str = typer.Option(..., "--reason", help="Reason for the decision."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Record one explicit authorization decision."""

    require_cli_permission("authorizations:decide")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    authorization = asyncio.run(
        runtime.authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=AuthorizationId(authorization_id),
                status=status,
                decided_by=decided_by,
                reason=reason,
            )
        )
    )
    typer.echo(f"authorization_id={authorization.id}")
    typer.echo(f"task_id={authorization.task_id}")
    typer.echo("status=" + (authorization.status.value if authorization.status is not None else ""))
    typer.echo(f"current_decision_status={authorization.current_decision.status.value}")
    typer.echo(f"current_decision_by={authorization.current_decision.decided_by}")
    typer.echo(f"current_decision_reason={authorization.current_decision.reason}")


@executions_app.command("list")
def list_executions(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter executions by task id.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Filter executions by project id.",
    ),
    state: ExecutionState | None = typer.Option(
        None,
        "--state",
        case_sensitive=False,
        help="Filter executions by execution state.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List persisted executions."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    executions = asyncio.run(
        runtime.execution_service.list_executions(
            task_id=TaskId(task_id) if task_id is not None else None,
            project_id=ProjectId(project_id) if project_id is not None else None,
            state=state,
            limit=limit,
        )
    )
    typer.echo(f"executions={len(executions)}")
    for execution in executions:
        typer.echo(
            " ".join(
                (
                    f"execution_id={execution.id}",
                    f"task_id={execution.task_id}",
                    f"project_id={execution.project_id or ''}",
                    f"state={execution.state.value}",
                    "available_transitions="
                    + ",".join(_execution_available_transitions(execution.state)),
                    f"role={execution.role.value}",
                    f"action={execution.action.value}",
                    f"model_id={execution.model_id}",
                )
            )
        )


@executions_app.command("show")
def show_execution(
    execution_id: str = typer.Argument(..., help="Persisted execution id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Show one persisted execution."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    execution = asyncio.run(
        runtime.execution_service.get_execution(ExecutionId(execution_id))
    )
    typer.echo(f"execution_id={execution.id}")
    typer.echo(f"task_id={execution.task_id}")
    typer.echo(f"project_id={execution.project_id or ''}")
    typer.echo(f"authorization_id={execution.authorization_id}")
    typer.echo(f"state={execution.state.value}")
    typer.echo(
        "available_transitions="
        + ",".join(_execution_available_transitions(execution.state))
    )
    typer.echo(f"role={execution.role.value}")
    typer.echo(f"action={execution.action.value}")
    typer.echo(f"model_id={execution.model_id}")
    typer.echo("requested_context=" + ",".join(execution.requested_context))
    typer.echo("authorized_context=" + ",".join(execution.authorized_context))
    typer.echo(f"created_at={execution.created_at.isoformat()}")
    typer.echo(
        "started_at="
        + (execution.started_at.isoformat() if execution.started_at is not None else "")
    )
    typer.echo(
        "completed_at="
        + (
            execution.completed_at.isoformat()
            if execution.completed_at is not None
            else ""
        )
    )
    if execution.result is not None:
        typer.echo(f"result_success={str(execution.result.success).lower()}")
        typer.echo("result_errors=" + ",".join(execution.result.errors))
        typer.echo("result_warnings=" + ",".join(execution.result.warnings))
        typer.echo(
            "result_total_tokens="
            + str(execution.result.resource_usage.total_tokens or "")
        )


@executions_app.command("request")
def request_execution(
    task_id: str = typer.Option(..., "--task-id", help="Persisted task id."),
    role: RoleName = typer.Option(..., "--role", case_sensitive=False, help="Execution role."),
    action: ActionName = typer.Option(..., "--action", case_sensitive=False, help="Execution action."),
    model_id: str = typer.Option(..., "--model-id", help="Provider-independent model id."),
    authorization_id: str = typer.Option(
        ...,
        "--authorization-id",
        help="Granted authorization id used to construct the execution.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Optional persisted project id.",
    ),
    requested_context: str = typer.Option(
        "",
        "--requested-context",
        help="Comma-separated requested context resources.",
    ),
    authorized_context: str = typer.Option(
        "",
        "--authorized-context",
        help="Comma-separated authorized context resources.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Request one execution directly through the execution service."""

    require_cli_permission("executions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    execution = asyncio.run(
        runtime.execution_service.request_execution(
            RequestExecutionCommand(
                task_id=TaskId(task_id),
                role=role,
                action=action,
                model_id=ModelId(model_id),
                authorization_id=AuthorizationId(authorization_id),
                project_id=ProjectId(project_id) if project_id else None,
                requested_context=_parse_csv_tuple(requested_context) or (),
                authorized_context=_parse_csv_tuple(authorized_context) or (),
            )
        )
    )
    typer.echo(f"execution_id={execution.id}")
    typer.echo(f"task_id={execution.task_id}")
    typer.echo(f"state={execution.state.value}")
    typer.echo(
        "available_transitions="
        + ",".join(_execution_available_transitions(execution.state))
    )
    typer.echo(f"authorization_id={execution.authorization_id}")


@executions_app.command("transition")
def transition_execution(
    execution_id: str = typer.Argument(..., help="Persisted execution id."),
    target_state: ExecutionState = typer.Option(
        ...,
        "--target-state",
        case_sensitive=False,
        help="Target execution state.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Transition one execution directly through the execution service."""

    require_cli_permission("executions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    execution = asyncio.run(
        runtime.execution_service.transition_execution(
            TransitionExecutionCommand(
                execution_id=ExecutionId(execution_id),
                target_state=target_state,
            )
        )
    )
    typer.echo(f"execution_id={execution.id}")
    typer.echo(f"state={execution.state.value}")
    typer.echo(
        "available_transitions="
        + ",".join(_execution_available_transitions(execution.state))
    )


@executions_app.command("cancel")
def cancel_execution(
    execution_id: str = typer.Argument(..., help="Persisted execution id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Cancel one execution -- a no-op if it has already finished on its own."""

    require_cli_permission("executions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    execution = asyncio.run(runtime.execution_engine.cancel(ExecutionId(execution_id)))
    typer.echo(f"execution_id={execution.id}")
    typer.echo(f"state={execution.state.value}")


@executions_app.command("complete")
def complete_execution(
    execution_id: str = typer.Argument(..., help="Persisted execution id."),
    output: str = typer.Option(..., "--output", help="Execution output payload."),
    success: bool = typer.Option(
        True,
        "--success/--failure",
        help="Whether the execution completed successfully.",
    ),
    errors: str = typer.Option(
        "",
        "--errors",
        help="Comma-separated execution errors.",
    ),
    warnings: str = typer.Option(
        "",
        "--warnings",
        help="Comma-separated execution warnings.",
    ),
    input_tokens: int | None = typer.Option(
        None,
        "--input-tokens",
        help="Optional provider input token count.",
    ),
    output_tokens: int | None = typer.Option(
        None,
        "--output-tokens",
        help="Optional provider output token count.",
    ),
    estimated_cost: float | None = typer.Option(
        None,
        "--estimated-cost",
        help="Optional provider estimated cost.",
    ),
    resource_metadata: str | None = typer.Option(
        None,
        "--resource-metadata",
        help="Optional resource-usage metadata as a JSON object string.",
    ),
    metadata: str | None = typer.Option(
        None,
        "--metadata",
        help="Optional execution-result metadata as a JSON object string.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Complete one execution directly through the execution service."""

    require_cli_permission("executions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    execution = asyncio.run(
        runtime.execution_service.complete_execution(
            CompleteExecutionCommand(
                execution_id=ExecutionId(execution_id),
                output=output,
                success=success,
                errors=_parse_csv_tuple(errors) or (),
                warnings=_parse_csv_tuple(warnings) or (),
                resource_usage=ResourceUsage(
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    metadata=_parse_metadata_json(resource_metadata),
                ),
                metadata=_parse_metadata_json(metadata),
            )
        )
    )
    typer.echo(f"execution_id={execution.id}")
    typer.echo(f"state={execution.state.value}")
    typer.echo(f"result_success={str(execution.result.success).lower()}")


@executions_app.command("run")
def run_execution(
    execution_id: str = typer.Argument(..., help="Persisted execution id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Run one authorized execution through the execution engine."""

    require_cli_permission("executions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    asyncio.run(
        _ensure_project_adapter_registered_for_execution_cli(
            runtime=runtime,
            execution_id=ExecutionId(execution_id),
        )
    )
    execution = asyncio.run(runtime.execution_engine.run(ExecutionId(execution_id)))
    typer.echo(f"execution_id={execution.id}")
    typer.echo(f"state={execution.state.value}")
    if execution.result is not None:
        typer.echo(f"result_success={str(execution.result.success).lower()}")
        typer.echo("result_errors=" + ",".join(execution.result.errors))
        typer.echo("result_warnings=" + ",".join(execution.result.warnings))


@executions_app.command("dispatch")
def dispatch_execution(
    execution_id: str = typer.Argument(..., help="Persisted execution id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Dispatch one execution.

    The HTTP API is the primary async surface. In the one-shot CLI, this
    command falls back to immediate execution so the process can complete
    reliably.
    """

    require_cli_permission("executions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    asyncio.run(
        _ensure_project_adapter_registered_for_execution_cli(
            runtime=runtime,
            execution_id=ExecutionId(execution_id),
        )
    )
    execution = asyncio.run(runtime.execution_engine.run(ExecutionId(execution_id)))
    typer.echo(f"execution_id={execution.id}")
    typer.echo(f"state={execution.state.value}")
    typer.echo("dispatch_requested=true")
    typer.echo("dispatch_mode=synchronous_fallback")
    typer.echo("active_in_process=false")
    if execution.result is not None:
        typer.echo(f"result_success={str(execution.result.success).lower()}")


@executions_app.command("resolve-context")
def resolve_execution_context(
    execution_id: str = typer.Argument(..., help="Persisted execution id."),
    source: ContextSource = typer.Option(
        ContextSource.SOURCE_FILE,
        "--source",
        case_sensitive=False,
        help="Context source category for the authorized resources.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Resolve authorized context directly for one execution."""

    require_cli_permission("executions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    asyncio.run(
        _ensure_project_adapter_registered_for_execution_cli(
            runtime=runtime,
            execution_id=ExecutionId(execution_id),
        )
    )
    package = asyncio.run(
        runtime.context_service.resolve_execution_context(
            ResolveExecutionContextCommand(
                execution_id=ExecutionId(execution_id),
                source=source,
            )
        )
    )
    typer.echo(f"execution_id={package.execution_id}")
    typer.echo(f"project_id={package.project_id}")
    typer.echo(f"context_items={len(package.items)}")
    for item in package.items:
        typer.echo(
            " ".join(
                (
                    f"source={item.reference.source.value}",
                    f"resource={item.reference.resource}",
                    f"content_bytes={len(item.content.encode('utf-8'))}",
                )
            )
        )


@executions_app.command("context")
def execution_context(
    execution_id: str = typer.Argument(..., help="Persisted execution id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List resolved context metadata for one execution."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    records = asyncio.run(
        runtime.context_resolution_repository.list_by_execution(ExecutionId(execution_id))
    )
    typer.echo(f"context_records={len(records)}")
    for record in records:
        typer.echo(
            " ".join(
                (
                    f"context_resolution_id={record.id}",
                    f"execution_id={record.execution_id}",
                    f"project_id={record.project_id}",
                    f"source={record.reference.source.value}",
                    f"resource={record.reference.resource}",
                    f"scope={record.reference.scope or ''}",
                    f"version={record.reference.version or ''}",
                    "requires_authorization="
                    + str(record.reference.requires_authorization).lower(),
                    f"content_bytes={record.content_bytes}",
                )
            )
        )


@policies_app.command("evaluate")
def evaluate_policy(
    execution_mode: ExecutionMode = typer.Option(
        ...,
        "--execution-mode",
        case_sensitive=False,
        help="Execution mode to evaluate.",
    ),
    role: RoleName = typer.Option(
        ...,
        "--role",
        case_sensitive=False,
        help="Role to evaluate.",
    ),
    action: ActionName = typer.Option(
        ...,
        "--action",
        case_sensitive=False,
        help="Action to evaluate.",
    ),
    requested_model: str = typer.Option(..., "--requested-model", help="Requested model id."),
    effective_model: str = typer.Option(..., "--effective-model", help="Effective model id."),
    current_task_state: TaskState = typer.Option(
        ...,
        "--current-task-state",
        case_sensitive=False,
        help="Current task lifecycle state.",
    ),
    project_operation: ProjectOperation = typer.Option(
        ProjectOperation.READ_CONTEXT,
        "--project-operation",
        case_sensitive=False,
        help="Project operation to evaluate.",
    ),
    provider_target: ProviderTarget = typer.Option(
        ProviderTarget.LOCAL,
        "--provider-target",
        case_sensitive=False,
        help="Provider target to evaluate.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Optional persisted project id used to derive readiness and security.",
    ),
    project_root: Path | None = typer.Option(
        None,
        "--project-root",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Optional project root used to derive readiness and security.",
    ),
    project_readiness_level: ProjectReadinessLevel | None = typer.Option(
        None,
        "--project-readiness-level",
        case_sensitive=False,
        help="Fallback readiness level when no persisted project or root is provided.",
    ),
    requested_context: str = typer.Option(
        "",
        "--requested-context",
        help="Comma-separated requested context resources.",
    ),
    authorized_context: str = typer.Option(
        "",
        "--authorized-context",
        help="Comma-separated authorized context resources.",
    ),
    context_sharing_levels: str = typer.Option(
        "",
        "--context-sharing-levels",
        help="Comma-separated provider sharing levels.",
    ),
    approve_suggestion: bool = typer.Option(
        False,
        "--approve-suggestion/--no-approve-suggestion",
        help="Whether the suggestion is already explicitly approved.",
    ),
    explicit_user_command: bool = typer.Option(
        False,
        "--explicit-user-command/--no-explicit-user-command",
        help="Whether the operation came from a direct explicit user command.",
    ),
    previous_role: RoleName | None = typer.Option(
        None,
        "--previous-role",
        case_sensitive=False,
        help="Optional previous role for cross-role transition evaluation.",
    ),
    previous_action: ActionName | None = typer.Option(
        None,
        "--previous-action",
        case_sensitive=False,
        help="Optional previous action for transition evaluation.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Evaluate one policy decision without executing the operation."""

    require_cli_permission("policies:evaluate")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    readiness_level, security_profile = asyncio.run(
        _resolve_policy_project_context_cli(
            runtime=runtime,
            project_id=project_id,
            project_root=project_root,
            fallback_readiness_level=project_readiness_level,
        )
    )
    decision = asyncio.run(
        runtime.policy_service.evaluate(
            PolicyOperation(
                execution_mode=execution_mode,
                role=role,
                action=action,
                requested_model=requested_model,
                effective_model=effective_model,
                requested_context=_parse_csv_tuple(requested_context) or (),
                authorized_context=_parse_csv_tuple(authorized_context) or (),
                current_task_state=current_task_state,
                project_operation=project_operation,
                provider_target=provider_target,
                project_readiness_level=readiness_level,
                project_security_profile=security_profile,
                context_sharing_levels=tuple(
                    ProviderSharingLevel(value)
                    for value in (_parse_csv_tuple(context_sharing_levels) or ())
                ),
                approve_suggestion=approve_suggestion,
                explicit_user_command=explicit_user_command,
                previous_role=previous_role,
                previous_action=previous_action,
            )
        )
    )
    typer.echo(f"allowed={str(decision.allowed).lower()}")
    typer.echo(f"reason={decision.reason}")
    typer.echo(
        "requires_authorization="
        + str(decision.requires_authorization).lower()
    )
    typer.echo(f"project_readiness_level={readiness_level.value}")
    typer.echo(
        "allow_cloud_provider_sharing="
        + str(security_profile.allow_cloud_provider_sharing).lower()
    )


@automatic_policy_app.command("show")
def show_automatic_policy(
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Show the persisted automatic-mode execution policy."""

    require_cli_permission("policies:evaluate")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    policy = asyncio.run(runtime.automatic_policy_service.get_automatic_policy())
    _echo_automatic_policy(policy)


@automatic_policy_app.command("set")
def set_automatic_policy(
    allowed_operations: str = typer.Option(
        "",
        "--allow-operation",
        help="Comma-separated role:action pairs allowed to run automatically, e.g. DEVELOPER:IMPLEMENT,QUALITY_AGENT:TEST.",
    ),
    allowed_cross_role_transitions: str = typer.Option(
        "",
        "--allow-cross-role-transition",
        help="Comma-separated previous_role:next_role pairs allowed to transition automatically.",
    ),
    allow_model_substitution: bool = typer.Option(
        False,
        "--allow-model-substitution/--no-allow-model-substitution",
        help="Whether an automatic operation may substitute the requested model.",
    ),
    allow_context_expansion: bool = typer.Option(
        False,
        "--allow-context-expansion/--no-allow-context-expansion",
        help="Whether an automatic operation may expand its authorized context beyond what was requested.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Replace the persisted automatic-mode execution policy."""

    require_cli_permission("policies:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    policy = AutomaticExecutionPolicy(
        allowed_operations=tuple(
            _parse_role_action_pair(entry)
            for entry in _parse_csv_tuple(allowed_operations) or ()
        ),
        allowed_cross_role_transitions=tuple(
            _parse_role_role_pair(entry)
            for entry in _parse_csv_tuple(allowed_cross_role_transitions) or ()
        ),
        allow_model_substitution=allow_model_substitution,
        allow_context_expansion=allow_context_expansion,
    )
    updated = asyncio.run(runtime.automatic_policy_service.set_automatic_policy(policy))
    _echo_automatic_policy(updated)


@events_app.command("list")
def list_events(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter events by task id.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Filter events by project id.",
    ),
    execution_id: str | None = typer.Option(
        None,
        "--execution-id",
        help="Filter events by execution id.",
    ),
    event_type: EventType | None = typer.Option(
        None,
        "--event-type",
        case_sensitive=False,
        help="Filter events by event type.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List persisted domain events."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    events = asyncio.run(
        runtime.event_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            project_id=ProjectId(project_id) if project_id is not None else None,
            execution_id=ExecutionId(execution_id) if execution_id is not None else None,
            event_type=event_type,
            limit=limit,
        )
    )
    for event in events:
        typer.echo(
            " ".join(
                (
                    f"event_id={event.event_id}",
                    f"occurred_at={event.occurred_at.isoformat()}",
                    f"event_type={event.event_type.value}",
                    f"source={event.source}",
                    f"task_id={event.task_id or ''}",
                    f"project_id={event.project_id or ''}",
                    f"execution_id={event.execution_id or ''}",
                )
            )
        )


@metrics_app.command("list")
def list_metrics(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter metrics by task id.",
    ),
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Filter metrics by project id.",
    ),
    execution_id: str | None = typer.Option(
        None,
        "--execution-id",
        help="Filter metrics by execution id.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="Filter metrics by metric name.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List persisted operational metrics."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    records = asyncio.run(
        runtime.metrics_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            project_id=ProjectId(project_id) if project_id is not None else None,
            execution_id=ExecutionId(execution_id) if execution_id is not None else None,
            name=name,
            limit=limit,
        )
    )
    for record in records:
        typer.echo(
            " ".join(
                (
                    f"metric_id={record.id}",
                    f"observed_at={record.observed_at.isoformat()}",
                    f"name={record.name}",
                    f"value={record.value}",
                    f"unit={record.unit}",
                    f"task_id={record.task_id or ''}",
                    f"project_id={record.project_id or ''}",
                    f"execution_id={record.execution_id or ''}",
                )
            )
        )


@metrics_app.command("summary")
def summarize_metrics(
    project_id: str | None = typer.Option(
        None,
        "--project-id",
        help="Filter metrics by project id.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="Filter metrics by metric name.",
    ),
    since: datetime | None = typer.Option(
        None,
        "--since",
        help="Only include metrics observed at or after this timestamp.",
    ),
    until: datetime | None = typer.Option(
        None,
        "--until",
        help="Only include metrics observed at or before this timestamp.",
    ),
    group_by: str = typer.Option(
        "",
        "--group-by",
        help="Comma-separated dimensions to group by: project_id, role, action, model_id, outcome.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Aggregate (count/sum/avg) metrics, one line per (name, group) bucket."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    try:
        summaries = asyncio.run(
            runtime.metrics_repository.summarize(
                project_id=ProjectId(project_id) if project_id is not None else None,
                name=name,
                since=since,
                until=until,
                group_by=_parse_csv_tuple(group_by) or (),
            )
        )
    except ValueError as exc:
        typer.echo(f"error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for summary in summaries:
        dimensions = ",".join(f"{key}={value}" for key, value in summary.dimensions.items())
        typer.echo(
            " ".join(
                (
                    f"name={summary.name}",
                    f"unit={summary.unit}",
                    f"count={summary.count}",
                    f"sum={summary.sum}",
                    f"avg={summary.avg}",
                    f"dimensions={dimensions}",
                )
            )
        )


@suggestions_app.command("list")
def list_suggestions(
    task_id: str | None = typer.Option(
        None,
        "--task-id",
        help="Filter suggestions by task id.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List persisted suggestions."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    suggestions = asyncio.run(
        runtime.suggestion_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            limit=limit,
        )
    )
    for suggestion in suggestions:
        typer.echo(
            " ".join(
                (
                    f"suggestion_id={suggestion.id}",
                    f"generated_at={suggestion.generated_at.isoformat()}",
                    f"status={suggestion.status.value}",
                    f"role={suggestion.suggested_role.value}",
                    f"action={suggestion.suggested_action.value}",
                    f"confidence={suggestion.confidence or ''}",
                    f"task_id={suggestion.task_id}",
                )
            )
        )


def _echo_suggestion(suggestion) -> None:
    typer.echo(f"suggestion_id={suggestion.id}")
    typer.echo(f"task_id={suggestion.task_id}")
    typer.echo(f"status={suggestion.status.value}")
    typer.echo(f"role={suggestion.suggested_role.value}")
    typer.echo(f"action={suggestion.suggested_action.value}")
    typer.echo(f"rationale={suggestion.rationale}")
    typer.echo(f"expected_impact={suggestion.expected_impact}")
    typer.echo(f"authorization_required={str(suggestion.authorization_required).lower()}")
    typer.echo(f"confidence={suggestion.confidence or ''}")
    typer.echo(f"generated_at={suggestion.generated_at.isoformat()}")
    typer.echo(
        "required_capabilities="
        + ",".join(sorted(c.value for c in suggestion.required_capabilities))
    )


@suggestions_app.command("show")
def show_suggestion(
    suggestion_id: str = typer.Argument(..., help="Persisted suggestion id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Show one persisted suggestion."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    suggestion = asyncio.run(runtime.suggestion_repository.get(SuggestionId(suggestion_id)))
    _echo_suggestion(suggestion)


@suggestions_app.command("generate")
def generate_suggestion(
    task_id: str = typer.Argument(..., help="Task id to generate a suggestion for."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Generate a next-step suggestion for a task's current state, on demand."""

    require_cli_permission("suggestions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)

    async def _generate():
        task = await runtime.task_service.get_task(TaskId(task_id))
        return await runtime.suggestion_engine.suggest_next(task)

    suggestion = asyncio.run(_generate())
    if suggestion is None:
        typer.echo(f"task_id={task_id}")
        typer.echo("suggestion=none")
        typer.echo("reason=no_suggestion_for_current_task_state")
        return
    _echo_suggestion(suggestion)


@suggestions_app.command("accept")
def accept_suggestion(
    suggestion_id: str = typer.Argument(..., help="Persisted suggestion id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Mark a suggestion as accepted. Does not itself authorize or execute anything."""

    require_cli_permission("suggestions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)

    async def _accept():
        suggestion = await runtime.suggestion_repository.get(SuggestionId(suggestion_id))
        return await runtime.suggestion_engine.mark_status(
            suggestion, SuggestionStatus.ACCEPTED
        )

    _echo_suggestion(asyncio.run(_accept()))


@suggestions_app.command("reject")
def reject_suggestion(
    suggestion_id: str = typer.Argument(..., help="Persisted suggestion id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Mark a suggestion as rejected."""

    require_cli_permission("suggestions:manage")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)

    async def _reject():
        suggestion = await runtime.suggestion_repository.get(SuggestionId(suggestion_id))
        return await runtime.suggestion_engine.mark_status(
            suggestion, SuggestionStatus.REJECTED
        )

    _echo_suggestion(asyncio.run(_reject()))


@projects_app.command("discover")
def discover_project(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the filesystem adapter.",
    ),
    limit: int = typer.Option(20, "--limit", min=1, max=100),
) -> None:
    """Discover project resources through a Project Adapter."""

    require_cli_permission()
    adapter = LocalFilesystemProjectAdapter(project_root)
    discovery = asyncio.run(adapter.discover(limit=limit))
    typer.echo(f"adapter_type={discovery.metadata.get('adapter_type', '')}")
    typer.echo(f"resources={len(discovery.resources)}")
    for resource in discovery.resources:
        typer.echo(
            " ".join(
                (
                    f"resource={resource.resource}",
                    f"source={resource.source.value}",
                    f"provider_sharing={resource.provider_sharing_level.value}",
                    f"persistence={resource.persistence_classification.value}",
                    f"restricted={str(resource.restricted).lower()}",
                    "capabilities="
                    + ",".join(
                        capability.value for capability in resource.capabilities
                    ),
                )
            )
        )


@projects_app.command("register")
def register_project(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root to persist as a connected project.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="Override the persisted project name. Defaults to the directory name.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Register one project explicitly in persistent storage."""

    require_cli_permission("projects:connect")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    adapter = LocalFilesystemProjectAdapter(project_root)
    readiness = asyncio.run(adapter.assess_readiness())
    capabilities = asyncio.run(adapter.capabilities())
    project = asyncio.run(
        runtime.project_service.register_project(
            RegisterProjectCommand(
                name=name or project_root.resolve().name,
                root_location=str(project_root.resolve()),
                adapter_type="local_filesystem",
                capabilities=capabilities,
                readiness_level=readiness.readiness_level,
                security_profile=readiness.security_profile,
                observed_readiness_level=readiness.readiness_level,
                observed_security_profile=readiness.security_profile,
            )
        )
    )
    typer.echo(f"project_id={project.id}")
    typer.echo(f"name={project.name}")
    typer.echo(f"root_location={project.root_location}")
    typer.echo(f"effective_readiness_level={project.readiness_level.value}")
    typer.echo(f"observed_readiness_level={project.observed_readiness_level.value}")
    typer.echo(
        "allow_cloud_provider_sharing="
        + str(project.security_profile.allow_cloud_provider_sharing).lower()
    )


@projects_app.command("readiness")
def project_readiness(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the filesystem adapter.",
    ),
) -> None:
    """Assess project readiness through a Project Adapter."""

    require_cli_permission()
    adapter = LocalFilesystemProjectAdapter(project_root)
    readiness = asyncio.run(adapter.assess_readiness())
    typer.echo(f"readiness_level={readiness.readiness_level.value}")
    typer.echo(f"has_git={str(readiness.has_git).lower()}")
    typer.echo(f"has_documentation={str(readiness.has_documentation).lower()}")
    typer.echo(f"has_tests={str(readiness.has_tests).lower()}")
    typer.echo("reasons=" + ",".join(readiness.reasons))


@projects_app.command("security")
def project_security(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the filesystem adapter.",
    ),
) -> None:
    """Inspect the derived project security profile."""

    require_cli_permission()
    adapter = LocalFilesystemProjectAdapter(project_root)
    readiness = asyncio.run(adapter.assess_readiness())
    profile = readiness.security_profile
    typer.echo(f"readiness_level={profile.readiness_level.value}")
    typer.echo(
        "allow_cloud_provider_sharing="
        + str(profile.allow_cloud_provider_sharing).lower()
    )
    typer.echo("access_scope=" + ",".join(profile.access_scope))
    typer.echo("restricted_areas=" + ",".join(profile.restricted_areas))


@projects_app.command("operate")
def operate_project(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root handled through the filesystem adapter.",
    ),
    operation: ProjectOperation = typer.Argument(
        ...,
        case_sensitive=False,
        help="Protected project operation to run.",
    ),
    title: str = typer.Option("Protected project operation", help="Task title."),
    model: str | None = typer.Option(
        None,
        "--model",
        help="Provider-independent model id. Defaults to configured provider model.",
    ),
    resource: str = typer.Option(
        "",
        "--resource",
        help="Relative project resource for read/write operations.",
    ),
    content: str = typer.Option(
        "",
        "--content",
        help="Content used by write operations.",
    ),
    command: str = typer.Option(
        "",
        "--command",
        help="Space-separated bounded command for RUN_COMMAND/RUN_VALIDATION.",
    ),
    test_args: str = typer.Option(
        "",
        "--test-args",
        help="Space-separated pytest args for RUN_TESTS.",
    ),
    approve_operation: bool = typer.Option(
        False,
        "--approve-operation/--no-approve-operation",
        help="Explicitly approve this operation in SUGGESTED mode.",
    ),
    execution_mode: ExecutionMode = typer.Option(
        ExecutionMode.SUGGESTED,
        "--execution-mode",
        case_sensitive=False,
        help="Execution mode enforced by the Orchestrator.",
    ),
    provider_target: ProviderTarget = typer.Option(
        ProviderTarget.LOCAL,
        "--provider-target",
        case_sensitive=False,
        help="Treat the protected operation as local or cloud for policy enforcement.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Run a protected project operation through orchestration."""

    require_cli_permission("projects:connect")
    _validate_project_operation_input(
        operation=operation,
        resource=resource,
        content=content,
        command=command,
    )
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    effective_settings = settings.model_copy(
        update={
            "database": settings.database.model_copy(update={"url": url}),
        }
    )
    result = asyncio.run(
        run_project_operation(
            project_root=project_root,
            operation=operation,
            title=title,
            resource=resource,
            content=content,
            command=_split_words(command),
            test_args=_split_words(test_args),
            model=model or effective_settings.ai_provider.model or "local-project-operation",
            provider_target=provider_target,
            approve_operation=approve_operation,
            execution_mode=execution_mode,
            dependencies=build_local_flow_dependencies_from_settings(effective_settings),
            storage_label=_safe_database_label(url),
        )
    )
    typer.echo(f"project_id={result['project_id']}")
    typer.echo(f"task_id={result['task_id']}")
    typer.echo(f"authorization_id={result['authorization_id']}")
    typer.echo(f"task_state={result['task_state']}")
    typer.echo(f"project_operation={result['project_operation']}")
    typer.echo(f"resource={result['resource']}")
    typer.echo(f"exit_code={result['exit_code']}")
    typer.echo(f"suggestion_id={result['suggestion_id']}")
    typer.echo(f"suggested_role={result['suggested_role']}")
    typer.echo(f"suggested_action={result['suggested_action']}")
    typer.echo(f"suggestion_status={result['suggestion_status']}")
    typer.echo(f"blocked_reason={result['blocked_reason']}")
    typer.echo(f"events={result['events']}")
    typer.echo(f"audit_records={result['audit_records']}")
    typer.echo(f"database={result['database']}")
    if result["output"]:
        typer.echo("output=" + result["output"].replace("\n", "\\n"))


@projects_app.command("list")
def list_projects(
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List persisted project configurations."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    projects = asyncio.run(runtime.project_service.list_projects())
    typer.echo(f"projects={len(projects)}")
    for project in projects:
        typer.echo(
            " ".join(
                (
                    f"project_id={project.id}",
                    f"name={project.name}",
                    f"effective_readiness_level={project.readiness_level.value}",
                    "observed_readiness_level="
                    + project.observed_readiness_level.value,
                    "allow_cloud_provider_sharing="
                    + str(
                        project.security_profile.allow_cloud_provider_sharing
                    ).lower(),
                    "persist_context_snapshots="
                    + str(
                        project.security_profile.persist_context_snapshots
                    ).lower(),
                )
            )
        )


@projects_app.command("list-all")
def list_all_projects(
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """List every project in the system with full admin details (admin-only).

    Unlike `projects list` (which only requires `projects:read`), this
    also surfaces `capabilities` and `connected_user_ids` -- the
    admin-facing project directory (`docs/TO-DO.md` user-config CRUD
    layer) -- and requires `admin:manage_projects`.
    """

    require_cli_permission("admin:manage_projects")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    projects = asyncio.run(runtime.project_service.list_projects())
    connection_repository = SQLAlchemyProjectConnectionRepository(runtime.database)
    typer.echo(f"projects={len(projects)}")
    for project in projects:
        connected = asyncio.run(
            connection_repository.list_user_ids_for_project(project.id)
        )
        typer.echo(
            " ".join(
                (
                    f"project_id={project.id}",
                    f"name={project.name}",
                    f"effective_readiness_level={project.readiness_level.value}",
                    "observed_readiness_level="
                    + project.observed_readiness_level.value,
                    "capabilities="
                    + ",".join(
                        capability.value for capability in project.capabilities
                    ),
                    "connected_user_ids="
                    + ",".join(str(user_id) for user_id in connected),
                )
            )
        )


@projects_app.command("lookup")
def lookup_project(
    project_root: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="External project root to match against persisted projects.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Look up one persisted project by root location."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    project = asyncio.run(
        runtime.project_service.get_project_by_root_location(str(project_root.resolve()))
    )
    typer.echo("found=" + str(project is not None).lower())
    if project is None:
        return
    typer.echo(f"project_id={project.id}")
    typer.echo(f"name={project.name}")
    typer.echo(f"root_location={project.root_location}")
    typer.echo(f"effective_readiness_level={project.readiness_level.value}")
    typer.echo(f"observed_readiness_level={project.observed_readiness_level.value}")


@projects_app.command("show")
def show_project(
    project_id: str = typer.Argument(..., help="Persisted project id."),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Show one persisted project configuration."""

    require_cli_permission("projects:read")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    project = asyncio.run(runtime.project_service.get_project(ProjectId(project_id)))
    profile = project.security_profile
    typer.echo(f"project_id={project.id}")
    typer.echo(f"name={project.name}")
    typer.echo(f"root_location={project.root_location}")
    typer.echo(f"adapter_type={project.adapter_type}")
    typer.echo(f"effective_readiness_level={project.readiness_level.value}")
    typer.echo(f"observed_readiness_level={project.observed_readiness_level.value}")
    typer.echo("access_scope=" + ",".join(profile.access_scope))
    typer.echo("restricted_areas=" + ",".join(profile.restricted_areas))
    typer.echo("sensitive_patterns=" + ",".join(profile.sensitive_patterns))
    typer.echo("allow_git_bootstrap=" + str(profile.allow_git_bootstrap).lower())
    typer.echo(
        "allow_architecture_restructure="
        + str(profile.allow_architecture_restructure).lower()
    )
    typer.echo("allow_cicd_changes=" + str(profile.allow_cicd_changes).lower())
    typer.echo(
        "allow_cloud_provider_sharing="
        + str(profile.allow_cloud_provider_sharing).lower()
    )
    typer.echo(
        "persist_architecture_summaries="
        + str(profile.persist_architecture_summaries).lower()
    )
    typer.echo(
        "persist_naming_summaries=" + str(profile.persist_naming_summaries).lower()
    )
    typer.echo(
        "persist_functional_summaries="
        + str(profile.persist_functional_summaries).lower()
    )
    typer.echo(
        "persist_context_snapshots="
        + str(profile.persist_context_snapshots).lower()
    )
    typer.echo(
        "observed_access_scope="
        + ",".join(project.observed_security_profile.access_scope)
    )


@projects_app.command("update-security")
def update_project_security(
    project_id: str = typer.Argument(..., help="Persisted project id."),
    readiness_level: ProjectReadinessLevel | None = typer.Option(
        None,
        "--readiness-level",
        case_sensitive=False,
        help="Override the persisted readiness level for the project.",
    ),
    access_scope: str | None = typer.Option(
        None,
        "--access-scope",
        help="Comma-separated access scope values.",
    ),
    restricted_areas: str | None = typer.Option(
        None,
        "--restricted-areas",
        help="Comma-separated restricted area names.",
    ),
    sensitive_patterns: str | None = typer.Option(
        None,
        "--sensitive-patterns",
        help="Comma-separated sensitive path/name patterns.",
    ),
    allow_git_bootstrap: str | None = typer.Option(
        None,
        "--allow-git-bootstrap",
        help="Allow OrchAI to initialize or fix Git when explicitly requested.",
    ),
    allow_architecture_restructure: str | None = typer.Option(
        None,
        "--allow-architecture-restructure",
        help="Allow architecture/base-structure changes when explicitly requested.",
    ),
    allow_cicd_changes: str | None = typer.Option(
        None,
        "--allow-cicd-changes",
        help="Allow CI/CD changes when explicitly requested.",
    ),
    allow_cloud_provider_sharing: str | None = typer.Option(
        None,
        "--allow-cloud-provider-sharing",
        help="Allow authorized context to cross a cloud provider boundary.",
    ),
    persist_architecture_summaries: str | None = typer.Option(
        None,
        "--persist-architecture-summaries",
        help="Allow persistence of architecture summaries.",
    ),
    persist_naming_summaries: str | None = typer.Option(
        None,
        "--persist-naming-summaries",
        help="Allow persistence of naming summaries.",
    ),
    persist_functional_summaries: str | None = typer.Option(
        None,
        "--persist-functional-summaries",
        help="Allow persistence of functional summaries.",
    ),
    persist_context_snapshots: str | None = typer.Option(
        None,
        "--persist-context-snapshots",
        help="Allow persistence of bounded context snapshots.",
    ),
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Update one persisted project security/readiness profile."""

    require_cli_permission("projects:connect")
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    runtime = build_sqlalchemy_runtime(url)
    project = asyncio.run(
        runtime.project_service.update_security_profile(
            UpdateProjectSecurityCommand(
                project_id=ProjectId(project_id),
                readiness_level=readiness_level,
                access_scope=_parse_csv_tuple(access_scope),
                restricted_areas=_parse_csv_tuple(restricted_areas),
                sensitive_patterns=_parse_csv_tuple(sensitive_patterns),
                allow_git_bootstrap=_parse_optional_bool(allow_git_bootstrap),
                allow_architecture_restructure=_parse_optional_bool(
                    allow_architecture_restructure
                ),
                allow_cicd_changes=_parse_optional_bool(allow_cicd_changes),
                allow_cloud_provider_sharing=_parse_optional_bool(
                    allow_cloud_provider_sharing
                ),
                persist_architecture_summaries=_parse_optional_bool(
                    persist_architecture_summaries
                ),
                persist_naming_summaries=_parse_optional_bool(
                    persist_naming_summaries
                ),
                persist_functional_summaries=_parse_optional_bool(
                    persist_functional_summaries
                ),
                persist_context_snapshots=_parse_optional_bool(
                    persist_context_snapshots
                ),
            )
        )
    )
    typer.echo(f"project_id={project.id}")
    typer.echo(f"effective_readiness_level={project.readiness_level.value}")
    typer.echo(f"observed_readiness_level={project.observed_readiness_level.value}")
    typer.echo(
        "allow_cloud_provider_sharing="
        + str(project.security_profile.allow_cloud_provider_sharing).lower()
    )
    typer.echo(
        "persist_context_snapshots="
        + str(project.security_profile.persist_context_snapshots).lower()
    )
    typer.echo("updated=true")


@modules_app.command("list")
def list_modules_command() -> None:
    """List registered Modules (Forge, Studio, ...) — ADR-015."""

    require_cli_permission()
    modules = list_modules()
    typer.echo(f"modules={len(modules)}")
    for module in modules:
        typer.echo(
            " ".join(
                (
                    f"module_id={module.id}",
                    f"name={module.name}",
                    f"requires_project={str(module.requires_project).lower()}",
                    f"project_adapter_kind={module.project_adapter_kind}",
                    f"task_pipeline_mode={module.task_pipeline_mode}",
                )
            )
        )


@providers_app.command("show")
def show_provider() -> None:
    """Show effective AI provider settings without exposing secrets."""

    require_cli_permission()
    settings = load_settings()
    typer.echo(f"provider={settings.ai_provider.provider}")
    typer.echo(f"model={settings.ai_provider.model}")
    typer.echo(f"base_url={settings.ai_provider.base_url or ''}")
    typer.echo(f"timeout_seconds={settings.ai_provider.timeout_seconds}")
    typer.echo(
        "api_key_configured="
        + str(settings.ai_provider.api_key is not None).lower()
    )
    typer.echo(f"organization={settings.ai_provider.organization or ''}")
    typer.echo(f"project={settings.ai_provider.project or ''}")


@providers_app.command("capabilities")
def provider_capabilities() -> None:
    """Show capabilities declared by the configured AI provider."""

    require_cli_permission()
    settings = load_settings()
    provider = provider_from_settings(settings)
    capabilities = asyncio.run(provider.capabilities())
    typer.echo(f"provider={settings.ai_provider.provider}")
    typer.echo(f"capabilities={','.join(sorted(capabilities))}")


@providers_app.command("health")
def provider_health() -> None:
    """Show operational health for the configured AI provider."""

    require_cli_permission()
    settings = load_settings()
    provider = provider_from_settings(settings)
    health = asyncio.run(provider.healthcheck())
    typer.echo(f"provider={health.provider_name}")
    typer.echo(f"reachable={str(health.reachable).lower()}")
    typer.echo(f"configured_model={settings.ai_provider.model}")
    typer.echo(f"message={health.message}")


@runtime_app.command("check")
def runtime_check(
    database_url: str | None = typer.Option(
        None,
        "--database-url",
        help="Database URL. Defaults to ORCHAI_DATABASE_URL, or PostgreSQL (postgresql://orchai:orchai@localhost:5432/orchai) when unset. Pass sqlite:///... or the 'sqlite' shorthand for fast local/test runs.",
    ),
) -> None:
    """Show a consolidated operational check for database and provider."""

    require_cli_permission()
    settings = load_settings()
    url = database_url or settings.database.sqlalchemy_url
    effective_settings = settings.model_copy(
        update={
            "database": settings.database.model_copy(update={"url": url}),
        }
    )
    runtime = build_sqlalchemy_runtime(effective_settings.database.sqlalchemy_url)
    provider = provider_from_settings(effective_settings)
    status = asyncio.run(
        collect_runtime_status(
            settings=effective_settings,
            provider=provider,
            database=runtime.database or SQLAlchemyDatabase(url),
        )
    )
    typer.echo(f"ready={str(status['ready']).lower()}")
    typer.echo(f"operational_mode={status['operational_mode']}")
    typer.echo(f"recommended_operational_dialect={status['recommended_operational_dialect']}")
    typer.echo(f"database={status['database']['url']}")
    typer.echo(f"database_reachable={str(status['database']['reachable']).lower()}")
    typer.echo(f"database_message={status['database']['message']}")
    typer.echo(f"provider={status['provider']['provider']}")
    typer.echo(f"provider_reachable={str(status['provider']['reachable']).lower()}")
    typer.echo(f"provider_message={status['provider']['message']}")
    typer.echo(f"configured_model={status['provider']['configured_model'] or ''}")
    typer.echo(f"warnings={len(status['warnings'])}")
    for warning in status["warnings"]:
        typer.echo(f"warning={warning}")


@api_app.command("serve")
def serve_api(
    host: str | None = typer.Option(
        None,
        "--host",
        help="Bind host. Defaults to ORCHAI_API_HOST or 127.0.0.1.",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help="Bind port. Defaults to ORCHAI_API_PORT or 8000.",
    ),
) -> None:
    """Serve the FastAPI interface."""

    settings = load_settings()
    effective_host = host or settings.api.host
    effective_port = port or settings.api.port
    typer.echo(f"host={effective_host}")
    typer.echo(f"port={effective_port}")
    uvicorn.run(api_application, host=effective_host, port=effective_port)


def _safe_database_label(url: str) -> str:
    parts = urlsplit(url)
    if parts.password is None:
        return url

    userinfo = parts.username or ""
    if userinfo:
        userinfo = f"{userinfo}:***"

    host = parts.hostname or ""
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parts.port is not None:
        host = f"{host}:{parts.port}"

    return urlunsplit(
        (
            parts.scheme,
            f"{userinfo}@{host}",
            parts.path,
            parts.query,
            parts.fragment,
        )
    )


def _parse_csv_tuple(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",")]
    return tuple(item for item in items if item)


def _parse_role_action_pair(entry: str) -> tuple[RoleName, ActionName]:
    role_value, _, action_value = entry.partition(":")
    return RoleName(role_value), ActionName(action_value)


def _parse_role_role_pair(entry: str) -> tuple[RoleName, RoleName]:
    previous_value, _, next_value = entry.partition(":")
    return RoleName(previous_value), RoleName(next_value)


def _echo_automatic_policy(policy: AutomaticExecutionPolicy) -> None:
    typer.echo(
        "allowed_operations="
        + ",".join(
            f"{role.value}:{action.value}" for role, action in policy.allowed_operations
        )
    )
    typer.echo(
        "allowed_cross_role_transitions="
        + ",".join(
            f"{previous.value}:{next_role.value}"
            for previous, next_role in policy.allowed_cross_role_transitions
        )
    )
    typer.echo(f"allow_model_substitution={str(policy.allow_model_substitution).lower()}")
    typer.echo(f"allow_context_expansion={str(policy.allow_context_expansion).lower()}")


def _parse_metadata_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"metadata must be a JSON object: {exc}") from exc
    if not isinstance(parsed, dict):
        raise typer.BadParameter("metadata must be a JSON object")
    return parsed


def _parse_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "y"}:
        return True
    if normalized in {"false", "0", "no", "n"}:
        return False
    raise typer.BadParameter(f"invalid boolean value: {value}")


def _split_words(value: str) -> tuple[str, ...]:
    return tuple(part for part in value.split() if part)


async def _resolve_policy_project_context_cli(
    *,
    runtime,
    project_id: str | None,
    project_root: Path | None,
    fallback_readiness_level: ProjectReadinessLevel | None,
):
    if project_id is not None:
        project = await runtime.project_service.get_project(ProjectId(project_id))
        return project.readiness_level, project.security_profile
    if project_root is not None:
        adapter = LocalFilesystemProjectAdapter(project_root)
        readiness = await adapter.assess_readiness()
        return readiness.readiness_level, readiness.security_profile
    if fallback_readiness_level is not None:
        return (
            fallback_readiness_level,
            ProjectSecurityProfile(readiness_level=fallback_readiness_level),
        )
    default_profile = ProjectSecurityProfile()
    return default_profile.readiness_level, default_profile


async def _ensure_project_adapter_registered_for_execution_cli(
    *,
    runtime,
    execution_id: ExecutionId,
) -> None:
    execution = await runtime.execution_service.get_execution(execution_id)
    if execution.project_id is None:
        return
    project = await runtime.project_service.get_project(execution.project_id)
    await runtime.project_adapters.register(
        project.id,
        LocalFilesystemProjectAdapter(Path(project.root_location)),
    )


def _validate_project_operation_input(
    *,
    operation: ProjectOperation,
    resource: str,
    content: str,
    command: str,
) -> None:
    if operation in {
        ProjectOperation.WRITE_SOURCE,
        ProjectOperation.WRITE_DOCUMENTATION,
    }:
        if not resource.strip():
            raise typer.BadParameter("write operations require --resource")
        if not content:
            raise typer.BadParameter("write operations require --content")
    if operation in {
        ProjectOperation.RUN_COMMAND,
        ProjectOperation.RUN_VALIDATION,
    } and not command.strip():
        raise typer.BadParameter(f"{operation.value} requires --command")


def _task_available_transitions(state: TaskState) -> tuple[str, ...]:
    machine = TaskStateMachine.default()
    return tuple(sorted(target.value for target in machine.available_targets(state)))


def _execution_available_transitions(state: ExecutionState) -> tuple[str, ...]:
    machine = ExecutionStateMachine.default()
    return tuple(sorted(target.value for target in machine.available_targets(state)))


if __name__ == "__main__":
    app()
