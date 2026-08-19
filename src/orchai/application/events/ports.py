"""Event application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.events import DomainEvent
from orchai.domain.identifiers import TaskId


class EventPublisher(Protocol):
    """Port for publishing domain events."""

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to interested consumers."""


class EventHandler(Protocol):
    """Port implemented by event consumers."""

    async def handle(self, event: DomainEvent) -> None:
        """Handle a published domain event."""


class EventRepository(Protocol):
    """Port for durable domain event history."""

    async def add(self, event: DomainEvent) -> None:
        """Persist an immutable event."""

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        limit: int = 20,
    ) -> tuple[DomainEvent, ...]:
        """Return events, newest first."""
