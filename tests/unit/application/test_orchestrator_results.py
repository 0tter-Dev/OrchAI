import asyncio
from datetime import UTC, datetime

from orchai.application.orchestration.orchestrator import (
    OrchestrationFlowResult,
    ProjectOperationResult,
    TaskWorkflowStageResult,
)
from orchai.application.orchestration.results import (
    audit_and_event_counts,
    dataclass_as_str_dict,
    suggestion_fields,
)
from orchai.domain.actions import ActionName
from orchai.domain.audit import AuditRecord
from orchai.domain.identifiers import TaskId
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion, SuggestionStatus
from orchai.infrastructure.persistence import InMemoryAuditRepository


def test_dataclass_as_str_dict_matches_the_previous_hand_written_shape() -> None:
    flow_result = OrchestrationFlowResult(
        project_id="p1",
        task_id="t1",
        authorization_id="a1",
        execution_id="e1",
        task_state="PLANNED",
        execution_state="COMPLETED",
        context_items=1,
        events=3,
        audit_records=5,
        database="sqlite",
    )

    assert dataclass_as_str_dict(flow_result) == {
        "project_id": "p1",
        "task_id": "t1",
        "authorization_id": "a1",
        "execution_id": "e1",
        "task_state": "PLANNED",
        "execution_state": "COMPLETED",
        "context_items": "1",
        "events": "3",
        "audit_records": "5",
        "database": "sqlite",
        "suggestion_id": "",
        "suggested_role": "",
        "suggested_action": "",
        "suggestion_status": "",
        "blocked_reason": "",
    }


def test_dataclass_as_str_dict_works_for_every_orchestrator_result_type() -> None:
    project_operation_result = ProjectOperationResult(
        project_id="p1",
        task_id="t1",
        authorization_id="a1",
        task_state="IMPLEMENTED",
        project_operation="WRITE_SOURCE",
    )
    task_workflow_stage_result = TaskWorkflowStageResult(
        project_id="p1",
        task_id="t1",
        stage="IMPLEMENT",
        task_state="IMPLEMENTED",
    )

    assert dataclass_as_str_dict(project_operation_result)["project_operation"] == (
        "WRITE_SOURCE"
    )
    assert dataclass_as_str_dict(task_workflow_stage_result)["stage"] == "IMPLEMENT"


def test_suggestion_fields_with_no_suggestion_returns_empty_strings() -> None:
    assert suggestion_fields(None) == {
        "suggestion_id": "",
        "suggested_role": "",
        "suggested_action": "",
        "suggestion_status": "",
    }


def test_suggestion_fields_flattens_a_real_suggestion() -> None:
    suggestion = Suggestion(
        task_id=TaskId.new(),
        suggested_role=RoleName.DEVELOPER,
        suggested_action=ActionName.IMPLEMENT,
        rationale="Implement the requested change.",
        status=SuggestionStatus.ACCEPTED,
    )

    fields = suggestion_fields(suggestion)

    assert fields == {
        "suggestion_id": str(suggestion.id),
        "suggested_role": "DEVELOPER",
        "suggested_action": "IMPLEMENT",
        "suggestion_status": "ACCEPTED",
    }


def test_audit_and_event_counts_reads_from_both_collaborators() -> None:
    async def run() -> None:
        task_id = TaskId.new()
        audit_repository = InMemoryAuditRepository()
        await audit_repository.add(
            AuditRecord(
                actor="test",
                operation="TASK_CREATED",
                outcome="recorded",
                occurred_at=datetime.now(UTC),
                task_id=task_id,
            )
        )
        await audit_repository.add(
            AuditRecord(
                actor="test",
                operation="TASK_STATE_TRANSITIONED",
                outcome="recorded",
                occurred_at=datetime.now(UTC),
                task_id=task_id,
            )
        )

        class _FakeEventHistory:
            published_events = ("e1", "e2", "e3")

        counts = await audit_and_event_counts(
            audit_repository=audit_repository,
            event_history=_FakeEventHistory(),
            task_id=task_id,
        )

        assert counts == {"events": 3, "audit_records": 2}

    asyncio.run(run())
