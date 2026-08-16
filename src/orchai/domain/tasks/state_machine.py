"""Authoritative task state machine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from orchai.domain.tasks.states import TaskState


class InvalidTaskStateTransitionError(ValueError):
    """Raised when a task state transition is not allowed."""

    def __init__(self, source: TaskState, target: TaskState) -> None:
        message = f"invalid task state transition: {source.value} -> {target.value}"
        super().__init__(message)
        self.source = source
        self.target = target


@dataclass(frozen=True, slots=True)
class TaskTransition:
    """A valid state transition produced by the state machine."""

    source: TaskState
    target: TaskState


class TaskStateMachine:
    """Deterministic task lifecycle transition rules."""

    def __init__(self, transitions: Mapping[TaskState, frozenset[TaskState]]) -> None:
        self._transitions = dict(transitions)

    @classmethod
    def default(cls) -> "TaskStateMachine":
        return cls(
            {
                TaskState.CREATED: frozenset(
                    {
                        TaskState.PLANNING,
                        TaskState.PLANNED,
                        TaskState.BLOCKED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.PLANNING: frozenset(
                    {
                        TaskState.PLANNED,
                        TaskState.BLOCKED,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.PLANNED: frozenset(
                    {
                        TaskState.IMPLEMENTING,
                        TaskState.REVIEWING,
                        TaskState.VALIDATING,
                        TaskState.TESTING,
                        TaskState.BLOCKED,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.IMPLEMENTING: frozenset(
                    {
                        TaskState.IMPLEMENTED,
                        TaskState.BLOCKED,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.IMPLEMENTED: frozenset(
                    {
                        TaskState.REVIEWING,
                        TaskState.VALIDATING,
                        TaskState.TESTING,
                        TaskState.COMPLETED,
                        TaskState.BLOCKED,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.REVIEWING: frozenset(
                    {
                        TaskState.IMPLEMENTING,
                        TaskState.VALIDATING,
                        TaskState.TESTING,
                        TaskState.COMPLETED,
                        TaskState.BLOCKED,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.VALIDATING: frozenset(
                    {
                        TaskState.IMPLEMENTING,
                        TaskState.TESTING,
                        TaskState.VALIDATED,
                        TaskState.BLOCKED,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.TESTING: frozenset(
                    {
                        TaskState.IMPLEMENTING,
                        TaskState.VALIDATED,
                        TaskState.BLOCKED,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.VALIDATED: frozenset(
                    {
                        TaskState.COMPLETED,
                        TaskState.BLOCKED,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.BLOCKED: frozenset(
                    {
                        TaskState.PLANNING,
                        TaskState.IMPLEMENTING,
                        TaskState.REVIEWING,
                        TaskState.VALIDATING,
                        TaskState.TESTING,
                        TaskState.FAILED,
                        TaskState.CANCELLED,
                    }
                ),
                TaskState.COMPLETED: frozenset(),
                TaskState.FAILED: frozenset(),
                TaskState.CANCELLED: frozenset(),
            }
        )

    def can_transition(self, source: TaskState, target: TaskState) -> bool:
        return target in self._transitions.get(source, frozenset())

    def transition(self, source: TaskState, target: TaskState) -> TaskTransition:
        if not self.can_transition(source, target):
            raise InvalidTaskStateTransitionError(source, target)
        return TaskTransition(source=source, target=target)

    def available_targets(self, source: TaskState) -> frozenset[TaskState]:
        return self._transitions.get(source, frozenset())

