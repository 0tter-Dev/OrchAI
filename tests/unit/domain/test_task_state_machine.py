import pytest

from orchai.domain.tasks import (
    InvalidTaskStateTransitionError,
    TaskState,
    TaskStateMachine,
)


def test_allows_normal_task_progression() -> None:
    state_machine = TaskStateMachine.default()

    assert state_machine.can_transition(TaskState.CREATED, TaskState.PLANNING)
    assert state_machine.can_transition(TaskState.PLANNING, TaskState.PLANNED)
    assert state_machine.can_transition(TaskState.PLANNED, TaskState.IMPLEMENTING)
    assert state_machine.can_transition(TaskState.IMPLEMENTING, TaskState.IMPLEMENTED)
    assert state_machine.can_transition(TaskState.IMPLEMENTED, TaskState.REVIEWING)
    assert state_machine.can_transition(TaskState.REVIEWING, TaskState.VALIDATING)
    assert state_machine.can_transition(TaskState.VALIDATING, TaskState.VALIDATED)
    assert state_machine.can_transition(TaskState.VALIDATED, TaskState.COMPLETED)


def test_completed_task_is_terminal() -> None:
    state_machine = TaskStateMachine.default()

    assert state_machine.available_targets(TaskState.COMPLETED) == frozenset()

    with pytest.raises(InvalidTaskStateTransitionError):
        state_machine.transition(TaskState.COMPLETED, TaskState.IMPLEMENTING)


def test_rejects_unconfigured_transition() -> None:
    state_machine = TaskStateMachine.default()

    with pytest.raises(InvalidTaskStateTransitionError):
        state_machine.transition(TaskState.CREATED, TaskState.COMPLETED)

