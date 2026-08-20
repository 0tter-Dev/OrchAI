"""Project entities."""

from __future__ import annotations

from dataclasses import dataclass, field

from orchai.domain.capabilities import CapabilityName
from orchai.domain.identifiers import ProjectId
from orchai.domain.projects.readiness import ProjectReadinessLevel
from orchai.domain.projects.security import ProjectSecurityProfile
from orchai.domain.projects.statuses import ProjectStatus


@dataclass(frozen=True, slots=True)
class Project:
    """External development project connected through an adapter."""

    name: str
    root_location: str
    adapter_type: str
    capabilities: frozenset[CapabilityName]
    id: ProjectId = field(default_factory=ProjectId.new)
    status: ProjectStatus = ProjectStatus.ACTIVE
    readiness_level: ProjectReadinessLevel = ProjectReadinessLevel.LEVEL_0_CONNECTABLE
    security_profile: ProjectSecurityProfile = field(
        default_factory=ProjectSecurityProfile
    )
    observed_readiness_level: ProjectReadinessLevel = (
        ProjectReadinessLevel.LEVEL_0_CONNECTABLE
    )
    observed_security_profile: ProjectSecurityProfile = field(
        default_factory=ProjectSecurityProfile
    )

    def __post_init__(self) -> None:
        name = self.name.strip()
        root_location = self.root_location.strip()
        adapter_type = self.adapter_type.strip()
        if not name:
            raise ValueError("project name must not be empty")
        if not root_location:
            raise ValueError("project root_location must not be empty")
        if not adapter_type:
            raise ValueError("project adapter_type must not be empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "root_location", root_location)
        object.__setattr__(self, "adapter_type", adapter_type)
        if self.security_profile.readiness_level != self.readiness_level:
            object.__setattr__(
                self,
                "security_profile",
                ProjectSecurityProfile(
                    **{
                        **self.security_profile.as_dict(),
                        "readiness_level": self.readiness_level.value,
                    }
                ),
            )
        if self.observed_security_profile.readiness_level != self.observed_readiness_level:
            object.__setattr__(
                self,
                "observed_security_profile",
                ProjectSecurityProfile(
                    **{
                        **self.observed_security_profile.as_dict(),
                        "readiness_level": self.observed_readiness_level.value,
                    }
                ),
            )
