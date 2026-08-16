"""Authoritative execution state machine."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from orchai.domain.executions.states import ExecutionState


class InvalidExecutionStateTransitionError(ValueError):
    """Raised when an execution state transition is not allowed."""

    def __init__(self, source: ExecutionState, target: ExecutionState) -> None:
        message = f"invalid execution state transition: {source.value} -> {target.value}"
        super().__init__(message)
        self.source = source
        self.target = target


@dataclass(frozen=True, slots=True)
class ExecutionTransition:
    """A valid execution state transition."""

    source: ExecutionState
    target: ExecutionState


class ExecutionStateMachine:
    """Deterministic execution lifecycle transition rules."""

    def __init__(
        self,
        transitions: Mapping[ExecutionState, frozenset[ExecutionState]],
    ) -> None:
        self._transitions = dict(transitions)

    @classmethod
    def default(cls) -> "ExecutionStateMachine":
        return cls(
            {
                ExecutionState.REQUESTED: frozenset(
                    {
                        ExecutionState.AUTHORIZED,
                        ExecutionState.REJECTED,
                        ExecutionState.BLOCKED,
                        ExecutionState.CANCELLED,
                    }
                ),
                ExecutionState.AUTHORIZED: frozenset(
                    {
                        ExecutionState.PREPARING,
                        ExecutionState.BLOCKED,
                        ExecutionState.CANCELLED,
                    }
                ),
                ExecutionState.PREPARING: frozenset(
                    {
                        ExecutionState.STARTED,
                        ExecutionState.BLOCKED,
                        ExecutionState.FAILED,
                        ExecutionState.CANCELLED,
                    }
                ),
                ExecutionState.STARTED: frozenset(
                    {
                        ExecutionState.RUNNING,
                        ExecutionState.COMPLETED,
                        ExecutionState.FAILED,
                        ExecutionState.TIMEOUT,
                        ExecutionState.CANCELLED,
                    }
                ),
                ExecutionState.RUNNING: frozenset(
                    {
                        ExecutionState.COMPLETED,
                        ExecutionState.FAILED,
                        ExecutionState.TIMEOUT,
                        ExecutionState.CANCELLED,
                    }
                ),
                ExecutionState.REJECTED: frozenset(),
                ExecutionState.BLOCKED: frozenset(),
                ExecutionState.COMPLETED: frozenset(),
                ExecutionState.FAILED: frozenset(),
                ExecutionState.CANCELLED: frozenset(),
                ExecutionState.TIMEOUT: frozenset(),
            }
        )

    def can_transition(self, source: ExecutionState, target: ExecutionState) -> bool:
        return target in self._transitions.get(source, frozenset())

    def transition(
        self,
        source: ExecutionState,
        target: ExecutionState,
    ) -> ExecutionTransition:
        if not self.can_transition(source, target):
            raise InvalidExecutionStateTransitionError(source, target)
        return ExecutionTransition(source=source, target=target)

    def available_targets(self, source: ExecutionState) -> frozenset[ExecutionState]:
        return self._transitions.get(source, frozenset())

