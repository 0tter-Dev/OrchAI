"""In-process event dispatcher."""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Awaitable

from orchai.domain.events import DomainEvent, EventType

EventHandlerFn = Callable[[DomainEvent], None | Awaitable[None]]


@dataclass(frozen=True, slots=True)
class EventDispatchFailure:
    """Failure captured while delivering an event to a handler."""

    event: DomainEvent
    handler_name: str
    error: Exception


class EventDispatchError(RuntimeError):
    """Raised after one or more handlers failed for an event."""

    def __init__(self, failures: tuple[EventDispatchFailure, ...]) -> None:
        super().__init__("one or more event handlers failed")
        self.failures = failures


class InProcessEventDispatcher:
    """Async-capable in-process dispatcher for the initial runtime."""

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[EventHandlerFn]] = defaultdict(list)
        self._global_handlers: list[EventHandlerFn] = []
        self._published: list[DomainEvent] = []
        self._failures: list[EventDispatchFailure] = []

    @property
    def published_events(self) -> tuple[DomainEvent, ...]:
        return tuple(self._published)

    @property
    def failures(self) -> tuple[EventDispatchFailure, ...]:
        return tuple(self._failures)

    def subscribe(self, event_type: EventType, handler: EventHandlerFn) -> None:
        self._handlers[event_type].append(handler)

    def subscribe_all(self, handler: EventHandlerFn) -> None:
        self._global_handlers.append(handler)

    async def publish(self, event: DomainEvent) -> None:
        self._published.append(event)
        failures: list[EventDispatchFailure] = []

        for handler in (*self._global_handlers, *self._handlers[event.event_type]):
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                failure = EventDispatchFailure(
                    event=event,
                    handler_name=_handler_name(handler),
                    error=exc,
                )
                failures.append(failure)
                self._failures.append(failure)

        if failures:
            raise EventDispatchError(tuple(failures))


def _handler_name(handler: EventHandlerFn) -> str:
    return getattr(handler, "__qualname__", repr(handler))
