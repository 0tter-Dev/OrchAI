"""Task entities and value objects."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from orchai.domain.identifiers import ProjectId, TaskId
from orchai.domain.tasks.execution_modes import ExecutionMode
from orchai.domain.tasks.state_machine import TaskStateMachine, TaskTransition
from orchai.domain.tasks.states import TaskState


@dataclass(frozen=True, slots=True)
class TaskScope:
    """Explicit scope constraints owned by a task."""

    requested_change: str
    acceptance_criteria: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    exclusions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        requested_change = self.requested_change.strip()
        if not requested_change:
            raise ValueError("task scope requested_change must not be empty")

        object.__setattr__(self, "requested_change", requested_change)
        object.__setattr__(
            self,
            "acceptance_criteria",
            _normalize_text_tuple(self.acceptance_criteria),
        )
        object.__setattr__(self, "constraints", _normalize_text_tuple(self.constraints))
        object.__setattr__(self, "exclusions", _normalize_text_tuple(self.exclusions))


@dataclass(slots=True)
class Task:
    """Bounded unit of work coordinated by OrchAI."""

    title: str
    description: str
    scope: TaskScope
    id: TaskId = field(default_factory=TaskId.new)
    project_id: ProjectId | None = None
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    _state: TaskState = field(default=TaskState.CREATED, repr=False)

    def __post_init__(self) -> None:
        title = self.title.strip()
        description = self.description.strip()
        if not title:
            raise ValueError("task title must not be empty")
        if not description:
            raise ValueError("task description must not be empty")

        self.title = title
        self.description = description

    @property
    def state(self) -> TaskState:
        return self._state

    def transition_to(
        self,
        target: TaskState,
        *,
        state_machine: TaskStateMachine,
    ) -> TaskTransition:
        transition = state_machine.transition(self._state, target)
        self._state = transition.target
        return transition


def _normalize_text_tuple(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(value.strip() for value in values if value.strip())

