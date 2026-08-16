"""In-memory project adapter registry."""

from __future__ import annotations

from orchai.application.projects.ports import ProjectAdapter, ProjectAdapterRegistry
from orchai.domain.identifiers import ProjectId


class ProjectAdapterNotFoundError(LookupError):
    """Raised when no adapter is registered for a project."""


class InMemoryProjectAdapterRegistry(ProjectAdapterRegistry):
    """Non-durable registry for project adapters."""

    def __init__(self) -> None:
        self._adapters: dict[ProjectId, ProjectAdapter] = {}

    async def register(self, project_id: ProjectId, adapter: ProjectAdapter) -> None:
        self._adapters[project_id] = adapter

    async def get(self, project_id: ProjectId) -> ProjectAdapter:
        try:
            return self._adapters[project_id]
        except KeyError as exc:
            raise ProjectAdapterNotFoundError(str(project_id)) from exc

