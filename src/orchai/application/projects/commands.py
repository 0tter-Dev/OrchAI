"""Project use-case commands."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from orchai.domain.capabilities import CapabilityName
from orchai.domain.identifiers import ProjectId
from orchai.domain.projects import ProjectReadinessLevel, ProjectSecurityProfile


@dataclass(frozen=True, slots=True)
class RegisterProjectCommand:
    """Command for registering an external project."""

    name: str
    root_location: str
    adapter_type: str = "local_filesystem"
    capabilities: Iterable[CapabilityName] = ()
    readiness_level: ProjectReadinessLevel = ProjectReadinessLevel.LEVEL_0_CONNECTABLE
    security_profile: ProjectSecurityProfile = field(
        default_factory=ProjectSecurityProfile
    )
    observed_readiness_level: ProjectReadinessLevel | None = None
    observed_security_profile: ProjectSecurityProfile | None = None


@dataclass(frozen=True, slots=True)
class UpdateProjectSecurityCommand:
    """Command for updating one persisted project security profile."""

    project_id: ProjectId
    readiness_level: ProjectReadinessLevel | None = None
    access_scope: tuple[str, ...] | None = None
    restricted_areas: tuple[str, ...] | None = None
    sensitive_patterns: tuple[str, ...] | None = None
    allow_git_bootstrap: bool | None = None
    allow_architecture_restructure: bool | None = None
    allow_cicd_changes: bool | None = None
    allow_cloud_provider_sharing: bool | None = None
    persist_architecture_summaries: bool | None = None
    persist_naming_summaries: bool | None = None
    persist_functional_summaries: bool | None = None
    persist_context_snapshots: bool | None = None
    metadata: Mapping[str, Any] | None = None
