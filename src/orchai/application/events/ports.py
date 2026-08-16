"""Event application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.events import DomainEvent


class EventPublisher(Protocol):
    """Port for publishing domain events."""

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to interested consumers."""


class EventHandler(Protocol):
    """Port implemented by event consumers."""

    async def handle(self, event: DomainEvent) -> None:
        """Handle a published domain event."""

