"""Audit application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.audit import AuditRecord
from orchai.domain.identifiers import (
    AuditRecordId,
    AuthorizationId,
    ExecutionId,
    ProjectId,
    TaskId,
)


class AuditRepository(Protocol):
    """Port for durable, append-oriented audit records."""

    async def add(self, record: AuditRecord) -> None:
        """Append an audit record."""

    async def get(self, audit_id: AuditRecordId) -> AuditRecord:
        """Return one audit record by id."""

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        project_id: ProjectId | None = None,
        execution_id: ExecutionId | None = None,
        authorization_id: AuthorizationId | None = None,
        limit: int = 20,
    ) -> tuple[AuditRecord, ...]:
        """Return audit records, newest first."""
