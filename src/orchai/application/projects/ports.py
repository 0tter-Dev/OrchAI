"""Project application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.capabilities import CapabilityName
from orchai.domain.context import ContextItem, ContextReference
from orchai.domain.identifiers import ProjectId
from orchai.domain.projects import Project


class ProjectRepository(Protocol):
    """Persistence boundary for project metadata."""

    async def add(self, project: Project) -> None:
        """Persist a newly registered project."""

    async def get(self, project_id: ProjectId) -> Project:
        """Return an existing project by id."""


class ProjectAdapter(Protocol):
    """Boundary for project-owned resources."""

    async def capabilities(self) -> frozenset[CapabilityName]:
        """Return capabilities exposed by the adapter."""

    async def resolve_context(
        self,
        references: tuple[ContextReference, ...],
    ) -> tuple[ContextItem, ...]:
        """Resolve authorized context references into bounded content."""


class ProjectAdapterRegistry(Protocol):
    """Registry that maps known projects to concrete adapters."""

    async def register(self, project_id: ProjectId, adapter: ProjectAdapter) -> None:
        """Associate a project with an adapter."""

    async def get(self, project_id: ProjectId) -> ProjectAdapter:
        """Return the adapter for a project."""

