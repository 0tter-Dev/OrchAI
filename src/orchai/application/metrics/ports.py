"""Metrics application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.identifiers import TaskId
from orchai.domain.metrics import MetricRecord


class MetricsRepository(Protocol):
    """Persistence boundary for operational metrics."""

    async def add_many(self, records: tuple[MetricRecord, ...]) -> None:
        """Persist metric records."""

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        limit: int = 20,
    ) -> tuple[MetricRecord, ...]:
        """Return metric records, newest first."""
