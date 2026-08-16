"""Minimal local orchestration flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from orchai.application.authorization import (
    AuthorizationService,
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.authorization.ports import AuthorizationRepository
from orchai.application.context import ContextService, ResolveExecutionContextCommand
from orchai.application.events import InProcessEventDispatcher
from orchai.application.executions import (
    CompleteExecutionCommand,
    ExecutionService,
    RequestExecutionCommand,
    TransitionExecutionCommand,
)
from orchai.application.executions.ports import ExecutionRepository
from orchai.application.projects import ProjectService, RegisterProjectCommand
from orchai.application.projects.ports import (
    ProjectAdapter,
    ProjectAdapterRegistry,
    ProjectRepository,
)
from orchai.application.tasks import CreateTaskCommand, TaskService, TransitionTaskCommand
from orchai.application.tasks.ports import TaskRepository
from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.capabilities import CapabilityName
from orchai.domain.executions import ExecutionState
from orchai.domain.identifiers import ModelId
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode, TaskState


async def run_local_flow(
    *,
    project_root: Path,
    context_path: str,
    title: str,
    model: str,
    dependencies: LocalFlowDependencies,
    storage_label: str = "provided",
) -> dict[str, str]:
    """Run a minimal authorized task/execution/context flow."""

    events = InProcessEventDispatcher()
    project_repository = dependencies.project_repository
    project_adapters = dependencies.project_adapters
    task_repository = dependencies.task_repository
    authorization_repository = dependencies.authorization_repository
    execution_repository = dependencies.execution_repository

    project_service = ProjectService(
        repository=project_repository,
        event_publisher=events,
    )
    task_service = TaskService(repository=task_repository, event_publisher=events)
    authorization_service = AuthorizationService(
        repository=authorization_repository,
        event_publisher=events,
    )
    execution_service = ExecutionService(
        repository=execution_repository,
        authorization_repository=authorization_repository,
        event_publisher=events,
    )
    context_service = ContextService(
        execution_repository=execution_repository,
        project_adapters=project_adapters,
        event_publisher=events,
    )

    project = await project_service.register_project(
        RegisterProjectCommand(
            name=project_root.name,
            root_location=str(project_root),
            capabilities=(
                CapabilityName.READ_PROJECT,
                CapabilityName.READ_DOCUMENTATION,
            ),
        )
    )
    await project_adapters.register(
        project.id,
        dependencies.create_project_adapter(project_root),
    )

    task = await task_service.create_task(
        CreateTaskCommand(
            title=title,
            description="Minimal CLI flow for an authorized local execution.",
            requested_change="Resolve authorized context and complete execution.",
            project_id=project.id,
            acceptance_criteria=("Execution receives only authorized context.",),
        )
    )
    await task_service.transition_task(
        TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNING)
    )
    await task_service.transition_task(
        TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNED)
    )

    model_id = ModelId(model)
    authorization = await authorization_service.request_authorization(
        RequestAuthorizationCommand(
            task_id=task.id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=model_id,
            context_scope=(context_path,),
            reason="User requested local CLI execution.",
            requester="cli",
            execution_mode=ExecutionMode.SUGGESTED,
        )
    )
    await authorization_service.decide_authorization(
        DecideAuthorizationCommand(
            authorization_id=authorization.id,
            status=AuthorizationDecisionStatus.GRANTED,
            decided_by="cli",
            reason="Explicit CLI demonstration approval.",
        )
    )

    await task_service.transition_task(
        TransitionTaskCommand(task_id=task.id, target_state=TaskState.IMPLEMENTING)
    )
    execution = await execution_service.request_execution(
        RequestExecutionCommand(
            task_id=task.id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=model_id,
            authorization_id=authorization.id,
            project_id=project.id,
            requested_context=(context_path,),
            authorized_context=(context_path,),
        )
    )
    package = await context_service.resolve_execution_context(
        ResolveExecutionContextCommand(execution_id=execution.id)
    )
    await execution_service.transition_execution(
        TransitionExecutionCommand(
            execution_id=execution.id,
            target_state=ExecutionState.PREPARING,
        )
    )
    await execution_service.transition_execution(
        TransitionExecutionCommand(
            execution_id=execution.id,
            target_state=ExecutionState.STARTED,
        )
    )
    await execution_service.transition_execution(
        TransitionExecutionCommand(
            execution_id=execution.id,
            target_state=ExecutionState.RUNNING,
        )
    )
    execution = await execution_service.complete_execution(
        CompleteExecutionCommand(
            execution_id=execution.id,
            output=f"Resolved {len(package.items)} authorized context item(s).",
        )
    )
    task = await task_service.transition_task(
        TransitionTaskCommand(task_id=task.id, target_state=TaskState.IMPLEMENTED)
    )

    return {
        "project_id": str(project.id),
        "task_id": str(task.id),
        "authorization_id": str(authorization.id),
        "execution_id": str(execution.id),
        "task_state": task.state.value,
        "execution_state": execution.state.value,
        "context_items": str(len(package.items)),
        "events": str(len(events.published_events)),
        "database": storage_label,
    }


@dataclass(frozen=True, slots=True)
class LocalFlowDependencies:
    project_repository: ProjectRepository
    task_repository: TaskRepository
    authorization_repository: AuthorizationRepository
    execution_repository: ExecutionRepository
    project_adapters: ProjectAdapterRegistry
    create_project_adapter: ProjectAdapterFactory


class ProjectAdapterFactory(Protocol):
    def __call__(self, project_root: Path) -> ProjectAdapter:
        """Build a project adapter for a local project root."""
