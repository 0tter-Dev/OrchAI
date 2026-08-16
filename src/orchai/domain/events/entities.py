"""Immutable domain event facts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from orchai.domain.events.types import EventType
from orchai.domain.identifiers import (
    CausationId,
    CorrelationId,
    EventId,
    ExecutionId,
    ProjectId,
    TaskId,
)


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Historical fact emitted by the orchestration domain."""

    event_type: EventType
    source: str
    event_id: EventId = field(default_factory=EventId.new)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    task_id: TaskId | None = None
    project_id: ProjectId | None = None
    execution_id: ExecutionId | None = None
    correlation_id: CorrelationId | None = None
    causation_id: CausationId | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        source = self.source.strip()
        if not source:
            raise ValueError("event source must not be empty")
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "payload", MappingProxyType(dict(self.payload)))

