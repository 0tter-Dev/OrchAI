"""Context application service."""

from __future__ import annotations

from orchai.application.events.ports import EventPublisher
from orchai.application.executions.ports import ExecutionRepository
from orchai.application.projects.ports import ProjectAdapterRegistry
from orchai.application.context.commands import ResolveExecutionContextCommand
from orchai.domain.context import (
    ContextPackage,
    ContextReference,
    UnauthorizedContextError,
)
from orchai.domain.events import DomainEvent, EventType


class ContextService:
    """Resolves only context already authorized for an execution."""

    def __init__(
        self,
        *,
        execution_repository: ExecutionRepository,
        project_adapters: ProjectAdapterRegistry,
        event_publisher: EventPublisher,
    ) -> None:
        self._execution_repository = execution_repository
        self._project_adapters = project_adapters
        self._event_publisher = event_publisher

    async def resolve_execution_context(
        self,
        command: ResolveExecutionContextCommand,
    ) -> ContextPackage:
        execution = await self._execution_repository.get(command.execution_id)
        if execution.project_id is None:
            raise UnauthorizedContextError("execution has no project boundary")

        requested = tuple(
            ContextReference(source=command.source, resource=resource)
            for resource in execution.requested_context
        )
        authorized = tuple(
            ContextReference(source=command.source, resource=resource)
            for resource in execution.authorized_context
        )
        if not set(authorized).issubset(set(requested)):
            raise UnauthorizedContextError(
                "authorized context must be a subset of requested context"
            )

        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.CONTEXT_REQUESTED,
                source="application.context",
                task_id=execution.task_id,
                project_id=execution.project_id,
                execution_id=execution.id,
                payload={
                    "requested_count": str(len(requested)),
                    "authorized_count": str(len(authorized)),
                },
            )
        )

        adapter = await self._project_adapters.get(execution.project_id)
        items = await adapter.resolve_context(authorized)
        package = ContextPackage(
            execution_id=execution.id,
            project_id=execution.project_id,
            requested_references=requested,
            authorized_references=authorized,
            items=items,
        )
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.CONTEXT_RESOLVED,
                source="application.context",
                task_id=execution.task_id,
                project_id=execution.project_id,
                execution_id=execution.id,
                payload={
                    "resolved_count": str(len(package.items)),
                    "provided_at": package.provided_at.isoformat(),
                },
            )
        )
        return package

