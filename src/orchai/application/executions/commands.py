"""Execution use-case commands."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from orchai.domain.actions import ActionName
from orchai.domain.executions import ExecutionState, ResourceUsage
from orchai.domain.identifiers import AuthorizationId, ExecutionId, ModelId, ProjectId, TaskId
from orchai.domain.roles import RoleName


@dataclass(frozen=True, slots=True)
class RequestExecutionCommand:
    """Command for constructing an authorized execution attempt."""

    task_id: TaskId
    role: RoleName
    action: ActionName
    model_id: ModelId
    authorization_id: AuthorizationId
    project_id: ProjectId | None = None
    requested_context: Iterable[str] = ()
    authorized_context: Iterable[str] = ()


@dataclass(frozen=True, slots=True)
class TransitionExecutionCommand:
    """Command for moving an execution through its lifecycle."""

    execution_id: ExecutionId
    target_state: ExecutionState


@dataclass(frozen=True, slots=True)
class CompleteExecutionCommand:
    """Command for recording an execution result."""

    execution_id: ExecutionId
    output: str
    success: bool = True
    errors: Iterable[str] = ()
    warnings: Iterable[str] = ()
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    metadata: Mapping[str, Any] = field(default_factory=dict)

