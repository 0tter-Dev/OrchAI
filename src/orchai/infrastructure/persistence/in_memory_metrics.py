"""In-memory metrics repository."""

from __future__ import annotations

from orchai.application.metrics import MetricsRepository
from orchai.domain.identifiers import MetricRecordId, ProjectId, TaskId
from orchai.domain.metrics import MetricRecord


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
        limit: int = 20,
    ) -> tuple[MetricRecord, ...]:
        records = tuple(
            record
            for record in self._records.values()
            if (task_id is None or record.task_id == task_id)
            and (project_id is None or record.project_id == project_id)
        )
        return tuple(
            sorted(records, key=lambda record: record.observed_at, reverse=True)[:limit]
        )
