"""Context references and resolved context packages."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from orchai.domain.context.sources import ContextSource
from orchai.domain.identifiers import ExecutionId, ProjectId


@dataclass(frozen=True, slots=True)
class ContextReference:
    """Reference to project-owned or orchestration-owned context."""

    source: ContextSource
    resource: str
    scope: str | None = None
    version: str | None = None
    requires_authorization: bool = True

    def __post_init__(self) -> None:
        resource = self.resource.strip()
        scope = self.scope.strip() if self.scope is not None else None
        version = self.version.strip() if self.version is not None else None
        if not resource:
            raise ValueError("context resource must not be empty")
        if scope == "":
            scope = None
        if version == "":
            version = None
        object.__setattr__(self, "resource", resource)
        object.__setattr__(self, "scope", scope)
        object.__setattr__(self, "version", version)


@dataclass(frozen=True, slots=True)
class ContextItem:
    """Resolved context content for one authorized reference."""

    reference: ContextReference
    content: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContextPackage:
    """Bounded context package provided to an execution."""

    execution_id: ExecutionId
    project_id: ProjectId
    requested_references: tuple[ContextReference, ...]
    authorized_references: tuple[ContextReference, ...]
    items: tuple[ContextItem, ...]
    provided_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        item_references = {item.reference for item in self.items}
        authorized = set(self.authorized_references)
        if not item_references.issubset(authorized):
            raise ValueError("context package contains unauthorized items")

