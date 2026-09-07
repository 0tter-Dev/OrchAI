"""Conversation use-case commands (ADR-014)."""

from __future__ import annotations

from dataclasses import dataclass

from orchai.domain.identifiers import ConversationId, ModuleId, ProjectId


@dataclass(frozen=True, slots=True)
class CreateConversationCommand:
    """Command for starting a new conversation."""

    module_id: ModuleId
    project_id: ProjectId | None = None
    title: str = ""


@dataclass(frozen=True, slots=True)
class SendMessageCommand:
    """Command for sending a user message and getting an assistant reply.

    Never escalates to a Task -- see
    `docs/decisions/ADR-014-CONVERSATION-DOMAIN-MODEL.md` §2. Task
    escalation (Phase 5) is a distinct, explicit action layered on top of
    this one, not a variant of it.
    """

    conversation_id: ConversationId
    content: str
    model: str | None = None
