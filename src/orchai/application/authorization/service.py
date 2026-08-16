"""Authorization application service."""

from __future__ import annotations

from orchai.application.authorization.commands import (
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.authorization.ports import AuthorizationRepository
from orchai.application.events.ports import EventPublisher
from orchai.domain.authorization import (
    Authorization,
    AuthorizationDecision,
    AuthorizationDecisionStatus,
    AuthorizationRequest,
    RequestedOperation,
)
from orchai.domain.events import DomainEvent, EventType


class AuthorizationService:
    """Coordinates authorization use cases without executing operations."""

    def __init__(
        self,
        *,
        repository: AuthorizationRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    async def request_authorization(
        self,
        command: RequestAuthorizationCommand,
    ) -> Authorization:
        operation = RequestedOperation(
            role=command.role,
            action=command.action,
            model_id=command.model_id,
            context_scope=tuple(command.context_scope),
            proposed_state=command.proposed_state,
        )
        authorization = Authorization.request_authorization(
            AuthorizationRequest(
                task_id=command.task_id,
                operation=operation,
                reason=command.reason,
                requester=command.requester,
                execution_mode=command.execution_mode,
                expires_at=command.expires_at,
            )
        )
        await self._repository.add(authorization)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.AUTHORIZATION_REQUESTED,
                source="application.authorization",
                task_id=authorization.task_id,
                payload=_authorization_payload(authorization),
            )
        )
        return authorization

    async def decide_authorization(
        self,
        command: DecideAuthorizationCommand,
    ) -> Authorization:
        authorization = await self._repository.get(command.authorization_id)
        decision = AuthorizationDecision(
            request_id=authorization.id,
            status=command.status,
            decided_by=command.decided_by,
            reason=command.reason,
        )
        authorization.record_decision(decision)
        await self._repository.save(authorization)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=_decision_event_type(command.status),
                source="application.authorization",
                task_id=authorization.task_id,
                payload=_authorization_payload(authorization),
            )
        )
        return authorization


def _decision_event_type(status: AuthorizationDecisionStatus) -> EventType:
    if status is AuthorizationDecisionStatus.GRANTED:
        return EventType.AUTHORIZATION_GRANTED
    if status is AuthorizationDecisionStatus.REJECTED:
        return EventType.AUTHORIZATION_REJECTED
    if status is AuthorizationDecisionStatus.EXPIRED:
        return EventType.AUTHORIZATION_EXPIRED
    return EventType.AUTHORIZATION_REVOKED


def _authorization_payload(authorization: Authorization) -> dict[str, str | None]:
    operation = authorization.request.operation
    return {
        "authorization_id": str(authorization.id),
        "role": operation.role.value,
        "action": operation.action.value,
        "model_id": str(operation.model_id) if operation.model_id is not None else None,
        "status": authorization.status.value if authorization.status is not None else None,
    }

