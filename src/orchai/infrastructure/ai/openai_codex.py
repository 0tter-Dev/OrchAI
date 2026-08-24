"""OpenAI/Codex AI provider adapter via the Responses API."""

from __future__ import annotations

from typing import Any

import httpx

from orchai.application.executions.ports import (
    AIProviderError,
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderHealthCheck,
    AIProviderPort,
)


class OpenAICodexAIProviderAdapter(AIProviderPort):
    """HTTPX-backed OpenAI adapter for Codex-capable models."""

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 120.0,
        organization: str | None = None,
        project: str | None = None,
        store: bool = False,
    ) -> None:
        normalized_key = api_key.strip()
        if not normalized_key:
            raise ValueError("api_key must not be empty")
        self._api_key = normalized_key
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._organization = organization.strip() if organization else None
        self._project = project.strip() if project else None
        self._store = store

    async def capabilities(self) -> frozenset[str]:
        return frozenset(
            {
                "execute",
                "validate_request",
                "cloud",
                "responses_api",
                "codex_models",
            }
        )

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        if not str(request.model_id).strip():
            from orchai.application.executions.ports import AIProviderValidationError

            raise AIProviderValidationError("model_id must not be empty")
        if not request.context:
            from orchai.application.executions.ports import AIProviderValidationError

            raise AIProviderValidationError("provider requires at least one context item")

    async def healthcheck(self) -> AIProviderHealthCheck:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._organization:
            headers["OpenAI-Organization"] = self._organization
        if self._project:
            headers["OpenAI-Project"] = self._project

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.get("/models", headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            return AIProviderHealthCheck(
                provider_name="openai",
                reachable=False,
                configured_model="",
                message=f"openai healthcheck failed: {exc}",
                metadata={"base_url": self._base_url},
            )

        data = response.json()
        models = data.get("data", [])
        return AIProviderHealthCheck(
            provider_name="openai",
            reachable=True,
            message="openai responded successfully",
            metadata={
                "base_url": self._base_url,
                "model_count": str(len(models)),
            },
        )

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        payload = {
            "model": str(request.model_id),
            "input": _prompt_from(request),
            "store": self._store,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if self._organization:
            headers["OpenAI-Organization"] = self._organization
        if self._project:
            headers["OpenAI-Project"] = self._project

        try:
            async with httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.post("/responses", json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"openai request failed: {exc}") from exc

        data = response.json()
        output = _extract_output_text(data)
        usage = data.get("usage", {})
        return AIProviderExecutionResult(
            output=output,
            provider_name="openai",
            input_tokens=_int_or_none(usage.get("input_tokens")),
            output_tokens=_int_or_none(usage.get("output_tokens")),
            metadata={
                "provider": "openai",
                "model": str(request.model_id),
                "response_id": str(data.get("id") or ""),
                "store": str(self._store).lower(),
            },
        )

    async def cancel(self, execution_id) -> None:
        raise AIProviderError("openai adapter does not support cancellation")


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


def _extract_output_text(data: dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct

    parts: list[str] = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n".join(parts).strip()


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
