"""Module domain entities (ADR-015).

A `ModuleDefinition` is a code-defined configuration bundle, not a
persisted aggregate -- the same treatment already given to `RoleName`
and `ActionName` (`domain/roles`, `domain/actions`): a closed
vocabulary, reviewed like any other architectural change, never
created or mutated through a runtime API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from orchai.domain.actions import ActionName
from orchai.domain.identifiers import ModuleId
from orchai.domain.roles import RoleName

#: How a module's project connection is realized. "none" means the
#: module never connects to a project (`requires_project=False`).
ProjectAdapterKind = Literal["local_filesystem", "media_workspace", "none"]

#: How a module's messages relate to the Task/Authorization/Execution
#: pipeline (ADR-014 §2, ADR-015 §4):
#:   full_workflow                          -- the full PLAN..DOCUMENT pipeline (Forge)
#:   conversational_with_protected_operations -- mostly chat; occasional
#:       authorized project writes via the existing ProjectOperation
#:       mechanism, without the full pipeline (Studio)
#:   conversational_only                    -- chat, no project pipeline at all
TaskPipelineMode = Literal[
    "full_workflow",
    "conversational_with_protected_operations",
    "conversational_only",
]


@dataclass(frozen=True, slots=True)
class ModuleDefinition:
    """A specialized experience within OrchAI Desktop (ADR-015)."""

    id: ModuleId
    name: str
    description: str
    system_prompt: str
    default_role: RoleName
    allowed_roles: frozenset[RoleName]
    allowed_actions: frozenset[ActionName]
    suggested_models: tuple[str, ...]
    project_adapter_kind: ProjectAdapterKind
    task_pipeline_mode: TaskPipelineMode
    requires_project: bool

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("module name must not be empty")
        if not self.system_prompt.strip():
            raise ValueError("module system_prompt must not be empty")
        if self.default_role not in self.allowed_roles:
            raise ValueError("module default_role must be one of allowed_roles")
