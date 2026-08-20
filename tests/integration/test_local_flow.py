import asyncio

from orchai.application.orchestration import run_local_flow
from orchai.bootstrap import (
    build_sqlalchemy_local_flow_dependencies,
    build_sqlalchemy_runtime,
)
from orchai.domain.identifiers import ExecutionId, TaskId
from orchai.domain.suggestions import SuggestionStatus
from orchai.infrastructure.persistence import SQLAlchemyProjectRepository


def test_local_flow_runs_task_authorization_execution_and_context(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / ".git").mkdir()
        docs = tmp_path / "docs"
        docs.mkdir()
        (docs / "INDEX.md").write_text("# Project\n\nUseful context.", encoding="utf-8")

        result = await run_local_flow(
            project_root=tmp_path,
            context_path="docs/INDEX.md",
            title="Integration flow",
            model="local-demo",
            dependencies=build_sqlalchemy_local_flow_dependencies(
                f"sqlite:///{tmp_path / 'orchai.db'}"
            ),
            storage_label=f"sqlite:///{tmp_path / 'orchai.db'}",
            approve_suggestion=True,
        )

        assert result["task_state"] == "IMPLEMENTED"
        assert result["execution_state"] == "COMPLETED"
        assert result["suggestion_status"] == "ACCEPTED"
        assert result["context_items"] == "1"
        assert result["database"].startswith("sqlite:///")
        assert int(result["events"]) >= 10
        assert int(result["audit_records"]) >= 10

        restarted_runtime = build_sqlalchemy_runtime(
            f"sqlite:///{tmp_path / 'orchai.db'}"
        )
        task_id = TaskId(result["task_id"])
        persisted_events = await restarted_runtime.event_repository.list(
            task_id=task_id,
            limit=100,
        )
        persisted_audit_records = await restarted_runtime.audit_repository.list(
            task_id=task_id,
            limit=100,
        )
        persisted_context_records = (
            await restarted_runtime.context_resolution_repository.list_by_execution(
                ExecutionId(result["execution_id"])
            )
        )
        persisted_metrics = await restarted_runtime.metrics_repository.list(
            task_id=task_id,
            limit=100,
        )
        persisted_suggestions = await restarted_runtime.suggestion_repository.list(
            task_id=task_id,
            limit=100,
        )

        assert len(persisted_events) >= 10
        assert len(persisted_audit_records) >= 10
        assert len(persisted_context_records) == 1
        assert {record.name for record in persisted_metrics} >= {
            "execution.success",
            "execution.duration",
        }
        assert len({record.id for record in persisted_metrics}) == len(persisted_metrics)
        assert persisted_suggestions[0].status is SuggestionStatus.ACCEPTED
        assert persisted_context_records[0].reference.resource == "docs/INDEX.md"
        assert persisted_audit_records[0].task_id == task_id
        assert restarted_runtime.database is not None
        project = await SQLAlchemyProjectRepository(restarted_runtime.database).get(
            result["project_id"]
        )
        assert project.readiness_level.value == "LEVEL_2_VALIDATABLE"
        assert project.security_profile.metadata["has_git"] == "True"

    asyncio.run(run())
