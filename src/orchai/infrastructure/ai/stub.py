"""Deterministic AI provider adapter for local smoke flows."""

from __future__ import annotations

from orchai.application.executions.ports import (
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderPort,
)


class StubAIProviderAdapter(AIProviderPort):
    """Provider adapter that returns a deterministic summary."""

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        context_count = len(request.context)
        return AIProviderExecutionResult(
            output=f"Stub provider processed {context_count} authorized context item(s).",
            provider_name="stub",
            metadata={
                "provider": "stub",
                "context_items": str(context_count),
                "role": request.role.value,
                "action": request.action.value,
                "model_id": str(request.model_id),
            },
        )
