"""Append-oriented audit records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from orchai.domain.identifiers import (
    AuditRecordId,
    AuthorizationId,
    CausationId,
    CorrelationId,
    EventId,
    ExecutionId,
    ProjectId,
    TaskId,
)


@dataclass(frozen=True, slots=True)
class AuditRecord:
    """Historical operational record derived from orchestration activity."""

    actor: str
    operation: str
    outcome: str
    id: AuditRecordId = field(default_factory=AuditRecordId.new)
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    task_id: TaskId | None = None
    project_id: ProjectId | None = None
    execution_id: ExecutionId | None = None
    authorization_id: AuthorizationId | None = None
    event_id: EventId | None = None
    correlation_id: CorrelationId | None = None
    causation_id: CausationId | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        actor = self.actor.strip()
        operation = self.operation.strip()
        outcome = self.outcome.strip()
        if not actor:
            raise ValueError("audit actor must not be empty")
        if not operation:
            raise ValueError("audit operation must not be empty")
        if not outcome:
            raise ValueError("audit outcome must not be empty")

        object.__setattr__(self, "actor", actor)
        object.__setattr__(self, "operation", operation)
        object.__setattr__(self, "outcome", outcome)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))
