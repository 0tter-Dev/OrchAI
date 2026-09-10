"""LiteLLM-backed AI provider adapter (ADR-013).

Replaces the previous per-provider adapters (`ollama.py`,
`openai_codex.py`): LiteLLM's unified `acompletion` call already covers
OpenAI, Anthropic, Gemini, Ollama, and other OpenAI-compatible local
runtimes behind one calling convention, selected by a `"<provider>/<model>"`
string (e.g. `"ollama/qwen2.5-coder:latest"`, `"anthropic/claude-..."`).

`litellm` itself is confined to this module -- `AIProviderPort` and
`ConversationAIProviderPort` (application/executions/ports.py,
application/conversations/ports.py) and their DTOs remain the only
contracts the rest of the codebase depends on. This class implements
both ports: one adapter, two application-facing shapes (Task-bounded
executions per ADR-013, and plain conversation turns per ADR-014).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import litellm

from orchai.application.conversations.ports import (
    ConversationAIProviderPort,
    ConversationCompletionRequest,
    ConversationCompletionResult,
    ConversationStreamChunk,
)
from orchai.application.executions.ports import (
    AIProviderError,
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderHealthCheck,
    AIProviderPort,
    AIProviderStreamChunk,
    AIProviderValidationError,
)


class LiteLLMProvider(AIProviderPort, ConversationAIProviderPort):
    """Multi-provider adapter backed by the `litellm` library."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 120.0,
    ) -> None:
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request", "multi_provider"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        if not str(request.model_id).strip():
            raise AIProviderValidationError("model_id must not be empty")

    async def healthcheck(self) -> AIProviderHealthCheck:
        # No single "list models"/"ping" endpoint is uniform across every
        # provider LiteLLM supports (unlike the old ollama.py's /api/tags
        # or openai_codex.py's /models), so this issues a minimal, real
        # completion request against the configured model instead. For
        # cloud providers this consumes a handful of tokens -- acceptable
        # for an operator-triggered health check (GET /providers/health,
        # `orchai providers health`), not something called on every request.
        try:
            response = await litellm.acompletion(
                model=self._model,
                messages=[{"role": "user", "content": "ping"}],
                api_key=self._api_key,
                api_base=self._base_url,
                timeout=self._timeout_seconds,
                max_tokens=1,
            )
        except Exception as exc:  # noqa: BLE001 - litellm raises provider-specific types
            return AIProviderHealthCheck(
                provider_name="litellm",
                reachable=False,
                configured_model=self._model,
                message=f"litellm healthcheck failed: {exc}",
                metadata={},
            )
        return AIProviderHealthCheck(
            provider_name="litellm",
            reachable=bool(response),
            configured_model=self._model,
            message="litellm responded successfully",
            metadata={},
        )

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        messages = [{"role": "user", "content": _prompt_from(request)}]
        try:
            response = await litellm.acompletion(
                model=str(request.model_id),
                messages=messages,
                api_key=self._api_key,
                api_base=self._base_url,
                timeout=self._timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - litellm raises provider-specific types
            raise AIProviderError(f"litellm request failed: {exc}") from exc

        output = _extract_output_text(response)
        usage = getattr(response, "usage", None)
        return AIProviderExecutionResult(
            output=output,
            provider_name="litellm",
            input_tokens=_int_or_none(getattr(usage, "prompt_tokens", None)),
            output_tokens=_int_or_none(getattr(usage, "completion_tokens", None)),
            estimated_cost=_estimated_cost(response),
            metadata={
                "provider": "litellm",
                "model": str(request.model_id),
            },
        )

    async def execute_stream(
        self,
        request: AIProviderExecutionRequest,
    ) -> AsyncIterator[AIProviderStreamChunk]:
        messages = [{"role": "user", "content": _prompt_from(request)}]
        async for delta, finished, input_tokens, output_tokens in _stream_litellm(
            model=str(request.model_id),
            messages=messages,
            api_key=self._api_key,
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
        ):
            yield AIProviderStreamChunk(
                delta=delta,
                finished=finished,
                provider_name="litellm",
                finish_reason="stop" if finished else None,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

    async def cancel(self, execution_id) -> None:
        # LiteLLM has no server-side request id to cancel a call in flight
        # by -- the real cancellation mechanism is ExecutionEngine.cancel()
        # stopping the asyncio.Task awaiting this provider (which aborts
        # the underlying HTTP call), not this method. This is therefore an
        # intentional no-op, not a missing feature: ExecutionEngine treats
        # a provider's cancel() as a secondary, best-effort signal only.
        return None

    async def complete(
        self,
        request: ConversationCompletionRequest,
    ) -> ConversationCompletionResult:
        """`ConversationAIProviderPort.complete` -- plain chat, not Task-bounded."""

        messages = [{"role": "system", "content": request.system_prompt}] if request.system_prompt else []
        messages.extend({"role": turn.role, "content": turn.content} for turn in request.history)
        try:
            response = await litellm.acompletion(
                model=request.model,
                messages=messages,
                api_key=self._api_key,
                api_base=self._base_url,
                timeout=self._timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001 - litellm raises provider-specific types
            raise AIProviderError(f"litellm request failed: {exc}") from exc

        usage = getattr(response, "usage", None)
        return ConversationCompletionResult(
            content=_extract_output_text(response),
            provider_name="litellm",
            input_tokens=_int_or_none(getattr(usage, "prompt_tokens", None)),
            output_tokens=_int_or_none(getattr(usage, "completion_tokens", None)),
            estimated_cost=_estimated_cost(response),
        )

    async def complete_stream(
        self,
        request: ConversationCompletionRequest,
    ) -> AsyncIterator[ConversationStreamChunk]:
        messages = [{"role": "system", "content": request.system_prompt}] if request.system_prompt else []
        messages.extend({"role": turn.role, "content": turn.content} for turn in request.history)
        async for delta, finished, input_tokens, output_tokens in _stream_litellm(
            model=request.model,
            messages=messages,
            api_key=self._api_key,
            base_url=self._base_url,
            timeout_seconds=self._timeout_seconds,
        ):
            yield ConversationStreamChunk(
                delta=delta,
                finished=finished,
                provider_name="litellm",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )


async def _stream_litellm(
    *,
    model: str,
    messages: list[dict[str, str]],
    api_key: str | None,
    base_url: str | None,
    timeout_seconds: float,
) -> AsyncIterator[tuple[str, bool, int | None, int | None]]:
    """Shared streaming call for `execute_stream()` and `complete_stream()`.

    Yields `(delta_text, finished, input_tokens, output_tokens)`. Token
    counts are `None` until the final usage-carrying chunk arrives
    (`stream_options={"include_usage": True}`), which typically has no
    `choices` of its own -- `delta_text` is `""` and `finished` is
    `False` for that chunk, since it carries no text and is not itself
    the finish-reason chunk.
    """

    try:
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            api_key=api_key,
            api_base=base_url,
            timeout=timeout_seconds,
            stream=True,
            stream_options={"include_usage": True},
        )
    except Exception as exc:  # noqa: BLE001 - litellm raises provider-specific types
        raise AIProviderError(f"litellm request failed: {exc}") from exc

    try:
        async for chunk in response:
            choices = getattr(chunk, "choices", None) or []
            delta_text = ""
            finished = False
            if choices:
                delta = getattr(choices[0], "delta", None)
                delta_text = (getattr(delta, "content", None) or "") if delta is not None else ""
                finished = getattr(choices[0], "finish_reason", None) is not None
            usage = getattr(chunk, "usage", None)
            input_tokens = _int_or_none(getattr(usage, "prompt_tokens", None)) if usage else None
            output_tokens = (
                _int_or_none(getattr(usage, "completion_tokens", None)) if usage else None
            )
            yield delta_text, finished, input_tokens, output_tokens
    except AIProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 - litellm raises provider-specific types
        raise AIProviderError(f"litellm stream failed: {exc}") from exc


def _prompt_from(request: AIProviderExecutionRequest) -> str:
    context = "\n\n".join(f"### {item.resource}\n{item.content}" for item in request.context)
    return "\n\n".join(
        (
            f"Role: {request.role.value}",
            f"Action: {request.action.value}",
            "Use only the authorized context below.",
            context,
        )
    )


def _extract_output_text(response: Any) -> str:
    choices = getattr(response, "choices", None) or []
    if not choices:
        return ""
    message = getattr(choices[0], "message", None)
    content = getattr(message, "content", None) if message is not None else None
    return content or ""


def _estimated_cost(response: Any) -> float | None:
    try:
        return litellm.completion_cost(completion_response=response)
    except Exception:  # noqa: BLE001 - cost lookup is best-effort, never fatal
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
