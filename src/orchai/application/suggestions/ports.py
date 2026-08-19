"""Suggestion application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.identifiers import TaskId
from orchai.domain.suggestions import Suggestion


class SuggestionRepository(Protocol):
    """Persistence boundary for non-authoritative suggestions."""

    async def add(self, suggestion: Suggestion) -> None:
        """Persist a generated suggestion."""

    async def save(self, suggestion: Suggestion) -> None:
        """Persist lifecycle changes to a suggestion."""

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        limit: int = 20,
    ) -> tuple[Suggestion, ...]:
        """Return suggestions, newest first."""
