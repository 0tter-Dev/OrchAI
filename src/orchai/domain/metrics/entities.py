"""Append-oriented metric records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from orchai.domain.identifiers import (
    ExecutionId,
    MetricRecordId,
    ProjectId,
    TaskId,
)


@dataclass(frozen=True, slots=True)
class MetricRecord:
    """Operational metric derived from authoritative orchestration records."""

    name: str
    value: float
    unit: str
    id: MetricRecordId = field(default_factory=MetricRecordId.new)
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    task_id: TaskId | None = None
    project_id: ProjectId | None = None
    execution_id: ExecutionId | None = None
    dimensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        name = self.name.strip()
        unit = self.unit.strip()
        if not name:
            raise ValueError("metric name must not be empty")
        if not unit:
            raise ValueError("metric unit must not be empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "unit", unit)
        object.__setattr__(self, "dimensions", MappingProxyType(dict(self.dimensions)))
