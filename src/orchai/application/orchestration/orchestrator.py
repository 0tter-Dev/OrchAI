"""Central application orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from orchai.application.audit import AuditRepository
from orchai.application.authorization import (
    AuthorizationService,
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.events.ports import EventPublisher
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
from orchai.application.projects.ports import (
    ProjectAdapter,
    ProjectAdapterRegistry,
    ProjectReadinessAssessment,
)
from orchai.application.suggestions import SuggestionEngine
from orchai.application.tasks import CreateTaskCommand, TaskService, TransitionTaskCommand
from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.identifiers import ModelId, ProjectId, TaskId
from orchai.domain.projects import Project, ProjectOperation, ProviderTarget
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion, SuggestionStatus
from orchai.domain.tasks import ExecutionMode, TaskState, TaskStateMachine
from orchai.infrastructure.projects.errors import ProjectAdapterError


class PublishedEventHistory(Protocol):
    """Event publisher capability used only for reporting flow results."""

    @property
    def published_events(self) -> tuple[DomainEvent, ...]:
        """Events published during the current process lifetime."""


class ProjectAdapterFactory(Protocol):
    def __call__(self, project_root: Path) -> ProjectAdapter:
        """Build a project adapter for a local project root."""


class TaskWorkflowStage(StrEnum):
    """Higher-level task-centric workflow stages."""

    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    REVIEW = "REVIEW"
    VALIDATE = "VALIDATE"
    TEST = "TEST"
    DOCUMENT = "DOCUMENT"


@dataclass(frozen=True, slots=True)
class RunLocalFlowCommand:
    """Input for the initial end-to-end orchestration flow."""

    project_root: Path
    context_path: str
    title: str
    model: str
    storage_label: str
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    approve_suggestion: bool = False
    automatic_policy: AutomaticExecutionPolicy = field(
        default_factory=AutomaticExecutionPolicy
    )


@dataclass(frozen=True, slots=True)
class RunProjectOperationCommand:
    """Input for a protected project-adapter operation."""

    project_root: Path
    operation: ProjectOperation
    title: str
    storage_label: str
    resource: str = ""
    content: str = ""
    command: tuple[str, ...] = ()
    test_args: tuple[str, ...] = ()
    model: str = "local-project-operation"
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED
    approve_operation: bool = False
    automatic_policy: AutomaticExecutionPolicy = field(
        default_factory=AutomaticExecutionPolicy
    )


@dataclass(frozen=True, slots=True)
class RunTaskWorkflowStageCommand:
    """Input for advancing one persisted task through one workflow stage."""

    task_id: TaskId
    storage_label: str
    model: str = "local-task-stage"
    stage: TaskWorkflowStage | None = None
    context_paths: tuple[str, ...] = ()
    documentation_path: str = ""
    test_args: tuple[str, ...] = ()
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    execution_mode: ExecutionMode | None = None
    approve_stage: bool = False
    requester: str = "operator"
    decider: str = "operator"
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


@dataclass(frozen=True, slots=True)
class ProjectOperationResult:
    """Serializable summary returned by a protected project operation."""

    project_id: str
    task_id: str
    authorization_id: str
    task_state: str
    project_operation: str
    output: str = ""
    exit_code: str = ""
    resource: str = ""
    blocked_reason: str = ""
    events: int = 0
    audit_records: int = 0
    database: str = ""
    suggestion_id: str = ""
    suggested_role: str = ""
    suggested_action: str = ""
    suggestion_status: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "authorization_id": self.authorization_id,
            "task_state": self.task_state,
            "project_operation": self.project_operation,
            "output": self.output,
            "exit_code": self.exit_code,
            "resource": self.resource,
            "blocked_reason": self.blocked_reason,
            "events": str(self.events),
            "audit_records": str(self.audit_records),
            "database": self.database,
            "suggestion_id": self.suggestion_id,
            "suggested_role": self.suggested_role,
            "suggested_action": self.suggested_action,
            "suggestion_status": self.suggestion_status,
        }


@dataclass(frozen=True, slots=True)
class TaskWorkflowStageResult:
    """Serializable summary returned by one task-centric workflow step."""

    project_id: str
    task_id: str
    stage: str
    task_state: str
    authorization_id: str = ""
    execution_id: str = ""
    execution_state: str = ""
    output: str = ""
    resource: str = ""
    blocked_reason: str = ""
    events: int = 0
    audit_records: int = 0
    database: str = ""
    suggestion_id: str = ""
    suggested_role: str = ""
    suggested_action: str = ""
    suggestion_status: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "stage": self.stage,
            "task_state": self.task_state,
            "authorization_id": self.authorization_id,
            "execution_id": self.execution_id,
            "execution_state": self.execution_state,
            "output": self.output,
            "resource": self.resource,
            "blocked_reason": self.blocked_reason,
            "events": str(self.events),
            "audit_records": str(self.audit_records),
            "database": self.database,
            "suggestion_id": self.suggestion_id,
            "suggested_role": self.suggested_role,
            "suggested_action": self.suggested_action,
            "suggestion_status": self.suggestion_status,
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
        event_publisher: EventPublisher,
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
        self._event_publisher = event_publisher
        self._event_history = event_history
        self._audit_repository = audit_repository

    async def run_local_flow(
        self,
        command: RunLocalFlowCommand,
    ) -> OrchestrationFlowResult:
        """Register a project, create a task, and advance it one gated stage.

        This is the entry point behind ``POST /requests`` and
        ``POST /flows/local``. Per
        ``docs/architecture/CHAT-FIRST-REQUEST-MODEL.md`` (section 3) and
        ADR-011 invariant #2, no workflow stage — including the very first
        one, PLAN — may bypass the suggestion/policy gate. This method
        therefore does not transition the task itself: it delegates the
        entire stage advance to :meth:`run_task_workflow_stage`, the same
        gated mechanism used by ``POST /tasks/{id}/advance`` and
        ``POST /requests/{id}/advance``, so a single code path enforces the
        gate everywhere regardless of storage backend. In SUGGESTED mode
        (the default) this call creates the task and stops at the PLAN
        suggestion, exactly as documented; only AUTOMATIC mode, with
        ``(TASK_PLANNER, PLAN)`` explicitly present in
        ``automatic_policy.allowed_operations``, may proceed past it
        without an explicit decision.
        """

        adapter = self._create_project_adapter(command.project_root)
        readiness = await adapter.assess_readiness()
        project = await self._project_service.register_project(
            RegisterProjectCommand(
                name=command.project_root.name,
                root_location=str(command.project_root),
                capabilities=await adapter.capabilities(),
                readiness_level=readiness.readiness_level,
                security_profile=readiness.security_profile,
                observed_readiness_level=readiness.readiness_level,
                observed_security_profile=readiness.security_profile,
            )
        )
        await self._publish_project_readiness(
            project=project,
            readiness=readiness,
        )
        await self._project_adapters.register(
            project.id,
            adapter,
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

        stage_result = await self.run_task_workflow_stage(
            RunTaskWorkflowStageCommand(
                task_id=task.id,
                storage_label=command.storage_label,
                model=command.model,
                stage=None,
                context_paths=(command.context_path,),
                provider_target=command.provider_target,
                execution_mode=command.execution_mode,
                approve_stage=command.approve_suggestion,
                requester="requests-api",
                decider="requests-api",
                automatic_policy=command.automatic_policy,
            )
        )
        return OrchestrationFlowResult(
            project_id=str(project.id),
            task_id=stage_result.task_id,
            authorization_id=stage_result.authorization_id,
            execution_id=stage_result.execution_id,
            task_state=stage_result.task_state,
            execution_state=stage_result.execution_state,
            context_items=1 if stage_result.execution_id else 0,
            events=stage_result.events,
            audit_records=stage_result.audit_records,
            database=stage_result.database,
            suggestion_id=stage_result.suggestion_id,
            suggested_role=stage_result.suggested_role,
            suggested_action=stage_result.suggested_action,
            suggestion_status=stage_result.suggestion_status,
            blocked_reason=stage_result.blocked_reason,
        )

    async def run_project_operation(
        self,
        command: RunProjectOperationCommand,
    ) -> ProjectOperationResult:
        """Run a protected project-adapter operation through policy and authorization.

        The task created here must reach ``PLANNED`` before its own operation
        can start (the state machine only allows IMPLEMENTING/REVIEWING/
        VALIDATING/TESTING directly from PLANNED). That bootstrap hop used to
        happen as two unconditional, ungated transitions — the same "surprise"
        shape found in the ``/requests`` flow. It is now gated by
        ``_advance_task_to_planned`` through the identical suggestion/policy
        mechanism: a single ``approve_operation=True`` still authorizes the
        whole call (bootstrap PLAN and the operation itself share that flag),
        but nothing reaches PLANNED without an explicit decision unless
        AUTOMATIC mode has ``(TASK_PLANNER, PLAN)`` configured in
        ``automatic_policy.allowed_operations``.
        """

        adapter, readiness, project = await self._connect_project(command.project_root)
        await self._project_adapters.register(project.id, adapter)
        task = await self._task_service.create_task(
            CreateTaskCommand(
                title=command.title,
                description="Protected project operation through the Project Adapter.",
                requested_change=f"Run project operation {command.operation.value}.",
                project_id=project.id,
                execution_mode=command.execution_mode,
                acceptance_criteria=("Operation passes policy and authorization.",),
            )
        )

        context_sharing_levels = ()
        if command.resource:
            classified_resource = await adapter.classify_resource(
                await _context_reference_for(adapter, command.resource)
            )
            context_sharing_levels = (classified_resource.provider_sharing_level,)

        active_policy = self._policy_service
        if (
            isinstance(self._policy_service, LocalPolicyService)
            and command.automatic_policy != AutomaticExecutionPolicy()
        ):
            active_policy = LocalPolicyService(
                automatic_policy=command.automatic_policy
            )

        task, plan_suggestion, blocked_reason = await self._advance_task_to_planned(
            task=task,
            project=project,
            active_policy=active_policy,
            execution_mode=command.execution_mode,
            approve=command.approve_operation,
            provider_target=command.provider_target,
            context_sharing_levels=context_sharing_levels,
            requested_context=(command.resource,) if command.resource else (),
        )
        if blocked_reason is not None:
            await self._publish_project_operation_blocked(
                project_id=project.id,
                readiness=project.readiness_level.value,
                provider_target=command.provider_target,
                reason=blocked_reason,
            )
            return await self._project_operation_result(
                project=project,
                task_id=str(task.id),
                authorization_id="",
                task_state=task.state.value,
                operation=command.operation,
                storage_label=command.storage_label,
                blocked_reason=blocked_reason,
                suggestion=plan_suggestion,
            )

        role, action, start_state, success_state = _operation_workflow(
            command.operation
        )
        policy_decision = await active_policy.evaluate(
            PolicyOperation(
                execution_mode=command.execution_mode,
                project_operation=command.operation,
                provider_target=command.provider_target,
                project_readiness_level=project.readiness_level,
                project_security_profile=project.security_profile,
                context_sharing_levels=context_sharing_levels,
                role=role,
                action=action,
                requested_model=command.model,
                effective_model=command.model,
                requested_context=(command.resource,) if command.resource else (),
                authorized_context=(command.resource,) if command.resource else (),
                current_task_state=task.state,
                approve_suggestion=command.approve_operation,
                explicit_user_command=True,
            )
        )
        if not policy_decision.allowed:
            await self._publish_project_operation_blocked(
                project_id=project.id,
                readiness=project.readiness_level.value,
                provider_target=command.provider_target,
                reason=policy_decision.reason,
            )
            return await self._project_operation_result(
                project=project,
                task_id=str(task.id),
                authorization_id="",
                task_state=task.state.value,
                operation=command.operation,
                storage_label=command.storage_label,
                blocked_reason=policy_decision.reason,
                suggestion=plan_suggestion,
            )

        authorization = await self._authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task.id,
                role=role,
                action=action,
                model_id=ModelId(command.model),
                context_scope=(command.resource,) if command.resource else (),
                reason="User requested protected project operation.",
                requester="cli",
                execution_mode=command.execution_mode,
            )
        )
        await self._authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="cli",
                reason="Explicit project operation approval.",
            )
        )
        task = await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=start_state)
        )

        try:
            operation_result = await _run_adapter_operation(adapter, command)
        except ProjectAdapterError as exc:
            task = await self._task_service.transition_task(
                TransitionTaskCommand(task_id=task.id, target_state=TaskState.FAILED)
            )
            await self._publish_project_operation_failed(
                project_id=project.id,
                operation=command.operation,
                reason=str(exc),
            )
            return await self._project_operation_result(
                project=project,
                task_id=str(task.id),
                authorization_id=str(authorization.id),
                task_state=task.state.value,
                operation=command.operation,
                storage_label=command.storage_label,
                blocked_reason=str(exc),
                suggestion=plan_suggestion,
            )

        task = await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=success_state)
        )
        await self._publish_project_operation_completed(
            project_id=project.id,
            operation=command.operation,
            payload=operation_result,
        )
        return await self._project_operation_result(
            project=project,
            task_id=str(task.id),
            authorization_id=str(authorization.id),
            task_state=task.state.value,
            operation=command.operation,
            storage_label=command.storage_label,
            output=operation_result.get("output", ""),
            exit_code=operation_result.get("exit_code", ""),
            resource=operation_result.get("resource", ""),
            suggestion=plan_suggestion,
        )

    async def _advance_task_to_planned(
        self,
        *,
        task,
        project,
        active_policy: PolicyPort,
        execution_mode: ExecutionMode,
        approve: bool,
        provider_target: ProviderTarget,
        context_sharing_levels: tuple,
        requested_context: tuple[str, ...],
    ) -> tuple:
        """Move a freshly created task from CREATED to PLANNED, gated.

        CREATED -> PLANNING is pure bookkeeping (it only readies the task so
        the suggestion engine can produce a PLAN suggestion — the same rule
        already applied by ``_resolve_task_stage``). PLANNING -> PLANNED is
        the actual PLAN action and must pass through the identical
        suggestion/policy gate as every other stage: it is never skipped
        silently, and only AUTOMATIC mode with ``(TASK_PLANNER, PLAN)``
        explicitly present in ``automatic_policy.allowed_operations`` may
        proceed without an explicit human or client decision.

        No AI execution is run for this bootstrap step — callers that need a
        real planning execution should go through the PLAN stage of
        ``run_task_workflow_stage`` instead (as ``run_local_flow`` now does).
        This helper only exists to authorize the mechanical state-machine
        hop that ``PLANNED`` requires before IMPLEMENTING/REVIEWING/
        VALIDATING/TESTING can be reached directly.
        """

        task = await self._task_service.transition_task(
            TransitionTaskCommand(
                task_id=task.id,
                target_state=TaskState.PLANNING,
                source="application.orchestration.tasks",
            )
        )
        suggestion = await self._suggestion_engine.suggest_next(task)
        role = suggestion.suggested_role if suggestion is not None else RoleName.TASK_PLANNER
        action = suggestion.suggested_action if suggestion is not None else ActionName.PLAN
        policy_decision = await active_policy.evaluate(
            PolicyOperation(
                execution_mode=execution_mode,
                project_operation=ProjectOperation.READ_CONTEXT,
                provider_target=provider_target,
                project_readiness_level=project.readiness_level,
                project_security_profile=project.security_profile,
                context_sharing_levels=context_sharing_levels,
                role=role,
                action=action,
                requested_model="",
                effective_model="",
                requested_context=requested_context,
                authorized_context=requested_context,
                current_task_state=task.state,
                approve_suggestion=approve,
                explicit_user_command=execution_mode is ExecutionMode.MANUAL,
            )
        )
        if suggestion is not None:
            suggestion = await self._suggestion_engine.mark_status(
                suggestion,
                (
                    SuggestionStatus.ACCEPTED
                    if policy_decision.allowed
                    else SuggestionStatus.PRESENTED
                ),
            )
        if not policy_decision.allowed:
            return task, suggestion, policy_decision.reason

        authorization = await self._authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task.id,
                role=role,
                action=action,
                model_id=None,
                context_scope=requested_context,
                reason="Bootstrap PLAN stage before a protected project operation.",
                requester="cli",
                execution_mode=execution_mode,
            )
        )
        await self._authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="cli",
                reason="Explicit project operation approval.",
            )
        )
        task = await self._task_service.transition_task(
            TransitionTaskCommand(
                task_id=task.id,
                target_state=TaskState.PLANNED,
                source="application.orchestration.tasks",
            )
        )
        return task, suggestion, None

    async def run_task_workflow_stage(
        self,
        command: RunTaskWorkflowStageCommand,
    ) -> TaskWorkflowStageResult:
        """Advance one persisted task through one workflow stage."""

        task = await self._task_service.get_task(command.task_id)
        if task.project_id is None:
            return await self._task_workflow_stage_result(
                task_id=str(task.id),
                project_id="",
                stage=(command.stage.value if command.stage is not None else ""),
                task_state=task.state.value,
                storage_label=command.storage_label,
                blocked_reason="task_has_no_project",
            )

        adapter, project = await self._connect_registered_project(task.project_id)
        effective_mode = command.execution_mode or task.execution_mode
        task, suggestion, stage = await self._resolve_task_stage(
            task=task,
            requested_stage=command.stage,
        )
        if stage is None:
            return await self._task_workflow_stage_result(
                task_id=str(task.id),
                project_id=str(project.id),
                stage="",
                task_state=task.state.value,
                storage_label=command.storage_label,
                suggestion=suggestion,
                blocked_reason="no_suggestion_available",
            )

        workflow = _task_stage_workflow(stage)
        context_paths = _normalized_paths(command.context_paths)
        if workflow.requires_context and not context_paths:
            return await self._task_workflow_stage_result(
                task_id=str(task.id),
                project_id=str(project.id),
                stage=stage.value,
                task_state=task.state.value,
                storage_label=command.storage_label,
                suggestion=suggestion,
                blocked_reason="stage_requires_context",
            )
        if workflow.documentation_required and not command.documentation_path.strip():
            return await self._task_workflow_stage_result(
                task_id=str(task.id),
                project_id=str(project.id),
                stage=stage.value,
                task_state=task.state.value,
                storage_label=command.storage_label,
                suggestion=suggestion,
                blocked_reason="documentation_path_required",
            )

        classified_levels = await self._classify_context_paths(
            adapter=adapter,
            context_paths=context_paths,
        )
        active_policy = self._policy_service
        if (
            isinstance(self._policy_service, LocalPolicyService)
            and command.automatic_policy != AutomaticExecutionPolicy()
        ):
            active_policy = LocalPolicyService(
                automatic_policy=command.automatic_policy
            )
        policy_decision = await active_policy.evaluate(
            PolicyOperation(
                execution_mode=effective_mode,
                project_operation=workflow.project_operation,
                provider_target=command.provider_target,
                project_readiness_level=project.readiness_level,
                project_security_profile=project.security_profile,
                context_sharing_levels=classified_levels,
                role=workflow.role,
                action=workflow.action,
                requested_model=command.model,
                effective_model=command.model,
                requested_context=context_paths,
                authorized_context=context_paths,
                current_task_state=task.state,
                approve_suggestion=command.approve_stage,
                explicit_user_command=command.stage is not None
                or effective_mode is ExecutionMode.MANUAL,
            )
        )
        if suggestion is not None:
            suggestion = await self._suggestion_engine.mark_status(
                suggestion,
                (
                    SuggestionStatus.ACCEPTED
                    if policy_decision.allowed
                    else SuggestionStatus.PRESENTED
                ),
            )
        if not policy_decision.allowed:
            await self._publish_project_operation_blocked(
                project_id=project.id,
                readiness=project.readiness_level.value,
                provider_target=command.provider_target,
                reason=policy_decision.reason,
            )
            return await self._task_workflow_stage_result(
                task_id=str(task.id),
                project_id=str(project.id),
                stage=stage.value,
                task_state=task.state.value,
                storage_label=command.storage_label,
                suggestion=suggestion,
                blocked_reason=policy_decision.reason,
            )

        authorization = await self._authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task.id,
                role=workflow.role,
                action=workflow.action,
                model_id=ModelId(command.model) if workflow.uses_ai else None,
                context_scope=context_paths,
                reason=f"Advance task through {stage.value} stage.",
                requester=command.requester,
                execution_mode=effective_mode,
            )
        )
        await self._authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by=command.decider,
                reason=f"Approved task workflow stage {stage.value}.",
            )
        )

        if task.state is not workflow.start_state:
            task = await self._task_service.transition_task(
                TransitionTaskCommand(
                    task_id=task.id,
                    target_state=workflow.start_state,
                    source="application.orchestration.tasks",
                )
            )

        if workflow.uses_ai:
            execution = await self._execution_service.request_execution(
                RequestExecutionCommand(
                    task_id=task.id,
                    role=workflow.role,
                    action=workflow.action,
                    model_id=ModelId(command.model),
                    authorization_id=authorization.id,
                    project_id=project.id,
                    requested_context=context_paths,
                    authorized_context=context_paths,
                )
            )
            execution = await self._execution_engine.run(execution.id)
            if execution.result is None or not execution.result.success:
                task = await self._transition_task_to_blocked(task)
                return await self._task_workflow_stage_result(
                    task_id=str(task.id),
                    project_id=str(project.id),
                    stage=stage.value,
                    task_state=task.state.value,
                    authorization_id=str(authorization.id),
                    execution_id=str(execution.id),
                    execution_state=execution.state.value,
                    output=execution.result.output if execution.result is not None else "",
                    storage_label=command.storage_label,
                    suggestion=suggestion,
                    blocked_reason=_execution_failure_reason(execution),
                )

            output = execution.result.output
            resource = ""
            if workflow.documentation_required:
                try:
                    documentation_reference = await _context_reference_for(
                        adapter,
                        command.documentation_path,
                    )
                    write_result = await adapter.write_documentation(
                        documentation_reference,
                        output,
                    )
                    resource = write_result.resource
                    await self._publish_project_operation_completed(
                        project_id=project.id,
                        operation=ProjectOperation.WRITE_DOCUMENTATION,
                        payload={
                            "resource": write_result.resource,
                            "bytes_written": str(write_result.bytes_written),
                            "output": f"wrote {write_result.bytes_written} byte(s)",
                        },
                    )
                except ProjectAdapterError as exc:
                    task = await self._transition_task_to_blocked(task)
                    return await self._task_workflow_stage_result(
                        task_id=str(task.id),
                        project_id=str(project.id),
                        stage=stage.value,
                        task_state=task.state.value,
                        authorization_id=str(authorization.id),
                        execution_id=str(execution.id),
                        execution_state=execution.state.value,
                        output=output,
                        storage_label=command.storage_label,
                        suggestion=suggestion,
                        blocked_reason=str(exc),
                    )

            if task.state is not workflow.success_state:
                task = await self._task_service.transition_task(
                    TransitionTaskCommand(
                        task_id=task.id,
                        target_state=workflow.success_state,
                        source="application.orchestration.tasks",
                    )
                )
            return await self._task_workflow_stage_result(
                task_id=str(task.id),
                project_id=str(project.id),
                stage=stage.value,
                task_state=task.state.value,
                authorization_id=str(authorization.id),
                execution_id=str(execution.id),
                execution_state=execution.state.value,
                output=output,
                resource=resource,
                storage_label=command.storage_label,
                suggestion=suggestion,
            )

        try:
            command_result = await adapter.run_tests(args=command.test_args)
        except ProjectAdapterError as exc:
            task = await self._transition_task_to_blocked(task)
            await self._publish_project_operation_failed(
                project_id=project.id,
                operation=workflow.project_operation,
                reason=str(exc),
            )
            return await self._task_workflow_stage_result(
                task_id=str(task.id),
                project_id=str(project.id),
                stage=stage.value,
                task_state=task.state.value,
                authorization_id=str(authorization.id),
                storage_label=command.storage_label,
                suggestion=suggestion,
                blocked_reason=str(exc),
            )

        if command_result.exit_code != 0:
            task = await self._transition_task_to_blocked(task)
            await self._publish_project_operation_failed(
                project_id=project.id,
                operation=workflow.project_operation,
                reason=f"tests exited with code {command_result.exit_code}",
            )
            return await self._task_workflow_stage_result(
                task_id=str(task.id),
                project_id=str(project.id),
                stage=stage.value,
                task_state=task.state.value,
                authorization_id=str(authorization.id),
                output=command_result.stdout,
                storage_label=command.storage_label,
                suggestion=suggestion,
                blocked_reason=f"tests exited with code {command_result.exit_code}",
            )

        task = await self._task_service.transition_task(
            TransitionTaskCommand(
                task_id=task.id,
                target_state=workflow.success_state,
                source="application.orchestration.tasks",
            )
        )
        await self._publish_project_operation_completed(
            project_id=project.id,
            operation=workflow.project_operation,
            payload={
                "command": " ".join(command_result.command),
                "exit_code": str(command_result.exit_code),
                "output": command_result.stdout,
                "stderr": command_result.stderr,
            },
        )
        return await self._task_workflow_stage_result(
            task_id=str(task.id),
            project_id=str(project.id),
            stage=stage.value,
            task_state=task.state.value,
            authorization_id=str(authorization.id),
            output=command_result.stdout,
            storage_label=command.storage_label,
            suggestion=suggestion,
        )

    async def _connect_project(
        self,
        project_root: Path,
    ) -> tuple[ProjectAdapter, ProjectReadinessAssessment, Project]:
        adapter = self._create_project_adapter(project_root)
        readiness = await adapter.assess_readiness()
        project = await self._project_service.register_project(
            RegisterProjectCommand(
                name=project_root.name,
                root_location=str(project_root),
                capabilities=await adapter.capabilities(),
                readiness_level=readiness.readiness_level,
                security_profile=readiness.security_profile,
                observed_readiness_level=readiness.readiness_level,
                observed_security_profile=readiness.security_profile,
            )
        )
        await self._publish_project_readiness(project=project, readiness=readiness)
        return adapter, readiness, project

    async def _connect_registered_project(
        self,
        project_id: ProjectId,
    ) -> tuple[ProjectAdapter, Project]:
        project = await self._project_service.get_project(project_id)
        adapter = self._create_project_adapter(Path(project.root_location))
        readiness = await adapter.assess_readiness()
        refreshed_project = await self._project_service.register_project(
            RegisterProjectCommand(
                name=project.name,
                root_location=project.root_location,
                capabilities=await adapter.capabilities(),
                readiness_level=project.readiness_level,
                security_profile=project.security_profile,
                observed_readiness_level=readiness.readiness_level,
                observed_security_profile=readiness.security_profile,
            )
        )
        await self._project_adapters.register(refreshed_project.id, adapter)
        await self._publish_project_readiness(
            project=refreshed_project,
            readiness=readiness,
        )
        return adapter, refreshed_project

    async def _project_operation_result(
        self,
        *,
        project: Project,
        task_id: str,
        authorization_id: str,
        task_state: str,
        operation: ProjectOperation,
        storage_label: str,
        output: str = "",
        exit_code: str = "",
        resource: str = "",
        blocked_reason: str = "",
        suggestion: Suggestion | None = None,
    ) -> ProjectOperationResult:
        audit_records = await self._audit_repository.list(
            task_id=TaskId(task_id),
            limit=100,
        )
        return ProjectOperationResult(
            project_id=str(project.id),
            task_id=task_id,
            authorization_id=authorization_id,
            task_state=task_state,
            project_operation=operation.value,
            output=output,
            exit_code=exit_code,
            resource=resource,
            blocked_reason=blocked_reason,
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
        )

    async def _task_workflow_stage_result(
        self,
        *,
        task_id: str,
        project_id: str,
        stage: str,
        task_state: str,
        storage_label: str,
        authorization_id: str = "",
        execution_id: str = "",
        execution_state: str = "",
        output: str = "",
        resource: str = "",
        blocked_reason: str = "",
        suggestion: Suggestion | None = None,
    ) -> TaskWorkflowStageResult:
        audit_records = await self._audit_repository.list(
            task_id=TaskId(task_id),
            limit=100,
        )
        return TaskWorkflowStageResult(
            project_id=project_id,
            task_id=task_id,
            stage=stage,
            task_state=task_state,
            authorization_id=authorization_id,
            execution_id=execution_id,
            execution_state=execution_state,
            output=output,
            resource=resource,
            blocked_reason=blocked_reason,
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
        )

    async def _resolve_task_stage(
        self,
        *,
        task,
        requested_stage: TaskWorkflowStage | None,
    ) -> tuple:
        if task.state is TaskState.CREATED:
            task = await self._task_service.transition_task(
                TransitionTaskCommand(
                    task_id=task.id,
                    target_state=TaskState.PLANNING,
                    source="application.orchestration.tasks",
                )
            )
        if requested_stage is not None:
            return task, None, requested_stage
        suggestion = await self._suggestion_engine.suggest_next(task)
        if suggestion is None:
            return task, None, None
        return task, suggestion, _task_stage_from_suggestion(suggestion)

    async def _classify_context_paths(
        self,
        *,
        adapter: ProjectAdapter,
        context_paths: tuple[str, ...],
    ) -> tuple:
        levels = []
        for resource in context_paths:
            classified_resource = await adapter.classify_resource(
                await _context_reference_for(adapter, resource)
            )
            levels.append(classified_resource.provider_sharing_level)
        return tuple(levels)

    async def _transition_task_to_blocked(self, task):
        if task.state is TaskState.BLOCKED:
            return task
        if TaskState.BLOCKED in TaskStateMachine.default().available_targets(task.state):
            return await self._task_service.transition_task(
                TransitionTaskCommand(
                    task_id=task.id,
                    target_state=TaskState.BLOCKED,
                    source="application.orchestration.tasks",
                )
            )
        return task

    async def _publish_project_readiness(
        self,
        *,
        project,
        readiness: ProjectReadinessAssessment,
    ) -> None:
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.PROJECT_READINESS_ASSESSED,
                source="application.orchestration",
                project_id=project.id,
                payload={
                    "observed_readiness_level": readiness.readiness_level.value,
                    "effective_readiness_level": project.readiness_level.value,
                    "has_git": str(readiness.has_git),
                    "has_documentation": str(readiness.has_documentation),
                    "has_tests": str(readiness.has_tests),
                },
            )
        )

    async def _publish_project_operation_blocked(
        self,
        *,
        project_id: ProjectId,
        readiness: str,
        provider_target: ProviderTarget,
        reason: str,
    ) -> None:
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.PROJECT_OPERATION_BLOCKED,
                source="application.orchestration",
                project_id=project_id,
                payload={
                    "readiness_level": readiness,
                    "provider_target": provider_target.value,
                    "reason": reason,
                },
            )
        )

    async def _publish_project_operation_completed(
        self,
        *,
        project_id: ProjectId,
        operation: ProjectOperation,
        payload: dict[str, str],
    ) -> None:
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.PROJECT_OPERATION_COMPLETED,
                source="application.orchestration",
                project_id=project_id,
                payload={
                    "project_operation": operation.value,
                    **payload,
                },
            )
        )

    async def _publish_project_operation_failed(
        self,
        *,
        project_id: ProjectId,
        operation: ProjectOperation,
        reason: str,
    ) -> None:
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.PROJECT_OPERATION_FAILED,
                source="application.orchestration",
                project_id=project_id,
                payload={
                    "project_operation": operation.value,
                    "reason": reason,
                },
            )
        )


async def _context_reference_for(
    adapter: ProjectAdapter,
    resource: str,
):
    discovery = await adapter.discover(limit=500)
    for item in discovery.resources:
        if item.resource == resource:
            from orchai.domain.context import ContextReference

            return ContextReference(source=item.source, resource=resource)
    from orchai.domain.context import ContextReference, ContextSource

    return ContextReference(source=ContextSource.SOURCE_FILE, resource=resource)


@dataclass(frozen=True, slots=True)
class _TaskStageWorkflow:
    stage: TaskWorkflowStage
    role: RoleName
    action: ActionName
    start_state: TaskState
    success_state: TaskState
    project_operation: ProjectOperation
    uses_ai: bool = True
    requires_context: bool = True
    documentation_required: bool = False


def _task_stage_workflow(stage: TaskWorkflowStage) -> _TaskStageWorkflow:
    if stage is TaskWorkflowStage.PLAN:
        return _TaskStageWorkflow(
            stage=stage,
            role=RoleName.TASK_PLANNER,
            action=ActionName.PLAN,
            start_state=TaskState.PLANNING,
            success_state=TaskState.PLANNED,
            project_operation=ProjectOperation.READ_CONTEXT,
        )
    if stage is TaskWorkflowStage.IMPLEMENT:
        return _TaskStageWorkflow(
            stage=stage,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            start_state=TaskState.IMPLEMENTING,
            success_state=TaskState.IMPLEMENTED,
            project_operation=ProjectOperation.WRITE_SOURCE,
        )
    if stage is TaskWorkflowStage.REVIEW:
        return _TaskStageWorkflow(
            stage=stage,
            role=RoleName.QUALITY_AGENT,
            action=ActionName.REVIEW,
            start_state=TaskState.REVIEWING,
            success_state=TaskState.REVIEWING,
            project_operation=ProjectOperation.READ_CONTEXT,
        )
    if stage is TaskWorkflowStage.VALIDATE:
        return _TaskStageWorkflow(
            stage=stage,
            role=RoleName.QUALITY_AGENT,
            action=ActionName.VALIDATE,
            start_state=TaskState.VALIDATING,
            success_state=TaskState.VALIDATING,
            project_operation=ProjectOperation.RUN_VALIDATION,
        )
    if stage is TaskWorkflowStage.TEST:
        return _TaskStageWorkflow(
            stage=stage,
            role=RoleName.QUALITY_AGENT,
            action=ActionName.TEST,
            start_state=TaskState.TESTING,
            success_state=TaskState.VALIDATED,
            project_operation=ProjectOperation.RUN_TESTS,
            uses_ai=False,
            requires_context=False,
        )
    return _TaskStageWorkflow(
        stage=stage,
        role=RoleName.DEVELOPER,
        action=ActionName.DOCUMENT,
        start_state=TaskState.VALIDATED,
        success_state=TaskState.COMPLETED,
        project_operation=ProjectOperation.WRITE_DOCUMENTATION,
        documentation_required=True,
    )


def _task_stage_from_suggestion(suggestion: Suggestion) -> TaskWorkflowStage:
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


def _normalized_paths(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value.strip() for value in values if value.strip())


def _execution_failure_reason(execution) -> str:
    if execution.result is None:
        return "execution_failed_without_result"
    if execution.result.errors:
        return "; ".join(execution.result.errors)
    return "execution_failed"


def _operation_workflow(
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


async def _run_adapter_operation(
    adapter: ProjectAdapter,
    command: RunProjectOperationCommand,
) -> dict[str, str]:
    from orchai.domain.context import ContextReference, ContextSource

    if command.operation is ProjectOperation.WRITE_SOURCE:
        result = await adapter.write(
            ContextReference(source=ContextSource.SOURCE_FILE, resource=command.resource),
            command.content,
        )
        return {
            "resource": result.resource,
            "bytes_written": str(result.bytes_written),
            "output": f"wrote {result.bytes_written} byte(s)",
        }
    if command.operation is ProjectOperation.WRITE_DOCUMENTATION:
        result = await adapter.write_documentation(
            ContextReference(
                source=ContextSource.PROJECT_DOCUMENTATION,
                resource=command.resource,
            ),
            command.content,
        )
        return {
            "resource": result.resource,
            "bytes_written": str(result.bytes_written),
            "output": f"wrote {result.bytes_written} byte(s)",
        }
    if command.operation is ProjectOperation.RUN_TESTS:
        result = await adapter.run_tests(args=command.test_args)
        return {
            "command": " ".join(result.command),
            "exit_code": str(result.exit_code),
            "output": result.stdout,
            "stderr": result.stderr,
        }
    if command.operation in {
        ProjectOperation.RUN_VALIDATION,
        ProjectOperation.RUN_COMMAND,
    }:
        result = await adapter.run_command(command.command)
        return {
            "command": " ".join(result.command),
            "exit_code": str(result.exit_code),
            "output": result.stdout,
            "stderr": result.stderr,
        }
    if command.operation is ProjectOperation.GIT_STATUS:
        result = await adapter.git_status()
        return {
            "branch": result.branch,
            "is_dirty": str(result.is_dirty),
            "ahead": str(result.ahead),
            "behind": str(result.behind),
            "output": f"branch={result.branch} dirty={str(result.is_dirty).lower()}",
        }
    raise ValueError(f"unsupported project operation: {command.operation.value}")
