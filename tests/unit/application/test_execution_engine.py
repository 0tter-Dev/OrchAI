import asyncio

from orchai.application.executions.ports import (
    AIProviderError,
    AIProviderExecutionRequest,
    AIProviderExecutionResult,
    AIProviderPort,
)
from orchai.application.orchestration import RunLocalFlowCommand
from orchai.application.orchestration.orchestrator import AutomaticExecutionPolicy
from orchai.bootstrap import build_in_memory_runtime
from orchai.domain.identifiers import TaskId
from orchai.domain.tasks import ExecutionMode


def test_execution_engine_invokes_provider_after_authorization(tmp_path) -> None:
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
                title="Engine success",
                model="fake-model",
                storage_label="memory",
                approve_suggestion=True,
            )
        )

        assert result.task_state == "IMPLEMENTED"
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

        assert result.task_state == "IMPLEMENTING"
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

        assert result.task_state == "PLANNED"
        assert result.execution_state == ""
        assert result.suggestion_status == "PRESENTED"
        assert result.blocked_reason == "suggested_mode_requires_approval"
        assert provider.request is None

    asyncio.run(run())


def test_orchestrator_automatic_mode_uses_configured_limits(tmp_path) -> None:
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
                title="Automatic allowed",
                model="fake-model",
                storage_label="memory",
                execution_mode=ExecutionMode.AUTOMATIC,
            )
        )

        assert result.task_state == "IMPLEMENTED"
        assert result.execution_state == "COMPLETED"
        assert result.suggestion_status == "ACCEPTED"
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

        assert result.task_state == "PLANNED"
        assert result.execution_state == ""
        assert result.suggestion_status == "PRESENTED"
        assert result.blocked_reason == "automatic_policy_denied"
        assert provider.request is None

    asyncio.run(run())


class RecordingProvider(AIProviderPort):
    def __init__(self) -> None:
        self.request: AIProviderExecutionRequest | None = None

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


class FailingProvider(AIProviderPort):
    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        raise AIProviderError("provider unavailable")
