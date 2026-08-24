"""In-memory event repository."""

from __future__ import annotations

from orchai.application.events import EventRepository
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.identifiers import EventId, ExecutionId, ProjectId, TaskId


class InMemoryEventRepository(EventRepository):
    """Non-durable event history for tests and local composition."""

    def __init__(self) -> None:
        self._events: dict[EventId, DomainEvent] = {}

    async def add(self, event: DomainEvent) -> None:
        self._events.setdefault(event.event_id, event)

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        execution_id: ExecutionId | None = None,
        event_type: EventType | None = None,
        limit: int = 20,
    ) -> tuple[DomainEvent, ...]:
        events = tuple(
            event
            for event in self._events.values()
            if (task_id is None or event.task_id == task_id)
            and (project_id is None or event.project_id == project_id)
            and (execution_id is None or event.execution_id == execution_id)
            and (event_type is None or event.event_type is event_type)
        )
        return tuple(
            sorted(events, key=lambda event: event.occurred_at, reverse=True)[:limit]
        )
