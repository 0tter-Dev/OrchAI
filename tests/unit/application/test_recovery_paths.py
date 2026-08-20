import asyncio

from orchai.application.executions.ports import AIProviderExecutionRequest, AIProviderExecutionResult, AIProviderPort
from orchai.application.orchestration import RunLocalFlowCommand
from orchai.bootstrap import build_in_memory_runtime


def test_context_resolution_failure_keeps_task_traceable(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / ".git").mkdir()
        runtime = build_in_memory_runtime(ai_provider=UnexpectedProvider())
        result = await runtime.orchestrator.run_local_flow(
            RunLocalFlowCommand(
                project_root=tmp_path,
                context_path="missing.md",
                title="Missing context",
                model="fake-model",
                storage_label="memory",
                approve_suggestion=True,
            )
        )

        assert result.task_state == "IMPLEMENTING"
        assert result.execution_state == "FAILED"
        audit_records = await runtime.audit_repository.list(limit=100)
        assert any(record.operation == "EXECUTION_FAILED" for record in audit_records)

    asyncio.run(run())


class UnexpectedProvider(AIProviderPort):
    async def capabilities(self) -> frozenset[str]:
        return frozenset({"execute", "validate_request"})

    async def validate_request(self, request: AIProviderExecutionRequest) -> None:
        return None

    async def execute(
        self,
        request: AIProviderExecutionRequest,
    ) -> AIProviderExecutionResult:
        raise AssertionError("provider should not run when context resolution fails")

    async def cancel(self, execution_id) -> None:
        return None
