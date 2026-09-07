"""Conversation and Message domain entities (ADR-014).

A `Conversation`/`Message` is a bounded context of its own, independent
of `Task`/`Execution` -- most messages are ordinary chat, not a unit of
orchestrated work. A `Message` escalates to a real `Task` only through
an explicit user action (`linked_task_id`/`linked_execution_id` are set
at that point); see `docs/decisions/ADR-014-CONVERSATION-DOMAIN-MODEL.md`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from orchai.domain.executions.entities import ResourceUsage
from orchai.domain.identifiers import (
    ConversationId,
    ExecutionId,
    MessageId,
    ModelId,
    ModuleId,
    ProjectId,
    TaskId,
)


class MessageRole(StrEnum):
    """Who authored a message."""

    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageStatus(StrEnum):
    """A message's own lifecycle -- deliberately simpler than `Task`'s or
    `Execution`'s state machines (ADR-014): a plain enum, no
    `StateMachine`-governed transitions. `STREAMING` is unused until
    Phase 4 (ADR-013) but included now so no schema migration is needed
    to add it later.
    """

    PENDING = "PENDING"
    STREAMING = "STREAMING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


@dataclass(slots=True)
class Conversation:
    """A multi-turn chat thread scoped to one Module (ADR-015)."""

    module_id: ModuleId
    id: ConversationId = field(default_factory=ConversationId.new)
    project_id: ProjectId | None = None
    title: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    archived: bool = False

    def __post_init__(self) -> None:
        self.title = self.title.strip()


@dataclass(slots=True)
class Message:
    """One turn in a Conversation."""

    conversation_id: ConversationId
    role: MessageRole
    content: str
    id: MessageId = field(default_factory=MessageId.new)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: MessageStatus = MessageStatus.COMPLETE
    error: str | None = None
    provider_name: str = ""
    model_id: ModelId | None = None
    linked_task_id: TaskId | None = None
    linked_execution_id: ExecutionId | None = None
    resource_usage: ResourceUsage = field(default_factory=ResourceUsage)

    def complete(self, *, content: str, resource_usage: ResourceUsage, provider_name: str) -> None:
        """Mark a pending assistant message as successfully completed."""

        self.content = content
        self.resource_usage = resource_usage
        self.provider_name = provider_name
        self.status = MessageStatus.COMPLETE

    def fail(self, error: str) -> None:
        """Mark a pending assistant message as failed."""

        self.status = MessageStatus.FAILED
        self.error = error
