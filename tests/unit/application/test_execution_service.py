import asyncio

import pytest

from orchai.application.authorization import (
    AuthorizationService,
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.events import InProcessEventDispatcher
from orchai.application.executions import (
    CompleteExecutionCommand,
    ExecutionService,
    RequestExecutionCommand,
    TransitionExecutionCommand,
)
from orchai.domain.actions import ActionName
from orchai.domain.authorization import (
    AuthorizationMismatchError,
    AuthorizationDecisionStatus,
    AuthorizationNotGrantedError,
)
from orchai.domain.events import EventType
from orchai.domain.executions import ExecutionState
from orchai.domain.identifiers import ModelId, TaskId
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode
from orchai.infrastructure.persistence import (
    InMemoryAuthorizationRepository,
    InMemoryExecutionRepository,
)


def test_execution_service_creates_only_authorized_execution() -> None:
    async def run() -> None:
        authorization_repository = InMemoryAuthorizationRepository()
        execution_repository = InMemoryExecutionRepository()
        events = InProcessEventDispatcher()
        authorization_service = AuthorizationService(
            repository=authorization_repository,
            event_publisher=events,
        )
        execution_service = ExecutionService(
            repository=execution_repository,
            authorization_repository=authorization_repository,
            event_publisher=events,
        )
        task_id = TaskId.new()
        model_id = ModelId("codex")
        authorization = await authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                context_scope=("src",),
                reason="Implement the requested task.",
                requester="user",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        await authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="user",
                reason="Approved.",
            )
        )

        execution = await execution_service.request_execution(
            RequestExecutionCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                authorization_id=authorization.id,
                requested_context=("src", "docs"),
                authorized_context=("src",),
            )
        )

        assert execution.state is ExecutionState.AUTHORIZED
        assert events.published_events[-2].event_type is EventType.EXECUTION_REQUESTED
        assert events.published_events[-1].event_type is EventType.EXECUTION_AUTHORIZED

    asyncio.run(run())


def test_execution_service_rejects_ungranted_authorization() -> None:
    async def run() -> None:
        authorization_repository = InMemoryAuthorizationRepository()
        execution_repository = InMemoryExecutionRepository()
        events = InProcessEventDispatcher()
        authorization_service = AuthorizationService(
            repository=authorization_repository,
            event_publisher=events,
        )
        execution_service = ExecutionService(
            repository=execution_repository,
            authorization_repository=authorization_repository,
            event_publisher=events,
        )
        model_id = ModelId("codex")
        authorization = await authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=TaskId.new(),
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                reason="Implement the requested task.",
                requester="user",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )

        with pytest.raises(AuthorizationNotGrantedError):
            await execution_service.request_execution(
                RequestExecutionCommand(
                    task_id=authorization.task_id,
                    role=RoleName.DEVELOPER,
                    action=ActionName.IMPLEMENT,
                    model_id=model_id,
                    authorization_id=authorization.id,
                )
            )

    asyncio.run(run())


def test_execution_service_rejects_authorization_from_another_task() -> None:
    async def run() -> None:
        authorization_repository = InMemoryAuthorizationRepository()
        execution_repository = InMemoryExecutionRepository()
        events = InProcessEventDispatcher()
        authorization_service = AuthorizationService(
            repository=authorization_repository,
            event_publisher=events,
        )
        execution_service = ExecutionService(
            repository=execution_repository,
            authorization_repository=authorization_repository,
            event_publisher=events,
        )
        model_id = ModelId("codex")
        authorization = await authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=TaskId.new(),
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                reason="Implement the requested task.",
                requester="user",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        await authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="user",
                reason="Approved.",
            )
        )

        with pytest.raises(AuthorizationMismatchError):
            await execution_service.request_execution(
                RequestExecutionCommand(
                    task_id=TaskId.new(),
                    role=RoleName.DEVELOPER,
                    action=ActionName.IMPLEMENT,
                    model_id=model_id,
                    authorization_id=authorization.id,
                )
            )

    asyncio.run(run())


def test_execution_service_records_completion_result() -> None:
    async def run() -> None:
        authorization_repository = InMemoryAuthorizationRepository()
        execution_repository = InMemoryExecutionRepository()
        events = InProcessEventDispatcher()
        authorization_service = AuthorizationService(
            repository=authorization_repository,
            event_publisher=events,
        )
        execution_service = ExecutionService(
            repository=execution_repository,
            authorization_repository=authorization_repository,
            event_publisher=events,
        )
        task_id = TaskId.new()
        model_id = ModelId("codex")
        authorization = await authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                reason="Implement the requested task.",
                requester="user",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        await authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="user",
                reason="Approved.",
            )
        )
        execution = await execution_service.request_execution(
            RequestExecutionCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                authorization_id=authorization.id,
            )
        )
        await execution_service.transition_execution(
            TransitionExecutionCommand(
                execution_id=execution.id,
                target_state=ExecutionState.PREPARING,
            )
        )
        await execution_service.transition_execution(
            TransitionExecutionCommand(
                execution_id=execution.id,
                target_state=ExecutionState.STARTED,
            )
        )
        await execution_service.transition_execution(
            TransitionExecutionCommand(
                execution_id=execution.id,
                target_state=ExecutionState.RUNNING,
            )
        )

        completed = await execution_service.complete_execution(
            CompleteExecutionCommand(
                execution_id=execution.id,
                output="Implemented.",
            )
        )

        assert completed.state is ExecutionState.COMPLETED
        assert completed.result is not None
        assert completed.result.output == "Implemented."
        assert events.published_events[-1].event_type is EventType.EXECUTION_COMPLETED

    asyncio.run(run())


def test_execution_service_retry_creates_distinct_attempts() -> None:
    async def run() -> None:
        authorization_repository = InMemoryAuthorizationRepository()
        execution_repository = InMemoryExecutionRepository()
        events = InProcessEventDispatcher()
        authorization_service = AuthorizationService(
            repository=authorization_repository,
            event_publisher=events,
        )
        execution_service = ExecutionService(
            repository=execution_repository,
            authorization_repository=authorization_repository,
            event_publisher=events,
        )
        task_id = TaskId.new()
        model_id = ModelId("codex")
        authorization = await authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                reason="Implement the requested task.",
                requester="user",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        await authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="user",
                reason="Approved.",
            )
        )

        first = await execution_service.request_execution(
            RequestExecutionCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                authorization_id=authorization.id,
            )
        )
        second = await execution_service.request_execution(
            RequestExecutionCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                authorization_id=authorization.id,
            )
        )

        assert first.id != second.id
        assert first.task_id == second.task_id
        assert first.authorization_id == second.authorization_id

    asyncio.run(run())
