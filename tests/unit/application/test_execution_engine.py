import asyncio

from orchai.application.executions.ports import (
    AIProviderError,
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderPort,
    AIProviderValidationError,
)
from orchai.application.orchestration import RunLocalFlowCommand
from orchai.application.orchestration.orchestrator import (
    AutomaticExecutionPolicy,
    RunTaskWorkflowStageCommand,
)
from orchai.bootstrap import build_in_memory_runtime
from orchai.domain.actions import ActionName
from orchai.domain.identifiers import TaskId
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode


def test_execution_engine_invokes_provider_after_authorization(tmp_path) -> None:
    """run_local_flow advances exactly one gated stage (PLAN, the first one
    for a freshly created task) — it does not jump ahead to IMPLEMENTED in a
    single call. See test_local_flow_stops_at_planned_pending_the_next_gated_stage
    in tests/integration/test_local_flow.py for the full two-call sequence.
    """

    async def run() -> None:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Context", encoding="utf-8")
        provider = RecordingProvider()
        runtime = build_in_memory_runtime(ai_provider=provider)

        result = await runtime.orchestrator.run_local_flow(
            RunLocalFlowCommand(
                project_root=tmp_path,
                context_path="docs/INDEX.md",
                title="Engine success",
                model="fake-model",
                storage_label="memory",
                approve_suggestion=True,
            )
        )

        assert result.task_state == "PLANNED"
        assert result.execution_state == "COMPLETED"
        assert result.suggestion_status == "ACCEPTED"
        assert provider.request is not None
        assert str(provider.request.model_id) == "fake-model"
        assert provider.request.context[0].resource == "docs/INDEX.md"
        metrics = await runtime.metrics_repository.list(
            task_id=TaskId(result.task_id),
            limit=100,
        )
        assert {metric.name for metric in metrics} >= {
            "execution.success",
            "execution.duration",
            "execution.input_tokens",
            "execution.output_tokens",
            "execution.total_tokens",
        }

    asyncio.run(run())


