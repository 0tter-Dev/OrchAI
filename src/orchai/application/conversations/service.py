"""Conversation application service (ADR-014).

Deliberately does not publish domain events or touch
`AuditRepository`/`MetricsRepository`: those exist to trace orchestrated
work (Task/Authorization/Execution), and most conversation turns are
ordinary chat, not orchestrated work (ADR-014's core distinction). Per-
message resource usage is still recorded, just on the `Message` itself,
not fanned out into the shared audit/metrics stream.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Literal

from orchai.application.conversations.commands import (
    CreateConversationCommand,
    SendMessageCommand,
)
from orchai.application.conversations.ports import (
    ConversationAIProviderPort,
    ConversationCompletionRequest,
    ConversationRepository,
    ConversationTurn,
    MessageRepository,
)
from orchai.application.executions.ports import AIProviderError
from orchai.domain.conversations import Conversation, Message, MessageRole, MessageStatus
from orchai.domain.executions import ResourceUsage
from orchai.domain.identifiers import (
    ConversationId,
    ExecutionId,
    ModelId,
    ModuleId,
    ProjectId,
    TaskId,
)
from orchai.domain.modules import ModuleDefinition


class UnknownModuleError(LookupError):
    """Raised when a conversation references a module that isn't registered."""


@dataclass(frozen=True, slots=True)
class ConversationStreamEvent:
    """One event of `ConversationService.send_message_stream()` (Phase 4).

    `type="user_message"` carries the persisted user `Message` (sent
    once, first); `type="delta"` carries an incremental piece of the
    assistant's reply in `content`; `type="done"` carries the final,
    persisted assistant `Message`; `type="error"` carries the failed,
    persisted assistant `Message` plus `error`.
    """

    type: Literal["user_message", "delta", "done", "error"]
    message: Message | None = None
    content: str = ""
    error: str | None = None


