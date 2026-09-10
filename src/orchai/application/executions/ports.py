"""Execution application ports."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from orchai.domain.actions import ActionName
from orchai.domain.executions import Execution, ExecutionState
from orchai.domain.identifiers import ExecutionId, ModelId, ProjectId, TaskId
from orchai.domain.roles import RoleName


class ExecutionRepository(Protocol):
    """Persistence boundary for execution attempts."""

    async def add(self, execution: Execution) -> None:
        """Persist a newly requested execution."""

    async def get(self, execution_id: ExecutionId) -> Execution:
        """Return an execution by id."""

    async def save(self, execution: Execution) -> None:
        """Persist changes to an execution."""

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        state: ExecutionState | None = None,
        limit: int = 20,
    ) -> tuple[Execution, ...]:
        """Return persisted executions."""


@dataclass(frozen=True, slots=True)
class AIProviderContextItem:
    """Provider-independent context item supplied to an AI adapter."""

    resource: str
    content: str
    source: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIProviderExecutionRequest:
    """Bounded execution request sent across the AI provider boundary."""

    execution_id: ExecutionId
    task_id: TaskId
    role: RoleName
    action: ActionName
    model_id: ModelId
    project_id: ProjectId | None
    context: tuple[AIProviderContextItem, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AIProviderExecutionResult:
    """Provider-independent AI execution outcome."""

    output: str
    success: bool = True
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost: float | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    provider_name: str = ""

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError("provider_name must not be empty")


@dataclass(frozen=True, slots=True)
class AIProviderStreamChunk:
    """One incremental chunk of a streamed execution (ADR-013, Phase 4).

    `Execution` itself still records exactly one terminal result
    (`AIProviderExecutionResult`) once the stream ends -- this DTO exists
    only for the transport between the provider and whatever accumulates
    it (`ExecutionEngine` for Task-bounded work; `ConversationService`
    for plain chat, via the separate `ConversationAIProviderPort`).
    """

    delta: str
    finished: bool = False
    provider_name: str = ""
    finish_reason: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class AIProviderHealthCheck:
    """Provider-independent operational health information."""

    provider_name: str
    reachable: bool
    configured_model: str = ""
    message: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.provider_name.strip():
            raise ValueError("provider_name must not be empty")


class AIProviderError(RuntimeError):
    """Stable provider-boundary error raised by AI adapters."""


class AIProviderContractError(AIProviderError):
    """Raised when an adapter returns an invalid provider result."""


class AIProviderValidationError(AIProviderError):
    """Raised when a provider rejects a request before execution."""


class AIProviderPort(Protocol):
    """Provider-independent AI execution adapter contract."""

    async def capabilities(self) -> frozenset[str]:
        """Return provider-declared capabilities."""

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        """Validate a bounded request before execution."""

    async def healthcheck(self) -> AIProviderHealthCheck:
        """Return provider operational health information."""

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        """Execute a bounded request using the selected AI provider."""

    def execute_stream(
        self,
        request: AIProviderExecutionRequest,
    ) -> AsyncIterator[AIProviderStreamChunk]:
        """Streaming variant of `execute()` (ADR-013, Phase 4).

        Not `async def`: implementations are async generators, called
        directly (never awaited first) to get the iterator.
        """

    async def cancel(self, execution_id: ExecutionId) -> None:
        """Cancel one execution when supported by the provider."""
