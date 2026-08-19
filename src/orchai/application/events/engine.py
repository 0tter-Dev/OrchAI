"""Durable in-process event engine."""

from __future__ import annotations

from orchai.application.events.dispatcher import (
    EventDispatchFailure,
    EventHandlerFn,
    InProcessEventDispatcher,
)
from orchai.application.events.ports import EventRepository
from orchai.domain.events import DomainEvent, EventType


class EventEngine:
    """Persists domain events before dispatching them in-process."""

    def __init__(
        self,
        *,
        repository: EventRepository,
        dispatcher: InProcessEventDispatcher | None = None,
    ) -> None:
        self._repository = repository
        self._dispatcher = dispatcher or InProcessEventDispatcher()

    @property
    def published_events(self) -> tuple[DomainEvent, ...]:
        return self._dispatcher.published_events

    @property
    def failures(self) -> tuple[EventDispatchFailure, ...]:
        return self._dispatcher.failures

    def subscribe(self, event_type: EventType, handler: EventHandlerFn) -> None:
        self._dispatcher.subscribe(event_type, handler)

    def subscribe_all(self, handler: EventHandlerFn) -> None:
        self._dispatcher.subscribe_all(handler)

    async def publish(self, event: DomainEvent) -> None:
        await self._repository.add(event)
        await self._dispatcher.publish(event)
