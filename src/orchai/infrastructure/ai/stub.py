"""Deterministic AI provider adapter for local smoke flows."""

from __future__ import annotations

from orchai.application.executions.ports import (
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderPort,
)


class StubAIProviderAdapter(AIProviderPort):
    """Provider adapter that returns a deterministic summary."""

    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        if not request.context:
            from orchai.application.executions.ports import AIProviderValidationError

            raise AIProviderValidationError("provider requires at least one context item")

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

    async def cancel(self, execution_id) -> None:
        return None
