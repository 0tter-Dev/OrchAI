"""Audit application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.audit import AuditRecord
from orchai.domain.identifiers import ProjectId, TaskId


class AuditRepository(Protocol):
    """Port for durable, append-oriented audit records."""

    async def add(self, record: AuditRecord) -> None:
        """Append an audit record."""

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        limit: int = 20,
    ) -> tuple[AuditRecord, ...]:
        """Return audit records, newest first."""
