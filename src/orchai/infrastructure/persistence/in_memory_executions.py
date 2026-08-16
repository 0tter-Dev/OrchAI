"""In-memory execution repository for tests and local bootstrap."""

from __future__ import annotations

from orchai.application.executions.ports import ExecutionRepository
from orchai.domain.executions import Execution
from orchai.domain.identifiers import ExecutionId


class ExecutionNotFoundError(LookupError):
    """Raised when an execution is not present in the repository."""


class InMemoryExecutionRepository(ExecutionRepository):
    """Simple non-durable execution repository."""

    def __init__(self) -> None:
        self._executions: dict[ExecutionId, Execution] = {}

    async def add(self, execution: Execution) -> None:
        self._executions[execution.id] = execution

    async def get(self, execution_id: ExecutionId) -> Execution:
        try:
            return self._executions[execution_id]
        except KeyError as exc:
            raise ExecutionNotFoundError(str(execution_id)) from exc

    async def save(self, execution: Execution) -> None:
        if execution.id not in self._executions:
            raise ExecutionNotFoundError(str(execution.id))
        self._executions[execution.id] = execution

    async def list(self) -> tuple[Execution, ...]:
        return tuple(self._executions.values())

