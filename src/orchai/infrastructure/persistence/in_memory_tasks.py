"""In-memory task repository for tests and local bootstrap."""

from __future__ import annotations

from orchai.application.tasks.ports import TaskRepository
from orchai.domain.identifiers import TaskId
from orchai.domain.tasks import Task


class TaskNotFoundError(LookupError):
    """Raised when a task is not present in the repository."""


class InMemoryTaskRepository(TaskRepository):
    """Simple non-durable repository implementation."""

    def __init__(self) -> None:
        self._tasks: dict[TaskId, Task] = {}

    async def add(self, task: Task) -> None:
        self._tasks[task.id] = task

    async def get(self, task_id: TaskId) -> Task:
        try:
            return self._tasks[task_id]
        except KeyError as exc:
            raise TaskNotFoundError(str(task_id)) from exc

    async def save(self, task: Task) -> None:
        if task.id not in self._tasks:
            raise TaskNotFoundError(str(task.id))
        self._tasks[task.id] = task

    async def list(self) -> tuple[Task, ...]:
        return tuple(self._tasks.values())

