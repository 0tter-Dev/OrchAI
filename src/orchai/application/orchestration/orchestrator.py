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
from orchai.domain.capabilities import CapabilityName
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.identifiers import ModelId, ProjectId, TaskId
from orchai.domain.projects import Project, ProjectOperation, ProviderTarget
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion, SuggestionStatus
from orchai.domain.tasks import ExecutionMode, TaskState
from orchai.infrastructure.projects.errors import ProjectAdapterError


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
        """Run a minimal authorized task/execution/context flow."""

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
        await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNING)
        )
        task = await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNED)
        )

        suggestion: Suggestion | None = None
        role = RoleName.DEVELOPER
        action = ActionName.IMPLEMENT
        if command.execution_mode is not ExecutionMode.MANUAL:
            suggestion = await self._suggestion_engine.suggest_next(task)
            if suggestion is None:
                return await self._blocked_result(
                    project_id=str(project.id),
                    task_id=str(task.id),
                    task_state=task.state.value,
                    storage_label=command.storage_label,
                    blocked_reason="no_suggestion_available",
                )
            role = suggestion.suggested_role
            action = suggestion.suggested_action

        classified_resource = await adapter.classify_resource(
            await _context_reference_for(adapter, command.context_path)
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
                execution_mode=command.execution_mode,
                project_operation=ProjectOperation.WRITE_SOURCE,
                provider_target=command.provider_target,
                project_readiness_level=project.readiness_level,
                project_security_profile=project.security_profile,
                context_sharing_levels=(classified_resource.provider_sharing_level,),
                role=role,
                action=action,
                requested_model=command.model,
                effective_model=command.model,
                requested_context=(command.context_path,),
                authorized_context=(command.context_path,),
                current_task_state=task.state,
                approve_suggestion=command.approve_suggestion,
                explicit_user_command=command.execution_mode is ExecutionMode.MANUAL,
            )
        )
        if suggestion is not None:
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
            await self._publish_project_operation_blocked(
                project_id=project.id,
                readiness=project.readiness_level.value,
                provider_target=command.provider_target,
                reason=policy_decision.reason,
            )
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
                role=role,
                action=action,
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
                role=role,
                action=action,
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
            suggestion_id=str(suggestion.id) if suggestion is not None else "",
            suggested_role=suggestion.suggested_role.value
            if suggestion is not None
            else "",
            suggested_action=suggestion.suggested_action.value
            if suggestion is not None
            else "",
            suggestion_status=suggestion.status.value if suggestion is not None else "",
        )

    async def run_project_operation(
        self,
        command: RunProjectOperationCommand,
    ) -> ProjectOperationResult:
        """Run a protected project-adapter operation through policy and authorization."""

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
        await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNING)
        )
        task = await self._task_service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNED)
        )

        context_sharing_levels = ()
        if command.resource:
            classified_resource = await adapter.classify_resource(
                await _context_reference_for(adapter, command.resource)
            )
            context_sharing_levels = (classified_resource.provider_sharing_level,)

        role, action, start_state, success_state = _operation_workflow(
            command.operation
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
        )

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
