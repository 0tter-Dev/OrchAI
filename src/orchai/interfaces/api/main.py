"""HTTP API for OrchAI."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from orchai.application.authorization import (
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.context import ResolveExecutionContextCommand
from orchai.application.conversations import (
    CreateConversationCommand,
    SendMessageCommand,
    UnknownModuleError,
)
from orchai.application.executions import (
    CompleteExecutionCommand,
    RequestExecutionCommand,
    TransitionExecutionCommand,
)
from orchai.application.identity import (
    AccessTokenClaims,
    AuthenticationResult,
    CreateAccessRoleCommand,
    CreateUserWithRolesCommand,
    LoginCommand,
    LogoutCommand,
    RefreshCommand,
    SetAccessRolesForUserCommand,
    SetPermissionsForRoleCommand,
    UpdateUserProfileCommand,
)
from orchai.application.modules import get_module, list_modules
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
    build_conversation_runtime_from_settings,
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
    ConversationId,
    ExecutionId,
    ModelId,
    ModuleId,
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
    InvalidRefreshTokenError,
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
from orchai.infrastructure.configuration import (
    DatabaseSettings,
    OrchAISettings,
    load_settings,
)
from orchai.infrastructure.identity import JWTAccessTokenIssuer
from orchai.infrastructure.persistence import (
    SQLAlchemyDatabase,
    SQLAlchemyProjectConnectionRepository,
)
from orchai.infrastructure.persistence.db import DatabaseAdmin
from orchai.infrastructure.projects import (
    LocalFilesystemProjectAdapter,
    MediaWorkspaceProjectAdapter,
)

_API_TAGS_METADATA = [
    {"name": "requests", "description": "Chat-first request interface — primary entry point for external clients."},
    {"name": "system", "description": "Service health, runtime posture, and API metadata."},
    {"name": "providers", "description": "AI provider configuration, capabilities, and health."},
    {"name": "modules", "description": "Module registry (Forge, Studio, ...) — ADR-015."},
    {"name": "conversations", "description": "Persistent chat conversations and messages — ADR-014."},
    {"name": "auth", "description": "Authentication (login/refresh/logout) — ADR-012."},
    {"name": "admin", "description": "Admin-only user/access-role/project configuration CRUD."},
    {"name": "me", "description": "Self-service: the logged-in user's own profile and projects."},
]


async def _resolve_access_token_claims(
    authorization: str | None,
) -> AccessTokenClaims | None:
    """Decode and validate the bearer access token, or `None` if auth is off.

    Reads settings fresh (matching this module's existing per-call
    `load_settings()` convention) rather than accepting a `database_url`
    override: which database backs identity/authentication is a system
    configuration concern, not something a caller should be able to
    redirect per request.

    Returns `None` when `ORCHAI_AUTH_ENFORCED` is false -- the Phase 3
    rollout default (`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6) --
    signaling callers to skip permission checks entirely. Raises
    `HTTPException(401)` for a missing, malformed, or invalid/expired token
    when enforcement is on.
    """

    settings = load_settings()
    if not settings.auth.enforced:
        return None
    return _decode_bearer_token(authorization)


def _decode_bearer_token(authorization: str | None) -> AccessTokenClaims:
    """Decode a required bearer access token, raising 401 on any problem.

    Factored out of `_resolve_access_token_claims` so `require_authenticated_user`
    (used by the `/me` self-service routes, which need a real caller
    unconditionally) can reuse the exact same decode path without
    duplicating token-handling logic, while `_resolve_access_token_claims`
    keeps its own early return for `ORCHAI_AUTH_ENFORCED=false`.
    """

    if authorization is None or not authorization.strip():
        raise HTTPException(status_code=401, detail="missing bearer access token")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="expected an 'Authorization: Bearer <token>' header",
        )
    settings = load_settings()
    issuer = JWTAccessTokenIssuer(
        secret_key=settings.auth.secret_key,
        ttl=timedelta(minutes=settings.auth.access_token_ttl_minutes),
    )
    try:
        return issuer.decode(token.strip())
    except InvalidAccessTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_permission(permission_key: str | None = None):
    """FastAPI dependency factory enforcing a permission (ADR-012).

    Inert when `ORCHAI_AUTH_ENFORCED` is false (the rollout default): the
    returned dependency resolves to `None` without touching the database.
    When enforcement is on: requires a valid, unexpired bearer access
    token (401 otherwise); a token carrying `is_superuser` bypasses the
    permission check entirely; otherwise the caller's effective permission
    set (via `IdentityService.effective_permission_keys`) must include
    `permission_key`, or the request is rejected with 403.

    `permission_key=None` means "must be authenticated, no specific
    permission required" -- for read-only endpoints that need a valid
    caller but not a named capability
    (`IDENTITY-AND-ACCESS-MODEL.md` §4).
    """

    async def _dependency(
        authorization: str | None = Header(default=None),
    ) -> AccessTokenClaims | None:
        claims = await _resolve_access_token_claims(authorization)
        if claims is None or claims.is_superuser or permission_key is None:
            return claims
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        effective_keys = (
            await identity_runtime.identity_service.effective_permission_keys(
                claims.user_id
            )
        )
        if permission_key not in effective_keys:
            raise HTTPException(
                status_code=403,
                detail=f"missing required permission: {permission_key}",
            )
        return claims

    return _dependency


def require_authenticated_user():
    """FastAPI dependency requiring a real authenticated user, always.

    Unlike `require_permission()`, this never no-ops when
    `ORCHAI_AUTH_ENFORCED` is false: the `/me` self-service routes have no
    meaningful "no-op" reading of "show/update my own profile" -- there is
    no caller to resolve without a token. Always requires a valid,
    unexpired bearer access token (401 otherwise) and returns its claims.
    Safe to introduce without touching the enforcement toggle's existing
    behavior anywhere else: `/me` is a brand-new surface with zero
    pre-existing callers.
    """

    async def _dependency(
        authorization: str | None = Header(default=None),
    ) -> AccessTokenClaims:
        return _decode_bearer_token(authorization)

    return _dependency


def _serialize_authentication_result(result: AuthenticationResult) -> dict[str, Any]:
    return {
        "user": {
            "id": str(result.user.id),
            "username": result.user.username,
            "is_superuser": result.user.is_superuser,
        },
        "token_type": "bearer",
        "access_token": result.access_token.token,
        "access_token_expires_at": result.access_token.expires_at.isoformat(),
        "refresh_token": result.raw_refresh_token,
        "refresh_token_expires_at": result.refresh_token.expires_at.isoformat(),
    }


class LoginRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    password: str


class RefreshRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class LogoutRequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    refresh_token: str


class LocalFlowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_root: str
    context_path: str
    title: str = "API local flow"
    model: str | None = None
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    approve_suggestion: bool = False
    database_url: str | None = None


class ProjectOperationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_root: str
    operation: ProjectOperation
    title: str = "Protected project operation"
    resource: str = ""
    content: str = ""
    command: list[str] = Field(default_factory=list)
    test_args: list[str] = Field(default_factory=list)
    model: str | None = None
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    approve_operation: bool = False
    database_url: str | None = None


class ProjectRegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_root: str
    name: str | None = None
    database_url: str | None = None


class ConversationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    module_id: str
    project_id: str | None = None
    title: str = ""
    database_url: str | None = None


class ConversationMessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    model: str | None = None
    database_url: str | None = None


class ConversationEscalateRequest(BaseModel):
    """Escalate a conversation message into a real Task (ADR-014 §2, Phase 5).

    Mirrors `ChatRequest` (`POST /requests`) minus `project_root` --
    resolved instead from the conversation's own `project_id`.
    """

    model_config = ConfigDict(extra="forbid")

    content: str
    model: str | None = None
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    context_paths: list[str] = Field(default_factory=list)
    approve_suggestion: bool = False
    database_url: str | None = None


class AuthorizationRequestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    role: RoleName
    action: ActionName
    reason: str
    requester: str
    execution_mode: ExecutionMode
    model_id: str | None = None
    context_scope: list[str] = Field(default_factory=list)
    proposed_state: TaskState | None = None
    expires_at: datetime | None = None
    database_url: str | None = None


class AuthorizationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: AuthorizationDecisionStatus
    decided_by: str
    reason: str
    database_url: str | None = None


class TaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str
    description: str
    requested_change: str
    project_id: str | None = None
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    acceptance_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    database_url: str | None = None


class TaskTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_state: TaskState
    source: str = "api.tasks"
    database_url: str | None = None


class TaskAdvanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: TaskWorkflowStage | None = None
    context_paths: list[str] = Field(default_factory=list)
    documentation_path: str = ""
    test_args: list[str] = Field(default_factory=list)
    model: str | None = None
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    execution_mode: ExecutionMode | None = None
    approve_stage: bool = False
    requester: str = "api"
    decider: str = "api"
    database_url: str | None = None


class PolicyEvaluateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_mode: ExecutionMode
    role: RoleName
    action: ActionName
    requested_model: str
    effective_model: str
    requested_context: list[str] = Field(default_factory=list)
    authorized_context: list[str] = Field(default_factory=list)
    current_task_state: TaskState
    project_operation: ProjectOperation = ProjectOperation.READ_CONTEXT
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    project_id: str | None = None
    project_root: str | None = None
    project_readiness_level: ProjectReadinessLevel | None = None
    context_sharing_levels: list[ProviderSharingLevel] = Field(default_factory=list)
    approve_suggestion: bool = False
    explicit_user_command: bool = False
    previous_role: RoleName | None = None
    previous_action: ActionName | None = None
    database_url: str | None = None


class AutomaticPolicyOperationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: RoleName
    action: ActionName


class AutomaticPolicyTransitionEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    previous_role: RoleName
    next_role: RoleName


class AutomaticPolicySetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_operations: list[AutomaticPolicyOperationEntry] = Field(default_factory=list)
    allowed_cross_role_transitions: list[AutomaticPolicyTransitionEntry] = Field(
        default_factory=list
    )
    allow_model_substitution: bool = False
    allow_context_expansion: bool = False
    database_url: str | None = None


class ExecutionRequestCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    role: RoleName
    action: ActionName
    model_id: str
    authorization_id: str
    project_id: str | None = None
    requested_context: list[str] = Field(default_factory=list)
    authorized_context: list[str] = Field(default_factory=list)
    database_url: str | None = None


class ExecutionTransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_state: ExecutionState
    database_url: str | None = None


class ExecutionCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_url: str | None = None


class ResourceUsageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionCompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output: str
    success: bool = True
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    resource_usage: ResourceUsageRequest = Field(default_factory=ResourceUsageRequest)
    metadata: dict[str, Any] = Field(default_factory=dict)
    database_url: str | None = None


class ResolveExecutionContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: ContextSource = ContextSource.SOURCE_FILE
    database_url: str | None = None


class ProjectSecurityUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    readiness_level: ProjectReadinessLevel | None = None
    access_scope: list[str] | None = None
    restricted_areas: list[str] | None = None
    sensitive_patterns: list[str] | None = None
    allow_git_bootstrap: bool | None = None
    allow_architecture_restructure: bool | None = None
    allow_cicd_changes: bool | None = None
    allow_cloud_provider_sharing: bool | None = None
    persist_architecture_summaries: bool | None = None
    persist_naming_summaries: bool | None = None
    persist_functional_summaries: bool | None = None
    persist_context_snapshots: bool | None = None
    database_url: str | None = None


class DatabaseSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    database_url: str | None = None
    maintenance_database: str = "postgres"


# ---------------------------------------------------------------------------
# User-configuration CRUD models (admin + self-service, ADR-012)
# ---------------------------------------------------------------------------


class AdminCreateUserRequest(BaseModel):
    """Admin-only "create user" request.

    `role_ids` is mandatory in spirit, not in schema: an empty list is
    accepted here (so the field can simply default) but rejected by
    `IdentityService.create_user_with_roles` unless `is_superuser` is set
    -- see `UserRequiresAccessRoleError`.
    """

    model_config = ConfigDict(extra="forbid")

    username: str
    password: str
    role_ids: list[str] = Field(default_factory=list)
    email: str | None = None
    is_superuser: bool = False


class SetAccessRolesRequest(BaseModel):
    """Replace-all body for `PUT /admin/users/{user_id}/access-roles`."""

    model_config = ConfigDict(extra="forbid")

    role_ids: list[str]


class AdminCreateAccessRoleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""


class SetRolePermissionsRequest(BaseModel):
    """Replace-all body for `PUT /admin/access-roles/{role_id}/permissions`."""

    model_config = ConfigDict(extra="forbid")

    permission_ids: list[str]


class MeUpdateRequest(BaseModel):
    """Self-service profile update body.

    Deliberately has no `role_ids`/`is_superuser`/`id` field -- see
    `UpdateUserProfileCommand`'s docstring.
    """

    model_config = ConfigDict(extra="forbid")

    username: str | None = None
    email: str | None = None


# ---------------------------------------------------------------------------
# Chat-First Request Interface Models (ADR-011)
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Primary entry point for external clients using a chat-like interface.

    The user provides a project, selects model/role/action, and describes
    the request as a natural language prompt.  OrchAI creates a Task and
    orchestrates the full flow transparently.
    """

    model_config = ConfigDict(extra="forbid")

    project_root: str
    prompt: str
    role: RoleName | None = None
    action: ActionName | None = None
    model: str | None = None
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    context_paths: list[str] = Field(default_factory=list)
    title: str | None = None
    approve_suggestion: bool = False
    database_url: str | None = None


class RequestApproveBody(BaseModel):
    """Approve a pending suggestion for a request in SUGGESTED mode.

    When no standalone Authorization is pending, approval is resolved by
    delegating internally to the same gated mechanism as
    POST /requests/{request_id}/advance (approve_stage=true). The optional
    fields below exist only to satisfy that delegated call when the current
    gated stage itself requires them (e.g. PLAN requires context_paths,
    DOCUMENT requires documentation_path) — they are ignored when a
    standalone Authorization is granted directly instead.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str = "Approved via request interface"
    decided_by: str = "user"
    context_paths: list[str] = Field(default_factory=list)
    documentation_path: str = ""
    test_args: list[str] = Field(default_factory=list)
    model: str | None = None
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    database_url: str | None = None


class RequestAdvanceBody(BaseModel):
    """Advance a request to the next workflow stage."""

    model_config = ConfigDict(extra="forbid")

    stage: TaskWorkflowStage | None = None
    context_paths: list[str] = Field(default_factory=list)
    documentation_path: str = ""
    test_args: list[str] = Field(default_factory=list)
    model: str | None = None
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    execution_mode: ExecutionMode | None = None
    approve_stage: bool = False
    requester: str = "api"
    decider: str = "api"
    database_url: str | None = None


def create_app() -> FastAPI:
    """Create the FastAPI application."""

    app = FastAPI(
        title="OrchAI API",
        version="0.2.6",
        summary="OrchAI orchestration API — chat-first request interface and operational surface.",
        description=(
            "API-first interface for OrchAI orchestration. "
            "The /requests resource is the primary entry point for external clients "
            "(chat UIs, web apps, mobile apps). "
            "Fine-grained endpoints (/tasks, /authorizations, /executions) remain "
            "available for operators and automated pipelines."
        ),
        openapi_tags=_API_TAGS_METADATA,
    )

    @app.get("/", tags=["system"], summary="Show API index and key entry points")
    async def root() -> dict[str, Any]:
        return {
            "service": "OrchAI API",
            "version": "0.2.6",
            "docs_url": str(app.docs_url),
            "redoc_url": str(app.redoc_url),
            "openapi_url": str(app.openapi_url),
            "recommended_operational_dialect": "postgresql",
            "entry_points": {
                "requests": "/requests",
                "health": "/health",
                "auth_login": "/auth/login",
                "auth_refresh": "/auth/refresh",
                "auth_logout": "/auth/logout",
                "runtime_settings": "/settings/runtime",
                "runtime_check": "/runtime/check",
                "provider_settings": "/providers/settings",
                "provider_capabilities": "/providers/capabilities",
                "provider_health": "/providers/health",
                "modules": "/modules",
                "conversations": "/conversations",
                "projects": "/projects",
                "tasks": "/tasks",
                "authorizations": "/authorizations",
                "executions": "/executions",
                "events": "/events",
                "audit": "/audit",
                "metrics": "/metrics",
                "suggestions": "/suggestions",
                "admin_users": "/admin/users",
                "admin_access_roles": "/admin/access-roles",
                "admin_projects": "/admin/projects",
                "me": "/me",
            },
            "interface_model": {
                "chat_first": "/requests — primary entry point for external clients",
                "operational": "/tasks, /authorizations, /executions — fine-grained control",
            },
        }

    @app.get("/health", tags=["system"], summary="Check basic service health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": "0.2.6"}

    @app.post(
        "/auth/login",
        tags=["auth"],
        summary="Exchange a username/password for an access/refresh token pair",
    )
    async def auth_login(request: LoginRequestBody) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        try:
            result = await identity_runtime.identity_service.login(
                LoginCommand(username=request.username, plain_password=request.password)
            )
        except InvalidCredentialsError as exc:
            raise HTTPException(
                status_code=401, detail="invalid username or password"
            ) from exc
        return _serialize_authentication_result(result)

    @app.post(
        "/auth/refresh",
        tags=["auth"],
        summary="Rotate a refresh token into a fresh access/refresh token pair",
    )
    async def auth_refresh(request: RefreshRequestBody) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        try:
            result = await identity_runtime.identity_service.refresh(
                RefreshCommand(raw_refresh_token=request.refresh_token)
            )
        except InvalidRefreshTokenError as exc:
            raise HTTPException(
                status_code=401,
                detail="invalid, expired, or already-used refresh token",
            ) from exc
        return _serialize_authentication_result(result)

    @app.post(
        "/auth/logout",
        tags=["auth"],
        summary="Revoke a refresh token (idempotent)",
        dependencies=[Depends(require_permission())],
    )
    async def auth_logout(request: LogoutRequestBody) -> dict[str, str]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        await identity_runtime.identity_service.logout(
            LogoutCommand(raw_refresh_token=request.refresh_token)
        )
        return {"status": "logged_out"}

    @app.post(
        "/flows/local",
        dependencies=[Depends(require_permission("requests:create"))],
    )
    async def local_flow(request: LocalFlowRequest) -> dict[str, str]:
        settings = _settings_override(request.database_url)
        url = settings.database.sqlalchemy_url
        return await run_local_flow(
            project_root=Path(request.project_root),
            context_path=request.context_path,
            title=request.title,
            model=request.model or settings.ai_provider.model or "local-demo",
            dependencies=build_local_flow_dependencies_from_settings(settings),
            storage_label=url,
            provider_target=request.provider_target,
            execution_mode=request.execution_mode,
            approve_suggestion=request.approve_suggestion,
        )

    @app.post(
        "/projects/operations",
        dependencies=[Depends(require_permission("projects:connect"))],
    )
    async def project_operation(request: ProjectOperationRequest) -> dict[str, str]:
        settings = _settings_override(request.database_url)
        url = settings.database.sqlalchemy_url
        return await run_project_operation(
            project_root=Path(request.project_root),
            operation=request.operation,
            title=request.title,
            dependencies=build_local_flow_dependencies_from_settings(settings),
            storage_label=url,
            resource=request.resource,
            content=request.content,
            command=tuple(request.command),
            test_args=tuple(request.test_args),
            model=request.model or settings.ai_provider.model or "local-project-operation",
            provider_target=request.provider_target,
            execution_mode=request.execution_mode,
            approve_operation=request.approve_operation,
        )

    @app.post(
        "/admin/db/sync",
        dependencies=[Depends(require_permission("admin:db"))],
    )
    async def sync_database(request: DatabaseSyncRequest) -> dict[str, str]:
        """Create the database if needed (PostgreSQL only), then migrate it.

        This is the single, standard database administration operation:
        create the target database when it does not exist yet (a no-op, not
        an error, for a local-flow/SQLite target, which does not need a
        database created up front), then apply migrations unconditionally.
        """

        settings = _settings_override(request.database_url)
        url = settings.database.url
        message = ""
        if settings.database.is_postgresql:
            created = DatabaseAdmin(
                url,
                maintenance_database=request.maintenance_database,
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
        SQLAlchemyDatabase(settings.database.sqlalchemy_url).migrate()
        return {
            "database": _safe_database_label(url),
            "create_status": create_status,
            "migrations": "applied",
            "message": message,
        }

    @app.get(
        "/projects/discover",
        dependencies=[Depends(require_permission())],
    )
    async def discover_project(
        project_root: str,
        limit: int = Query(20, ge=1, le=100),
    ) -> dict[str, Any]:
        adapter = LocalFilesystemProjectAdapter(Path(project_root))
        discovery = await adapter.discover(limit=limit)
        return {
            "metadata": dict(discovery.metadata),
            "resources": [_serialize_resource(resource) for resource in discovery.resources],
        }

    @app.get(
        "/projects/readiness",
        dependencies=[Depends(require_permission())],
    )
    async def project_readiness(project_root: str) -> dict[str, Any]:
        adapter = LocalFilesystemProjectAdapter(Path(project_root))
        readiness = await adapter.assess_readiness()
        return _serialize_readiness(readiness)

    @app.get(
        "/projects/security",
        dependencies=[Depends(require_permission())],
    )
    async def project_security(project_root: str) -> dict[str, Any]:
        adapter = LocalFilesystemProjectAdapter(Path(project_root))
        readiness = await adapter.assess_readiness()
        return readiness.security_profile.as_dict()

    @app.get(
        "/projects",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def list_projects(database_url: str | None = None) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        projects = await runtime.project_service.list_projects()
        return {
            "projects": [_serialize_project(project) for project in projects],
            "count": len(projects),
        }

    @app.post("/projects")
    async def register_project(
        request: ProjectRegisterRequest,
        claims: AccessTokenClaims | None = Depends(require_permission("projects:connect")),
    ) -> dict[str, Any]:
        settings = _settings_override(request.database_url)
        runtime = build_sqlalchemy_runtime(settings.database.sqlalchemy_url)
        adapter = LocalFilesystemProjectAdapter(Path(request.project_root))
        readiness = await adapter.assess_readiness()
        capabilities = await adapter.capabilities()
        project = await runtime.project_service.register_project(
            RegisterProjectCommand(
                name=request.name or Path(request.project_root).resolve().name,
                root_location=str(Path(request.project_root).resolve()),
                adapter_type="local_filesystem",
                capabilities=capabilities,
                readiness_level=readiness.readiness_level,
                security_profile=readiness.security_profile,
                observed_readiness_level=readiness.readiness_level,
                observed_security_profile=readiness.security_profile,
            )
        )
        serialized = _serialize_project(project)
        if claims is not None:
            # Record a purely informational reference -- "this user connected
            # this project to OrchAI" -- not an access-control boundary; see
            # `ProjectConnectionRepository`'s module docstring. Never blocks
            # registration: enforcement being off (claims is None) just means
            # no connector is recorded.
            connection_repository = SQLAlchemyProjectConnectionRepository(
                runtime.database
            )
            await connection_repository.link(project.id, claims.user_id)
            serialized["connected_by_user_id"] = str(claims.user_id)
        return serialized

    @app.get(
        "/projects/lookup",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def lookup_project(
        project_root: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        project = await runtime.project_service.get_project_by_root_location(
            str(Path(project_root).resolve())
        )
        return {
            "project": _serialize_project(project) if project is not None else None,
            "found": project is not None,
        }

    @app.post(
        "/tasks",
        dependencies=[Depends(require_permission("requests:create"))],
    )
    async def create_task(request: TaskCreateRequest) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        task = await runtime.task_service.create_task(
            CreateTaskCommand(
                title=request.title,
                description=request.description,
                requested_change=request.requested_change,
                project_id=ProjectId(request.project_id) if request.project_id else None,
                execution_mode=request.execution_mode,
                acceptance_criteria=tuple(request.acceptance_criteria),
                constraints=tuple(request.constraints),
                exclusions=tuple(request.exclusions),
            )
        )
        return _serialize_task(task)

    @app.post(
        "/tasks/{task_id}/transition",
        dependencies=[Depends(require_permission("requests:advance"))],
    )
    async def transition_task(
        task_id: str,
        request: TaskTransitionRequest,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        task = await runtime.task_service.transition_task(
            TransitionTaskCommand(
                task_id=TaskId(task_id),
                target_state=request.target_state,
                source=request.source,
            )
        )
        return _serialize_task(task)

    @app.post(
        "/tasks/{task_id}/advance",
        dependencies=[Depends(require_permission("requests:advance"))],
    )
    async def advance_task(
        task_id: str,
        request: TaskAdvanceRequest,
    ) -> dict[str, str]:
        settings = _settings_override(request.database_url)
        url = settings.database.sqlalchemy_url
        return await run_task_workflow_stage(
            task_id=task_id,
            dependencies=build_local_flow_dependencies_from_settings(settings),
            storage_label=url,
            model=request.model or settings.ai_provider.model or "local-task-stage",
            stage=request.stage,
            context_paths=tuple(request.context_paths),
            documentation_path=request.documentation_path,
            test_args=tuple(request.test_args),
            provider_target=request.provider_target,
            execution_mode=request.execution_mode,
            approve_stage=request.approve_stage,
            requester=request.requester,
            decider=request.decider,
        )

    @app.post(
        "/policies/evaluate",
        dependencies=[Depends(require_permission("policies:evaluate"))],
    )
    async def evaluate_policy(request: PolicyEvaluateRequest) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        readiness_level, security_profile = await _resolve_policy_project_context(
            runtime=runtime,
            project_id=request.project_id,
            project_root=request.project_root,
            fallback_readiness_level=request.project_readiness_level,
        )
        decision = await runtime.policy_service.evaluate(
            PolicyOperation(
                execution_mode=request.execution_mode,
                role=request.role,
                action=request.action,
                requested_model=request.requested_model,
                effective_model=request.effective_model,
                requested_context=tuple(request.requested_context),
                authorized_context=tuple(request.authorized_context),
                current_task_state=request.current_task_state,
                project_operation=request.project_operation,
                provider_target=request.provider_target,
                project_readiness_level=readiness_level,
                project_security_profile=security_profile,
                context_sharing_levels=tuple(request.context_sharing_levels),
                approve_suggestion=request.approve_suggestion,
                explicit_user_command=request.explicit_user_command,
                previous_role=request.previous_role,
                previous_action=request.previous_action,
            )
        )
        return {
            "allowed": decision.allowed,
            "reason": decision.reason,
            "requires_authorization": decision.requires_authorization,
            "metadata": dict(decision.metadata),
            "project_readiness_level": readiness_level.value,
            "allow_cloud_provider_sharing": (
                security_profile.allow_cloud_provider_sharing
            ),
        }

    @app.get(
        "/policies/automatic",
        tags=["system"],
        summary="Show the persisted automatic-mode execution policy",
        dependencies=[Depends(require_permission("policies:evaluate"))],
    )
    async def get_automatic_policy(database_url: str | None = None) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        policy = await runtime.automatic_policy_service.get_automatic_policy()
        return _serialize_automatic_policy(policy)

    @app.put(
        "/policies/automatic",
        tags=["system"],
        summary="Replace the persisted automatic-mode execution policy",
        dependencies=[Depends(require_permission("policies:manage"))],
    )
    async def set_automatic_policy(request: AutomaticPolicySetRequest) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        policy = AutomaticExecutionPolicy(
            allowed_operations=tuple(
                (entry.role, entry.action) for entry in request.allowed_operations
            ),
            allowed_cross_role_transitions=tuple(
                (entry.previous_role, entry.next_role)
                for entry in request.allowed_cross_role_transitions
            ),
            allow_model_substitution=request.allow_model_substitution,
            allow_context_expansion=request.allow_context_expansion,
        )
        updated = await runtime.automatic_policy_service.set_automatic_policy(policy)
        return _serialize_automatic_policy(updated)

    @app.get(
        "/settings/runtime",
        tags=["system"],
        summary="Show effective runtime settings",
        dependencies=[Depends(require_permission())],
    )
    async def runtime_settings(database_url: str | None = None) -> dict[str, Any]:
        settings = _settings_override(database_url)
        return {
            "database": {
                "url": _safe_database_label(settings.database.url),
                "sqlalchemy_url": _safe_database_label(
                    settings.database.sqlalchemy_url
                ),
                "dialect": settings.database.dialect,
                "is_postgresql": settings.database.is_postgresql,
                "is_sqlite": settings.database.is_sqlite,
                "operational_role": (
                    "primary" if settings.database.is_postgresql else "local-only"
                ),
                "recommended_operational_dialect": "postgresql",
            },
            "ai_provider": {
                "provider": settings.ai_provider.provider,
                "base_url": settings.ai_provider.base_url,
                "organization": settings.ai_provider.organization,
                "project": settings.ai_provider.project,
                "model": settings.ai_provider.model,
                "timeout_seconds": settings.ai_provider.timeout_seconds,
                "api_key_configured": settings.ai_provider.api_key is not None,
            },
            "api": {
                "host": settings.api.host,
                "port": settings.api.port,
            },
        }

    @app.get(
        "/providers/settings",
        tags=["providers"],
        summary="Show effective AI provider settings",
        dependencies=[Depends(require_permission())],
    )
    async def provider_settings(database_url: str | None = None) -> dict[str, Any]:
        settings = _settings_override(database_url)
        return {
            "provider": settings.ai_provider.provider,
            "base_url": settings.ai_provider.base_url,
            "organization": settings.ai_provider.organization,
            "project": settings.ai_provider.project,
            "model": settings.ai_provider.model,
            "timeout_seconds": settings.ai_provider.timeout_seconds,
            "api_key_configured": settings.ai_provider.api_key is not None,
        }

    @app.get(
        "/runtime/check",
        tags=["system"],
        summary="Run a consolidated runtime operational check",
        dependencies=[Depends(require_permission())],
    )
    async def runtime_check(database_url: str | None = None) -> dict[str, Any]:
        settings = _settings_override(database_url)
        runtime = build_sqlalchemy_runtime(settings.database.sqlalchemy_url)
        provider = provider_from_settings(settings)
        return await collect_runtime_status(
            settings=settings,
            provider=provider,
            database=runtime.database or SQLAlchemyDatabase(settings.database.sqlalchemy_url),
        )

    @app.get(
        "/providers/capabilities",
        tags=["providers"],
        summary="Show declared capabilities of the configured provider",
        dependencies=[Depends(require_permission())],
    )
    async def provider_capabilities(database_url: str | None = None) -> dict[str, Any]:
        settings = _settings_override(database_url)
        provider = provider_from_settings(settings)
        capabilities = await provider.capabilities()
        return {
            "provider": settings.ai_provider.provider,
            "capabilities": sorted(capabilities),
            "model": settings.ai_provider.model,
        }

    @app.get(
        "/providers/health",
        tags=["providers"],
        summary="Show operational health of the configured provider",
        dependencies=[Depends(require_permission())],
    )
    async def provider_health(database_url: str | None = None) -> dict[str, Any]:
        settings = _settings_override(database_url)
        provider = provider_from_settings(settings)
        health = await provider.healthcheck()
        return {
            "provider": health.provider_name,
            "reachable": health.reachable,
            "configured_model": settings.ai_provider.model,
            "message": health.message,
            "metadata": dict(health.metadata),
        }

    @app.get(
        "/modules",
        tags=["modules"],
        summary="List available Modules (Forge, Studio, ...)",
        dependencies=[Depends(require_permission())],
    )
    async def list_modules_route() -> dict[str, Any]:
        modules = list_modules()
        return {
            "modules": [_serialize_module(module) for module in modules],
            "count": len(modules),
        }

    @app.get(
        "/modules/{module_id}",
        tags=["modules"],
        summary="Show one Module's metadata",
        dependencies=[Depends(require_permission())],
    )
    async def get_module_route(module_id: str) -> dict[str, Any]:
        module = get_module(ModuleId(module_id))
        if module is None:
            raise HTTPException(status_code=404, detail=f"unknown module: {module_id!r}")
        return _serialize_module(module)

    @app.post(
        "/conversations",
        tags=["conversations"],
        summary="Start a new conversation (ADR-014)",
        dependencies=[Depends(require_permission())],
    )
    async def create_conversation_route(request: ConversationCreateRequest) -> dict[str, Any]:
        settings = _settings_override(request.database_url)
        runtime = build_conversation_runtime_from_settings(settings)
        try:
            conversation = await runtime.conversation_service.create_conversation(
                CreateConversationCommand(
                    module_id=ModuleId(request.module_id),
                    project_id=ProjectId(request.project_id) if request.project_id else None,
                    title=request.title,
                )
            )
        except UnknownModuleError as exc:
            raise HTTPException(
                status_code=404, detail=f"unknown module: {request.module_id!r}"
            ) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return _serialize_conversation(conversation)

    @app.get(
        "/conversations",
        tags=["conversations"],
        summary="List conversations",
        dependencies=[Depends(require_permission())],
    )
    async def list_conversations_route(
        module_id: str | None = None,
        project_id: str | None = None,
        limit: int = 20,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_conversation_runtime_from_settings(_settings_override(database_url))
        conversations = await runtime.conversation_service.list_conversations(
            module_id=ModuleId(module_id) if module_id else None,
            project_id=ProjectId(project_id) if project_id else None,
            limit=limit,
        )
        return {
            "conversations": [_serialize_conversation(c) for c in conversations],
            "count": len(conversations),
        }

    @app.get(
        "/conversations/{conversation_id}",
        tags=["conversations"],
        summary="Show one conversation",
        dependencies=[Depends(require_permission())],
    )
    async def get_conversation_route(
        conversation_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_conversation_runtime_from_settings(_settings_override(database_url))
        try:
            conversation = await runtime.conversation_service.get_conversation(
                ConversationId(conversation_id)
            )
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail=f"unknown conversation: {conversation_id!r}"
            ) from exc
        return _serialize_conversation(conversation)

    @app.post(
        "/conversations/{conversation_id}/messages",
        tags=["conversations"],
        summary="Send a user message and stream the assistant's reply (SSE)",
        dependencies=[Depends(require_permission())],
    )
    async def send_conversation_message_route(
        conversation_id: str,
        request: ConversationMessageCreateRequest,
    ) -> StreamingResponse:
        settings = _settings_override(request.database_url)
        runtime = build_conversation_runtime_from_settings(settings)

        # Validated eagerly, before the streaming response starts, so an
        # unknown conversation still gets a real 404 -- once the SSE body
        # begins, the HTTP status line has already been sent and any
        # further error can only be signaled in-band (a `type: "error"`
        # event), the same tradeoff every streaming chat API makes.
        try:
            await runtime.conversation_service.get_conversation(
                ConversationId(conversation_id)
            )
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail=f"unknown conversation: {conversation_id!r}"
            ) from exc

        async def event_stream() -> AsyncIterator[str]:
            async for event in runtime.conversation_service.send_message_stream(
                SendMessageCommand(
                    conversation_id=ConversationId(conversation_id),
                    content=request.content,
                    model=request.model,
                )
            ):
                yield _serialize_stream_event(event)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get(
        "/conversations/{conversation_id}/messages",
        tags=["conversations"],
        summary="List a conversation's messages",
        dependencies=[Depends(require_permission())],
    )
    async def list_conversation_messages_route(
        conversation_id: str,
        limit: int = 100,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_conversation_runtime_from_settings(_settings_override(database_url))
        messages = await runtime.conversation_service.list_messages(
            ConversationId(conversation_id), limit=limit
        )
        return {
            "messages": [_serialize_message(message) for message in messages],
            "count": len(messages),
        }

    @app.post(
        "/conversations/{conversation_id}/escalate",
        tags=["conversations"],
        summary="Escalate a message into a real Task via /requests (ADR-014 §2)",
        description=(
            "Explicit-only escalation: a conversation message never turns into "
            "a Task on its own (ADR-014 invariant #2). This reuses the exact "
            "same orchestration machinery POST /requests does -- authorization, "
            "policy, and suggestion evaluation apply identically -- and records "
            "the resulting task_id/execution_id on the persisted user message."
        ),
        dependencies=[Depends(require_permission("requests:create"))],
    )
    async def escalate_conversation_message_route(
        conversation_id: str,
        request: ConversationEscalateRequest,
    ) -> dict[str, Any]:
        settings = _settings_override(request.database_url)
        url = settings.database.sqlalchemy_url
        conversation_runtime = build_conversation_runtime_from_settings(settings)

        try:
            conversation = await conversation_runtime.conversation_service.get_conversation(
                ConversationId(conversation_id)
            )
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail=f"unknown conversation: {conversation_id!r}"
            ) from exc
        if conversation.project_id is None:
            raise HTTPException(
                status_code=400,
                detail="conversation has no project to escalate against",
            )

        project_runtime = build_sqlalchemy_runtime(url)
        project = await project_runtime.project_service.get_project(conversation.project_id)

        prompt_lines = request.content.strip().splitlines()
        title = prompt_lines[0][:120] if prompt_lines else "Untitled request"
        context_path = request.context_paths[0] if request.context_paths else "."

        flow_result = await run_local_flow(
            project_root=Path(project.root_location),
            context_path=context_path,
            title=title,
            model=request.model or settings.ai_provider.model or "local-demo",
            dependencies=build_local_flow_dependencies_from_settings(settings),
            storage_label=url,
            provider_target=request.provider_target,
            execution_mode=request.execution_mode,
            approve_suggestion=request.approve_suggestion,
        )

        task_id = flow_result.get("task_id", "")
        execution_id = flow_result.get("execution_id") or None
        message = await conversation_runtime.conversation_service.escalate_message(
            conversation_id=ConversationId(conversation_id),
            content=request.content,
            task_id=TaskId(task_id),
            execution_id=ExecutionId(execution_id) if execution_id else None,
        )

        snapshot = await collect_task_snapshot(
            runtime=project_runtime,
            task_id=TaskId(task_id),
            history_limit=50,
        )
        return {
            "message": _serialize_message(message),
            "flow": _serialize_request_flow(snapshot, request_id=task_id),
        }

    @app.get(
        "/projects/{project_id}",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def show_project(
        project_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        project = await runtime.project_service.get_project(ProjectId(project_id))
        return _serialize_project(project)

    @app.get(
        "/projects/{project_id}/attachments",
        tags=["conversations"],
        summary="Discover a project's attachment/media resources (Studio, ADR-015)",
        description=(
            "Uses MediaWorkspaceProjectAdapter, independent of whatever "
            "adapter_type the project was registered with -- Studio "
            "browses the same connected folder Forge sees, just through "
            "a media-oriented lens (docs/architecture/MODULES.md)."
        ),
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def list_project_attachments(
        project_id: str,
        limit: int = Query(50, ge=1, le=200),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        try:
            project = await runtime.project_service.get_project(ProjectId(project_id))
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail=f"unknown project: {project_id!r}"
            ) from exc
        adapter = MediaWorkspaceProjectAdapter(Path(project.root_location))
        discovery = await adapter.discover(limit=limit)
        return {
            "metadata": dict(discovery.metadata),
            "resources": [_serialize_resource(resource) for resource in discovery.resources],
        }

    @app.get(
        "/tasks",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def list_tasks(
        project_id: str | None = None,
        state: TaskState | None = None,
        limit: int = Query(20, ge=1, le=100),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        tasks = await runtime.task_service.list_tasks(
            project_id=ProjectId(project_id) if project_id is not None else None,
            state=state,
            limit=limit,
        )
        return {"tasks": [_serialize_task(task) for task in tasks], "count": len(tasks)}

    @app.get(
        "/authorizations",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def list_authorizations(
        task_id: str | None = None,
        status: AuthorizationDecisionStatus | None = None,
        pending_only: bool = False,
        limit: int = Query(20, ge=1, le=100),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        authorizations = await runtime.authorization_service.list_authorizations(
            task_id=TaskId(task_id) if task_id is not None else None,
            status=status,
            pending_only=pending_only,
            limit=limit,
        )
        return {
            "authorizations": [
                _serialize_authorization(authorization)
                for authorization in authorizations
            ],
            "count": len(authorizations),
        }

    @app.get(
        "/authorizations/{authorization_id}",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def show_authorization(
        authorization_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        authorization = await runtime.authorization_service.get_authorization(
            AuthorizationId(authorization_id)
        )
        return _serialize_authorization(authorization)

    @app.post(
        "/authorizations/request",
        dependencies=[Depends(require_permission("authorizations:decide"))],
    )
    async def request_authorization(
        request: AuthorizationRequestCreateRequest,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        authorization = await runtime.authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=TaskId(request.task_id),
                role=request.role,
                action=request.action,
                reason=request.reason,
                requester=request.requester,
                execution_mode=request.execution_mode,
                model_id=ModelId(request.model_id) if request.model_id else None,
                context_scope=tuple(request.context_scope),
                proposed_state=request.proposed_state,
                expires_at=request.expires_at,
            )
        )
        return _serialize_authorization(authorization)

    @app.post(
        "/authorizations/{authorization_id}/decision",
        dependencies=[Depends(require_permission("authorizations:decide"))],
    )
    async def decide_authorization(
        authorization_id: str,
        request: AuthorizationDecisionRequest,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        authorization = await runtime.authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=AuthorizationId(authorization_id),
                status=request.status,
                decided_by=request.decided_by,
                reason=request.reason,
            )
        )
        return _serialize_authorization(authorization)

    @app.get(
        "/tasks/{task_id}",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def show_task(
        task_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        task = await runtime.task_service.get_task(TaskId(task_id))
        return _serialize_task(task)

    @app.get(
        "/tasks/{task_id}/snapshot",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def task_snapshot(
        task_id: str,
        history_limit: int = Query(100, ge=1, le=500),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        snapshot = await collect_task_snapshot(
            runtime=runtime,
            task_id=TaskId(task_id),
            history_limit=history_limit,
        )
        return _serialize_task_snapshot(snapshot)

    @app.get(
        "/executions",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def list_executions(
        task_id: str | None = None,
        project_id: str | None = None,
        state: ExecutionState | None = None,
        limit: int = Query(20, ge=1, le=100),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        executions = await runtime.execution_service.list_executions(
            task_id=TaskId(task_id) if task_id is not None else None,
            project_id=ProjectId(project_id) if project_id is not None else None,
            state=state,
            limit=limit,
        )
        return {
            "executions": [_serialize_execution(execution) for execution in executions],
            "count": len(executions),
        }

    @app.get(
        "/executions/{execution_id}",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def show_execution(
        execution_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        execution = await runtime.execution_service.get_execution(ExecutionId(execution_id))
        return _serialize_execution(execution)

    @app.post(
        "/executions/request",
        dependencies=[Depends(require_permission("executions:manage"))],
    )
    async def request_execution(
        request: ExecutionRequestCreateRequest,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        execution = await runtime.execution_service.request_execution(
            RequestExecutionCommand(
                task_id=TaskId(request.task_id),
                role=request.role,
                action=request.action,
                model_id=ModelId(request.model_id),
                authorization_id=AuthorizationId(request.authorization_id),
                project_id=ProjectId(request.project_id) if request.project_id else None,
                requested_context=tuple(request.requested_context),
                authorized_context=tuple(request.authorized_context),
            )
        )
        return _serialize_execution(execution)

    @app.post(
        "/executions/{execution_id}/transition",
        dependencies=[Depends(require_permission("executions:manage"))],
    )
    async def transition_execution(
        execution_id: str,
        request: ExecutionTransitionRequest,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        execution = await runtime.execution_service.transition_execution(
            TransitionExecutionCommand(
                execution_id=ExecutionId(execution_id),
                target_state=request.target_state,
            )
        )
        return _serialize_execution(execution)

    @app.post(
        "/executions/{execution_id}/cancel",
        dependencies=[Depends(require_permission("executions:manage"))],
    )
    async def cancel_execution(
        execution_id: str,
        request: ExecutionCancelRequest,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        execution = await runtime.execution_engine.cancel(ExecutionId(execution_id))
        return _serialize_execution(execution)

    @app.post(
        "/executions/{execution_id}/complete",
        dependencies=[Depends(require_permission("executions:manage"))],
    )
    async def complete_execution(
        execution_id: str,
        request: ExecutionCompleteRequest,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        execution = await runtime.execution_service.complete_execution(
            CompleteExecutionCommand(
                execution_id=ExecutionId(execution_id),
                output=request.output,
                success=request.success,
                errors=tuple(request.errors),
                warnings=tuple(request.warnings),
                resource_usage=ResourceUsage(
                    input_tokens=request.resource_usage.input_tokens,
                    output_tokens=request.resource_usage.output_tokens,
                    estimated_cost=request.resource_usage.estimated_cost,
                    metadata=request.resource_usage.metadata,
                ),
                metadata=request.metadata,
            )
        )
        return _serialize_execution(execution)

    @app.post(
        "/executions/{execution_id}/run",
        dependencies=[Depends(require_permission("executions:manage"))],
    )
    async def run_execution(
        execution_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        await _ensure_project_adapter_registered_for_execution(
            runtime=runtime,
            execution_id=ExecutionId(execution_id),
        )
        execution = await runtime.execution_engine.run(ExecutionId(execution_id))
        return _serialize_execution(execution)

    @app.post(
        "/executions/{execution_id}/dispatch",
        dependencies=[Depends(require_permission("executions:manage"))],
    )
    async def dispatch_execution(
        execution_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        await _ensure_project_adapter_registered_for_execution(
            runtime=runtime,
            execution_id=ExecutionId(execution_id),
        )
        dispatched_task = runtime.execution_engine.dispatch(ExecutionId(execution_id))
        execution = await runtime.execution_service.get_execution(ExecutionId(execution_id))
        payload = _serialize_execution(execution)
        payload["dispatched"] = True
        payload["active_in_process"] = runtime.execution_engine.is_active(
            ExecutionId(execution_id)
        )
        payload["task_done"] = dispatched_task.done()
        return payload

    @app.post(
        "/executions/{execution_id}/resolve-context",
        dependencies=[Depends(require_permission("executions:manage"))],
    )
    async def resolve_execution_context(
        execution_id: str,
        request: ResolveExecutionContextRequest,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        await _ensure_project_adapter_registered_for_execution(
            runtime=runtime,
            execution_id=ExecutionId(execution_id),
        )
        package = await runtime.context_service.resolve_execution_context(
            ResolveExecutionContextCommand(
                execution_id=ExecutionId(execution_id),
                source=request.source,
            )
        )
        return {
            "execution_id": str(package.execution_id),
            "project_id": str(package.project_id),
            "provided_at": package.provided_at.isoformat(),
            "requested_references": [
                _serialize_context_reference(reference)
                for reference in package.requested_references
            ],
            "authorized_references": [
                _serialize_context_reference(reference)
                for reference in package.authorized_references
            ],
            "items": [
                _serialize_context_item(item)
                for item in package.items
            ],
            "count": len(package.items),
        }

    @app.get(
        "/executions/{execution_id}/context",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def execution_context(
        execution_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        records = await runtime.context_resolution_repository.list_by_execution(
            ExecutionId(execution_id)
        )
        return {
            "records": [
                _serialize_context_resolution_record(record) for record in records
            ],
            "count": len(records),
        }

    @app.patch(
        "/projects/{project_id}/security",
        dependencies=[Depends(require_permission("projects:connect"))],
    )
    async def update_project_security(
        project_id: str,
        request: ProjectSecurityUpdateRequest,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(request.database_url))
        project = await runtime.project_service.update_security_profile(
            UpdateProjectSecurityCommand(
                project_id=ProjectId(project_id),
                readiness_level=request.readiness_level,
                access_scope=_tuple_or_none(request.access_scope),
                restricted_areas=_tuple_or_none(request.restricted_areas),
                sensitive_patterns=_tuple_or_none(request.sensitive_patterns),
                allow_git_bootstrap=request.allow_git_bootstrap,
                allow_architecture_restructure=request.allow_architecture_restructure,
                allow_cicd_changes=request.allow_cicd_changes,
                allow_cloud_provider_sharing=request.allow_cloud_provider_sharing,
                persist_architecture_summaries=request.persist_architecture_summaries,
                persist_naming_summaries=request.persist_naming_summaries,
                persist_functional_summaries=request.persist_functional_summaries,
                persist_context_snapshots=request.persist_context_snapshots,
            )
        )
        return _serialize_project(project)

    @app.get(
        "/events",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def list_events(
        task_id: str | None = None,
        project_id: str | None = None,
        execution_id: str | None = None,
        event_type: EventType | None = None,
        limit: int = Query(20, ge=1, le=100),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        events = await runtime.event_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            project_id=ProjectId(project_id) if project_id is not None else None,
            execution_id=ExecutionId(execution_id) if execution_id is not None else None,
            event_type=event_type,
            limit=limit,
        )
        return {"events": [_serialize_event(event) for event in events], "count": len(events)}

    @app.get(
        "/audit",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def list_audit(
        task_id: str | None = None,
        project_id: str | None = None,
        execution_id: str | None = None,
        authorization_id: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        records = await runtime.audit_repository.list(
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
        return {
            "records": [_serialize_audit_record(record) for record in records],
            "count": len(records),
        }

    @app.get(
        "/audit/{audit_id}",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def get_audit_record(
        audit_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        record = await runtime.audit_repository.get(AuditRecordId(audit_id))
        return _serialize_audit_record(record)

    @app.get(
        "/metrics",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def list_metrics(
        task_id: str | None = None,
        project_id: str | None = None,
        execution_id: str | None = None,
        name: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        records = await runtime.metrics_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            project_id=ProjectId(project_id) if project_id is not None else None,
            execution_id=ExecutionId(execution_id) if execution_id is not None else None,
            name=name,
            limit=limit,
        )
        return {
            "records": [_serialize_metric_record(record) for record in records],
            "count": len(records),
        }

    @app.get(
        "/metrics/summary",
        tags=["system"],
        summary="Aggregate (count/sum/avg) metrics, grouped by role/action/model/project",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def summarize_metrics(
        project_id: str | None = None,
        name: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        group_by: str = "",
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        try:
            summaries = await runtime.metrics_repository.summarize(
                project_id=ProjectId(project_id) if project_id is not None else None,
                name=name,
                since=since,
                until=until,
                group_by=_parse_group_by(group_by),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "summaries": [_serialize_metric_summary(summary) for summary in summaries],
            "count": len(summaries),
        }

    @app.get(
        "/suggestions",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def list_suggestions(
        task_id: str | None = None,
        limit: int = Query(20, ge=1, le=100),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        suggestions = await runtime.suggestion_repository.list(
            task_id=TaskId(task_id) if task_id is not None else None,
            limit=limit,
        )
        return {
            "suggestions": [_serialize_suggestion(suggestion) for suggestion in suggestions],
            "count": len(suggestions),
        }

    @app.get(
        "/suggestions/{suggestion_id}",
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def get_suggestion(
        suggestion_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        suggestion = await runtime.suggestion_repository.get(SuggestionId(suggestion_id))
        return _serialize_suggestion(suggestion)

    @app.post(
        "/tasks/{task_id}/suggestions",
        dependencies=[Depends(require_permission("suggestions:manage"))],
    )
    async def generate_suggestion(
        task_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Generate a next-step suggestion for a task's current state, on demand."""

        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        task = await runtime.task_service.get_task(TaskId(task_id))
        suggestion = await runtime.suggestion_engine.suggest_next(task)
        return {
            "task_id": task_id,
            "suggestion": _serialize_suggestion(suggestion) if suggestion else None,
        }

    @app.post(
        "/suggestions/{suggestion_id}/accept",
        dependencies=[Depends(require_permission("suggestions:manage"))],
    )
    async def accept_suggestion(
        suggestion_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Mark a suggestion as accepted. Does not itself authorize or execute anything."""

        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        suggestion = await runtime.suggestion_repository.get(SuggestionId(suggestion_id))
        updated = await runtime.suggestion_engine.mark_status(
            suggestion, SuggestionStatus.ACCEPTED
        )
        return _serialize_suggestion(updated)

    @app.post(
        "/suggestions/{suggestion_id}/reject",
        dependencies=[Depends(require_permission("suggestions:manage"))],
    )
    async def reject_suggestion(
        suggestion_id: str,
        database_url: str | None = None,
    ) -> dict[str, Any]:
        """Mark a suggestion as rejected."""

        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        suggestion = await runtime.suggestion_repository.get(SuggestionId(suggestion_id))
        updated = await runtime.suggestion_engine.mark_status(
            suggestion, SuggestionStatus.REJECTED
        )
        return _serialize_suggestion(updated)

    # -----------------------------------------------------------------------
    # Chat-First Request Interface (ADR-011)
    # -----------------------------------------------------------------------

    @app.post(
        "/requests",
        tags=["requests"],
        summary="Create a request — chat-first entry point for external clients",
        description=(
            "Accepts a project path, AI model, role, action, and a natural language "
            "prompt. OrchAI creates a Task and orchestrates the full flow. "
            "Returns request_id and current status. In SUGGESTED mode (default), "
            "also returns the generated suggestion and an approve_url."
        ),
        dependencies=[Depends(require_permission("requests:create"))],
    )
    async def create_request(request: ChatRequest) -> dict[str, Any]:
        settings = _settings_override(request.database_url)
        url = settings.database.sqlalchemy_url

        # Derive title from first line of prompt if not explicitly provided
        prompt_lines = request.prompt.strip().splitlines()
        title = request.title or (prompt_lines[0][:120] if prompt_lines else "Untitled request")

        # Use first context path if provided, otherwise use project root as context
        context_path = request.context_paths[0] if request.context_paths else "."

        flow_result = await run_local_flow(
            project_root=Path(request.project_root),
            context_path=context_path,
            title=title,
            model=request.model or settings.ai_provider.model or "local-demo",
            dependencies=build_local_flow_dependencies_from_settings(settings),
            storage_label=url,
            provider_target=request.provider_target,
            execution_mode=request.execution_mode,
            approve_suggestion=request.approve_suggestion,
        )

        request_id = flow_result.get("task_id", "")
        runtime = build_sqlalchemy_runtime(url)
        snapshot = await collect_task_snapshot(
            runtime=runtime,
            task_id=TaskId(request_id),
            history_limit=50,
        )

        flow = _serialize_request_flow(snapshot, request_id=request_id)
        return {
            **flow,
            "role": request.role.value if request.role is not None else None,
            "action": request.action.value if request.action is not None else None,
            "prompt": request.prompt,
        }

    @app.get(
        "/requests/{request_id}/flow",
        tags=["requests"],
        summary="Observe the full orchestration flow for a request",
        description=(
            "Returns the complete observable state of a request: task, "
            "orchestration steps (audit), authorizations, executions, "
            "context metadata, suggestions, events, and aggregated metrics. "
            "This is the primary data source for a chat-interface progress view."
        ),
        dependencies=[Depends(require_permission("projects:read"))],
    )
    async def get_request_flow(
        request_id: str,
        history_limit: int = Query(100, ge=1, le=500),
        database_url: str | None = None,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        snapshot = await collect_task_snapshot(
            runtime=runtime,
            task_id=TaskId(request_id),
            history_limit=history_limit,
        )
        return _serialize_request_flow(snapshot, request_id=request_id)

    @app.post(
        "/requests/{request_id}/approve",
        tags=["requests"],
        summary="Approve a pending suggestion and continue the orchestration flow",
        description=(
            "Records an explicit user approval for this request and continues "
            "the orchestration flow. Covers two cases: (1) a standalone "
            "Authorization already exists in a pending (undecided) state — it "
            "is granted directly; (2) the far more common SUGGESTED-mode case, "
            "where a stage was blocked before any Authorization was ever "
            "created and only a PRESENTED suggestion exists — this is resolved "
            "by delegating internally to the same gated single-stage-advance "
            "mechanism used by POST /requests/{request_id}/advance with "
            "approve_stage=true. Neither case bypasses authorization policy: "
            "both still pass through policy evaluation and record an explicit "
            "decision."
        ),
        dependencies=[Depends(require_permission("requests:approve"))],
    )
    async def approve_request(
        request_id: str,
        body: RequestApproveBody,
    ) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(body.database_url))

        # Case 1: a standalone Authorization is already pending (undecided) —
        # e.g. created directly via POST /authorizations/request against this
        # task, outside the orchestrator's own request/decide flow. Find the
        # most recent one explicitly by created_at: repository implementations
        # do not guarantee a common ordering (in-memory preserves insertion
        # order, SQLAlchemy orders by created_at desc), so relying on list
        # position would silently pick the wrong record on Postgres.
        pending = await runtime.authorization_service.list_authorizations(
            task_id=TaskId(request_id),
            pending_only=True,
            limit=20,
        )

        if pending:
            authorization = max(pending, key=lambda a: a.request.created_at)
            updated = await runtime.authorization_service.decide_authorization(
                DecideAuthorizationCommand(
                    authorization_id=authorization.id,
                    status=AuthorizationDecisionStatus.GRANTED,
                    decided_by=body.decided_by,
                    reason=body.reason,
                )
            )
            return {
                "request_id": request_id,
                "approved": True,
                "status": "GRANTED",
                "authorization_id": str(updated.id),
                "flow_url": f"/requests/{request_id}/flow",
                "advance_url": f"/requests/{request_id}/advance",
                "message": "Authorization granted. Use advance_url to continue to the next stage.",
            }

        # Case 2: no standalone Authorization exists yet. In SUGGESTED mode
        # (the default execution mode), run_task_workflow_stage returns before
        # ever creating an Authorization when policy blocks — only the
        # suggestion is marked PRESENTED. That PRESENTED suggestion is the
        # signal that there is something here to approve.
        suggestions = await runtime.suggestion_repository.list(
            task_id=TaskId(request_id),
            limit=20,
        )
        pending_suggestion = max(
            (s for s in suggestions if s.status is SuggestionStatus.PRESENTED),
            key=lambda s: s.generated_at,
            default=None,
        )
        if pending_suggestion is None:
            return {
                "request_id": request_id,
                "approved": False,
                "status": "no_pending_authorization",
                "message": (
                    "No pending authorization or presented suggestion found "
                    "for this request. The flow may have already proceeded, "
                    "or no suggestion was generated yet."
                ),
                "flow_url": f"/requests/{request_id}/flow",
            }

        # Delegate to the same gated mechanism used by /advance, passing
        # approve_stage explicitly. This is still an explicit human decision
        # evaluated by policy — not a bypass: if policy still refuses (e.g.
        # execution mode/config changed underneath), the result comes back
        # blocked exactly as /advance would report it.
        settings = _settings_override(body.database_url)
        url = settings.database.sqlalchemy_url
        result = await run_task_workflow_stage(
            task_id=request_id,
            dependencies=build_local_flow_dependencies_from_settings(settings),
            storage_label=url,
            model=body.model or settings.ai_provider.model or "local-task-stage",
            context_paths=tuple(body.context_paths),
            documentation_path=body.documentation_path,
            test_args=tuple(body.test_args),
            provider_target=body.provider_target,
            approve_stage=True,
            requester=body.decided_by,
            decider=body.decided_by,
        )
        return {
            "request_id": request_id,
            "approved": not result.get("blocked_reason"),
            **result,
            "flow_url": f"/requests/{request_id}/flow",
        }

    @app.post(
        "/requests/{request_id}/advance",
        tags=["requests"],
        summary="Advance a request to the next workflow stage",
        description=(
            "Drives the request through the next orchestration stage "
            "(PLANNING → IMPLEMENT → REVIEW → VALIDATION → TEST → DOCUMENT). "
            "Equivalent to POST /tasks/{task_id}/advance but under the request surface."
        ),
        dependencies=[Depends(require_permission("requests:advance"))],
    )
    async def advance_request(
        request_id: str,
        body: RequestAdvanceBody,
    ) -> dict[str, Any]:
        settings = _settings_override(body.database_url)
        url = settings.database.sqlalchemy_url

        result = await run_task_workflow_stage(
            task_id=request_id,
            dependencies=build_local_flow_dependencies_from_settings(settings),
            storage_label=url,
            model=body.model or settings.ai_provider.model or "local-task-stage",
            stage=body.stage,
            context_paths=tuple(body.context_paths),
            documentation_path=body.documentation_path,
            test_args=tuple(body.test_args),
            provider_target=body.provider_target,
            execution_mode=body.execution_mode,
            approve_stage=body.approve_stage,
            requester=body.requester,
            decider=body.decider,
        )
        return {
            "request_id": request_id,
            **result,
            "flow_url": f"/requests/{request_id}/flow",
        }

    # -----------------------------------------------------------------
    # User-configuration CRUD (admin + self-service, ADR-012)
    # -----------------------------------------------------------------

    @app.get(
        "/admin/users",
        tags=["admin"],
        summary="List every user in the system with full admin details",
        dependencies=[Depends(require_permission("admin:manage_users"))],
    )
    async def admin_list_users(
        is_active: bool | None = None,
        limit: int = Query(20, ge=1, le=100),
    ) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        service = identity_runtime.identity_service
        users = await service.list_users(is_active=is_active, limit=limit)
        # Connections are descriptive project-DB metadata, not identity data
        # (see `ProjectConnectionRepository`'s module docstring) -- resolved
        # against the default primary database, matching every other
        # unscoped admin lookup in this module.
        project_runtime = build_sqlalchemy_runtime(_database_url(None))
        connection_repository = SQLAlchemyProjectConnectionRepository(
            project_runtime.database
        )
        result = []
        for user in users:
            roles = await service.list_roles_for_user(user.id)
            connected_project_ids = await connection_repository.list_project_ids_for_user(
                user.id
            )
            result.append(
                _serialize_user(
                    user,
                    access_roles=roles,
                    connected_project_ids=tuple(
                        str(project_id) for project_id in connected_project_ids
                    ),
                )
            )
        return {"users": result, "count": len(result)}

    @app.post(
        "/admin/users",
        tags=["admin"],
        summary="Create a new user together with its initial access roles",
        dependencies=[Depends(require_permission("admin:manage_users"))],
    )
    async def admin_create_user(request: AdminCreateUserRequest) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        service = identity_runtime.identity_service
        try:
            user = await service.create_user_with_roles(
                CreateUserWithRolesCommand(
                    username=request.username,
                    plain_password=request.password,
                    role_ids=tuple(AccessRoleId(rid) for rid in request.role_ids),
                    email=request.email,
                    is_superuser=request.is_superuser,
                )
            )
        except DuplicateUsernameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except UserRequiresAccessRoleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(
                status_code=404, detail=f"unknown access role: {exc}"
            ) from exc
        roles = await service.list_roles_for_user(user.id)
        return _serialize_user(user, access_roles=roles)

    @app.put(
        "/admin/users/{user_id}/access-roles",
        tags=["admin"],
        summary="Replace the full set of access roles assigned to a user",
        dependencies=[Depends(require_permission("admin:manage_users"))],
    )
    async def admin_set_user_access_roles(
        user_id: str,
        request: SetAccessRolesRequest,
    ) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        service = identity_runtime.identity_service
        try:
            await service.set_access_roles_for_user(
                SetAccessRolesForUserCommand(
                    user_id=UserId(user_id),
                    role_ids=tuple(AccessRoleId(rid) for rid in request.role_ids),
                )
            )
        except UserRequiresAccessRoleError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        user = await service.get_user(UserId(user_id))
        roles = await service.list_roles_for_user(user.id)
        return _serialize_user(user, access_roles=roles)

    @app.get(
        "/admin/access-roles",
        tags=["admin"],
        summary="List every access role with its linked users and permissions",
        dependencies=[Depends(require_permission("admin:manage_users"))],
    )
    async def admin_list_access_roles(
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        service = identity_runtime.identity_service
        roles = await service.list_access_roles(limit=limit)
        result = []
        for role in roles:
            permissions = await service.list_permissions_for_role(role.id)
            users = await service.list_users_for_role(role.id)
            result.append(
                _serialize_access_role(role, permissions=permissions, users=users)
            )
        return {"access_roles": result, "count": len(result)}

    @app.post(
        "/admin/access-roles",
        tags=["admin"],
        summary="Create a new access role",
        dependencies=[Depends(require_permission("admin:manage_users"))],
    )
    async def admin_create_access_role(
        request: AdminCreateAccessRoleRequest,
    ) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        service = identity_runtime.identity_service
        try:
            role = await service.create_access_role(
                CreateAccessRoleCommand(
                    name=request.name,
                    description=request.description,
                )
            )
        except DuplicateAccessRoleNameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _serialize_access_role(role)

    @app.put(
        "/admin/access-roles/{role_id}/permissions",
        tags=["admin"],
        summary="Replace the full set of permissions bundled into an access role",
        dependencies=[Depends(require_permission("admin:manage_users"))],
    )
    async def admin_set_role_permissions(
        role_id: str,
        request: SetRolePermissionsRequest,
    ) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        service = identity_runtime.identity_service
        try:
            await service.set_permissions_for_role(
                SetPermissionsForRoleCommand(
                    role_id=AccessRoleId(role_id),
                    permission_ids=tuple(
                        PermissionId(pid) for pid in request.permission_ids
                    ),
                )
            )
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        role = await service.get_access_role(AccessRoleId(role_id))
        permissions = await service.list_permissions_for_role(role.id)
        users = await service.list_users_for_role(role.id)
        return _serialize_access_role(role, permissions=permissions, users=users)

    @app.get(
        "/admin/projects",
        tags=["admin"],
        summary="List every project in the system with full admin details",
        dependencies=[Depends(require_permission("admin:manage_projects"))],
    )
    async def admin_list_projects(database_url: str | None = None) -> dict[str, Any]:
        runtime = build_sqlalchemy_runtime(_database_url(database_url))
        projects = await runtime.project_service.list_projects()
        connection_repository = SQLAlchemyProjectConnectionRepository(
            runtime.database
        )
        result = []
        for project in projects:
            connected_user_ids = await connection_repository.list_user_ids_for_project(
                project.id
            )
            serialized = _serialize_project(project)
            serialized["connected_user_ids"] = [
                str(user_id) for user_id in connected_user_ids
            ]
            result.append(serialized)
        return {"projects": result, "count": len(result)}

    @app.get(
        "/me",
        tags=["me"],
        summary="Show the logged-in user's own profile",
    )
    async def show_me(
        claims: AccessTokenClaims = Depends(require_authenticated_user()),
    ) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        service = identity_runtime.identity_service
        user = await service.get_user(claims.user_id)
        roles = await service.list_roles_for_user(user.id)
        project_runtime = build_sqlalchemy_runtime(_database_url(None))
        connection_repository = SQLAlchemyProjectConnectionRepository(
            project_runtime.database
        )
        connected_project_ids = await connection_repository.list_project_ids_for_user(
            user.id
        )
        return _serialize_user(
            user,
            access_roles=roles,
            connected_project_ids=tuple(
                str(project_id) for project_id in connected_project_ids
            ),
        )

    @app.patch(
        "/me",
        tags=["me"],
        summary="Update the logged-in user's own profile (username/email only)",
    )
    async def update_me(
        request: MeUpdateRequest,
        claims: AccessTokenClaims = Depends(require_authenticated_user()),
    ) -> dict[str, Any]:
        identity_runtime = build_identity_runtime_from_settings(load_settings())
        service = identity_runtime.identity_service
        try:
            user = await service.update_user_profile(
                UpdateUserProfileCommand(
                    user_id=claims.user_id,
                    username=request.username,
                    email=request.email,
                )
            )
        except DuplicateUsernameError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        roles = await service.list_roles_for_user(user.id)
        return _serialize_user(user, access_roles=roles)

    @app.get(
        "/me/projects",
        tags=["me"],
        summary="List the projects the logged-in user has connected to OrchAI",
    )
    async def list_me_projects(
        claims: AccessTokenClaims = Depends(require_authenticated_user()),
    ) -> dict[str, Any]:
        project_runtime = build_sqlalchemy_runtime(_database_url(None))
        connection_repository = SQLAlchemyProjectConnectionRepository(
            project_runtime.database
        )
        project_ids = await connection_repository.list_project_ids_for_user(
            claims.user_id
        )
        projects = [
            _serialize_project(await project_runtime.project_service.get_project(pid))
            for pid in project_ids
        ]
        return {"projects": projects, "count": len(projects)}

    # OrchAI Desktop (ADR-017): when the desktop shell has a built frontend
    # available, it points ORCHAI_DESKTOP_STATIC_DIR at it before creating
    # this app. Mounted under /app, not "/" -- the API already owns "/"
    # (the entry-points index above) and every other top-level path; a
    # mount at "/" would never be reached for those exact paths, since
    # explicit routes registered earlier always match first, but would
    # still shadow any *new* top-level API route added later. No-op for
    # every other caller (CLI, direct HTTP, tests): the env var is unset
    # by default.
    desktop_static_dir = os.environ.get("ORCHAI_DESKTOP_STATIC_DIR")
    if desktop_static_dir and Path(desktop_static_dir).is_dir():
        app.mount(
            "/app",
            StaticFiles(directory=desktop_static_dir, html=True),
            name="orchai-desktop-frontend",
        )

    return app


def _database_url(url: str | None) -> str:
    if url is None:
        return load_settings().database.sqlalchemy_url
    return DatabaseSettings(url=url).sqlalchemy_url


def _parse_group_by(value: str) -> tuple[str, ...]:
    return tuple(field.strip() for field in value.split(",") if field.strip())


def _settings_override(database_url: str | None) -> OrchAISettings:
    settings = load_settings()
    if database_url is None:
        return settings
    return settings.model_copy(
        update={"database": DatabaseSettings(url=database_url)},
    )


async def _resolve_policy_project_context(
    *,
    runtime,
    project_id: str | None,
    project_root: str | None,
    fallback_readiness_level: ProjectReadinessLevel | None,
):
    if project_id is not None:
        project = await runtime.project_service.get_project(ProjectId(project_id))
        return project.readiness_level, project.security_profile
    if project_root is not None:
        adapter = LocalFilesystemProjectAdapter(Path(project_root))
        readiness = await adapter.assess_readiness()
        return readiness.readiness_level, readiness.security_profile
    if fallback_readiness_level is not None:
        return (
            fallback_readiness_level,
            ProjectSecurityProfile(readiness_level=fallback_readiness_level),
        )
    default_profile = ProjectSecurityProfile()
    return default_profile.readiness_level, default_profile


async def _ensure_project_adapter_registered_for_execution(
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


def _tuple_or_none(values: list[str] | None) -> tuple[str, ...] | None:
    if values is None:
        return None
    return tuple(values)


def _serialize_module(module) -> dict[str, Any]:
    # `system_prompt` is deliberately never included (ADR-015 invariant #2)
    # -- it is internal orchestration configuration, not display metadata.
    return {
        "module_id": str(module.id),
        "name": module.name,
        "description": module.description,
        "default_role": module.default_role.value,
        "allowed_roles": sorted(role.value for role in module.allowed_roles),
        "allowed_actions": sorted(action.value for action in module.allowed_actions),
        "suggested_models": list(module.suggested_models),
        "project_adapter_kind": module.project_adapter_kind,
        "task_pipeline_mode": module.task_pipeline_mode,
        "requires_project": module.requires_project,
    }


def _serialize_conversation(conversation) -> dict[str, Any]:
    return {
        "conversation_id": str(conversation.id),
        "module_id": str(conversation.module_id),
        "project_id": str(conversation.project_id) if conversation.project_id else None,
        "title": conversation.title,
        "created_at": conversation.created_at.isoformat(),
        "archived": conversation.archived,
    }


def _serialize_message(message) -> dict[str, Any]:
    return {
        "message_id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "role": message.role.value,
        "content": message.content,
        "created_at": message.created_at.isoformat(),
        "status": message.status.value,
        "error": message.error,
        "provider_name": message.provider_name,
        "model_id": str(message.model_id) if message.model_id else None,
        "linked_task_id": str(message.linked_task_id) if message.linked_task_id else None,
        "linked_execution_id": str(message.linked_execution_id)
        if message.linked_execution_id
        else None,
        "resource_usage": {
            "input_tokens": message.resource_usage.input_tokens,
            "output_tokens": message.resource_usage.output_tokens,
            "estimated_cost": message.resource_usage.estimated_cost,
        },
    }


def _serialize_stream_event(event) -> str:
    """Format one `ConversationStreamEvent` as an SSE `data:` line (Phase 4)."""

    payload: dict[str, Any] = {"type": event.type}
    if event.type == "delta":
        payload["content"] = event.content
    else:
        payload["message"] = _serialize_message(event.message) if event.message else None
    if event.type == "error":
        payload["error"] = event.error
    return f"data: {json.dumps(payload)}\n\n"


def _serialize_project(project) -> dict[str, Any]:
    return {
        "project_id": str(project.id),
        "name": project.name,
        "root_location": project.root_location,
        "adapter_type": project.adapter_type,
        "status": project.status.value,
        "capabilities": sorted(capability.value for capability in project.capabilities),
        "effective_readiness_level": project.readiness_level.value,
        "observed_readiness_level": project.observed_readiness_level.value,
        "security_profile": project.security_profile.as_dict(),
        "observed_security_profile": project.observed_security_profile.as_dict(),
    }


def _serialize_user(
    user,
    *,
    access_roles: tuple[Any, ...] = (),
    connected_project_ids: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Serialize a user record for the admin/self CRUD surface.

    `password_hash` is intentionally never included -- see
    `IDENTITY-AND-ACCESS-MODEL.md`'s "claro que a senha é uma exceção"
    requirement.
    """

    return {
        "user_id": str(user.id),
        "username": user.username,
        "email": user.email,
        "is_superuser": user.is_superuser,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
        "updated_at": user.updated_at.isoformat(),
        "access_roles": [
            {"role_id": str(role.id), "name": role.name} for role in access_roles
        ],
        "connected_project_ids": list(connected_project_ids),
    }


def _serialize_access_role(
    role,
    *,
    permissions: tuple[Any, ...] = (),
    users: tuple[Any, ...] = (),
) -> dict[str, Any]:
    return {
        "role_id": str(role.id),
        "name": role.name,
        "description": role.description,
        "permissions": [
            {
                "permission_id": str(permission.id),
                "key": permission.key,
                "description": permission.description,
            }
            for permission in permissions
        ],
        "users": [
            {"user_id": str(user.id), "username": user.username} for user in users
        ],
    }


def _serialize_permission(permission) -> dict[str, Any]:
    return {
        "permission_id": str(permission.id),
        "key": permission.key,
        "description": permission.description,
    }


def _serialize_task(task) -> dict[str, Any]:
    return {
        "task_id": str(task.id),
        "project_id": str(task.project_id) if task.project_id is not None else None,
        "title": task.title,
        "description": task.description,
        "state": task.state.value,
        "available_transitions": _task_available_transitions(task.state),
        "execution_mode": task.execution_mode.value,
        "scope": {
            "requested_change": task.scope.requested_change,
            "acceptance_criteria": list(task.scope.acceptance_criteria),
            "constraints": list(task.scope.constraints),
            "exclusions": list(task.scope.exclusions),
        },
    }


def _serialize_authorization(authorization) -> dict[str, Any]:
    current_decision = authorization.current_decision
    operation = authorization.request.operation
    return {
        "authorization_id": str(authorization.id),
        "task_id": str(authorization.task_id),
        "status": authorization.status.value if authorization.status is not None else None,
        "request": {
            "role": operation.role.value,
            "action": operation.action.value,
            "model_id": str(operation.model_id) if operation.model_id is not None else None,
            "context_scope": list(operation.context_scope),
            "proposed_state": (
                operation.proposed_state.value
                if operation.proposed_state is not None
                else None
            ),
            "reason": authorization.request.reason,
            "requester": authorization.request.requester,
            "execution_mode": authorization.request.execution_mode.value,
            "created_at": authorization.request.created_at.isoformat(),
            "expires_at": (
                authorization.request.expires_at.isoformat()
                if authorization.request.expires_at is not None
                else None
            ),
        },
        "current_decision": (
            {
                "decision_id": str(current_decision.id),
                "status": current_decision.status.value,
                "decided_by": current_decision.decided_by,
                "reason": current_decision.reason,
                "decided_at": current_decision.decided_at.isoformat(),
            }
            if current_decision is not None
            else None
        ),
        "decisions": [
            {
                "decision_id": str(decision.id),
                "status": decision.status.value,
                "decided_by": decision.decided_by,
                "reason": decision.reason,
                "decided_at": decision.decided_at.isoformat(),
            }
            for decision in authorization.decisions
        ],
    }


def _serialize_context_reference(reference) -> dict[str, Any]:
    return {
        "source": reference.source.value,
        "resource": reference.resource,
        "scope": reference.scope,
        "version": reference.version,
        "requires_authorization": reference.requires_authorization,
    }


def _serialize_context_item(item) -> dict[str, Any]:
    return {
        "reference": _serialize_context_reference(item.reference),
        "content": item.content,
        "metadata": dict(item.metadata),
    }


def _serialize_execution(execution) -> dict[str, Any]:
    resource_usage = execution.result.resource_usage if execution.result is not None else None
    return {
        "execution_id": str(execution.id),
        "task_id": str(execution.task_id),
        "project_id": str(execution.project_id) if execution.project_id is not None else None,
        "authorization_id": str(execution.authorization_id),
        "role": execution.role.value,
        "action": execution.action.value,
        "model_id": str(execution.model_id),
        "state": execution.state.value,
        "available_transitions": _execution_available_transitions(execution.state),
        "requested_context": list(execution.requested_context),
        "authorized_context": list(execution.authorized_context),
        "created_at": execution.created_at.isoformat(),
        "started_at": execution.started_at.isoformat()
        if execution.started_at is not None
        else None,
        "completed_at": execution.completed_at.isoformat()
        if execution.completed_at is not None
        else None,
        "result": {
            "output": execution.result.output,
            "success": execution.result.success,
            "errors": list(execution.result.errors),
            "warnings": list(execution.result.warnings),
            "metadata": dict(execution.result.metadata),
            "resource_usage": {
                "input_tokens": resource_usage.input_tokens if resource_usage else None,
                "output_tokens": resource_usage.output_tokens if resource_usage else None,
                "total_tokens": resource_usage.total_tokens if resource_usage else None,
                "estimated_cost": resource_usage.estimated_cost
                if resource_usage
                else None,
                "metadata": dict(resource_usage.metadata) if resource_usage else {},
            },
        }
        if execution.result is not None
        else None,
    }


def _serialize_context_resolution_record(record) -> dict[str, Any]:
    reference = record.reference
    return {
        "context_resolution_id": str(record.id),
        "execution_id": str(record.execution_id),
        "project_id": str(record.project_id),
        "resolved_at": record.resolved_at.isoformat(),
        "content_sha256": record.content_sha256,
        "content_bytes": record.content_bytes,
        "reference": {
            "source": reference.source.value,
            "resource": reference.resource,
            "scope": reference.scope,
            "version": reference.version,
            "requires_authorization": reference.requires_authorization,
        },
        "metadata": dict(record.metadata),
    }


def _serialize_resource(resource) -> dict[str, Any]:
    return {
        "resource": resource.resource,
        "source": resource.source.value,
        "capabilities": sorted(capability.value for capability in resource.capabilities),
        "provider_sharing_level": resource.provider_sharing_level.value,
        "persistence_classification": resource.persistence_classification.value,
        "restricted": resource.restricted,
        "metadata": dict(resource.metadata),
    }


def _serialize_readiness(readiness) -> dict[str, Any]:
    return {
        "readiness_level": readiness.readiness_level.value,
        "reasons": list(readiness.reasons),
        "has_git": readiness.has_git,
        "has_documentation": readiness.has_documentation,
        "has_tests": readiness.has_tests,
        "security_profile": readiness.security_profile.as_dict(),
        "metadata": dict(readiness.metadata),
    }


def _serialize_event(event) -> dict[str, Any]:
    return {
        "event_id": str(event.event_id),
        "event_type": event.event_type.value,
        "source": event.source,
        "occurred_at": event.occurred_at.isoformat(),
        "task_id": str(event.task_id) if event.task_id is not None else None,
        "project_id": str(event.project_id) if event.project_id is not None else None,
        "execution_id": str(event.execution_id) if event.execution_id is not None else None,
        "payload": dict(event.payload),
    }


def _serialize_audit_record(record) -> dict[str, Any]:
    return {
        "audit_id": str(record.id),
        "occurred_at": record.occurred_at.isoformat(),
        "actor": record.actor,
        "operation": record.operation,
        "outcome": record.outcome,
        "task_id": str(record.task_id) if record.task_id is not None else None,
        "project_id": str(record.project_id) if record.project_id is not None else None,
        "execution_id": str(record.execution_id) if record.execution_id is not None else None,
        "authorization_id": (
            str(record.authorization_id) if record.authorization_id is not None else None
        ),
        "event_id": str(record.event_id) if record.event_id is not None else None,
        "correlation_id": (
            str(record.correlation_id) if record.correlation_id is not None else None
        ),
        "causation_id": (
            str(record.causation_id) if record.causation_id is not None else None
        ),
        "metadata": dict(record.metadata),
    }


def _serialize_metric_record(record) -> dict[str, Any]:
    return {
        "metric_id": str(record.id),
        "observed_at": record.observed_at.isoformat(),
        "name": record.name,
        "value": record.value,
        "unit": record.unit,
        "task_id": str(record.task_id) if record.task_id is not None else None,
        "project_id": str(record.project_id) if record.project_id is not None else None,
        "execution_id": str(record.execution_id) if record.execution_id is not None else None,
        "dimensions": dict(record.dimensions),
    }


def _serialize_metric_summary(summary) -> dict[str, Any]:
    return {
        "name": summary.name,
        "unit": summary.unit,
        "count": summary.count,
        "sum": summary.sum,
        "avg": summary.avg,
        "dimensions": dict(summary.dimensions),
    }


def _serialize_automatic_policy(policy: AutomaticExecutionPolicy) -> dict[str, Any]:
    return {
        "allowed_operations": [
            {"role": role.value, "action": action.value}
            for role, action in policy.allowed_operations
        ],
        "allowed_cross_role_transitions": [
            {"previous_role": previous.value, "next_role": next_role.value}
            for previous, next_role in policy.allowed_cross_role_transitions
        ],
        "allow_model_substitution": policy.allow_model_substitution,
        "allow_context_expansion": policy.allow_context_expansion,
    }


def _serialize_suggestion(suggestion) -> dict[str, Any]:
    return {
        "suggestion_id": str(suggestion.id),
        "task_id": str(suggestion.task_id),
        "related_execution_id": (
            str(suggestion.related_execution_id)
            if suggestion.related_execution_id is not None
            else None
        ),
        "suggested_role": suggestion.suggested_role.value,
        "suggested_action": suggestion.suggested_action.value,
        "rationale": suggestion.rationale,
        "required_capabilities": sorted(
            capability.value for capability in suggestion.required_capabilities
        ),
        "expected_impact": suggestion.expected_impact,
        "authorization_required": suggestion.authorization_required,
        "confidence": suggestion.confidence,
        "status": suggestion.status.value,
        "generated_at": suggestion.generated_at.isoformat(),
        "metadata": dict(suggestion.metadata),
    }


def _serialize_task_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "task": _serialize_task(snapshot["task"]),
        "authorizations": [
            _serialize_authorization(authorization)
            for authorization in snapshot["authorizations"]
        ],
        "executions": [
            _serialize_execution(execution) for execution in snapshot["executions"]
        ],
        "suggestions": [
            _serialize_suggestion(suggestion) for suggestion in snapshot["suggestions"]
        ],
        "events": [_serialize_event(event) for event in snapshot["events"]],
        "audit_records": [
            _serialize_audit_record(record) for record in snapshot["audit_records"]
        ],
        "metric_records": [
            _serialize_metric_record(record)
            for record in snapshot["metric_records"]
        ],
        "context_records": [
            _serialize_context_resolution_record(record)
            for record in snapshot["context_records"]
        ],
        "counts": {
            "authorizations": len(snapshot["authorizations"]),
            "executions": len(snapshot["executions"]),
            "suggestions": len(snapshot["suggestions"]),
            "events": len(snapshot["events"]),
            "audit_records": len(snapshot["audit_records"]),
            "metric_records": len(snapshot["metric_records"]),
            "context_records": len(snapshot["context_records"]),
        },
        "history_limit": snapshot["history_limit"],
    }


def _serialize_request_flow(snapshot: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    """Serialize the full orchestration flow for the chat-first request interface.

    Returns a unified view of task state, authorizations, executions, suggestions,
    events, audit, metrics, and context — structured for a conversational UI to
    render as a live progress view (GET /requests/{request_id}/flow).
    """
    task = snapshot["task"]
    executions = snapshot["executions"]
    suggestions = snapshot["suggestions"]
    authorizations = snapshot["authorizations"]

    # Derive a high-level request status from the current task and suggestion state
    task_state = task.state.value
    if task_state == "COMPLETED":
        status = "COMPLETED"
    elif task_state in ("CANCELLED",):
        status = "CANCELLED"
    elif task_state in ("FAILED",):
        status = "FAILED"
    elif suggestions and any(
        s.status is SuggestionStatus.PRESENTED for s in suggestions
    ):
        status = "PENDING_SUGGESTION"
    elif authorizations and any(a.status is None for a in authorizations):
        status = "PENDING_AUTHORIZATION"
    elif executions and any(
        getattr(e.state, "value", None) == "RUNNING" for e in executions
    ):
        status = "RUNNING"
    else:
        status = "IN_PROGRESS"

    rid = request_id or str(task.id)

    # Select "most recent" explicitly by timestamp rather than list position:
    # repository implementations do not share a common ordering (in-memory
    # preserves insertion order, SQLAlchemy orders list() results newest-first),
    # so relying on reversed()/[-1] silently picks the wrong record on Postgres.
    pending_suggestion = max(
        (s for s in suggestions if s.status is SuggestionStatus.PRESENTED),
        key=lambda s: s.generated_at,
        default=None,
    )
    latest_execution = max(executions, key=lambda e: e.created_at, default=None)
    pending_authorization = max(
        (a for a in authorizations if a.status is None),
        key=lambda a: a.request.created_at,
        default=None,
    )

    return {
        "request_id": rid,
        "status": status,
        "task": _serialize_task(task),
        "suggestion": _serialize_suggestion(pending_suggestion) if pending_suggestion else None,
        "execution": _serialize_execution(latest_execution) if latest_execution else None,
        "pending_authorization_id": (
            str(pending_authorization.id) if pending_authorization else None
        ),
        "authorizations": [_serialize_authorization(a) for a in authorizations],
        "executions": [_serialize_execution(e) for e in executions],
        "suggestions": [_serialize_suggestion(s) for s in suggestions],
        "events": [_serialize_event(e) for e in snapshot["events"]],
        "audit_records": [_serialize_audit_record(r) for r in snapshot["audit_records"]],
        "metric_records": [_serialize_metric_record(r) for r in snapshot["metric_records"]],
        "context_records": [
            _serialize_context_resolution_record(r) for r in snapshot["context_records"]
        ],
        "counts": {
            "authorizations": len(authorizations),
            "executions": len(executions),
            "suggestions": len(suggestions),
            "events": len(snapshot["events"]),
            "audit_records": len(snapshot["audit_records"]),
            "metric_records": len(snapshot["metric_records"]),
            "context_records": len(snapshot["context_records"]),
        },
        "flow_url": f"/requests/{rid}/flow",
        "approve_url": f"/requests/{rid}/approve",
        "advance_url": f"/requests/{rid}/advance",
        "snapshot_url": f"/tasks/{rid}/snapshot",
    }


def _task_available_transitions(state: TaskState) -> list[str]:
    machine = TaskStateMachine.default()
    return sorted(target.value for target in machine.available_targets(state))


def _execution_available_transitions(state: ExecutionState) -> list[str]:
    machine = ExecutionStateMachine.default()
    return sorted(target.value for target in machine.available_targets(state))


def _safe_database_label(url: str) -> str:
    if "@" not in url or ":" not in url:
        return url
    prefix, suffix = url.split("@", maxsplit=1)
    if ":" not in prefix:
        return url
    username, _password = prefix.rsplit(":", maxsplit=1)
    return f"{username}:***@{suffix}"


app = create_app()
