"""Metrics application ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from orchai.domain.identifiers import ExecutionId, ProjectId, TaskId
from orchai.domain.metrics import MetricRecord, MetricSummary

#: Dimensions a caller may group a summary by: "project_id" is resolved from
#: `MetricRecord.project_id` (a real column); the rest are looked up in
#: `MetricRecord.dimensions` (as set by `MetricsEventHandler`).
SUMMARY_GROUP_BY_FIELDS = frozenset({"project_id", "role", "action", "model_id", "outcome"})


class MetricsRepository(Protocol):
    """Persistence boundary for operational metrics."""

    async def add_many(self, records: tuple[MetricRecord, ...]) -> None:
        """Persist metric records."""

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        execution_id: ExecutionId | None = None,
        name: str | None = None,
        limit: int = 20,
    ) -> tuple[MetricRecord, ...]:
        """Return metric records, newest first."""

    async def summarize(
        self,
        *,
        project_id: ProjectId | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        name: str | None = None,
        group_by: tuple[str, ...] = (),
    ) -> tuple[MetricSummary, ...]:
        """Aggregate (count/sum/avg) matching records, one bucket per name.

        Every bucket is scoped to a single metric ``name`` (summing
        ``execution.duration`` and ``execution.success`` together would be
        meaningless) plus whatever ``group_by`` fields were requested (a
        subset of ``SUMMARY_GROUP_BY_FIELDS``). An empty ``group_by``
        yields exactly one bucket per distinct metric name present in the
        filtered set.
        """
