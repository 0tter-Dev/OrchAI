"""Execution application ports."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from typing import Protocol

from orchai.domain.actions import ActionName
from orchai.domain.executions import Execution
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


class AIProviderError(RuntimeError):
    """Stable provider-boundary error raised by AI adapters."""


class AIProviderContractError(AIProviderError):
    """Raised when an adapter returns an invalid provider result."""


class AIProviderPort(Protocol):
    """Provider-independent AI execution adapter contract."""

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        """Execute a bounded request using the selected AI provider."""
