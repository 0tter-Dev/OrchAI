"""Runtime dependency composition."""

from __future__ import annotations

from pathlib import Path

from orchai.application.orchestration.local_flow import LocalFlowDependencies
from orchai.infrastructure.persistence import (
    InMemoryAuthorizationRepository,
    InMemoryExecutionRepository,
    InMemoryProjectRepository,
    InMemoryTaskRepository,
    SQLAlchemyAuthorizationRepository,
    SQLAlchemyDatabase,
    SQLAlchemyExecutionRepository,
    SQLAlchemyProjectRepository,
    SQLAlchemyTaskRepository,
)
from orchai.infrastructure.projects import (
    InMemoryProjectAdapterRegistry,
    LocalFilesystemProjectAdapter,
)


def build_in_memory_local_flow_dependencies() -> LocalFlowDependencies:
    """Compose local-flow dependencies using non-durable repositories."""

    return LocalFlowDependencies(
        project_repository=InMemoryProjectRepository(),
        task_repository=InMemoryTaskRepository(),
        authorization_repository=InMemoryAuthorizationRepository(),
        execution_repository=InMemoryExecutionRepository(),
        project_adapters=InMemoryProjectAdapterRegistry(),
        create_project_adapter=lambda project_root: LocalFilesystemProjectAdapter(
            project_root
        ),
    )


def build_sqlalchemy_local_flow_dependencies(database_url: str) -> LocalFlowDependencies:
    """Compose local-flow dependencies using SQLAlchemy repositories."""

    database = SQLAlchemyDatabase(database_url)
    database.migrate()
    return LocalFlowDependencies(
        project_repository=SQLAlchemyProjectRepository(database),
        task_repository=SQLAlchemyTaskRepository(database),
        authorization_repository=SQLAlchemyAuthorizationRepository(database),
        execution_repository=SQLAlchemyExecutionRepository(database),
        project_adapters=InMemoryProjectAdapterRegistry(),
        create_project_adapter=_local_filesystem_adapter,
    )


def _local_filesystem_adapter(project_root: Path) -> LocalFilesystemProjectAdapter:
    return LocalFilesystemProjectAdapter(project_root)
