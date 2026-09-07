import asyncio

import pytest

from orchai.application.conversations import (
    ConversationService,
    CreateConversationCommand,
    SendMessageCommand,
    UnknownModuleError,
)
from orchai.application.modules import get_module
from orchai.domain.conversations import MessageRole, MessageStatus
from orchai.domain.identifiers import ExecutionId, ModuleId, ProjectId, TaskId
from orchai.infrastructure.ai.stub import StubAIProviderAdapter
from orchai.infrastructure.persistence import (
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)


def _service() -> ConversationService:
    return ConversationService(
        conversation_repository=InMemoryConversationRepository(),
        message_repository=InMemoryMessageRepository(),
        ai_provider=StubAIProviderAdapter(),
        get_module=get_module,
    )


def test_create_conversation_requires_a_project_when_the_module_needs_one() -> None:
    service = _service()

    with pytest.raises(ValueError, match="requires a project"):
        asyncio.run(
            service.create_conversation(
                CreateConversationCommand(module_id=ModuleId("forge"))
            )
        )


def test_create_conversation_rejects_an_unknown_module() -> None:
    service = _service()

    with pytest.raises(UnknownModuleError):
        asyncio.run(
            service.create_conversation(
                CreateConversationCommand(
                    module_id=ModuleId("does-not-exist"),
                    project_id=ProjectId("proj-1"),
                )
            )
        )


def test_send_message_persists_both_turns_and_completes_the_assistant_reply() -> None:
    async def run() -> None:
        service = _service()
        conversation = await service.create_conversation(
            CreateConversationCommand(
                module_id=ModuleId("forge"),
                project_id=ProjectId("proj-1"),
            )
        )

        user_message, assistant_message = await service.send_message(
            SendMessageCommand(conversation_id=conversation.id, content="hello")
        )

        assert user_message.role is MessageRole.USER
        assert user_message.content == "hello"
        assert assistant_message.role is MessageRole.ASSISTANT
        assert assistant_message.status is MessageStatus.COMPLETE
        assert assistant_message.provider_name == "stub"
        assert assistant_message.model_id is not None

        history = await service.list_messages(conversation.id)
        assert [m.id for m in history] == [user_message.id, assistant_message.id]

    asyncio.run(run())


def test_send_message_uses_the_modules_first_suggested_model_by_default() -> None:
    async def run() -> None:
        service = _service()
        conversation = await service.create_conversation(
            CreateConversationCommand(
                module_id=ModuleId("forge"),
                project_id=ProjectId("proj-1"),
            )
        )
        forge = get_module(ModuleId("forge"))

        _, assistant_message = await service.send_message(
            SendMessageCommand(conversation_id=conversation.id, content="hello")
        )

        assert str(assistant_message.model_id) == forge.suggested_models[0]

    asyncio.run(run())


def test_send_message_raises_for_an_unknown_conversation() -> None:
    from orchai.domain.identifiers import ConversationId

    service = _service()

    with pytest.raises(LookupError):
        asyncio.run(
            service.send_message(
                SendMessageCommand(conversation_id=ConversationId.new(), content="hi")
            )
        )


def test_send_message_stream_yields_user_message_then_deltas_then_done() -> None:
    async def run() -> None:
        service = _service()
        conversation = await service.create_conversation(
            CreateConversationCommand(
                module_id=ModuleId("forge"),
                project_id=ProjectId("proj-1"),
            )
        )

        events = [
            event
            async for event in service.send_message_stream(
                SendMessageCommand(conversation_id=conversation.id, content="hello")
            )
        ]

        assert events[0].type == "user_message"
        assert events[0].message.content == "hello"
        assert [event.type for event in events[1:-1]] == ["delta"] * (len(events) - 2)
        assert "".join(event.content for event in events[1:-1]).strip() != ""

        final = events[-1]
        assert final.type == "done"
        assert final.message.status is MessageStatus.COMPLETE
        assert final.message.content == "".join(event.content for event in events[1:-1])
        assert final.message.provider_name == "stub"

        history = await service.list_messages(conversation.id)
        assert [m.id for m in history] == [events[0].message.id, final.message.id]

    asyncio.run(run())


def test_send_message_stream_raises_for_an_unknown_conversation() -> None:
    from orchai.domain.identifiers import ConversationId

    async def run() -> None:
        service = _service()
        with pytest.raises(LookupError):
            async for _ in service.send_message_stream(
                SendMessageCommand(conversation_id=ConversationId.new(), content="hi")
            ):
                pass

    asyncio.run(run())


def test_escalate_message_persists_a_user_message_linked_to_the_task() -> None:
    async def run() -> None:
        service = _service()
        conversation = await service.create_conversation(
            CreateConversationCommand(
                module_id=ModuleId("forge"),
                project_id=ProjectId("proj-1"),
            )
        )
        task_id = TaskId.new()
        execution_id = ExecutionId.new()

        message = await service.escalate_message(
            conversation_id=conversation.id,
            content="Implement the login form",
            task_id=task_id,
            execution_id=execution_id,
        )

        assert message.role is MessageRole.USER
        assert message.status is MessageStatus.COMPLETE
        assert message.linked_task_id == task_id
        assert message.linked_execution_id == execution_id

        history = await service.list_messages(conversation.id)
        assert history == (message,)

    asyncio.run(run())


def test_escalate_message_allows_no_execution_id_yet() -> None:
    async def run() -> None:
        service = _service()
        conversation = await service.create_conversation(
            CreateConversationCommand(
                module_id=ModuleId("forge"),
                project_id=ProjectId("proj-1"),
            )
        )

        message = await service.escalate_message(
            conversation_id=conversation.id,
            content="Plan the refactor",
            task_id=TaskId.new(),
            execution_id=None,
        )

        assert message.linked_execution_id is None

    asyncio.run(run())


def test_escalate_message_raises_for_an_unknown_conversation() -> None:
    from orchai.domain.identifiers import ConversationId

    async def run() -> None:
        service = _service()
        with pytest.raises(LookupError):
            await service.escalate_message(
                conversation_id=ConversationId.new(),
                content="hi",
                task_id=TaskId.new(),
                execution_id=None,
            )

    asyncio.run(run())
