import pytest

from orchai.domain.actions import ActionName
from orchai.domain.executions import (
    Execution,
    ExecutionResult,
    ExecutionState,
    ExecutionStateMachine,
    InvalidExecutionStateTransitionError,
)
from orchai.domain.identifiers import AuthorizationId, ModelId, TaskId
from orchai.domain.roles import RoleName


def test_execution_lifecycle_reaches_completed_with_result() -> None:
    execution = Execution(
        task_id=TaskId.new(),
        role=RoleName.DEVELOPER,
        action=ActionName.IMPLEMENT,
        model_id=ModelId("codex"),
        authorization_id=AuthorizationId.new(),
    )
    state_machine = ExecutionStateMachine.default()

    execution.transition_to(ExecutionState.AUTHORIZED, state_machine=state_machine)
    execution.transition_to(ExecutionState.PREPARING, state_machine=state_machine)
    execution.transition_to(ExecutionState.STARTED, state_machine=state_machine)
    execution.transition_to(ExecutionState.RUNNING, state_machine=state_machine)
    transition = execution.complete(
        ExecutionResult(output="Implemented.", success=True),
        state_machine=state_machine,
    )

    assert transition.target is ExecutionState.COMPLETED
    assert execution.state is ExecutionState.COMPLETED
    assert execution.result is not None
    assert execution.result.output == "Implemented."


def test_completed_execution_is_terminal() -> None:
    state_machine = ExecutionStateMachine.default()

    assert state_machine.available_targets(ExecutionState.COMPLETED) == frozenset()

    with pytest.raises(InvalidExecutionStateTransitionError):
        state_machine.transition(ExecutionState.COMPLETED, ExecutionState.RUNNING)


def test_failed_execution_result_requires_error_detail() -> None:
    with pytest.raises(ValueError):
        ExecutionResult(output="", success=False)

