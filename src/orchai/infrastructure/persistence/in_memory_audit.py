"""In-memory audit repository."""

from __future__ import annotations

from orchai.application.audit import AuditRepository
from orchai.domain.audit import AuditRecord
from orchai.domain.identifiers import AuditRecordId, EventId, ProjectId, TaskId


class InMemoryAuditRepository(AuditRepository):
    """Non-durable audit storage for tests and local composition."""

    def __init__(self) -> None:
        self._records: dict[AuditRecordId, AuditRecord] = {}
        self._event_index: dict[EventId, AuditRecordId] = {}

    async def add(self, record: AuditRecord) -> None:
        if record.event_id is not None and record.event_id in self._event_index:
            return
        self._records[record.id] = record
        if record.event_id is not None:
            self._event_index[record.event_id] = record.id

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        limit: int = 20,
    ) -> tuple[AuditRecord, ...]:
        records = tuple(
            record
            for record in self._records.values()
            if (task_id is None or record.task_id == task_id)
            and (project_id is None or record.project_id == project_id)
        )
        return tuple(
            sorted(records, key=lambda record: record.occurred_at, reverse=True)[:limit]
        )
