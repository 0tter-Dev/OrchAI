import asyncio

from orchai.application.events import InProcessEventDispatcher
from orchai.application.orchestration.stages import (
    TaskWorkflowStage,
    operation_workflow,
    resolve_task_stage,
    task_stage_from_suggestion,
    task_stage_workflow,
)
from orchai.application.suggestions import SuggestionEngine
from orchai.application.tasks import CreateTaskCommand, TaskService
from orchai.domain.actions import ActionName
from orchai.domain.identifiers import TaskId
from orchai.domain.projects import ProjectOperation
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion
from orchai.domain.tasks import ExecutionMode, TaskState
from orchai.infrastructure.persistence import (
    InMemorySuggestionRepository,
    InMemoryTaskRepository,
)


def test_task_stage_workflow_maps_every_stage_to_its_role_and_states() -> None:
    plan = task_stage_workflow(TaskWorkflowStage.PLAN)
    assert (plan.role, plan.action) == (RoleName.TASK_PLANNER, ActionName.PLAN)
    assert (plan.start_state, plan.success_state) == (
        TaskState.PLANNING,
        TaskState.PLANNED,
    )
    assert plan.uses_ai is True
    assert plan.requires_context is True
    assert plan.documentation_required is False

    implement = task_stage_workflow(TaskWorkflowStage.IMPLEMENT)
    assert (implement.role, implement.action) == (RoleName.DEVELOPER, ActionName.IMPLEMENT)
    assert implement.project_operation is ProjectOperation.WRITE_SOURCE

    review = task_stage_workflow(TaskWorkflowStage.REVIEW)
    assert (review.role, review.action) == (RoleName.QUALITY_AGENT, ActionName.REVIEW)
    assert review.start_state is review.success_state is TaskState.REVIEWING

    validate = task_stage_workflow(TaskWorkflowStage.VALIDATE)
    assert (validate.role, validate.action) == (RoleName.QUALITY_AGENT, ActionName.VALIDATE)

    test_stage = task_stage_workflow(TaskWorkflowStage.TEST)
    assert test_stage.uses_ai is False
    assert test_stage.requires_context is False
    assert test_stage.success_state is TaskState.VALIDATED

    document = task_stage_workflow(TaskWorkflowStage.DOCUMENT)
    assert document.documentation_required is True
    assert document.success_state is TaskState.COMPLETED


def test_task_stage_from_suggestion_round_trips_every_action() -> None:
    for action, expected_stage in (
        (ActionName.PLAN, TaskWorkflowStage.PLAN),
        (ActionName.IMPLEMENT, TaskWorkflowStage.IMPLEMENT),
        (ActionName.REVIEW, TaskWorkflowStage.REVIEW),
        (ActionName.VALIDATE, TaskWorkflowStage.VALIDATE),
        (ActionName.TEST, TaskWorkflowStage.TEST),
        (ActionName.DOCUMENT, TaskWorkflowStage.DOCUMENT),
    ):
        suggestion = Suggestion(
            task_id=TaskId.new(),
            suggested_role=RoleName.DEVELOPER,
            suggested_action=action,
            rationale="test",
        )
        assert task_stage_from_suggestion(suggestion) is expected_stage


def test_operation_workflow_maps_every_project_operation() -> None:
    assert operation_workflow(ProjectOperation.WRITE_SOURCE) == (
        RoleName.DEVELOPER,
        ActionName.IMPLEMENT,
        TaskState.IMPLEMENTING,
        TaskState.IMPLEMENTED,
    )
    assert operation_workflow(ProjectOperation.WRITE_DOCUMENTATION) == (
        RoleName.DEVELOPER,
        ActionName.DOCUMENT,
        TaskState.IMPLEMENTING,
        TaskState.IMPLEMENTED,
    )
    assert operation_workflow(ProjectOperation.RUN_TESTS) == (
        RoleName.QUALITY_AGENT,
        ActionName.TEST,
        TaskState.TESTING,
        TaskState.VALIDATED,
    )
    for operation in (
        ProjectOperation.RUN_VALIDATION,
        ProjectOperation.RUN_COMMAND,
        ProjectOperation.GIT_STATUS,
    ):
        assert operation_workflow(operation) == (
            RoleName.QUALITY_AGENT,
            ActionName.VALIDATE,
            TaskState.VALIDATING,
            TaskState.VALIDATED,
        )
    # Anything else (e.g. READ_CONTEXT) falls back to the IMPLEMENT shape.
    assert operation_workflow(ProjectOperation.READ_CONTEXT) == (
        RoleName.DEVELOPER,
        ActionName.IMPLEMENT,
        TaskState.IMPLEMENTING,
        TaskState.IMPLEMENTED,
    )


def _build_services() -> tuple[TaskService, SuggestionEngine]:
    events = InProcessEventDispatcher()
    task_service = TaskService(repository=InMemoryTaskRepository(), event_publisher=events)
    suggestion_engine = SuggestionEngine(InMemorySuggestionRepository())
    return task_service, suggestion_engine


def test_resolve_task_stage_moves_a_created_task_to_planning_and_suggests_plan() -> None:
    async def run() -> None:
        task_service, suggestion_engine = _build_services()
        task = await task_service.create_task(
            CreateTaskCommand(
                title="Resolve stage",
                description="Test",
                requested_change="N/A",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        assert task.state is TaskState.CREATED

        resolved_task, suggestion, stage = await resolve_task_stage(
            task_service=task_service,
            suggestion_engine=suggestion_engine,
            task=task,
            requested_stage=None,
        )

        assert resolved_task.state is TaskState.PLANNING
        assert suggestion is not None
        assert suggestion.suggested_action is ActionName.PLAN
        assert stage is TaskWorkflowStage.PLAN

    asyncio.run(run())


def test_resolve_task_stage_an_explicit_stage_bypasses_the_suggestion_engine() -> None:
    async def run() -> None:
        task_service, suggestion_engine = _build_services()
        task = await task_service.create_task(
            CreateTaskCommand(
                title="Resolve stage",
                description="Test",
                requested_change="N/A",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )

        resolved_task, suggestion, stage = await resolve_task_stage(
            task_service=task_service,
            suggestion_engine=suggestion_engine,
            task=task,
            requested_stage=TaskWorkflowStage.IMPLEMENT,
        )

        assert suggestion is None
        assert stage is TaskWorkflowStage.IMPLEMENT
        # CREATED -> PLANNING bookkeeping still happens even with an
        # explicit stage -- only which *stage* to run skips the engine.
        assert resolved_task.state is TaskState.PLANNING

    asyncio.run(run())
