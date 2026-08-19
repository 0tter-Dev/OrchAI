"""Audit consumers for orchestration events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from orchai.application.audit.ports import AuditRepository
from orchai.domain.audit import AuditRecord
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.identifiers import AuthorizationId


class AuditEventHandler:
    """Turns immutable domain events into independently queryable audit records."""

    def __init__(self, repository: AuditRepository) -> None:
        self._repository = repository

    async def handle(self, event: DomainEvent) -> None:
        await self._repository.add(
            AuditRecord(
                actor=_actor_for(event),
                operation=event.event_type.value,
                outcome=_outcome_for(event.event_type),
                occurred_at=event.occurred_at,
                task_id=event.task_id,
                project_id=event.project_id,
                execution_id=event.execution_id,
                authorization_id=_authorization_id_from(event.payload),
                event_id=event.event_id,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                metadata={
                    "source": event.source,
                    "event_type": event.event_type.value,
                    "payload": dict(event.payload),
                },
            )
        )


def _actor_for(event: DomainEvent) -> str:
    payload = event.payload
    for key in ("decided_by", "requester", "actor"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return event.source


def _outcome_for(event_type: EventType) -> str:
    if event_type in {
        EventType.AUTHORIZATION_REJECTED,
        EventType.EXECUTION_FAILED,
        EventType.REVIEW_FAILED,
        EventType.VALIDATION_FAILED,
        EventType.TEST_FAILED,
        EventType.CONTEXT_REJECTED,
    }:
        return "failed"
    if event_type in {
        EventType.AUTHORIZATION_GRANTED,
        EventType.EXECUTION_COMPLETED,
        EventType.TASK_COMPLETED,
        EventType.CONTEXT_RESOLVED,
    }:
        return "succeeded"
    if event_type is EventType.AUTHORIZATION_REVOKED:
        return "revoked"
    if event_type is EventType.AUTHORIZATION_EXPIRED:
        return "expired"
    return "recorded"


def _authorization_id_from(payload: Any) -> AuthorizationId | None:
    if not isinstance(payload, Mapping):
        return None
    value = payload.get("authorization_id")
    if not isinstance(value, str) or not value.strip():
        return None
    return AuthorizationId(value)
