"""Task-centric snapshot helpers shared by CLI and API."""

from __future__ import annotations

from typing import Any

from orchai.domain.identifiers import TaskId


async def collect_task_snapshot(
    *,
    runtime,
    task_id: TaskId,
    history_limit: int = 100,
) -> dict[str, Any]:
    """Collect the persisted operational view for one task."""

    task = await runtime.task_service.get_task(task_id)
    authorizations = await runtime.authorization_service.list_authorizations(
        task_id=task_id,
        limit=history_limit,
    )
    executions = await runtime.execution_service.list_executions(
        task_id=task_id,
        limit=history_limit,
    )
    suggestions = await runtime.suggestion_repository.list(
        task_id=task_id,
        limit=history_limit,
    )
    events = await runtime.event_repository.list(
        task_id=task_id,
        limit=history_limit,
    )
    audit_records = await runtime.audit_repository.list(
        task_id=task_id,
        limit=history_limit,
    )
    metric_records = await runtime.metrics_repository.list(
        task_id=task_id,
        limit=history_limit,
    )

    context_records = []
    for execution in executions:
        context_records.extend(
            await runtime.context_resolution_repository.list_by_execution(execution.id)
        )

    return {
        "task": task,
        "authorizations": authorizations,
        "executions": executions,
        "suggestions": suggestions,
        "events": events,
        "audit_records": audit_records,
        "metric_records": metric_records,
        "context_records": tuple(context_records),
        "history_limit": history_limit,
    }
