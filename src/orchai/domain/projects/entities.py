"""Project entities."""

from __future__ import annotations

from dataclasses import dataclass, field

from orchai.domain.capabilities import CapabilityName
from orchai.domain.identifiers import ProjectId
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

