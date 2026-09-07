import asyncio
from types import SimpleNamespace

import pytest

from orchai.application.conversations.ports import (
    ConversationCompletionRequest,
    ConversationTurn,
)
from orchai.application.executions.ports import (
    AIProviderContextItem,
    AIProviderExecutionRequest,
)
from orchai.domain.actions import ActionName
from orchai.domain.identifiers import ExecutionId, ModelId, ProjectId, TaskId
from orchai.domain.roles import RoleName
from orchai.infrastructure.ai.litellm_provider import LiteLLMProvider


def _fake_stream_chunk(*, content: str | None, finish_reason: str | None = None, usage=None):
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=SimpleNamespace(content=content), finish_reason=finish_reason)]
        if content is not None or finish_reason is not None
        else [],
        usage=usage,
    )


async def _fake_stream(chunks):
    for chunk in chunks:
        yield chunk


def _fake_response(content: str, *, prompt_tokens: int, completion_tokens: int):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


def test_litellm_provider_execute_builds_a_single_completion_call(monkeypatch) -> None:
    captured: dict[str, object] = {}

    async def fake_acompletion(**kwargs):
        captured.update(kwargs)
        return _fake_response("implemented", prompt_tokens=5, completion_tokens=8)

    monkeypatch.setattr("orchai.infrastructure.ai.litellm_provider.litellm.acompletion", fake_acompletion)
    monkeypatch.setattr(
        "orchai.infrastructure.ai.litellm_provider.litellm.completion_cost",
        lambda completion_response: 0.001,
    )

    adapter = LiteLLMProvider(model="ollama/qwen2.5-coder:latest")

    result = asyncio.run(adapter.execute(_request()))

    assert result.output == "implemented"
    assert result.provider_name == "litellm"
    assert result.input_tokens == 5
    assert result.output_tokens == 8
    assert result.estimated_cost == 0.001
    assert captured["model"] == "qwen2.5-coder:latest"
    assert "Role: DEVELOPER" in captured["messages"][0]["content"]


def test_litellm_provider_healthcheck_reports_reachability(monkeypatch) -> None:
    async def fake_acompletion(**kwargs):
        return _fake_response("pong", prompt_tokens=1, completion_tokens=1)

    monkeypatch.setattr("orchai.infrastructure.ai.litellm_provider.litellm.acompletion", fake_acompletion)

    adapter = LiteLLMProvider(model="ollama/qwen2.5-coder:latest")
    health = asyncio.run(adapter.healthcheck())

    assert health.provider_name == "litellm"
    assert health.reachable is True
    assert health.configured_model == "ollama/qwen2.5-coder:latest"


def test_litellm_provider_healthcheck_reports_unreachable_on_failure(monkeypatch) -> None:
    async def fake_acompletion(**kwargs):
        raise RuntimeError("connection refused")

    monkeypatch.setattr("orchai.infrastructure.ai.litellm_provider.litellm.acompletion", fake_acompletion)

    adapter = LiteLLMProvider(model="ollama/qwen2.5-coder:latest")
    health = asyncio.run(adapter.healthcheck())

    assert health.reachable is False
    assert "connection refused" in health.message


def test_litellm_provider_validate_request_accepts_a_well_formed_request() -> None:
    adapter = LiteLLMProvider(model="ollama/qwen2.5-coder:latest")

    asyncio.run(adapter.validate_request(_request()))


def test_litellm_provider_cancel_is_a_no_op() -> None:
    """LiteLLM has no server-side request id to cancel by -- the real
    cancellation mechanism is ExecutionEngine.cancel() stopping the
    asyncio.Task, not this method (Phase 7.2)."""

    adapter = LiteLLMProvider(model="ollama/qwen2.5-coder:latest")

    result = asyncio.run(adapter.cancel(ExecutionId("exec-1")))

    assert result is None


def test_litellm_provider_execute_stream_yields_deltas_then_a_finished_chunk(monkeypatch) -> None:
    chunks = [
        _fake_stream_chunk(content="hel"),
        _fake_stream_chunk(content="lo"),
        _fake_stream_chunk(content=None, finish_reason="stop"),
        _fake_stream_chunk(content=None, usage=SimpleNamespace(prompt_tokens=4, completion_tokens=2)),
    ]

    async def fake_acompletion(**kwargs):
        assert kwargs["stream"] is True
        return _fake_stream(chunks)

    monkeypatch.setattr("orchai.infrastructure.ai.litellm_provider.litellm.acompletion", fake_acompletion)

    adapter = LiteLLMProvider(model="ollama/qwen2.5-coder:latest")

    async def run():
        return [chunk async for chunk in adapter.execute_stream(_request())]

    results = asyncio.run(run())

    assert [c.delta for c in results] == ["hel", "lo", "", ""]
    assert [c.finished for c in results] == [False, False, True, False]
    assert results[-1].input_tokens == 4
    assert results[-1].output_tokens == 2


def test_litellm_provider_complete_stream_yields_deltas_for_conversations(monkeypatch) -> None:
    chunks = [
        _fake_stream_chunk(content="hi"),
        _fake_stream_chunk(content=None, finish_reason="stop"),
    ]

    async def fake_acompletion(**kwargs):
        assert kwargs["stream"] is True
        return _fake_stream(chunks)

    monkeypatch.setattr("orchai.infrastructure.ai.litellm_provider.litellm.acompletion", fake_acompletion)

    adapter = LiteLLMProvider(model="ollama/qwen2.5-coder:latest")
    request = ConversationCompletionRequest(
        model="ollama/qwen2.5-coder:latest",
        system_prompt="You are a helper.",
        history=(ConversationTurn(role="user", content="hello"),),
    )

    async def run():
        return [chunk async for chunk in adapter.complete_stream(request)]

    results = asyncio.run(run())

    assert [c.delta for c in results] == ["hi", ""]
    assert results[-1].finished is True
    assert all(c.provider_name == "litellm" for c in results)


def test_litellm_provider_stream_wraps_transport_errors(monkeypatch) -> None:
    async def fake_acompletion(**kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("orchai.infrastructure.ai.litellm_provider.litellm.acompletion", fake_acompletion)

    adapter = LiteLLMProvider(model="ollama/qwen2.5-coder:latest")

    async def run():
        async for _ in adapter.execute_stream(_request()):
            pass

    with pytest.raises(Exception, match="boom"):
        asyncio.run(run())


def _request() -> AIProviderExecutionRequest:
    return AIProviderExecutionRequest(
        execution_id=ExecutionId("exec-1"),
        task_id=TaskId("task-1"),
        role=RoleName.DEVELOPER,
        action=ActionName.IMPLEMENT,
        model_id=ModelId("qwen2.5-coder:latest"),
        project_id=ProjectId("project-1"),
        context=(
            AIProviderContextItem(
                resource="docs/INDEX.md",
                content="Authorized docs",
                source="PROJECT_DOCUMENTATION",
            ),
        ),
    )
