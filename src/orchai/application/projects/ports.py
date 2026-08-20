"""Project application ports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from typing import Protocol

from orchai.domain.capabilities import CapabilityName
from orchai.domain.context import ContextItem, ContextReference, ContextSource
from orchai.domain.identifiers import ProjectId
from orchai.domain.projects import (
    PersistenceClassification,
    Project,
    ProjectReadinessLevel,
    ProjectSecurityProfile,
    ProviderSharingLevel,
)


@dataclass(frozen=True, slots=True)
class ProjectResource:
    """Metadata for a project-owned resource exposed through an adapter."""

    resource: str
    source: ContextSource
    capabilities: frozenset[CapabilityName]
    provider_sharing_level: ProviderSharingLevel = (
        ProviderSharingLevel.CLOUD_ALLOWED_WITH_AUTHORIZATION
    )
    persistence_classification: PersistenceClassification = (
        PersistenceClassification.DEFAULT_ALLOWED
    )
    restricted: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProjectDiscovery:
    """Bounded project discovery result."""

    resources: tuple[ProjectResource, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProjectReadinessAssessment:
    """Assessment of a project's operational readiness."""

    readiness_level: ProjectReadinessLevel
    security_profile: ProjectSecurityProfile
    reasons: tuple[str, ...] = ()
    has_git: bool = False
    has_documentation: bool = False
    has_tests: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProjectWriteResult:
    """Stable result for project write operations."""

    resource: str
    bytes_written: int
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProjectCommandResult:
    """Stable result for project command/test execution."""

    command: tuple[str, ...]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ProjectGitStatus:
    """Stable Git status snapshot exposed by project adapters."""

    branch: str = ""
    is_dirty: bool = False
    ahead: int = 0
    behind: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ProjectRepository(Protocol):
    """Persistence boundary for project metadata."""

    async def add(self, project: Project) -> None:
        """Persist a newly registered project."""

    async def save(self, project: Project) -> None:
        """Persist an existing project state."""

    async def get(self, project_id: ProjectId) -> Project:
        """Return an existing project by id."""

    async def get_by_root_location(self, root_location: str) -> Project | None:
        """Return an existing project by normalized root location when present."""

    async def list(self) -> tuple[Project, ...]:
        """Return persisted projects."""


class ProjectAdapter(Protocol):
    """Boundary for project-owned resources."""

    async def capabilities(self) -> frozenset[CapabilityName]:
        """Return capabilities exposed by the adapter."""

    async def discover(self, *, limit: int = 100) -> ProjectDiscovery:
        """Discover project resources without reading their full contents."""

    async def assess_readiness(self) -> ProjectReadinessAssessment:
        """Assess the project's operational readiness."""

    async def classify_resource(self, reference: ContextReference) -> ProjectResource:
        """Classify one resource for security/readiness enforcement."""

    async def classify_persistence(
        self,
        reference: ContextReference,
    ) -> PersistenceClassification:
        """Return the persistence classification for one resource."""

    async def classify_provider_sharing(
        self,
        reference: ContextReference,
    ) -> ProviderSharingLevel:
        """Return whether a resource may cross a provider boundary."""

    async def write(
        self,
        reference: ContextReference,
        content: str,
    ) -> ProjectWriteResult:
        """Write source-like content when the adapter exposes the capability."""

    async def write_documentation(
        self,
        reference: ContextReference,
        content: str,
    ) -> ProjectWriteResult:
        """Write documentation content when the adapter exposes the capability."""

    async def run_tests(
        self,
        *,
        args: tuple[str, ...] = (),
    ) -> ProjectCommandResult:
        """Run bounded project tests when the adapter exposes the capability."""

    async def run_command(
        self,
        command: tuple[str, ...],
    ) -> ProjectCommandResult:
        """Run one bounded project command when the adapter exposes the capability."""

    async def git_status(self) -> ProjectGitStatus:
        """Return bounded Git status metadata when the adapter exposes the capability."""

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
