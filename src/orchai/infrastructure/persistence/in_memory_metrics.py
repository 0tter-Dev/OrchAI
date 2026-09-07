"""In-memory metrics repository."""

from __future__ import annotations

from datetime import datetime

from orchai.application.metrics import MetricsRepository
from orchai.application.metrics.aggregation import summarize_records
from orchai.domain.identifiers import ExecutionId, MetricRecordId, ProjectId, TaskId
from orchai.domain.metrics import MetricRecord, MetricSummary


class InMemoryMetricsRepository(MetricsRepository):
    """Non-durable metrics storage."""

    def __init__(self) -> None:
        self._records: dict[MetricRecordId, MetricRecord] = {}

    async def add_many(self, records: tuple[MetricRecord, ...]) -> None:
        for record in records:
            self._records.setdefault(record.id, record)

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        execution_id: ExecutionId | None = None,
        name: str | None = None,
        limit: int = 20,
    ) -> tuple[MetricRecord, ...]:
        records = tuple(
            record
            for record in self._records.values()
            if (task_id is None or record.task_id == task_id)
            and (project_id is None or record.project_id == project_id)
            and (execution_id is None or record.execution_id == execution_id)
            and (name is None or record.name == name)
        )
        return tuple(
            sorted(records, key=lambda record: record.observed_at, reverse=True)[:limit]
        )

    async def summarize(
        self,
        *,
        project_id: ProjectId | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        name: str | None = None,
        group_by: tuple[str, ...] = (),
    ) -> tuple[MetricSummary, ...]:
        records = tuple(
            record
            for record in self._records.values()
            if (project_id is None or record.project_id == project_id)
            and (name is None or record.name == name)
            and (since is None or record.observed_at >= since)
            and (until is None or record.observed_at <= until)
        )
        return summarize_records(records, group_by=group_by)
