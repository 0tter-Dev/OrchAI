import asyncio

from orchai.application.authorization import (
    AuthorizationService,
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.events import InProcessEventDispatcher
from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.events import EventType
from orchai.domain.identifiers import ModelId, TaskId
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode
from orchai.infrastructure.persistence import InMemoryAuthorizationRepository


def test_authorization_service_requests_and_grants_authorization() -> None:
    async def run() -> None:
        repository = InMemoryAuthorizationRepository()
        events = InProcessEventDispatcher()
        service = AuthorizationService(
            repository=repository,
            event_publisher=events,
        )

        authorization = await service.request_authorization(
            RequestAuthorizationCommand(
                task_id=TaskId.new(),
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=ModelId("codex"),
                reason="Implement a task.",
                requester="user",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        decided = await service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="user",
                reason="Approved.",
            )
        )

        assert decided.status is AuthorizationDecisionStatus.GRANTED
        assert events.published_events[0].event_type is EventType.AUTHORIZATION_REQUESTED
        assert events.published_events[1].event_type is EventType.AUTHORIZATION_GRANTED

    asyncio.run(run())