def test_execution_engine_maps_provider_error_to_failed_execution(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Context", encoding="utf-8")
        runtime = build_in_memory_runtime(ai_provider=FailingProvider())

        result = await runtime.orchestrator.run_local_flow(
            RunLocalFlowCommand(
                project_root=tmp_path,
                context_path="docs/INDEX.md",
                title="Engine failure",
                model="fake-model",
                storage_label="memory",
                approve_suggestion=True,
            )
        )

        # A failed execution during the (now gated) PLAN stage transitions the
        # task to BLOCKED via run_task_workflow_stage's failure handling,
        # rather than leaving it stuck mid-transition.
        assert result.task_state == "BLOCKED"
        assert result.execution_state == "FAILED"
        metrics = await runtime.metrics_repository.list(
            task_id=TaskId(result.task_id),
            limit=100,
        )
        assert {metric.name for metric in metrics} >= {
            "execution.failure",
            "execution.duration",
        }

    asyncio.run(run())


def test_orchestrator_suggested_mode_requires_approval(tmp_path) -> None:
    async def run() -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Context", encoding="utf-8")
        provider = RecordingProvider()
        runtime = build_in_memory_runtime(ai_provider=provider)

        result = await runtime.orchestrator.run_local_flow(
            RunLocalFlowCommand(
                project_root=tmp_path,
                context_path="docs/INDEX.md",
                title="Suggested block",
                model="fake-model",
                storage_label="memory",
            )
        )

        # Without .git, _resolve_task_stage still moves CREATED -> PLANNING
        # (pure bookkeeping so the suggestion engine can run), but PLAN itself
        # is blocked pending approval, so the task never reaches PLANNED.
        assert result.task_state == "PLANNING"
        assert result.execution_state == ""
        assert result.suggestion_status == "PRESENTED"
        assert result.blocked_reason == "suggested_mode_requires_approval"
        assert provider.request is None

    asyncio.run(run())


def test_orchestrator_automatic_mode_uses_configured_limits(tmp_path) -> None:
    """AUTOMATIC mode never skips a stage "for free" — PLAN is gated exactly
    like every other stage, and only proceeds without a human decision when
    (TASK_PLANNER, PLAN) is explicitly present in
    AutomaticExecutionPolicy.allowed_operations. The default policy only
    allows (DEVELOPER, IMPLEMENT), so it denies PLAN until configured.
    """

    async def run() -> None:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Context", encoding="utf-8")
        provider = RecordingProvider()
        runtime = build_in_memory_runtime(ai_provider=provider)

        default_policy_result = await runtime.orchestrator.run_local_flow(
            RunLocalFlowCommand(
                project_root=tmp_path,
                context_path="docs/INDEX.md",
                title="Automatic without configuration",
                model="fake-model",
                storage_label="memory",
                execution_mode=ExecutionMode.AUTOMATIC,
            )
        )
        assert default_policy_result.task_state == "PLANNING"
        assert default_policy_result.blocked_reason == "automatic_policy_denied"
        assert provider.request is None

        configured_policy_result = await runtime.orchestrator.run_local_flow(
            RunLocalFlowCommand(
                project_root=tmp_path,
                context_path="docs/INDEX.md",
                title="Automatic with PLAN explicitly configured",
                model="fake-model",
                storage_label="memory",
                execution_mode=ExecutionMode.AUTOMATIC,
                automatic_policy=AutomaticExecutionPolicy(
                    allowed_operations=(
                        (RoleName.TASK_PLANNER, ActionName.PLAN),
                        (RoleName.DEVELOPER, ActionName.IMPLEMENT),
                    ),
                ),
            )
        )
        assert configured_policy_result.task_state == "PLANNED"
        assert configured_policy_result.execution_state == "COMPLETED"
        assert configured_policy_result.suggestion_status == "ACCEPTED"
        assert configured_policy_result.blocked_reason == ""
        assert provider.request is not None

    asyncio.run(run())


def test_orchestrator_automatic_mode_blocks_disallowed_operation(tmp_path) -> None:
    async def run() -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Context", encoding="utf-8")
        provider = RecordingProvider()
        runtime = build_in_memory_runtime(ai_provider=provider)

        result = await runtime.orchestrator.run_local_flow(
            RunLocalFlowCommand(
                project_root=tmp_path,
                context_path="docs/INDEX.md",
                title="Automatic denied",
                model="fake-model",
                storage_label="memory",
                execution_mode=ExecutionMode.AUTOMATIC,
                automatic_policy=AutomaticExecutionPolicy(allowed_operations=()),
            )
        )

        # Same shift as the SUGGESTED-mode case above: the block now happens
        # at PLAN itself, so the task never gets past PLANNING.
        assert result.task_state == "PLANNING"
        assert result.execution_state == ""
        assert result.suggestion_status == "PRESENTED"
        assert result.blocked_reason == "automatic_policy_denied"
        assert provider.request is None

    asyncio.run(run())


def test_orchestrator_blocks_source_changes_when_project_has_no_git(tmp_path) -> None:
    """The git-readiness gate applies to source-writing stages (IMPLEMENT),
    not to PLAN (a read-only planning step) — so run_local_flow's single
    gated PLAN stage completes normally even with no .git directory. The
    block only appears once IMPLEMENT is explicitly advanced afterwards,
    mirroring the two-call sequence in
    test_local_flow_stops_at_planned_pending_the_next_gated_stage.
    """

    async def run() -> None:
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Context", encoding="utf-8")
        provider = RecordingProvider()
        runtime = build_in_memory_runtime(ai_provider=provider)

        plan_result = await runtime.orchestrator.run_local_flow(
            RunLocalFlowCommand(
                project_root=tmp_path,
                context_path="docs/INDEX.md",
                title="Readiness denied",
                model="fake-model",
                storage_label="memory",
                approve_suggestion=True,
            )
        )

        assert plan_result.task_state == "PLANNED"
        assert plan_result.execution_state == "COMPLETED"
        assert plan_result.blocked_reason == ""

        implement_result = await runtime.orchestrator.run_task_workflow_stage(
            RunTaskWorkflowStageCommand(
                task_id=TaskId(plan_result.task_id),
                storage_label="memory",
                model="fake-model",
                context_paths=("docs/INDEX.md",),
                approve_stage=True,
            )
        )

        assert implement_result.task_state == "PLANNED"
        assert implement_result.execution_state == ""
        assert implement_result.suggestion_status == "PRESENTED"
        assert implement_result.blocked_reason == "source_write_requires_level_1"
        # The provider was invoked once, for the PLAN stage above — the
        # blocked IMPLEMENT stage never reaches execution at all.
        assert provider.request is not None

    asyncio.run(run())


def test_execution_engine_maps_provider_validation_error_to_failed_execution(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Context", encoding="utf-8")
        runtime = build_in_memory_runtime(ai_provider=ValidationRejectingProvider())

        result = await runtime.orchestrator.run_local_flow(
            RunLocalFlowCommand(
                project_root=tmp_path,
                context_path="docs/INDEX.md",
                title="Engine validation failure",
                model="fake-model",
                storage_label="memory",
                approve_suggestion=True,
            )
        )

        # Same BLOCKED transition on execution failure as the provider-error
        # case above.
        assert result.task_state == "BLOCKED"
        assert result.execution_state == "FAILED"
        metrics = await runtime.metrics_repository.list(
            task_id=TaskId(result.task_id),
            limit=100,
        )
        assert {metric.name for metric in metrics} >= {"execution.failure"}

    asyncio.run(run())


class RecordingProvider(AIProviderPort):
    def __init__(self) -> None:
        self.request: AIProviderExecutionRequest | None = None

    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        return None

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        self.request = request
        return AIProviderExecutionResult(
            output="done",
            provider_name="fake",
            input_tokens=3,
            output_tokens=5,
            metadata={"provider": "fake"},
        )

    async def cancel(self, execution_id) -> None:
        return None


class FailingProvider(AIProviderPort):
    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        return None

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        raise AIProviderError("provider unavailable")

    async def cancel(self, execution_id) -> None:
        return None


class ValidationRejectingProvider(AIProviderPort):
    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        raise AIProviderValidationError("provider validation failed")

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        raise AssertionError("provider should not execute after validation failure")

    async def cancel(self, execution_id) -> None:
        return None
