"""Domain-event publishing helpers used by the orchestrator.

Extracted (Phase 7.5) from `Orchestrator`'s `_publish_*` methods: each one
only ever touched `self._event_publisher`, so they become plain functions
taking the publisher explicitly instead of bound methods.
"""

from __future__ import annotations

from orchai.application.events.ports import EventPublisher
from orchai.application.projects.ports import ProjectReadinessAssessment
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.identifiers import ProjectId
from orchai.domain.projects import Project, ProjectOperation, ProviderTarget


async def publish_project_readiness(
    *,
    event_publisher: EventPublisher,
    project: Project,
    readiness: ProjectReadinessAssessment,
) -> None:
    await event_publisher.publish(
        DomainEvent(
            event_type=EventType.PROJECT_READINESS_ASSESSED,
            source="application.orchestration",
            project_id=project.id,
            payload={
                "observed_readiness_level": readiness.readiness_level.value,
                "effective_readiness_level": project.readiness_level.value,
                "has_git": str(readiness.has_git),
                "has_documentation": str(readiness.has_documentation),
                "has_tests": str(readiness.has_tests),
            },
        )
    )


async def publish_project_operation_blocked(
    *,
    event_publisher: EventPublisher,
    project_id: ProjectId,
    readiness: str,
    provider_target: ProviderTarget,
    reason: str,
) -> None:
    await event_publisher.publish(
        DomainEvent(
            event_type=EventType.PROJECT_OPERATION_BLOCKED,
            source="application.orchestration",
            project_id=project_id,
            payload={
                "readiness_level": readiness,
                "provider_target": provider_target.value,
                "reason": reason,
            },
        )
    )


async def publish_project_operation_completed(
    *,
    event_publisher: EventPublisher,
    project_id: ProjectId,
    operation: ProjectOperation,
    payload: dict[str, str],
) -> None:
    await event_publisher.publish(
        DomainEvent(
            event_type=EventType.PROJECT_OPERATION_COMPLETED,
            source="application.orchestration",
            project_id=project_id,
            payload={
                "project_operation": operation.value,
                **payload,
            },
        )
    )


async def publish_project_operation_failed(
    *,
    event_publisher: EventPublisher,
    project_id: ProjectId,
    operation: ProjectOperation,
    reason: str,
) -> None:
    await event_publisher.publish(
        DomainEvent(
            event_type=EventType.PROJECT_OPERATION_FAILED,
            source="application.orchestration",
            project_id=project_id,
            payload={
                "project_operation": operation.value,
                "reason": reason,
            },
        )
    )
