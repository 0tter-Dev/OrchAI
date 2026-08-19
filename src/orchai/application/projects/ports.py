"""Project application ports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from typing import Protocol

from orchai.domain.capabilities import CapabilityName
from orchai.domain.context import ContextItem, ContextReference, ContextSource
from orchai.domain.identifiers import ProjectId
from orchai.domain.projects import Project


@dataclass(frozen=True, slots=True)
class ProjectResource:
    """Metadata for a project-owned resource exposed through an adapter."""

    resource: str
    source: ContextSource
    capabilities: frozenset[CapabilityName]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProjectDiscovery:
    """Bounded project discovery result."""

    resources: tuple[ProjectResource, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


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

    async def discover(self, *, limit: int = 100) -> ProjectDiscovery:
        """Discover project resources without reading their full contents."""

    async def read_context(self, reference: ContextReference) -> ContextItem:
        """Read one authorized context reference."""

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
