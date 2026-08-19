"""In-memory context resolution metadata repository."""

from __future__ import annotations

from orchai.application.context.ports import ContextResolutionRepository
from orchai.domain.context import ContextResolutionRecord
from orchai.domain.identifiers import ContextResolutionId, ExecutionId


class InMemoryContextResolutionRepository(ContextResolutionRepository):
    """Non-durable resolved context metadata storage."""

    def __init__(self) -> None:
        self._records: dict[ContextResolutionId, ContextResolutionRecord] = {}

    async def add_many(self, records: tuple[ContextResolutionRecord, ...]) -> None:
        for record in records:
            self._records.setdefault(record.id, record)

    async def list_by_execution(
        self,
        execution_id: ExecutionId,
    ) -> tuple[ContextResolutionRecord, ...]:
        records = tuple(
            record
            for record in self._records.values()
            if record.execution_id == execution_id
        )
        return tuple(sorted(records, key=lambda record: record.resolved_at))
