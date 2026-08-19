"""Context application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.context import ContextResolutionRecord
from orchai.domain.identifiers import ExecutionId


class ContextResolutionRepository(Protocol):
    """Persistence boundary for resolved context metadata."""

    async def add_many(self, records: tuple[ContextResolutionRecord, ...]) -> None:
        """Persist resolved context metadata records."""

    async def list_by_execution(
        self,
        execution_id: ExecutionId,
    ) -> tuple[ContextResolutionRecord, ...]:
        """Return context resolution metadata for an execution."""
