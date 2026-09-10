"""Deterministic AI provider adapter for local smoke flows."""

from __future__ import annotations

from collections.abc import AsyncIterator

from orchai.application.conversations.ports import (
    ConversationAIProviderPort,
    ConversationCompletionRequest,
    ConversationCompletionResult,
    ConversationStreamChunk,
)
from orchai.application.executions.ports import (
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderHealthCheck,
    AIProviderPort,
    AIProviderStreamChunk,
)


class StubAIProviderAdapter(AIProviderPort, ConversationAIProviderPort):
    """Provider adapter that returns a deterministic summary."""

    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        if not request.context:
            from orchai.application.executions.ports import AIProviderValidationError

            raise AIProviderValidationError("provider requires at least one context item")

    async def healthcheck(self) -> AIProviderHealthCheck:
        return AIProviderHealthCheck(
            provider_name="stub",
            reachable=True,
            message="stub provider is always available for local smoke usage",
            metadata={"provider": "stub"},
        )

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

    async def execute_stream(
        self,
        request: AIProviderExecutionRequest,
    ) -> AsyncIterator[AIProviderStreamChunk]:
        context_count = len(request.context)
        text = f"Stub provider processed {context_count} authorized context item(s)."
        yield AIProviderStreamChunk(delta=text, provider_name="stub")
        yield AIProviderStreamChunk(
            delta="", finished=True, provider_name="stub", finish_reason="stop"
        )

    async def cancel(self, execution_id) -> None:
        return None

    async def complete(
        self,
        request: ConversationCompletionRequest,
    ) -> ConversationCompletionResult:
        return ConversationCompletionResult(
            content=f"Stub provider processed {len(request.history)} message(s).",
            provider_name="stub",
        )

    async def complete_stream(
        self,
        request: ConversationCompletionRequest,
    ) -> AsyncIterator[ConversationStreamChunk]:
        text = f"Stub provider processed {len(request.history)} message(s)."
        for word in text.split(" "):
            yield ConversationStreamChunk(delta=word + " ", provider_name="stub")
        yield ConversationStreamChunk(delta="", finished=True, provider_name="stub")
