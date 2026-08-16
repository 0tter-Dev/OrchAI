"""Execution application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.executions import Execution
from orchai.domain.identifiers import ExecutionId


class ExecutionRepository(Protocol):
    """Persistence boundary for execution attempts."""

    async def add(self, execution: Execution) -> None:
        """Persist a newly requested execution."""

    async def get(self, execution_id: ExecutionId) -> Execution:
        """Return an execution by id."""

    async def save(self, execution: Execution) -> None:
        """Persist changes to an execution."""

