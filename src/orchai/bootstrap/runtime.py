"""Runtime dependency composition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Protocol

from orchai.application.audit import AuditEventHandler, AuditRepository
from orchai.application.authorization import AuthorizationService
from orchai.application.authorization.ports import AuthorizationRepository
from orchai.application.context import ContextService
from orchai.application.context.ports import ContextResolutionRepository
from orchai.application.conversations import ConversationAIProviderPort, ConversationService
from orchai.application.events import EventEngine, EventRepository
from orchai.application.executions import ExecutionService
from orchai.application.executions.engine import ExecutionEngine
from orchai.application.executions.ports import AIProviderPort, ExecutionRepository
from orchai.application.identity import IdentityService
from orchai.application.metrics import MetricsEventHandler, MetricsRepository
from orchai.application.modules import get_module as _get_module
from orchai.application.orchestration.local_flow import LocalFlowDependencies
from orchai.application.orchestration.orchestrator import Orchestrator
from orchai.application.policies import (
    AutomaticExecutionPolicy,
    AutomaticPolicyRepository,
    AutomaticPolicyService,
    LocalPolicyService,
)
from orchai.application.projects import ProjectService
from orchai.application.projects.ports import (
    ProjectAdapter,
    ProjectAdapterRegistry,
    ProjectRepository,
)
from orchai.application.suggestions import SuggestionEngine, SuggestionRepository
from orchai.application.tasks import TaskService
from orchai.application.tasks.ports import TaskRepository
from orchai.infrastructure.ai import LiteLLMProvider, StubAIProviderAdapter
from orchai.infrastructure.configuration import OrchAISettings, load_settings
from orchai.infrastructure.identity import (
    Argon2PasswordHasher,
    JWTAccessTokenIssuer,
    Sha256RefreshTokenHasher,
)
from orchai.infrastructure.persistence import (
    InMemoryAuditRepository,
    InMemoryAuthorizationRepository,
    InMemoryAutomaticPolicyRepository,
    InMemoryContextResolutionRepository,
    InMemoryConversationRepository,
    InMemoryEventRepository,
    InMemoryExecutionRepository,
    InMemoryMessageRepository,
    InMemoryMetricsRepository,
    InMemoryProjectRepository,
    InMemorySuggestionRepository,
    InMemoryTaskRepository,
    SQLAlchemyAccessControlRepository,
    SQLAlchemyAccessRoleRepository,
    SQLAlchemyAuditRepository,
    SQLAlchemyAuthorizationRepository,
    SQLAlchemyAutomaticPolicyRepository,
    SQLAlchemyContextResolutionRepository,
    SQLAlchemyConversationRepository,
    SQLAlchemyDatabase,
    SQLAlchemyEventRepository,
    SQLAlchemyExecutionRepository,
    SQLAlchemyMessageRepository,
    SQLAlchemyMetricsRepository,
    SQLAlchemyPermissionRepository,
    SQLAlchemyProjectRepository,
    SQLAlchemyRefreshTokenRepository,
    SQLAlchemySuggestionRepository,
    SQLAlchemyTaskRepository,
    SQLAlchemyUserRepository,
)
from orchai.infrastructure.projects import (
    InMemoryProjectAdapterRegistry,
    LocalFilesystemProjectAdapter,
)

#: Canonical permission-key catalog (ADR-012,
#: `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §4). Auto-seeded
#: idempotently by `build_sqlalchemy_identity_runtime` on every startup so
#: that `permissions`/`access_roles` are never left empty in a fresh
#: database -- without this, no non-superuser could ever pass a permission
#: check, since `IdentityService.effective_permission_keys` can only
#: return keys of `Permission` rows that actually exist. `admin:manage_projects`
#: is new (user-configuration CRUD layer); the other ten mirror §4 exactly.
PERMISSION_CATALOG: dict[str, str] = {
    "requests:create": "Create new orchestration requests/local flows.",
    "requests:advance": "Advance an existing request or task to its next state.",
    "requests:approve": "Approve a pending request.",
    "projects:connect": "Register or operate on a project connected to OrchAI.",
    "projects:read": (
        "Read project, task, execution, authorization, audit, event, "
        "metrics, and suggestion data."
    ),
    "authorizations:decide": "Request or decide an authorization.",
    "executions:manage": "Manage (start, inspect, control) executions.",
    "suggestions:manage": "Accept, reject, or create suggestions for a task.",
    "policies:evaluate": "Evaluate an automatic execution policy.",
    "policies:manage": "View and change the persisted automatic execution policy.",
    "admin:manage_users": (
        "Create users and modify user records/access-role assignments. "
        "Superuser-only in practice, modeled as a normal permission so it "
        "can in principle be delegated."
    ),
    "admin:db": "Run database maintenance operations (e.g. schema sync).",
    "admin:manage_projects": (
        "List every project in the system and its full details (admin "
        "project directory), independent of any project connection."
    ),
}


@dataclass(frozen=True, slots=True)
class OrchAIRuntime:
    """Composed application runtime."""

    orchestrator: Orchestrator
    project_service: ProjectService
    task_service: TaskService
    authorization_service: AuthorizationService
    execution_service: ExecutionService
    context_service: ContextService
    policy_service: LocalPolicyService
    automatic_policy_repository: AutomaticPolicyRepository
    automatic_policy_service: AutomaticPolicyService
    project_adapters: ProjectAdapterRegistry
    event_repository: EventRepository
    audit_repository: AuditRepository
    context_resolution_repository: ContextResolutionRepository
    metrics_repository: MetricsRepository
    suggestion_repository: SuggestionRepository
    suggestion_engine: SuggestionEngine
    event_engine: EventEngine
    execution_engine: ExecutionEngine
    database: SQLAlchemyDatabase | None = None


def build_in_memory_runtime(
    *,
    ai_provider: AIProviderPort | None = None,
    automatic_policy: AutomaticExecutionPolicy | None = None,
) -> OrchAIRuntime:
    """Compose a non-durable runtime for focused tests."""

    return _build_runtime(
        project_repository=InMemoryProjectRepository(),
        task_repository=InMemoryTaskRepository(),
        authorization_repository=InMemoryAuthorizationRepository(),
        execution_repository=InMemoryExecutionRepository(),
        event_repository=InMemoryEventRepository(),
        audit_repository=InMemoryAuditRepository(),
        context_resolution_repository=InMemoryContextResolutionRepository(),
        metrics_repository=InMemoryMetricsRepository(),
        suggestion_repository=InMemorySuggestionRepository(),
        automatic_policy_repository=InMemoryAutomaticPolicyRepository(),
        project_adapters=InMemoryProjectAdapterRegistry(),
        create_project_adapter=_local_filesystem_adapter,
        ai_provider=ai_provider or StubAIProviderAdapter(),
        automatic_policy=automatic_policy,
    )


def build_sqlalchemy_runtime(
    database_url: str,
    *,
    ai_provider: AIProviderPort | None = None,
    automatic_policy: AutomaticExecutionPolicy | None = None,
) -> OrchAIRuntime:
    """Compose the SQLAlchemy-backed runtime."""

    database = SQLAlchemyDatabase(database_url)
    database.migrate()
    return _build_runtime(
        project_repository=SQLAlchemyProjectRepository(database),
        task_repository=SQLAlchemyTaskRepository(database),
        authorization_repository=SQLAlchemyAuthorizationRepository(database),
        execution_repository=SQLAlchemyExecutionRepository(database),
        event_repository=SQLAlchemyEventRepository(database),
        audit_repository=SQLAlchemyAuditRepository(database),
        context_resolution_repository=SQLAlchemyContextResolutionRepository(database),
        metrics_repository=SQLAlchemyMetricsRepository(database),
        suggestion_repository=SQLAlchemySuggestionRepository(database),
        automatic_policy_repository=SQLAlchemyAutomaticPolicyRepository(database),
        project_adapters=InMemoryProjectAdapterRegistry(),
        create_project_adapter=_local_filesystem_adapter,
        ai_provider=ai_provider or StubAIProviderAdapter(),
        automatic_policy=automatic_policy,
        database=database,
    )


def build_runtime_from_settings(
    settings: OrchAISettings | None = None,
    *,
    ai_provider: AIProviderPort | None = None,
    automatic_policy: AutomaticExecutionPolicy | None = None,
) -> OrchAIRuntime:
    """Compose the primary runtime from effective settings."""

    effective_settings = settings or load_settings()
    return build_sqlalchemy_runtime(
        effective_settings.database.sqlalchemy_url,
        ai_provider=ai_provider or provider_from_settings(effective_settings),
        automatic_policy=automatic_policy,
    )


def build_in_memory_local_flow_dependencies() -> LocalFlowDependencies:
    """Compose local-flow dependencies using non-durable repositories."""

    return LocalFlowDependencies(orchestrator=build_in_memory_runtime().orchestrator)


def build_sqlalchemy_local_flow_dependencies(database_url: str) -> LocalFlowDependencies:
    """Compose local-flow dependencies using SQLAlchemy repositories."""

    return LocalFlowDependencies(
        orchestrator=build_sqlalchemy_runtime(database_url).orchestrator
    )


def build_local_flow_dependencies_from_settings(
    settings: OrchAISettings | None = None,
    *,
    ai_provider: AIProviderPort | None = None,
    automatic_policy: AutomaticExecutionPolicy | None = None,
) -> LocalFlowDependencies:
    """Compose local-flow dependencies from effective settings."""

    return LocalFlowDependencies(
        orchestrator=build_runtime_from_settings(
            settings,
            ai_provider=ai_provider,
            automatic_policy=automatic_policy,
        ).orchestrator
    )


def _build_runtime(
    *,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    authorization_repository: AuthorizationRepository,
    execution_repository: ExecutionRepository,
    event_repository: EventRepository,
    audit_repository: AuditRepository,
    context_resolution_repository: ContextResolutionRepository,
    metrics_repository: MetricsRepository,
    suggestion_repository: SuggestionRepository,
    automatic_policy_repository: AutomaticPolicyRepository,
    project_adapters: ProjectAdapterRegistry,
    create_project_adapter: ProjectAdapterFactory,
    ai_provider: AIProviderPort,
    automatic_policy: AutomaticExecutionPolicy | None = None,
    database: SQLAlchemyDatabase | None = None,
) -> OrchAIRuntime:
    event_engine = EventEngine(repository=event_repository)
    event_engine.subscribe_all(AuditEventHandler(audit_repository).handle)
    event_engine.subscribe_all(
        MetricsEventHandler(
            repository=metrics_repository,
            execution_repository=execution_repository,
        ).handle
    )

    project_service = ProjectService(
        repository=project_repository,
        event_publisher=event_engine,
    )
    task_service = TaskService(
        repository=task_repository,
        event_publisher=event_engine,
    )
    authorization_service = AuthorizationService(
        repository=authorization_repository,
        event_publisher=event_engine,
    )
    execution_service = ExecutionService(
        repository=execution_repository,
        authorization_repository=authorization_repository,
        event_publisher=event_engine,
    )
    context_service = ContextService(
        execution_repository=execution_repository,
        project_adapters=project_adapters,
        event_publisher=event_engine,
        resolution_repository=context_resolution_repository,
    )
    execution_engine = ExecutionEngine(
        execution_repository=execution_repository,
        execution_service=execution_service,
        context_service=context_service,
        ai_provider=ai_provider,
    )
    suggestion_engine = SuggestionEngine(suggestion_repository)
    policy_service = (
        LocalPolicyService(automatic_policy=automatic_policy)
        if automatic_policy is not None
        else LocalPolicyService(automatic_policy_repository=automatic_policy_repository)
    )
    automatic_policy_service = AutomaticPolicyService(
        repository=automatic_policy_repository,
        event_publisher=event_engine,
    )
    orchestrator = Orchestrator(
        project_service=project_service,
        task_service=task_service,
        authorization_service=authorization_service,
        execution_service=execution_service,
        execution_engine=execution_engine,
        suggestion_engine=suggestion_engine,
        policy_service=policy_service,
        project_adapters=project_adapters,
        create_project_adapter=create_project_adapter,
        event_publisher=event_engine,
        event_history=event_engine,
        audit_repository=audit_repository,
    )

    return OrchAIRuntime(
        orchestrator=orchestrator,
        project_service=project_service,
        task_service=task_service,
        authorization_service=authorization_service,
        execution_service=execution_service,
        context_service=context_service,
        policy_service=policy_service,
        automatic_policy_repository=automatic_policy_repository,
        automatic_policy_service=automatic_policy_service,
        project_adapters=project_adapters,
        event_repository=event_repository,
        audit_repository=audit_repository,
        context_resolution_repository=context_resolution_repository,
        metrics_repository=metrics_repository,
        suggestion_repository=suggestion_repository,
        suggestion_engine=suggestion_engine,
        event_engine=event_engine,
        execution_engine=execution_engine,
        database=database,
    )


class ProjectAdapterFactory(Protocol):
    def __call__(self, project_root: Path) -> ProjectAdapter:
        """Build a project adapter for a local project root."""


def _local_filesystem_adapter(project_root: Path) -> LocalFilesystemProjectAdapter:
    return LocalFilesystemProjectAdapter(project_root)


@dataclass(frozen=True, slots=True)
class IdentityRuntime:
    """Composed identity runtime (ADR-012, `docs/TO-DO.md` Priority 1 Phase 3).

    Kept separate from `OrchAIRuntime` rather than folded into it: identity
    is consumed by the new enforcement hook and `/auth/*` surface, not by
    the existing orchestration call sites, and keeping it a distinct,
    additive builder avoids touching `OrchAIRuntime`'s shape (and every
    existing call site/test that constructs one).
    """

    identity_service: IdentityService
    access_token_issuer: JWTAccessTokenIssuer
    database: SQLAlchemyDatabase


def build_sqlalchemy_identity_runtime(
    database_url: str,
    *,
    secret_key: str,
    access_token_ttl_minutes: int = 15,
    refresh_token_ttl_days: int = 30,
) -> IdentityRuntime:
    """Compose the SQLAlchemy-backed identity runtime.

    Reuses the same audit/metrics event-subscription pattern as
    `_build_runtime` so identity events (user created, login, token
    issued/revoked, ...) flow into the same durable `/events` and `/audit`
    history as every other domain event, rather than being a second,
    disconnected event stream.
    """

    database = SQLAlchemyDatabase(database_url)
    database.migrate()

    permission_repository = SQLAlchemyPermissionRepository(database)
    permission_repository.seed_catalog(PERMISSION_CATALOG)

    event_repository = SQLAlchemyEventRepository(database)
    audit_repository = SQLAlchemyAuditRepository(database)
    metrics_repository = SQLAlchemyMetricsRepository(database)
    execution_repository = SQLAlchemyExecutionRepository(database)
    event_engine = EventEngine(repository=event_repository)
    event_engine.subscribe_all(AuditEventHandler(audit_repository).handle)
    event_engine.subscribe_all(
        MetricsEventHandler(
            repository=metrics_repository,
            execution_repository=execution_repository,
        ).handle
    )

    access_token_issuer = JWTAccessTokenIssuer(
        secret_key=secret_key,
        ttl=timedelta(minutes=access_token_ttl_minutes),
    )
    identity_service = IdentityService(
        user_repository=SQLAlchemyUserRepository(database),
        access_role_repository=SQLAlchemyAccessRoleRepository(database),
        permission_repository=permission_repository,
        refresh_token_repository=SQLAlchemyRefreshTokenRepository(database),
        access_control_repository=SQLAlchemyAccessControlRepository(database),
        password_hasher=Argon2PasswordHasher(),
        event_publisher=event_engine,
        access_token_issuer=access_token_issuer,
        refresh_token_hasher=Sha256RefreshTokenHasher(),
        refresh_token_ttl=timedelta(days=refresh_token_ttl_days),
    )
    return IdentityRuntime(
        identity_service=identity_service,
        access_token_issuer=access_token_issuer,
        database=database,
    )


def build_identity_runtime_from_settings(
    settings: OrchAISettings | None = None,
) -> IdentityRuntime:
    """Compose the identity runtime from effective settings."""

    effective_settings = settings or load_settings()
    return build_sqlalchemy_identity_runtime(
        effective_settings.database.sqlalchemy_url,
        secret_key=effective_settings.auth.secret_key,
        access_token_ttl_minutes=effective_settings.auth.access_token_ttl_minutes,
        refresh_token_ttl_days=effective_settings.auth.refresh_token_ttl_days,
    )


@dataclass(frozen=True, slots=True)
class ConversationRuntime:
    """Composed conversation runtime (ADR-014).

    Kept separate from `OrchAIRuntime`, the same way `IdentityRuntime`
    is: `Conversation`/`Message` are their own bounded context, not part
    of the Task/Execution aggregate family.
    """

    conversation_service: ConversationService
    database: SQLAlchemyDatabase


def build_sqlalchemy_conversation_runtime(
    database_url: str,
    *,
    ai_provider: ConversationAIProviderPort,
) -> ConversationRuntime:
    """Compose the SQLAlchemy-backed conversation runtime."""

    database = SQLAlchemyDatabase(database_url)
    database.migrate()
    conversation_service = ConversationService(
        conversation_repository=SQLAlchemyConversationRepository(database),
        message_repository=SQLAlchemyMessageRepository(database),
        ai_provider=ai_provider,
        get_module=_get_module,
    )
    return ConversationRuntime(conversation_service=conversation_service, database=database)


def build_in_memory_conversation_runtime(
    *,
    ai_provider: ConversationAIProviderPort,
) -> ConversationService:
    """Compose a non-durable conversation service for focused tests."""

    return ConversationService(
        conversation_repository=InMemoryConversationRepository(),
        message_repository=InMemoryMessageRepository(),
        ai_provider=ai_provider,
        get_module=_get_module,
    )


def build_conversation_runtime_from_settings(
    settings: OrchAISettings | None = None,
    *,
    ai_provider: ConversationAIProviderPort | None = None,
) -> ConversationRuntime:
    """Compose the conversation runtime from effective settings."""

    effective_settings = settings or load_settings()
    return build_sqlalchemy_conversation_runtime(
        effective_settings.database.sqlalchemy_url,
        ai_provider=ai_provider or provider_from_settings(effective_settings),
    )


def provider_from_settings(settings: OrchAISettings) -> AIProviderPort:
    """Instantiate the configured AI provider adapter."""

    provider = settings.ai_provider.provider
    if provider == "stub":
        return StubAIProviderAdapter()
    if provider == "litellm":
        return LiteLLMProvider(
            model=settings.ai_provider.model,
            api_key=settings.ai_provider.api_key,
            base_url=settings.ai_provider.base_url,
            timeout_seconds=settings.ai_provider.timeout_seconds,
        )
    raise ValueError(f"unsupported ai provider: {provider}")
