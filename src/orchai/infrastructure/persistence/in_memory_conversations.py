"""In-memory conversation/message repositories for tests and local bootstrap."""

from __future__ import annotations

from orchai.application.conversations.ports import ConversationRepository, MessageRepository
from orchai.domain.conversations import Conversation, Message
from orchai.domain.identifiers import ConversationId, MessageId, ModuleId, ProjectId


class ConversationNotFoundError(LookupError):
    """Raised when a conversation is not present in the repository."""


class MessageNotFoundError(LookupError):
    """Raised when a message is not present in the repository."""


class InMemoryConversationRepository(ConversationRepository):
    """Simple non-durable repository implementation."""

    def __init__(self) -> None:
        self._conversations: dict[ConversationId, Conversation] = {}

    async def add(self, conversation: Conversation) -> None:
        self._conversations[conversation.id] = conversation

    async def get(self, conversation_id: ConversationId) -> Conversation:
        try:
            return self._conversations[conversation_id]
        except KeyError as exc:
            raise ConversationNotFoundError(str(conversation_id)) from exc

    async def save(self, conversation: Conversation) -> None:
        if conversation.id not in self._conversations:
            raise ConversationNotFoundError(str(conversation.id))
        self._conversations[conversation.id] = conversation

    async def list(
        self,
        *,
        module_id: ModuleId | None = None,
        project_id: ProjectId | None = None,
        limit: int = 20,
    ) -> tuple[Conversation, ...]:
        conversations = tuple(reversed(tuple(self._conversations.values())))
        if module_id is not None:
            conversations = tuple(c for c in conversations if c.module_id == module_id)
        if project_id is not None:
            conversations = tuple(c for c in conversations if c.project_id == project_id)
        return conversations[: max(limit, 1)]


class InMemoryMessageRepository(MessageRepository):
    """Simple non-durable repository implementation."""

    def __init__(self) -> None:
        self._messages: dict[MessageId, Message] = {}

    async def add(self, message: Message) -> None:
        self._messages[message.id] = message

    async def get(self, message_id: MessageId) -> Message:
        try:
            return self._messages[message_id]
        except KeyError as exc:
            raise MessageNotFoundError(str(message_id)) from exc

    async def save(self, message: Message) -> None:
        if message.id not in self._messages:
            raise MessageNotFoundError(str(message.id))
        self._messages[message.id] = message

    async def list(
        self,
        *,
        conversation_id: ConversationId,
        limit: int = 100,
    ) -> tuple[Message, ...]:
        messages = tuple(
            m for m in self._messages.values() if m.conversation_id == conversation_id
        )
        messages = tuple(sorted(messages, key=lambda m: m.created_at))
        return messages[: max(limit, 1)]
