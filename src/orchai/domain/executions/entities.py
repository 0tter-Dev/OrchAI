"""Execution entities and value objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from orchai.domain.actions import ActionName
from orchai.domain.identifiers import AuthorizationId, ExecutionId, ModelId, ProjectId, TaskId
from orchai.domain.roles import RoleName
from orchai.domain.executions.state_machine import ExecutionStateMachine, ExecutionTransition
from orchai.domain.executions.states import ExecutionState


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    """Resource usage reported by an execution attempt."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for value_name, value in {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
        }.items():
            if value is not None and value < 0:
                raise ValueError(f"{value_name} must not be negative")
        if self.estimated_cost is not None and self.estimated_cost < 0:
            raise ValueError("estimated_cost must not be negative")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def total_tokens(self) -> int | None:
        if self.input_tokens is None and self.output_tokens is None:
            return None
        return (self.input_tokens or 0) + (self.output_tokens or 0)


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Outcome details for a completed or failed execution."""

    output: str
    success: bool
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "errors",
            tuple(error.strip() for error in self.errors if error.strip()),
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(warning.strip() for warning in self.warnings if warning.strip()),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
        if not self.success and not self.errors:
            raise ValueError("failed execution results must include at least one error")


@dataclass(slots=True)
class Execution:
    """A traceable attempt to perform an action for one task."""

    task_id: TaskId
    role: RoleName
    action: ActionName
    model_id: ModelId
    authorization_id: AuthorizationId
    id: ExecutionId = field(default_factory=ExecutionId.new)
    project_id: ProjectId | None = None
    requested_context: tuple[str, ...] = ()
    authorized_context: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result: ExecutionResult | None = None
    _state: ExecutionState = field(default=ExecutionState.REQUESTED, repr=False)

    def __post_init__(self) -> None:
        self.requested_context = _normalize_context(self.requested_context)
        self.authorized_context = _normalize_context(self.authorized_context)

    @property
    def state(self) -> ExecutionState:
        return self._state

    def transition_to(
        self,
        target: ExecutionState,
        *,
        state_machine: ExecutionStateMachine,
    ) -> ExecutionTransition:
        transition = state_machine.transition(self._state, target)
        self._state = transition.target
        if target is ExecutionState.STARTED:
            self.started_at = datetime.now(UTC)
        return transition

    def complete(
        self,
        result: ExecutionResult,
        *,
        state_machine: ExecutionStateMachine,
    ) -> ExecutionTransition:
        target = ExecutionState.COMPLETED if result.success else ExecutionState.FAILED
        transition = self.transition_to(target, state_machine=state_machine)
        self.result = result
        self.completed_at = datetime.now(UTC)
        return transition


def _normalize_context(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value.strip() for value in values if value.strip())

