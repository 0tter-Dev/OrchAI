import asyncio
from collections.abc import AsyncIterator

from orchai.application.authorization import (
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.executions import RequestExecutionCommand
from orchai.application.executions.ports import (
    AIProviderError,
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderPort,
    AIProviderStreamChunk,
    AIProviderValidationError,
)
from orchai.application.orchestration import RunLocalFlowCommand
from orchai.application.orchestration.orchestrator import (
    AutomaticExecutionPolicy,
    RunTaskWorkflowStageCommand,
)
from orchai.application.projects import RegisterProjectCommand
from orchai.application.tasks import CreateTaskCommand, TransitionTaskCommand
from orchai.bootstrap import build_in_memory_runtime
from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.capabilities import CapabilityName
from orchai.domain.executions import ExecutionState
from orchai.domain.identifiers import ModelId, TaskId
from orchai.domain.projects import ProjectReadinessLevel, ProjectSecurityProfile
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode, TaskState
from orchai.infrastructure.projects import LocalFilesystemProjectAdapter


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


async def _authorized_execution(runtime, tmp_path):
    """Build one execution through to AUTHORIZED, ready for run()/cancel()."""

    project = await runtime.project_service.register_project(
        RegisterProjectCommand(
            name="Cancel target",
            root_location=str(tmp_path),
            capabilities=(CapabilityName.READ_PROJECT,),
            readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
            security_profile=ProjectSecurityProfile(
                readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
                access_scope=("READ_PROJECT",),
            ),
        )
    )
    await runtime.project_adapters.register(
        project.id, LocalFilesystemProjectAdapter(tmp_path)
    )
    task = await runtime.task_service.create_task(
        CreateTaskCommand(
            title="Cancel target task",
            description="Verify execution cancellation.",
            requested_change="N/A.",
            project_id=project.id,
            execution_mode=ExecutionMode.SUGGESTED,
        )
    )
    task = await runtime.task_service.transition_task(
        TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNING)
    )
    authorization = await runtime.authorization_service.request_authorization(
        RequestAuthorizationCommand(
            task_id=task.id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=ModelId("fake-model"),
            context_scope=(),
            reason="Cancellation test.",
            requester="test",
            execution_mode=ExecutionMode.SUGGESTED,
        )
    )
    authorization = await runtime.authorization_service.decide_authorization(
        DecideAuthorizationCommand(
            authorization_id=authorization.id,
            status=AuthorizationDecisionStatus.GRANTED,
            decided_by="test",
            reason="Approved.",
        )
    )
    return await runtime.execution_service.request_execution(
        RequestExecutionCommand(
            task_id=task.id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=ModelId("fake-model"),
            authorization_id=authorization.id,
            project_id=project.id,
            requested_context=(),
            authorized_context=(),
        )
    )


def test_execution_engine_cancel_stops_a_dispatched_in_flight_execution(tmp_path) -> None:
    """`.dispatch()` (used by `POST /executions/{id}/dispatch`, unlike the
    orchestrator's own synchronous `.run()` call) tracks a real
    `asyncio.Task` -- cancelling it must interrupt the provider call in
    flight and still leave the execution in a terminal, persisted CANCELLED
    state (not stuck RUNNING), since `asyncio.CancelledError` bypasses
    `run()`'s own `except Exception` handler.
    """

    async def run() -> None:
        provider = SlowProvider()
        runtime = build_in_memory_runtime(ai_provider=provider)
        execution = await _authorized_execution(runtime, tmp_path)

        dispatched_task = runtime.execution_engine.dispatch(execution.id)
        await asyncio.wait_for(provider.started.wait(), timeout=1)
        assert runtime.execution_engine.is_active(execution.id) is True

        cancelled = await runtime.execution_engine.cancel(execution.id)

        assert cancelled.state is ExecutionState.CANCELLED
        # The dispatched asyncio.Task itself ends in the cancelled state
        # (CancelledError propagates out of run() uncaught) once the event
        # loop actually gets to process the cancellation -- the repository
        # writes above never truly suspend, so nothing forces that to
        # happen until we explicitly await the task here.
        try:
            await asyncio.wait_for(dispatched_task, timeout=1)
        except asyncio.CancelledError:
            pass
        assert dispatched_task.cancelled()
        persisted = await runtime.execution_service.get_execution(execution.id)
        assert persisted.state is ExecutionState.CANCELLED

    asyncio.run(run())


def test_execution_engine_cancel_transitions_a_non_dispatched_execution(tmp_path) -> None:
    """An execution that was never `.dispatch()`-ed (e.g. still AUTHORIZED,
    no tracked asyncio.Task) has no live task to interrupt, but cancel()
    must still transition it to CANCELLED directly."""

    async def run() -> None:
        runtime = build_in_memory_runtime(ai_provider=RecordingProvider())
        execution = await _authorized_execution(runtime, tmp_path)
        assert runtime.execution_engine.is_active(execution.id) is False

        cancelled = await runtime.execution_engine.cancel(execution.id)

        assert cancelled.state is ExecutionState.CANCELLED

    asyncio.run(run())


