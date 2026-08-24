"""Task application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.identifiers import ProjectId, TaskId
from orchai.domain.tasks import Task, TaskState


class TaskRepository(Protocol):
    """Persistence boundary for task state."""

    async def add(self, task: Task) -> None:
        """Persist a newly created task."""

    async def get(self, task_id: TaskId) -> Task:
        """Return an existing task by id."""

    async def save(self, task: Task) -> None:
        """Persist changes to an existing task."""

    async def list(
        self,
        *,
        project_id: ProjectId | None = None,
        state: TaskState | None = None,
        limit: int = 20,
    ) -> tuple[Task, ...]:
        """Return persisted tasks."""
