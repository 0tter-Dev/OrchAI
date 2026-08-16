"""Execution application service."""

from __future__ import annotations

from orchai.application.authorization.ports import AuthorizationRepository
from orchai.application.events.ports import EventPublisher
from orchai.application.executions.commands import (
    CompleteExecutionCommand,
    RequestExecutionCommand,
    TransitionExecutionCommand,
)
from orchai.application.executions.ports import ExecutionRepository
from orchai.domain.authorization import AuthorizationMismatchError, RequestedOperation
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.executions import (
    Execution,
    ExecutionResult,
    ExecutionState,
    ExecutionStateMachine,
    ExecutionTransition,
)


class ExecutionService:
    """Coordinates execution lifecycle without invoking AI providers directly."""

    def __init__(
        self,
        *,
        repository: ExecutionRepository,
        authorization_repository: AuthorizationRepository,
        event_publisher: EventPublisher,
        state_machine: ExecutionStateMachine | None = None,
    ) -> None:
        self._repository = repository
        self._authorization_repository = authorization_repository
        self._event_publisher = event_publisher
        self._state_machine = state_machine or ExecutionStateMachine.default()

    async def request_execution(self, command: RequestExecutionCommand) -> Execution:
        authorization = await self._authorization_repository.get(
            command.authorization_id
        )
        if authorization.task_id != command.task_id:
            raise AuthorizationMismatchError(
                "authorization does not belong to execution task"
            )
        authorization.ensure_grants(
            operation=RequestedOperation(
                role=command.role,
                action=command.action,
                model_id=command.model_id,
                context_scope=tuple(command.authorized_context),
            )
        )

        execution = Execution(
            task_id=command.task_id,
            role=command.role,
            action=command.action,
            model_id=command.model_id,
            authorization_id=command.authorization_id,
            project_id=command.project_id,
            requested_context=tuple(command.requested_context),
            authorized_context=tuple(command.authorized_context),
        )
        await self._repository.add(execution)
        await self._event_publisher.publish(
            _execution_event(
                execution=execution,
                event_type=EventType.EXECUTION_REQUESTED,
                payload={"state": execution.state.value},
            )
        )

        transition = execution.transition_to(
            ExecutionState.AUTHORIZED,
            state_machine=self._state_machine,
        )
        await self._repository.save(execution)
        await self._event_publisher.publish(
            _transition_event(
                execution=execution,
                transition=transition,
                event_type=EventType.EXECUTION_AUTHORIZED,
            )
        )
        return execution

    async def transition_execution(
        self,
        command: TransitionExecutionCommand,
    ) -> Execution:
        execution = await self._repository.get(command.execution_id)
        transition = execution.transition_to(
            command.target_state,
            state_machine=self._state_machine,
        )
        await self._repository.save(execution)
        await self._event_publisher.publish(
            _transition_event(
                execution=execution,
                transition=transition,
                event_type=_transition_event_type(transition.target),
            )
        )
        return execution

    async def complete_execution(
        self,
        command: CompleteExecutionCommand,
    ) -> Execution:
        execution = await self._repository.get(command.execution_id)
        result = ExecutionResult(
            output=command.output,
            success=command.success,
            errors=tuple(command.errors),
            warnings=tuple(command.warnings),
            resource_usage=command.resource_usage,
            metadata=command.metadata,
        )
        transition = execution.complete(result, state_machine=self._state_machine)
        await self._repository.save(execution)
        await self._event_publisher.publish(
            _transition_event(
                execution=execution,
                transition=transition,
                event_type=_transition_event_type(transition.target),
            )
        )
        return execution


def _transition_event_type(target: ExecutionState) -> EventType:
    if target is ExecutionState.STARTED:
        return EventType.EXECUTION_STARTED
    if target is ExecutionState.COMPLETED:
        return EventType.EXECUTION_COMPLETED
    if target is ExecutionState.FAILED:
        return EventType.EXECUTION_FAILED
    return EventType.EXECUTION_STATE_TRANSITIONED


def _transition_event(
    *,
    execution: Execution,
    transition: ExecutionTransition,
    event_type: EventType,
) -> DomainEvent:
    return _execution_event(
        execution=execution,
        event_type=event_type,
        payload={
            "from_state": transition.source.value,
            "to_state": transition.target.value,
        },
    )


def _execution_event(
    *,
    execution: Execution,
    event_type: EventType,
    payload: dict[str, str],
) -> DomainEvent:
    return DomainEvent(
        event_type=event_type,
        source="application.executions",
        task_id=execution.task_id,
        project_id=execution.project_id,
        execution_id=execution.id,
        payload={
            "execution_id": str(execution.id),
            "authorization_id": str(execution.authorization_id),
            "role": execution.role.value,
            "action": execution.action.value,
            "model_id": str(execution.model_id),
            **payload,
        },
    )
