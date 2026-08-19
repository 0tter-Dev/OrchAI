"""Metrics consumers for orchestration events."""

from __future__ import annotations

from hashlib import sha256

from orchai.application.executions.ports import ExecutionRepository
from orchai.application.metrics.ports import MetricsRepository
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.identifiers import MetricRecordId
from orchai.domain.executions import Execution
from orchai.domain.metrics import MetricRecord


class MetricsEventHandler:
    """Derives operational metrics from authoritative execution events."""

    def __init__(
        self,
        *,
        repository: MetricsRepository,
        execution_repository: ExecutionRepository,
    ) -> None:
        self._repository = repository
        self._execution_repository = execution_repository

    async def handle(self, event: DomainEvent) -> None:
        if event.event_type not in {
            EventType.EXECUTION_COMPLETED,
            EventType.EXECUTION_FAILED,
        }:
            return
        if event.execution_id is None:
            return

        execution = await self._execution_repository.get(event.execution_id)
        await self._repository.add_many(_records_for_execution(execution))


def _records_for_execution(execution: Execution) -> tuple[MetricRecord, ...]:
    result = execution.result
    if result is None:
        return ()

    dimensions = {
        "role": execution.role.value,
        "action": execution.action.value,
        "model_id": str(execution.model_id),
        "outcome": "success" if result.success else "failure",
    }
    records = [
        MetricRecord(
            id=_metric_record_id(execution, "execution.success"),
            name="execution.success",
            value=1.0 if result.success else 0.0,
            unit="count",
            task_id=execution.task_id,
            project_id=execution.project_id,
            execution_id=execution.id,
            dimensions=dimensions,
        ),
        MetricRecord(
            id=_metric_record_id(execution, "execution.failure"),
            name="execution.failure",
            value=0.0 if result.success else 1.0,
            unit="count",
            task_id=execution.task_id,
            project_id=execution.project_id,
            execution_id=execution.id,
            dimensions=dimensions,
        ),
    ]

    if execution.started_at is not None and execution.completed_at is not None:
        duration_ms = (
            execution.completed_at - execution.started_at
        ).total_seconds() * 1000
        records.append(
            MetricRecord(
                id=_metric_record_id(execution, "execution.duration"),
                name="execution.duration",
                value=duration_ms,
                unit="ms",
                task_id=execution.task_id,
                project_id=execution.project_id,
                execution_id=execution.id,
                dimensions=dimensions,
            )
        )

    usage = result.resource_usage
    for name, value in {
        "execution.input_tokens": usage.input_tokens,
        "execution.output_tokens": usage.output_tokens,
        "execution.total_tokens": usage.total_tokens,
        "execution.estimated_cost": usage.estimated_cost,
    }.items():
        if value is None:
            continue
        records.append(
            MetricRecord(
                id=_metric_record_id(execution, name),
                name=name,
                value=float(value),
                unit="tokens" if "tokens" in name else "estimated_cost",
                task_id=execution.task_id,
                project_id=execution.project_id,
                execution_id=execution.id,
                dimensions=dimensions,
            )
        )

    return tuple(records)


def _metric_record_id(execution: Execution, name: str) -> MetricRecordId:
    raw = f"{execution.id}:{name}".encode("utf-8")
    return MetricRecordId(sha256(raw).hexdigest())