class ConversationService:
    """Coordinates conversation/message use cases."""

    def __init__(
        self,
        *,
        conversation_repository: ConversationRepository,
        message_repository: MessageRepository,
        ai_provider: ConversationAIProviderPort,
        get_module: Callable[[ModuleId], ModuleDefinition | None],
    ) -> None:
        self._conversations = conversation_repository
        self._messages = message_repository
        self._ai_provider = ai_provider
        self._get_module = get_module

    async def create_conversation(self, command: CreateConversationCommand) -> Conversation:
        module = self._get_module(command.module_id)
        if module is None:
            raise UnknownModuleError(str(command.module_id))
        if module.requires_project and command.project_id is None:
            raise ValueError(f"module {command.module_id} requires a project")

        conversation = Conversation(
            module_id=command.module_id,
            project_id=command.project_id,
            title=command.title,
        )
        await self._conversations.add(conversation)
        return conversation

    async def get_conversation(self, conversation_id: ConversationId) -> Conversation:
        return await self._conversations.get(conversation_id)

    async def escalate_message(
        self,
        *,
        conversation_id: ConversationId,
        content: str,
        task_id: TaskId,
        execution_id: ExecutionId | None,
    ) -> Message:
        """Persist a user message already turned into a real Task (Phase 5).

        The caller (`interfaces/api/main.py`'s `/conversations/{id}/escalate`
        route) has already created the Task/Execution through the same
        `/requests` machinery any other caller uses (ADR-011) --- this
        method only records the link on the triggering message, per
        ADR-014 §2 and invariant #2. It never creates a Task itself:
        `application/conversations` has no dependency on
        `application/orchestration`, keeping the two bounded contexts
        separate.
        """

        conversation = await self._conversations.get(conversation_id)
        if conversation.project_id is None:
            raise ValueError("cannot escalate a message in a conversation without a project")

        message = Message(
            conversation_id=conversation_id,
            role=MessageRole.USER,
            content=content,
            status=MessageStatus.COMPLETE,
            linked_task_id=task_id,
            linked_execution_id=execution_id,
        )
        await self._messages.add(message)
        return message

    async def list_conversations(
        self,
        *,
        module_id: ModuleId | None = None,
        project_id: ProjectId | None = None,
        limit: int = 20,
    ) -> tuple[Conversation, ...]:
        return await self._conversations.list(
            module_id=module_id,
            project_id=project_id,
            limit=limit,
        )

    async def list_messages(
        self,
        conversation_id: ConversationId,
        *,
        limit: int = 100,
    ) -> tuple[Message, ...]:
        return await self._messages.list(conversation_id=conversation_id, limit=limit)

    async def send_message(self, command: SendMessageCommand) -> tuple[Message, Message]:
        """Persist the user's message and return `(user_message, assistant_message)`.

        Non-streaming: the assistant message is fully resolved -- COMPLETE
        or FAILED -- before this returns. See `send_message_stream()` for
        the incremental (Phase 4) variant.
        """

        module, user_message, turns, resolved_model = await self._start_turn(command)
        assistant_message = self._new_assistant_message(
            command.conversation_id, resolved_model, status=MessageStatus.PENDING
        )
        await self._messages.add(assistant_message)

        try:
            result = await self._ai_provider.complete(
                ConversationCompletionRequest(
                    model=resolved_model,
                    system_prompt=module.system_prompt,
                    history=turns,
                )
            )
        except AIProviderError as exc:
            assistant_message.fail(str(exc))
            await self._messages.save(assistant_message)
            return user_message, assistant_message

        assistant_message.complete(
            content=result.content,
            resource_usage=ResourceUsage(
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                estimated_cost=result.estimated_cost,
            ),
            provider_name=result.provider_name,
        )
        await self._messages.save(assistant_message)
        return user_message, assistant_message

    async def send_message_stream(
        self,
        command: SendMessageCommand,
    ) -> AsyncIterator[ConversationStreamEvent]:
        """Streaming variant of `send_message()` (Phase 4, ADR-013).

        Yields a `user_message` event first, then one `delta` event per
        incremental chunk of the assistant's reply, then a final `done`
        (or `error`) event carrying the fully persisted assistant
        message. Cost estimation is skipped for streamed replies -- most
        providers only expose it for a complete response -- so a streamed
        `Message.resource_usage.estimated_cost` is always `None`.
        """

        module, user_message, turns, resolved_model = await self._start_turn(command)
        yield ConversationStreamEvent(type="user_message", message=user_message)

        assistant_message = self._new_assistant_message(
            command.conversation_id, resolved_model, status=MessageStatus.STREAMING
        )
        await self._messages.add(assistant_message)

        accumulated: list[str] = []
        input_tokens: int | None = None
        output_tokens: int | None = None
        provider_name = ""
        try:
            async for chunk in self._ai_provider.complete_stream(
                ConversationCompletionRequest(
                    model=resolved_model,
                    system_prompt=module.system_prompt,
                    history=turns,
                )
            ):
                provider_name = chunk.provider_name or provider_name
                input_tokens = chunk.input_tokens if chunk.input_tokens is not None else input_tokens
                output_tokens = (
                    chunk.output_tokens if chunk.output_tokens is not None else output_tokens
                )
                if chunk.delta:
                    accumulated.append(chunk.delta)
                    assistant_message.content = "".join(accumulated)
                    yield ConversationStreamEvent(type="delta", content=chunk.delta)
        except AIProviderError as exc:
            assistant_message.fail(str(exc))
            await self._messages.save(assistant_message)
            yield ConversationStreamEvent(type="error", message=assistant_message, error=str(exc))
            return

        assistant_message.complete(
            content="".join(accumulated),
            resource_usage=ResourceUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            provider_name=provider_name or "unknown",
        )
        await self._messages.save(assistant_message)
        yield ConversationStreamEvent(type="done", message=assistant_message)

    async def _start_turn(
        self,
        command: SendMessageCommand,
    ) -> tuple[ModuleDefinition, Message, tuple[ConversationTurn, ...], str]:
        """Persist the user's message and prepare the assistant's turn.

        Shared by `send_message()` and `send_message_stream()` so the two
        differ only in how they call the AI provider.
        """

        conversation = await self._conversations.get(command.conversation_id)
        module = self._get_module(conversation.module_id)
        if module is None:
            raise UnknownModuleError(str(conversation.module_id))

        user_message = Message(
            conversation_id=command.conversation_id,
            role=MessageRole.USER,
            content=command.content,
            status=MessageStatus.COMPLETE,
        )
        await self._messages.add(user_message)

        history = await self._messages.list(conversation_id=command.conversation_id, limit=100)
        turns = tuple(
            ConversationTurn(
                role="user" if message.role is MessageRole.USER else "assistant",
                content=message.content,
            )
            for message in history
            if message.role in (MessageRole.USER, MessageRole.ASSISTANT) and message.content
        )

        resolved_model = command.model or _default_model(module)
        return module, user_message, turns, resolved_model

    def _new_assistant_message(
        self,
        conversation_id: ConversationId,
        resolved_model: str,
        *,
        status: MessageStatus,
    ) -> Message:
        return Message(
            conversation_id=conversation_id,
            role=MessageRole.ASSISTANT,
            content="",
            status=status,
            model_id=ModelId(resolved_model) if resolved_model.strip() else None,
        )


def _default_model(module: ModuleDefinition) -> str:
    return module.suggested_models[0] if module.suggested_models else ""
