from orchai.domain.conversations import Conversation, Message, MessageRole, MessageStatus
from orchai.domain.executions import ResourceUsage
from orchai.domain.identifiers import ConversationId, ModuleId


def test_conversation_strips_title_whitespace() -> None:
    conversation = Conversation(module_id=ModuleId("forge"), title="  Hello  ")

    assert conversation.title == "Hello"
    assert conversation.archived is False


def test_message_defaults_to_complete_status() -> None:
    message = Message(
        conversation_id=ConversationId.new(),
        role=MessageRole.USER,
        content="hi",
    )

    assert message.status is MessageStatus.COMPLETE
    assert message.error is None


def test_message_complete_sets_content_usage_and_provider() -> None:
    message = Message(
        conversation_id=ConversationId.new(),
        role=MessageRole.ASSISTANT,
        content="",
        status=MessageStatus.PENDING,
    )

    message.complete(
        content="the answer",
        resource_usage=ResourceUsage(input_tokens=3, output_tokens=5),
        provider_name="stub",
    )

    assert message.status is MessageStatus.COMPLETE
    assert message.content == "the answer"
    assert message.provider_name == "stub"
    assert message.resource_usage.total_tokens == 8


def test_message_fail_records_error_and_leaves_content_untouched() -> None:
    message = Message(
        conversation_id=ConversationId.new(),
        role=MessageRole.ASSISTANT,
        content="",
        status=MessageStatus.PENDING,
    )

    message.fail("provider unreachable")

    assert message.status is MessageStatus.FAILED
    assert message.error == "provider unreachable"
    assert message.content == ""
