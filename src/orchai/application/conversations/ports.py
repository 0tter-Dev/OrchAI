"""Conversation application ports (ADR-014)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Literal, Protocol

from orchai.domain.conversations import Conversation, Message
from orchai.domain.identifiers import ConversationId, MessageId, ModuleId, ProjectId


class ConversationRepository(Protocol):
    """Persistence boundary for conversations."""

    async def add(self, conversation: Conversation) -> None:
        """Persist a newly created conversation."""

    async def get(self, conversation_id: ConversationId) -> Conversation:
        """Return a conversation by id."""

    async def save(self, conversation: Conversation) -> None:
        """Persist changes to an existing conversation."""

    async def list(
        self,
        *,
        module_id: ModuleId | None = None,
        project_id: ProjectId | None = None,
        limit: int = 20,
    ) -> tuple[Conversation, ...]:
        """Return persisted conversations, most recently created first."""


class MessageRepository(Protocol):
    """Persistence boundary for messages."""

    async def add(self, message: Message) -> None:
        """Persist a newly created message."""

    async def get(self, message_id: MessageId) -> Message:
        """Return a message by id."""

    async def save(self, message: Message) -> None:
        """Persist changes to an existing message."""

    async def list(
        self,
        *,
        conversation_id: ConversationId,
        limit: int = 100,
    ) -> tuple[Message, ...]:
        """Return a conversation's messages, oldest first."""


#: A single turn shaped for a provider call -- deliberately not
#: `AIProviderExecutionRequest` (application/executions/ports.py): that
#: DTO is Task/Role/Action-shaped (ADR-013), and most conversation
#: messages are not Task-shaped at all (ADR-014). Role is a plain string
#: ("user" | "assistant" | "system") matching the wire format every LLM
#: chat API already uses, not `domain.conversations.MessageRole`, to
#: keep this port independent of that enum's exact values.
@dataclass(frozen=True, slots=True)
class ConversationTurn:
    role: Literal["user", "assistant", "system"]
    content: str


@dataclass(frozen=True, slots=True)
class ConversationCompletionRequest:
    """Bounded, Task-independent completion request for plain chat."""

    model: str
    system_prompt: str
    history: tuple[ConversationTurn, ...]


@dataclass(frozen=True, slots=True)
class ConversationCompletionResult:
    """Provider-independent outcome of a conversational completion."""

    content: str
    provider_name: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None


@dataclass(frozen=True, slots=True)
class ConversationStreamChunk:
    """One incremental chunk of a streamed conversational reply (Phase 4)."""

    delta: str
    finished: bool = False
    provider_name: str = ""
    input_tokens: int | None = None
    output_tokens: int | None = None


class ConversationAIProviderPort(Protocol):
    """AI provider boundary for plain (non-Task) conversation turns.

    Kept separate from `AIProviderPort` (application/executions/ports.py)
    because that port is Task/Role/Action-shaped -- see the
    `ConversationTurn` docstring above and
    `docs/decisions/ADR-014-CONVERSATION-DOMAIN-MODEL.md`'s implementation
    note. Implemented by the same `LiteLLMProvider` adapter introduced in
    ADR-013 (one adapter, two application-facing port contracts).
    """

    async def complete(
        self,
        request: ConversationCompletionRequest,
    ) -> ConversationCompletionResult:
        """Return a single, non-streaming completion for `request`."""

    def complete_stream(
        self,
        request: ConversationCompletionRequest,
    ) -> AsyncIterator[ConversationStreamChunk]:
        """Streaming variant of `complete()`.

        Not `async def`: implementations are async generators, called
        directly (never awaited first) to get the iterator.
        """
