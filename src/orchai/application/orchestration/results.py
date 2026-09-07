"""Serialization helpers shared by every orchestrator result dataclass.

`OrchestrationFlowResult`, `ProjectOperationResult`, and
`TaskWorkflowStageResult` (orchestrator.py) all serialize the same way --
every field rendered to a string -- and all attach the same
suggestion-plus-audit/event bookkeeping before being returned. Extracted
(Phase 7.5) so that shape has one implementation instead of three
near-identical copies.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Any

from orchai.application.audit import AuditRepository
from orchai.application.orchestration.ports import PublishedEventHistory
from orchai.domain.identifiers import TaskId
from orchai.domain.suggestions import Suggestion


def dataclass_as_str_dict(instance: Any) -> dict[str, str]:
    """Render every field of a flat result dataclass as a string.

    Every orchestrator result dataclass is a flat set of `str`/`int`
    fields with no nesting, so `str()` is lossless for either.
    """

    return {field.name: str(getattr(instance, field.name)) for field in fields(instance)}


def suggestion_fields(suggestion: Suggestion | None) -> dict[str, str]:
    """Flatten the suggestion_id/role/action/status fields every result carries."""

    if suggestion is None:
        return {
            "suggestion_id": "",
            "suggested_role": "",
            "suggested_action": "",
            "suggestion_status": "",
        }
    return {
        "suggestion_id": str(suggestion.id),
        "suggested_role": suggestion.suggested_role.value,
        "suggested_action": suggestion.suggested_action.value,
        "suggestion_status": suggestion.status.value,
    }


async def audit_and_event_counts(
    *,
    audit_repository: AuditRepository,
    event_history: PublishedEventHistory,
    task_id: TaskId,
) -> dict[str, int]:
    """Return the `events`/`audit_records` counts every result reports."""

    audit_records = await audit_repository.list(task_id=task_id, limit=100)
    return {
        "events": len(event_history.published_events),
        "audit_records": len(audit_records),
    }
