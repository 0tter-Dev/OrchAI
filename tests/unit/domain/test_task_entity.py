import pytest

from orchai.domain.tasks import Task, TaskScope, TaskState, TaskStateMachine


def test_task_starts_created_and_transitions_through_state_machine() -> None:
    task = Task(
        title="Implement task lifecycle",
        description="Create first domain slice.",
        scope=TaskScope(requested_change="Add task state machine."),
    )

    transition = task.transition_to(
        TaskState.PLANNING,
        state_machine=TaskStateMachine.default(),
    )

    assert transition.source is TaskState.CREATED
    assert transition.target is TaskState.PLANNING
    assert task.state is TaskState.PLANNING


def test_task_requires_explicit_scope() -> None:
    with pytest.raises(ValueError):
        Task(
            title="No scope",
            description="Invalid task.",
            scope=TaskScope(requested_change=" "),
        )

