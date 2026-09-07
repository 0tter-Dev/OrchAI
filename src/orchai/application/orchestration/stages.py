"""Task-workflow-stage vocabulary and pure mapping helpers.

Extracted (Phase 7.5) from orchestrator.py: `TaskWorkflowStage` and its
`TaskStageWorkflow` mapping describe *what* each stage means (role,
action, states, whether it uses AI) independent of any orchestration
control flow, so they -- and the small pure functions that navigate them
-- can live on their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from orchai.application.suggestions import SuggestionEngine
from orchai.application.tasks import TaskService, TransitionTaskCommand
from orchai.domain.actions import ActionName
from orchai.domain.projects import ProjectOperation
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion
from orchai.domain.tasks import TaskState


class TaskWorkflowStage(StrEnum):
    """Higher-level task-centric workflow stages."""

    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    REVIEW = "REVIEW"
    VALIDATE = "VALIDATE"
    TEST = "TEST"
    DOCUMENT = "DOCUMENT"


@dataclass(frozen=True, slots=True)
class TaskStageWorkflow:
    stage: TaskWorkflowStage
    role: RoleName
    action: ActionName
    start_state: TaskState
    success_state: TaskState
    project_operation: ProjectOperation
    uses_ai: bool = True
    requires_context: bool = True
    documentation_required: bool = False


def task_stage_workflow(stage: TaskWorkflowStage) -> TaskStageWorkflow:
    if stage is TaskWorkflowStage.PLAN:
        return TaskStageWorkflow(
            stage=stage,
            role=RoleName.TASK_PLANNER,
            action=ActionName.PLAN,
            start_state=TaskState.PLANNING,
            success_state=TaskState.PLANNED,
            project_operation=ProjectOperation.READ_CONTEXT,
        )
    if stage is TaskWorkflowStage.IMPLEMENT:
        return TaskStageWorkflow(
            stage=stage,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            start_state=TaskState.IMPLEMENTING,
            success_state=TaskState.IMPLEMENTED,
            project_operation=ProjectOperation.WRITE_SOURCE,
        )
    if stage is TaskWorkflowStage.REVIEW:
        return TaskStageWorkflow(
            stage=stage,
            role=RoleName.QUALITY_AGENT,
            action=ActionName.REVIEW,
            start_state=TaskState.REVIEWING,
            success_state=TaskState.REVIEWING,
            project_operation=ProjectOperation.READ_CONTEXT,
        )
    if stage is TaskWorkflowStage.VALIDATE:
        return TaskStageWorkflow(
            stage=stage,
            role=RoleName.QUALITY_AGENT,
            action=ActionName.VALIDATE,
            start_state=TaskState.VALIDATING,
            success_state=TaskState.VALIDATING,
            project_operation=ProjectOperation.RUN_VALIDATION,
        )
    if stage is TaskWorkflowStage.TEST:
        return TaskStageWorkflow(
            stage=stage,
            role=RoleName.QUALITY_AGENT,
            action=ActionName.TEST,
            start_state=TaskState.TESTING,
            success_state=TaskState.VALIDATED,
            project_operation=ProjectOperation.RUN_TESTS,
            uses_ai=False,
            requires_context=False,
        )
    return TaskStageWorkflow(
        stage=stage,
        role=RoleName.DEVELOPER,
        action=ActionName.DOCUMENT,
        start_state=TaskState.VALIDATED,
        success_state=TaskState.COMPLETED,
        project_operation=ProjectOperation.WRITE_DOCUMENTATION,
        documentation_required=True,
    )


def task_stage_from_suggestion(suggestion: Suggestion) -> TaskWorkflowStage:
    if suggestion.suggested_action is ActionName.PLAN:
        return TaskWorkflowStage.PLAN
    if suggestion.suggested_action is ActionName.IMPLEMENT:
        return TaskWorkflowStage.IMPLEMENT
    if suggestion.suggested_action is ActionName.REVIEW:
        return TaskWorkflowStage.REVIEW
    if suggestion.suggested_action is ActionName.VALIDATE:
        return TaskWorkflowStage.VALIDATE
    if suggestion.suggested_action is ActionName.TEST:
        return TaskWorkflowStage.TEST
    return TaskWorkflowStage.DOCUMENT


def operation_workflow(
    operation: ProjectOperation,
) -> tuple[RoleName, ActionName, TaskState, TaskState]:
    if operation is ProjectOperation.WRITE_SOURCE:
        return (
            RoleName.DEVELOPER,
            ActionName.IMPLEMENT,
            TaskState.IMPLEMENTING,
            TaskState.IMPLEMENTED,
        )
    if operation is ProjectOperation.WRITE_DOCUMENTATION:
        return (
            RoleName.DEVELOPER,
            ActionName.DOCUMENT,
            TaskState.IMPLEMENTING,
            TaskState.IMPLEMENTED,
        )
    if operation is ProjectOperation.RUN_TESTS:
        return (
            RoleName.QUALITY_AGENT,
            ActionName.TEST,
            TaskState.TESTING,
            TaskState.VALIDATED,
        )
    if operation in {
        ProjectOperation.RUN_VALIDATION,
        ProjectOperation.RUN_COMMAND,
        ProjectOperation.GIT_STATUS,
    }:
        return (
            RoleName.QUALITY_AGENT,
            ActionName.VALIDATE,
            TaskState.VALIDATING,
            TaskState.VALIDATED,
        )
    return (
        RoleName.DEVELOPER,
        ActionName.IMPLEMENT,
        TaskState.IMPLEMENTING,
        TaskState.IMPLEMENTED,
    )


async def resolve_task_stage(
    *,
    task_service: TaskService,
    suggestion_engine: SuggestionEngine,
    task,
    requested_stage: TaskWorkflowStage | None,
) -> tuple:
    """Move a freshly created task into PLANNING and pick its next stage.

    Returns ``(task, suggestion, stage)``: an explicit ``requested_stage``
    always wins (and carries no suggestion, since the caller didn't ask
    the suggestion engine); otherwise the next suggested stage is used,
    or ``(task, None, None)`` if the suggestion engine has nothing to
    propose.
    """

    if task.state is TaskState.CREATED:
        task = await task_service.transition_task(
            TransitionTaskCommand(
                task_id=task.id,
                target_state=TaskState.PLANNING,
                source="application.orchestration.tasks",
            )
        )
    if requested_stage is not None:
        return task, None, requested_stage
    suggestion = await suggestion_engine.suggest_next(task)
    if suggestion is None:
        return task, None, None
    return task, suggestion, task_stage_from_suggestion(suggestion)
