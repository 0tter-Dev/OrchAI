"""Task use-case commands."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from orchai.domain.identifiers import ProjectId, TaskId
from orchai.domain.tasks import ExecutionMode, TaskState


@dataclass(frozen=True, slots=True)
class CreateTaskCommand:
    """Command for creating a new task."""

    title: str
    description: str
    requested_change: str
    project_id: ProjectId | None = None
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    acceptance_criteria: Iterable[str] = ()
    constraints: Iterable[str] = ()
    exclusions: Iterable[str] = ()


@dataclass(frozen=True, slots=True)
class TransitionTaskCommand:
    """Command for requesting a task state transition."""

    task_id: TaskId
    target_state: TaskState
    source: str = "application.tasks"

