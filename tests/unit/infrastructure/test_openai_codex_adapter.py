import asyncio
import json

import httpx
import pytest

from orchai.application.executions.ports import (
    AIProviderContextItem,
    AIProviderError,
    AIProviderExecutionRequest,
)
from orchai.domain.actions import ActionName
from orchai.domain.identifiers import ExecutionId, ModelId, ProjectId, TaskId
from orchai.domain.roles import RoleName
from orchai.infrastructure.ai.openai_codex import OpenAICodexAIProviderAdapter


def test_openai_codex_adapter_builds_responses_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "id": "resp_123",
                "output_text": "implemented",
                "usage": {"input_tokens": 11, "output_tokens": 7},
            },
        )

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        adapter = OpenAICodexAIProviderAdapter(
            api_key="secret",
            base_url="https://api.openai.com/v1",
            organization="org_123",
            project="proj_123",
        )

        original_client = httpx.AsyncClient

        class MockClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.AsyncClient = MockClient
        try:
            result = await adapter.execute(_request())
        finally:
            httpx.AsyncClient = original_client

        assert result.output == "implemented"
        assert result.provider_name == "openai"
        assert result.input_tokens == 11
        assert result.output_tokens == 7

    asyncio.run(run())

    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["headers"]["authorization"] == "Bearer secret"
    assert captured["headers"]["openai-organization"] == "org_123"
    assert captured["headers"]["openai-project"] == "proj_123"
    assert captured["json"]["model"] == "gpt-5-codex"
    assert captured["json"]["store"] is False
    assert "Use only the authorized context below." in captured["json"]["input"]


def test_openai_codex_adapter_maps_http_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": {"message": "boom"}})

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        adapter = OpenAICodexAIProviderAdapter(
            api_key="secret",
            base_url="https://api.openai.com/v1",
        )
        original_client = httpx.AsyncClient

        class MockClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.AsyncClient = MockClient
        try:
            with pytest.raises(AIProviderError):
                await adapter.execute(_request())
        finally:
            httpx.AsyncClient = original_client

    asyncio.run(run())


def test_openai_codex_adapter_healthcheck_reports_reachability() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"id": "gpt-5-codex"},
                    {"id": "gpt-5-mini"},
                ]
            },
        )

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        adapter = OpenAICodexAIProviderAdapter(
            api_key="secret",
            base_url="https://api.openai.com/v1",
        )
        original_client = httpx.AsyncClient

        class MockClient(httpx.AsyncClient):
            def __init__(self, *args, **kwargs):
                kwargs["transport"] = transport
                super().__init__(*args, **kwargs)

        httpx.AsyncClient = MockClient
        try:
            health = await adapter.healthcheck()
        finally:
            httpx.AsyncClient = original_client

        assert health.provider_name == "openai"
        assert health.reachable is True
        assert health.metadata["model_count"] == "2"

    asyncio.run(run())


def _request() -> AIProviderExecutionRequest:
    return AIProviderExecutionRequest(
        execution_id=ExecutionId("exec-1"),
        task_id=TaskId("task-1"),
        role=RoleName.DEVELOPER,
        action=ActionName.IMPLEMENT,
        model_id=ModelId("gpt-5-codex"),
        project_id=ProjectId("project-1"),
        context=(
            AIProviderContextItem(
                resource="docs/INDEX.md",
                content="Authorized docs",
                source="PROJECT_DOCUMENTATION",
            ),
        ),
    )
