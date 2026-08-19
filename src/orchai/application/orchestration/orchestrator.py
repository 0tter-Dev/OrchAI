"""Central application orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from orchai.application.audit import AuditRepository
from orchai.application.authorization import (
    AuthorizationService,
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.executions import (
    ExecutionService,
    RequestExecutionCommand,
)
from orchai.application.executions.engine import ExecutionEngine
from orchai.application.policies import (
    AutomaticExecutionPolicy,
    LocalPolicyService,
    PolicyOperation,
    PolicyPort,
)
from orchai.application.projects import ProjectService, RegisterProjectCommand
from orchai.application.projects.ports import ProjectAdapter, ProjectAdapterRegistry
from orchai.application.suggestions import SuggestionEngine
from orchai.application.tasks import CreateTaskCommand, TaskService, TransitionTaskCommand
from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.capabilities import CapabilityName
from orchai.domain.events import DomainEvent
from orchai.domain.identifiers import ModelId, TaskId
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion, SuggestionStatus
from orchai.domain.tasks import ExecutionMode, TaskState


class PublishedEventHistory(Protocol):
    """Event publisher capability used only for reporting flow results."""

    @property
    def published_events(self) -> tuple[DomainEvent, ...]:
        """Events published during the current process lifetime."""


class ProjectAdapterFactory(Protocol):
    def __call__(self, project_root: Path) -> ProjectAdapter:
        """Build a project adapter for a local project root."""


@dataclass(frozen=True, slots=True)
class RunLocalFlowCommand:
    """Input for the initial end-to-end orchestration flow."""

    project_root: Path
    context_path: str
    title: str
    model: str
    storage_label: str
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    approve_suggestion: bool = False
    automatic_policy: AutomaticExecutionPolicy = field(
        default_factory=AutomaticExecutionPolicy
    )


@dataclass(frozen=True, slots=True)
class OrchestrationFlowResult:
    """Serializable summary returned by a completed orchestration flow."""

    project_id: str
    task_id: str
    authorization_id: str
    execution_id: str
    task_state: str
    execution_state: str
    context_items: int
    events: int
    audit_records: int
    database: str
    suggestion_id: str = ""
    suggested_role: str = ""
    suggested_action: str = ""
    suggestion_status: str = ""
    blocked_reason: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "authorization_id": self.authorization_id,
            "execution_id": self.execution_id,
            "task_state": self.task_state,
            "execution_state": self.execution_state,
            "context_items": str(self.context_items),
            "events": str(self.events),
            "audit_records": str(self.audit_records),
            "database": self.database,
            "suggestion_id": self.suggestion_id,
            "suggested_role": self.suggested_role,
            "suggested_action": self.suggested_action,
            "suggestion_status": self.suggestion_status,
            "blocked_reason": self.blocked_reason,
        }


class Orchestrator:
    """Coordinates application services without owning their domain rules."""

    def __init__(
        self,
        *,
        project_service: ProjectService,
        task_service: TaskService,
        authorization_service: AuthorizationService,
        execution_service: ExecutionService,
        execution_engine: ExecutionEngine,
        suggestion_engine: SuggestionEngine,
        policy_service: PolicyPort,
        project_adapters: ProjectAdapterRegistry,
        create_project_adapter: ProjectAdapterFactory,
        event_history: PublishedEventHistory,
        audit_repository: AuditRepository,
    ) -> None:
        self._project_service = project_service
        self._task_service = task_service
        self._authorization_service = authorization_service
        self._execution_service = execution_service
        self._execution_engine = execution_engine
        self._suggestion_engine = suggestion_engine
        self._policy_service = policy_service
        self._project_adapters = project_adapters
        self._create_project_adapter = create_project_adapter
        self._event_history = event_history
        self._audit_repository = audit_repository

    async def run_local_flow(
        self,
        command: RunLocalFlowCommand,
    ) -> OrchestrationFlowResult:
        """Run a minimal authorized task/execution/context flow."""

        project = await self._project_service.register_project(
            RegisterProjectCommand(
                name=command.project_root.name,
                root_location=str(command.project_root),
                capabilities=(
                    CapabilityName.READ_PROJECT,
                    CapabilityName.READ_DOCUMENTATION,
                ),
            )
        )
        await self._project_adapters.register(
            project.id,
            self._create_project_adapter(command.project_root),
        )

        task = await self._task_service.create_task(
            CreateTaskCommand(
                title=command.title,
                description="Minimal CLI flow for an authorized local execution.",
                requested_change="Resolve authorized context and complete execution.",
                project_id=project.id,
                execution_mode=command.execution_mode,
                acceptance_criteria=("Execution receives only authorized context.",),
            )
        )
        await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNING)
        )
        task = await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNED)
        )

        suggestion = await self._suggestion_engine.suggest_next(task)
        if suggestion is None:
            return await self._blocked_result(
                project_id=str(project.id),
                task_id=str(task.id),
                task_state=task.state.value,
                storage_label=command.storage_label,
                blocked_reason="no_suggestion_available",
            )

        active_policy = LocalPolicyService(automatic_policy=command.automatic_policy)
        policy_decision = await active_policy.evaluate(
            PolicyOperation(
                execution_mode=command.execution_mode,
                role=suggestion.suggested_role,
                action=suggestion.suggested_action,
                requested_model=command.model,
                effective_model=command.model,
                requested_context=(command.context_path,),
                authorized_context=(command.context_path,),
                current_task_state=task.state,
                approve_suggestion=command.approve_suggestion,
            )
        )
        suggestion_status = (
            SuggestionStatus.ACCEPTED
            if policy_decision.allowed
            else SuggestionStatus.PRESENTED
        )
        suggestion = await self._suggestion_engine.mark_status(
            suggestion,
            suggestion_status,
        )
        if not policy_decision.allowed:
            return await self._blocked_result(
                project_id=str(project.id),
                task_id=str(task.id),
                task_state=task.state.value,
                storage_label=command.storage_label,
                suggestion=suggestion,
                blocked_reason=policy_decision.reason,
            )

        model_id = ModelId(command.model)
        authorization = await self._authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task.id,
                role=suggestion.suggested_role,
                action=suggestion.suggested_action,
                model_id=model_id,
                context_scope=(command.context_path,),
                reason="User requested local CLI execution.",
                requester="cli",
                execution_mode=command.execution_mode,
            )
        )
        await self._authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="cli",
                reason="Explicit CLI demonstration approval.",
            )
        )

        await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=TaskState.IMPLEMENTING)
        )
        execution = await self._execution_service.request_execution(
            RequestExecutionCommand(
                task_id=task.id,
                role=suggestion.suggested_role,
                action=suggestion.suggested_action,
                model_id=model_id,
                authorization_id=authorization.id,
                project_id=project.id,
                requested_context=(command.context_path,),
                authorized_context=(command.context_path,),
            )
        )
        execution = await self._execution_engine.run(execution.id)
        if execution.result is not None and execution.result.success:
            task = await self._task_service.transition_task(
                TransitionTaskCommand(
                    task_id=task.id,
                    target_state=TaskState.IMPLEMENTED,
                )
            )

        audit_records = await self._audit_repository.list(task_id=task.id, limit=100)
        return OrchestrationFlowResult(
            project_id=str(project.id),
            task_id=str(task.id),
            authorization_id=str(authorization.id),
            execution_id=str(execution.id),
            task_state=task.state.value,
            execution_state=execution.state.value,
            context_items=len(execution.authorized_context),
            events=len(self._event_history.published_events),
            audit_records=len(audit_records),
            database=command.storage_label,
            suggestion_id=str(suggestion.id),
            suggested_role=suggestion.suggested_role.value,
            suggested_action=suggestion.suggested_action.value,
            suggestion_status=suggestion.status.value,
        )

    async def _blocked_result(
        self,
        *,
        project_id: str,
        task_id: str,
        task_state: str,
        storage_label: str,
        blocked_reason: str,
        suggestion: Suggestion | None = None,
    ) -> OrchestrationFlowResult:
        audit_records = await self._audit_repository.list(
            task_id=TaskId(task_id),
            limit=100,
        )
        return OrchestrationFlowResult(
            project_id=project_id,
            task_id=task_id,
            authorization_id="",
            execution_id="",
            task_state=task_state,
            execution_state="",
            context_items=0,
            events=len(self._event_history.published_events),
            audit_records=len(audit_records),
            database=storage_label,
            suggestion_id=str(suggestion.id) if suggestion is not None else "",
            suggested_role=suggestion.suggested_role.value
            if suggestion is not None
            else "",
            suggested_action=suggestion.suggested_action.value
            if suggestion is not None
            else "",
            suggestion_status=suggestion.status.value if suggestion is not None else "",
            blocked_reason=blocked_reason,
        )
