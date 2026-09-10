"""Central application orchestrator."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from orchai.application.audit import AuditRepository
from orchai.application.authorization import AuthorizationService
from orchai.application.events.ports import EventPublisher
from orchai.application.executions import (
    ExecutionService,
    RequestExecutionCommand,
)
from orchai.application.executions.engine import ExecutionEngine
from orchai.application.orchestration.connections import (
    connect_project,
    connect_registered_project,
    run_adapter_operation,
)
from orchai.application.orchestration.events import (
    publish_project_operation_blocked,
    publish_project_operation_completed,
    publish_project_operation_failed,
)
from orchai.application.orchestration.gating import evaluate_and_authorize
from orchai.application.orchestration.ports import (
    ProjectAdapterFactory,
    PublishedEventHistory,
)
from orchai.application.orchestration.results import (
    audit_and_event_counts,
    dataclass_as_str_dict,
    suggestion_fields,
)
from orchai.application.orchestration.stages import (
    TaskStageWorkflow,
    TaskWorkflowStage,
    operation_workflow,
    resolve_task_stage,
    task_stage_workflow,
)
from orchai.application.policies import (
    AutomaticExecutionPolicy,
    LocalPolicyService,
    PolicyOperation,
    PolicyPort,
)
from orchai.application.projects import ProjectService
from orchai.application.projects.ports import (
    ProjectAdapter,
    ProjectAdapterRegistry,
)
from orchai.application.suggestions import SuggestionEngine
from orchai.application.tasks import CreateTaskCommand, TaskService, TransitionTaskCommand
from orchai.domain.actions import ActionName
from orchai.domain.authorization import Authorization
from orchai.domain.identifiers import ModelId, TaskId
from orchai.domain.projects import Project, ProjectOperation, ProviderTarget
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion
from orchai.domain.tasks import ExecutionMode, Task, TaskState, TaskStateMachine
from orchai.infrastructure.projects.errors import ProjectAdapterError

__all__ = [
    "OrchestrationFlowResult",
    "OrchestrationStreamEvent",
    "Orchestrator",
    "ProjectAdapterFactory",
    "ProjectOperationResult",
    "PublishedEventHistory",
    "RunLocalFlowCommand",
    "RunProjectOperationCommand",
    "RunTaskWorkflowStageCommand",
    "TaskWorkflowStage",
    "TaskWorkflowStageResult",
]


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
        return dataclass_as_str_dict(self)


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
        return dataclass_as_str_dict(self)


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
        return dataclass_as_str_dict(self)


@dataclass(frozen=True, slots=True)
class OrchestrationStreamEvent:
    """One incremental event from `run_task_workflow_stage_stream()`.

    Mirrors `AIProviderStreamChunk`/`ConversationStreamEvent`'s
    delta-then-done shape one layer up: `type="delta"` carries one
    incremental chunk of AI provider output (only emitted for a stage
    where `TaskStageWorkflow.uses_ai` is true); the stream always ends
    with exactly one `type="done"` event carrying the same
    `TaskWorkflowStageResult` `run_task_workflow_stage()` would have
    returned for an equivalent non-streaming call -- a stage that never
    reaches AI execution (blocked, no suggestion, or the non-AI TEST
    stage) emits only that single `done` event.
    """

    type: str
    delta: str = ""
    finished: bool = False
    result: TaskWorkflowStageResult | None = None


@dataclass(slots=True)
class _PreparedWorkflowStage:
    """Shared setup result for one workflow-stage advance attempt.

    Produced by `Orchestrator._prepare_workflow_stage()` and consumed by
    both `run_task_workflow_stage()` and its streaming counterpart --
    everything through policy/authorization and the stage's
    `start_state` transition is identical regardless of whether the
    stage's own AI execution (if any) streams or not.
    """

    task: Task
    project: Project
    adapter: ProjectAdapter
    stage: TaskWorkflowStage
    workflow: TaskStageWorkflow
    context_paths: tuple[str, ...]
    authorization: Authorization
    suggestion: Suggestion | None


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

        adapter, _readiness, project = await connect_project(
            create_project_adapter=self._create_project_adapter,
            project_service=self._project_service,
            event_publisher=self._event_publisher,
            project_root=command.project_root,
        )
        await self._project_adapters.register(project.id, adapter)

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

        adapter, readiness, project = await connect_project(
            create_project_adapter=self._create_project_adapter,
            project_service=self._project_service,
            event_publisher=self._event_publisher,
            project_root=command.project_root,
        )
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
            await publish_project_operation_blocked(
                event_publisher=self._event_publisher,
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

        role, action, start_state, success_state = operation_workflow(
            command.operation
        )
        gate = await evaluate_and_authorize(
            policy_service=active_policy,
            authorization_service=self._authorization_service,
            suggestion_engine=None,
            suggestion=None,
            operation=PolicyOperation(
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
            ),
            task_id=task.id,
            role=role,
            action=action,
            model_id=ModelId(command.model),
            context_scope=(command.resource,) if command.resource else (),
            reason="User requested protected project operation.",
            requester="cli",
            decider="cli",
            decision_reason="Explicit project operation approval.",
        )
        if not gate.policy_decision.allowed:
            await publish_project_operation_blocked(
                event_publisher=self._event_publisher,
                project_id=project.id,
                readiness=project.readiness_level.value,
                provider_target=command.provider_target,
                reason=gate.policy_decision.reason,
            )
            return await self._project_operation_result(
                project=project,
                task_id=str(task.id),
                authorization_id="",
                task_state=task.state.value,
                operation=command.operation,
                storage_label=command.storage_label,
                blocked_reason=gate.policy_decision.reason,
                suggestion=plan_suggestion,
            )

        authorization = gate.authorization
        task = await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=start_state)
        )

        try:
            operation_result = await run_adapter_operation(adapter, command)
        except ProjectAdapterError as exc:
            task = await self._task_service.transition_task(
                TransitionTaskCommand(task_id=task.id, target_state=TaskState.FAILED)
            )
            await publish_project_operation_failed(
                event_publisher=self._event_publisher,
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
        await publish_project_operation_completed(
            event_publisher=self._event_publisher,
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
        gate = await evaluate_and_authorize(
            policy_service=active_policy,
            authorization_service=self._authorization_service,
            suggestion_engine=self._suggestion_engine,
            suggestion=suggestion,
            operation=PolicyOperation(
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
            ),
            task_id=task.id,
            role=role,
            action=action,
            model_id=None,
            context_scope=requested_context,
            reason="Bootstrap PLAN stage before a protected project operation.",
            requester="cli",
            decider="cli",
            decision_reason="Explicit project operation approval.",
        )
        if not gate.policy_decision.allowed:
            return task, gate.suggestion, gate.policy_decision.reason

        task = await self._task_service.transition_task(
            TransitionTaskCommand(
                task_id=task.id,
                target_state=TaskState.PLANNED,
                source="application.orchestration.tasks",
            )
        )
        return task, gate.suggestion, None

    async def run_task_workflow_stage(
        self,
        command: RunTaskWorkflowStageCommand,
    ) -> TaskWorkflowStageResult:
        """Advance one persisted task through one workflow stage."""

        prepared = await self._prepare_workflow_stage(command)
        if isinstance(prepared, TaskWorkflowStageResult):
            return prepared

        if not prepared.workflow.uses_ai:
            return await self._finalize_test_stage_result(prepared=prepared, command=command)

        execution = await self._execution_service.request_execution(
            RequestExecutionCommand(
                task_id=prepared.task.id,
                role=prepared.workflow.role,
                action=prepared.workflow.action,
                model_id=ModelId(command.model),
                authorization_id=prepared.authorization.id,
                project_id=prepared.project.id,
                requested_context=prepared.context_paths,
                authorized_context=prepared.context_paths,
            )
        )
        execution = await self._execution_engine.run(execution.id)
        return await self._finalize_ai_stage_result(
            execution=execution, prepared=prepared, command=command
        )

    async def run_task_workflow_stage_stream(
        self,
        command: RunTaskWorkflowStageCommand,
    ) -> AsyncIterator[OrchestrationStreamEvent]:
        """Streaming counterpart of :meth:`run_task_workflow_stage`.

        Shares the exact same setup, gating, and result-finalization
        logic (`_prepare_workflow_stage`, `_finalize_ai_stage_result`,
        `_finalize_test_stage_result`) -- the only difference is that an
        AI-driven stage's execution is run through
        `ExecutionEngine.run_stream()` instead of `run()`, with each
        `AIProviderStreamChunk`'s delta forwarded onward as a `delta`
        event. A stage that never reaches AI execution (blocked, no
        suggestion, or the non-AI TEST stage) yields exactly one `done`
        event and nothing else, identical in substance to what
        `run_task_workflow_stage()` would have returned.
        """

        prepared = await self._prepare_workflow_stage(command)
        if isinstance(prepared, TaskWorkflowStageResult):
            yield OrchestrationStreamEvent(type="done", result=prepared)
            return

        if not prepared.workflow.uses_ai:
            result = await self._finalize_test_stage_result(prepared=prepared, command=command)
            yield OrchestrationStreamEvent(type="done", result=result)
            return

        execution = await self._execution_service.request_execution(
            RequestExecutionCommand(
                task_id=prepared.task.id,
                role=prepared.workflow.role,
                action=prepared.workflow.action,
                model_id=ModelId(command.model),
                authorization_id=prepared.authorization.id,
                project_id=prepared.project.id,
                requested_context=prepared.context_paths,
                authorized_context=prepared.context_paths,
            )
        )
        async for chunk in self._execution_engine.run_stream(execution.id):
            yield OrchestrationStreamEvent(type="delta", delta=chunk.delta, finished=chunk.finished)
        execution = await self._execution_service.get_execution(execution.id)
        result = await self._finalize_ai_stage_result(
            execution=execution, prepared=prepared, command=command
        )
        yield OrchestrationStreamEvent(type="done", result=result)

    async def _prepare_workflow_stage(
        self,
        command: RunTaskWorkflowStageCommand,
    ) -> _PreparedWorkflowStage | TaskWorkflowStageResult:
        """Shared setup for one workflow-stage advance attempt.

        Returns a `TaskWorkflowStageResult` directly for every early-exit
        case (no project, no suggestion, missing context/documentation
        path, policy denial) -- the caller (`run_task_workflow_stage()`
        or its streaming counterpart) returns/yields it as-is, since
        nothing runs in those cases regardless of streaming. Otherwise
        returns a `_PreparedWorkflowStage` ready for the stage's own
        AI or test execution.
        """

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

        adapter, project = await connect_registered_project(
            create_project_adapter=self._create_project_adapter,
            project_service=self._project_service,
            project_adapters=self._project_adapters,
            event_publisher=self._event_publisher,
            project_id=task.project_id,
        )
        effective_mode = command.execution_mode or task.execution_mode
        task, suggestion, stage = await resolve_task_stage(
            task_service=self._task_service,
            suggestion_engine=self._suggestion_engine,
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

        workflow = task_stage_workflow(stage)
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
        gate = await evaluate_and_authorize(
            policy_service=active_policy,
            authorization_service=self._authorization_service,
            suggestion_engine=self._suggestion_engine,
            suggestion=suggestion,
            operation=PolicyOperation(
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
            ),
            task_id=task.id,
            role=workflow.role,
            action=workflow.action,
            model_id=ModelId(command.model) if workflow.uses_ai else None,
            context_scope=context_paths,
            reason=f"Advance task through {stage.value} stage.",
            requester=command.requester,
            decider=command.decider,
            decision_reason=f"Approved task workflow stage {stage.value}.",
        )
        suggestion = gate.suggestion
        if not gate.policy_decision.allowed:
            await publish_project_operation_blocked(
                event_publisher=self._event_publisher,
                project_id=project.id,
                readiness=project.readiness_level.value,
                provider_target=command.provider_target,
                reason=gate.policy_decision.reason,
            )
            return await self._task_workflow_stage_result(
                task_id=str(task.id),
                project_id=str(project.id),
                stage=stage.value,
                task_state=task.state.value,
                storage_label=command.storage_label,
                suggestion=suggestion,
                blocked_reason=gate.policy_decision.reason,
            )

        authorization = gate.authorization

        if task.state is not workflow.start_state:
            task = await self._task_service.transition_task(
                TransitionTaskCommand(
                    task_id=task.id,
                    target_state=workflow.start_state,
                    source="application.orchestration.tasks",
                )
            )

        return _PreparedWorkflowStage(
            task=task,
            project=project,
            adapter=adapter,
            stage=stage,
            workflow=workflow,
            context_paths=context_paths,
            authorization=authorization,
            suggestion=suggestion,
        )

    async def _finalize_ai_stage_result(
        self,
        *,
        execution,
        prepared: _PreparedWorkflowStage,
        command: RunTaskWorkflowStageCommand,
    ) -> TaskWorkflowStageResult:
        """Turn one terminal AI-driven `Execution` into the stage result.

        Shared tail of the `uses_ai` branch for both
        `run_task_workflow_stage()` (passed `run()`'s result) and
        `run_task_workflow_stage_stream()` (passed `run_stream()`'s
        reassembled terminal `Execution`, re-fetched after the stream
        ends) -- identical handling either way, so completion/blocked
        transitions and documentation writing need no branching by
        streamed-vs-not.
        """

        task, project, stage, workflow, authorization, suggestion = (
            prepared.task,
            prepared.project,
            prepared.stage,
            prepared.workflow,
            prepared.authorization,
            prepared.suggestion,
        )
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
                    prepared.adapter,
                    command.documentation_path,
                )
                write_result = await prepared.adapter.write_documentation(
                    documentation_reference,
                    output,
                )
                resource = write_result.resource
                await publish_project_operation_completed(
                    event_publisher=self._event_publisher,
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

    async def _finalize_test_stage_result(
        self,
        *,
        prepared: _PreparedWorkflowStage,
        command: RunTaskWorkflowStageCommand,
    ) -> TaskWorkflowStageResult:
        """Run and finalize the non-AI TEST stage (never streamed)."""

        task, project, stage, workflow, authorization, suggestion, adapter = (
            prepared.task,
            prepared.project,
            prepared.stage,
            prepared.workflow,
            prepared.authorization,
            prepared.suggestion,
            prepared.adapter,
        )
        try:
            command_result = await adapter.run_tests(args=command.test_args)
        except ProjectAdapterError as exc:
            task = await self._transition_task_to_blocked(task)
            await publish_project_operation_failed(
                event_publisher=self._event_publisher,
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
            await publish_project_operation_failed(
                event_publisher=self._event_publisher,
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
        await publish_project_operation_completed(
            event_publisher=self._event_publisher,
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
        counts = await audit_and_event_counts(
            audit_repository=self._audit_repository,
            event_history=self._event_history,
            task_id=TaskId(task_id),
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
            events=counts["events"],
            audit_records=counts["audit_records"],
            database=storage_label,
            **suggestion_fields(suggestion),
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
        counts = await audit_and_event_counts(
            audit_repository=self._audit_repository,
            event_history=self._event_history,
            task_id=TaskId(task_id),
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
            events=counts["events"],
            audit_records=counts["audit_records"],
            database=storage_label,
            **suggestion_fields(suggestion),
        )

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


def _normalized_paths(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value.strip() for value in values if value.strip())


def _execution_failure_reason(execution) -> str:
    if execution.result is None:
        return "execution_failed_without_result"
    if execution.result.errors:
        return "; ".join(execution.result.errors)
    return "execution_failed"
