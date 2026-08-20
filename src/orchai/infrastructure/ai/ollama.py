"""Ollama AI provider adapter."""

from __future__ import annotations

from typing import Any

import httpx

from orchai.application.executions.ports import (
    AIProviderError,
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderPort,
)


class OllamaAIProviderAdapter(AIProviderPort):
    """HTTPX-backed Ollama adapter."""

    def __init__(
        self,
        *,
        base_url: str = "http://localhost:11434",
        timeout_seconds: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        if not str(request.model_id).strip():
            from orchai.application.executions.ports import AIProviderValidationError

            raise AIProviderValidationError("model_id must not be empty")

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        payload = {
            "model": str(request.model_id),
            "prompt": _prompt_from(request),
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.post("/api/generate", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"ollama request failed: {exc}") from exc

        data = response.json()
        output = str(data.get("response") or "")
        return AIProviderExecutionResult(
            output=output,
            provider_name="ollama",
            input_tokens=_int_or_none(data.get("prompt_eval_count")),
            output_tokens=_int_or_none(data.get("eval_count")),
            metadata={
                "provider": "ollama",
                "model": str(request.model_id),
                "done": str(data.get("done")),
            },
        )

    async def cancel(self, execution_id) -> None:
        raise AIProviderError("ollama adapter does not support cancellation")


def _prompt_from(request: AIProviderExecutionRequest) -> str:
    context = "\n\n".join(
        f"### {item.resource}\n{item.content}" for item in request.context
    )
    return "\n\n".join(
        (
            f"Role: {request.role.value}",
            f"Action: {request.action.value}",
            "Use only the authorized context below.",
            context,
        )
    )


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
