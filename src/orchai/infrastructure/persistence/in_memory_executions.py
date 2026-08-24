"""In-memory execution repository for tests and local bootstrap."""

from __future__ import annotations

from orchai.application.executions.ports import ExecutionRepository
from orchai.domain.executions import Execution, ExecutionState
from orchai.domain.identifiers import ExecutionId, ProjectId, TaskId


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

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        state: ExecutionState | None = None,
        limit: int = 20,
    ) -> tuple[Execution, ...]:
        executions = tuple(reversed(tuple(self._executions.values())))
        if task_id is not None:
            executions = tuple(
                execution for execution in executions if execution.task_id == task_id
            )
        if project_id is not None:
            executions = tuple(
                execution
                for execution in executions
                if execution.project_id == project_id
            )
        if state is not None:
            executions = tuple(
                execution for execution in executions if execution.state is state
            )
        return executions[: max(limit, 1)]
