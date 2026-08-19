"""Context application service."""

from __future__ import annotations

from hashlib import sha256

from orchai.application.context.commands import ResolveExecutionContextCommand
from orchai.application.context.ports import ContextResolutionRepository
from orchai.application.events.ports import EventPublisher
from orchai.application.executions.ports import ExecutionRepository
from orchai.application.projects.ports import ProjectAdapterRegistry
from orchai.domain.capabilities import CapabilityName
from orchai.domain.context import (
    ContextPackage,
    ContextReference,
    ContextResolutionRecord,
    UnauthorizedContextError,
)
from orchai.domain.events import DomainEvent, EventType
from orchai.infrastructure.projects.errors import ProjectCapabilityError


class ContextService:
    """Resolves only context already authorized for an execution."""

    def __init__(
        self,
        *,
        execution_repository: ExecutionRepository,
        project_adapters: ProjectAdapterRegistry,
        event_publisher: EventPublisher,
        resolution_repository: ContextResolutionRepository | None = None,
    ) -> None:
        self._execution_repository = execution_repository
        self._project_adapters = project_adapters
        self._event_publisher = event_publisher
        self._resolution_repository = resolution_repository

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
        adapter_capabilities = await adapter.capabilities()
        for reference in authorized:
            required = _required_capability(reference)
            if required not in adapter_capabilities:
                raise ProjectCapabilityError(
                    f"adapter lacks required capability: {required.value}"
                )
        items = await adapter.resolve_context(authorized)
        package = ContextPackage(
            execution_id=execution.id,
            project_id=execution.project_id,
            requested_references=requested,
            authorized_references=authorized,
            items=items,
        )
        records = _resolution_records(package)
        if self._resolution_repository is not None:
            await self._resolution_repository.add_many(records)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.CONTEXT_RESOLVED,
                source="application.context",
                task_id=execution.task_id,
                project_id=execution.project_id,
                execution_id=execution.id,
                payload={
                    "resolved_count": str(len(package.items)),
                    "resolution_records": str(len(records)),
                    "provided_at": package.provided_at.isoformat(),
                },
            )
        )
        return package


def _resolution_records(
    package: ContextPackage,
) -> tuple[ContextResolutionRecord, ...]:
    return tuple(
        ContextResolutionRecord(
            execution_id=package.execution_id,
            project_id=package.project_id,
            reference=item.reference,
            content_sha256=sha256(item.content.encode("utf-8")).hexdigest(),
            content_bytes=len(item.content.encode("utf-8")),
            resolved_at=package.provided_at,
            metadata=dict(item.metadata),
        )
        for item in package.items
    )


def _required_capability(reference: ContextReference) -> CapabilityName:
    if reference.source.value == "PROJECT_DOCUMENTATION":
        return CapabilityName.READ_DOCUMENTATION
    return CapabilityName.READ_PROJECT
