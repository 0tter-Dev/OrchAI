import asyncio
import json

import httpx

from orchai.application.executions.ports import (
    AIProviderContextItem,
    AIProviderExecutionRequest,
)
from orchai.domain.actions import ActionName
from orchai.domain.identifiers import ExecutionId, ModelId, ProjectId, TaskId
from orchai.domain.roles import RoleName
from orchai.infrastructure.ai.ollama import OllamaAIProviderAdapter


def test_ollama_adapter_healthcheck_reports_reachability() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder"}]})

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        adapter = OllamaAIProviderAdapter(base_url="http://localhost:11434")
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

        assert health.provider_name == "ollama"
        assert health.reachable is True
        assert health.metadata["model_count"] == "1"

    asyncio.run(run())


def test_ollama_adapter_execute_builds_generate_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["json"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "response": "implemented",
                "prompt_eval_count": 5,
                "eval_count": 8,
                "done": True,
            },
        )

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        adapter = OllamaAIProviderAdapter(base_url="http://localhost:11434")
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
        assert result.provider_name == "ollama"
        assert result.input_tokens == 5
        assert result.output_tokens == 8

    asyncio.run(run())

    assert captured["url"] == "http://localhost:11434/api/generate"
    assert captured["json"]["model"] == "qwen2.5-coder:latest"
    assert captured["json"]["stream"] is False


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
