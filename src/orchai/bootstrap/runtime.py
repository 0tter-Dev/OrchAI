"""Runtime dependency composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from orchai.application.audit import AuditEventHandler, AuditRepository
from orchai.application.authorization import AuthorizationService
from orchai.application.authorization.ports import AuthorizationRepository
from orchai.application.context import ContextService
from orchai.application.context.ports import ContextResolutionRepository
from orchai.application.events import EventEngine, EventRepository
from orchai.application.executions import ExecutionService
from orchai.application.executions.engine import ExecutionEngine
from orchai.application.executions.ports import AIProviderPort, ExecutionRepository
from orchai.application.metrics import MetricsEventHandler, MetricsRepository
from orchai.application.orchestration.local_flow import LocalFlowDependencies
from orchai.application.orchestration.orchestrator import Orchestrator
from orchai.application.policies import AutomaticExecutionPolicy, LocalPolicyService
from orchai.application.projects import ProjectService
from orchai.application.projects.ports import (
    ProjectAdapter,
    ProjectAdapterRegistry,
    ProjectRepository,
)
from orchai.application.tasks import TaskService
from orchai.application.tasks.ports import TaskRepository
from orchai.application.suggestions import SuggestionEngine, SuggestionRepository
from orchai.infrastructure.ai import StubAIProviderAdapter
from orchai.infrastructure.persistence import (
    InMemoryAuditRepository,
    InMemoryAuthorizationRepository,
    InMemoryContextResolutionRepository,
    InMemoryEventRepository,
    InMemoryExecutionRepository,
    InMemoryMetricsRepository,
    InMemoryProjectRepository,
    InMemorySuggestionRepository,
    InMemoryTaskRepository,
    SQLAlchemyAuditRepository,
    SQLAlchemyAuthorizationRepository,
    SQLAlchemyContextResolutionRepository,
    SQLAlchemyDatabase,
    SQLAlchemyEventRepository,
    SQLAlchemyExecutionRepository,
    SQLAlchemyMetricsRepository,
    SQLAlchemyProjectRepository,
    SQLAlchemySuggestionRepository,
    SQLAlchemyTaskRepository,
)
from orchai.infrastructure.projects import (
    InMemoryProjectAdapterRegistry,
    LocalFilesystemProjectAdapter,
)


@dataclass(frozen=True, slots=True)
class OrchAIRuntime:
    """Composed application runtime."""

    orchestrator: Orchestrator
    project_service: ProjectService
    event_repository: EventRepository
    audit_repository: AuditRepository
    context_resolution_repository: ContextResolutionRepository
    metrics_repository: MetricsRepository
    suggestion_repository: SuggestionRepository
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
        project_adapters=InMemoryProjectAdapterRegistry(),
        create_project_adapter=_local_filesystem_adapter,
        ai_provider=ai_provider or StubAIProviderAdapter(),
        automatic_policy=automatic_policy,
        database=database,
    )


def build_in_memory_local_flow_dependencies() -> LocalFlowDependencies:
    """Compose local-flow dependencies using non-durable repositories."""

    return LocalFlowDependencies(orchestrator=build_in_memory_runtime().orchestrator)


def build_sqlalchemy_local_flow_dependencies(database_url: str) -> LocalFlowDependencies:
    """Compose local-flow dependencies using SQLAlchemy repositories."""

    return LocalFlowDependencies(
        orchestrator=build_sqlalchemy_runtime(database_url).orchestrator
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
    policy_service = LocalPolicyService(automatic_policy=automatic_policy)
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
        event_repository=event_repository,
        audit_repository=audit_repository,
        context_resolution_repository=context_resolution_repository,
        metrics_repository=metrics_repository,
        suggestion_repository=suggestion_repository,
        event_engine=event_engine,
        execution_engine=execution_engine,
        database=database,
    )


class ProjectAdapterFactory(Protocol):
    def __call__(self, project_root: Path) -> ProjectAdapter:
        """Build a project adapter for a local project root."""


def _local_filesystem_adapter(project_root: Path) -> LocalFilesystemProjectAdapter:
    return LocalFilesystemProjectAdapter(project_root)