def test_execution_engine_cancel_is_idempotent_once_terminal(tmp_path) -> None:
    """Cancelling an already-terminal execution (e.g. a second cancel call)
    must not raise -- it is treated as a no-op, returning the execution as
    it stands rather than propagating InvalidExecutionStateTransitionError.
    """

    async def run() -> None:
        runtime = build_in_memory_runtime(ai_provider=RecordingProvider())
        execution = await _authorized_execution(runtime, tmp_path)
        first_cancel = await runtime.execution_engine.cancel(execution.id)
        assert first_cancel.state is ExecutionState.CANCELLED

        second_cancel = await runtime.execution_engine.cancel(execution.id)

        assert second_cancel.state is ExecutionState.CANCELLED

    asyncio.run(run())


def test_execution_engine_cancel_swallows_a_provider_cancel_error(tmp_path) -> None:
    """A provider's best-effort `.cancel()` failing (e.g. LiteLLM's earlier
    behavior of raising) must never block the authoritative state
    transition to CANCELLED."""

    async def run() -> None:
        runtime = build_in_memory_runtime(ai_provider=CancelRaisingProvider())
        execution = await _authorized_execution(runtime, tmp_path)

        cancelled = await runtime.execution_engine.cancel(execution.id)

        assert cancelled.state is ExecutionState.CANCELLED

    asyncio.run(run())


def test_execution_engine_run_stream_accumulates_deltas_into_one_completed_execution(
    tmp_path,
) -> None:
    """`run_stream()` must yield every provider chunk as it arrives, then
    reassemble the accumulated deltas into the same terminal
    `Execution` shape `run()` produces -- exactly one COMPLETED state,
    not a partial or duplicated one.
    """

    async def run() -> None:
        provider = StreamingProvider(("Hel", "lo", ", ", "world."))
        runtime = build_in_memory_runtime(ai_provider=provider)
        execution = await _authorized_execution(runtime, tmp_path)

        chunks = [chunk async for chunk in runtime.execution_engine.run_stream(execution.id)]

        assert [chunk.delta for chunk in chunks] == ["Hel", "lo", ", ", "world.", ""]
        assert chunks[-1].finished is True
        persisted = await runtime.execution_service.get_execution(execution.id)
        assert persisted.state is ExecutionState.COMPLETED
        assert persisted.result is not None
        assert persisted.result.output == "Hello, world."
        assert persisted.result.resource_usage.input_tokens == 4
        assert persisted.result.resource_usage.output_tokens == 6

    asyncio.run(run())


def test_execution_engine_run_stream_fails_the_execution_on_a_mid_stream_error(
    tmp_path,
) -> None:
    """A provider error raised partway through the stream must still land
    on exactly one terminal `Execution` state (FAILED), same as a
    non-streaming provider failure in `run()`."""

    async def run() -> None:
        provider = MidStreamFailingProvider(("partial",))
        runtime = build_in_memory_runtime(ai_provider=provider)
        execution = await _authorized_execution(runtime, tmp_path)

        chunks = [chunk async for chunk in runtime.execution_engine.run_stream(execution.id)]

        assert [chunk.delta for chunk in chunks] == ["partial"]
        persisted = await runtime.execution_service.get_execution(execution.id)
        assert persisted.state is ExecutionState.FAILED
        assert persisted.result is not None
        assert persisted.result.errors == ("provider stream disconnected",)

    asyncio.run(run())


class SlowProvider(AIProviderPort):
    """Never completes on its own -- only cancellation ends it."""

    def __init__(self) -> None:
        self.started = asyncio.Event()

    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        return None

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        self.started.set()
        await asyncio.sleep(3600)
        raise AssertionError("should have been cancelled before this point")

    async def cancel(self, execution_id) -> None:
        return None


class CancelRaisingProvider(AIProviderPort):
    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        return None

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        raise AssertionError("execute should not be called in this test")

    async def cancel(self, execution_id) -> None:
        raise AIProviderError("provider does not support cancellation")


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


class StreamingProvider(AIProviderPort):
    """Yields deltas then a token-carrying finished chunk, mirroring how
    `LiteLLMProvider.execute_stream()` reports usage on a chunk separate
    from the one that sets `finished=True`."""

    def __init__(self, deltas: tuple[str, ...]) -> None:
        self._deltas = deltas

    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "execute_stream", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        return None

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        raise AssertionError("run_stream should call execute_stream, not execute")

    async def execute_stream(
        self, request: AIProviderExecutionRequest
    ) -> AsyncIterator[AIProviderStreamChunk]:
        for delta in self._deltas:
            yield AIProviderStreamChunk(delta=delta, provider_name="streaming-fake")
        yield AIProviderStreamChunk(
            delta="",
            finished=True,
            provider_name="streaming-fake",
            finish_reason="stop",
            input_tokens=4,
            output_tokens=6,
        )

    async def cancel(self, execution_id) -> None:
        return None


class MidStreamFailingProvider(AIProviderPort):
    """Yields a few deltas, then raises AIProviderError mid-stream."""

    def __init__(self, deltas: tuple[str, ...]) -> None:
        self._deltas = deltas

    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "execute_stream", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        return None

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        raise AssertionError("run_stream should call execute_stream, not execute")

    async def execute_stream(
        self, request: AIProviderExecutionRequest
    ) -> AsyncIterator[AIProviderStreamChunk]:
        for delta in self._deltas:
            yield AIProviderStreamChunk(delta=delta, provider_name="streaming-fake")
        raise AIProviderError("provider stream disconnected")

    async def cancel(self, execution_id) -> None:
        return None
