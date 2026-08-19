"""In-memory suggestion repository."""

from __future__ import annotations

from orchai.application.suggestions import SuggestionRepository
from orchai.domain.identifiers import SuggestionId, TaskId
from orchai.domain.suggestions import Suggestion


class InMemorySuggestionRepository(SuggestionRepository):
    """Non-durable suggestion storage."""

    def __init__(self) -> None:
        self._suggestions: dict[SuggestionId, Suggestion] = {}

    async def add(self, suggestion: Suggestion) -> None:
        self._suggestions.setdefault(suggestion.id, suggestion)

    async def save(self, suggestion: Suggestion) -> None:
        self._suggestions[suggestion.id] = suggestion

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        limit: int = 20,
    ) -> tuple[Suggestion, ...]:
        suggestions = tuple(
            suggestion
            for suggestion in self._suggestions.values()
            if task_id is None or suggestion.task_id == task_id
        )
        return tuple(
            sorted(
                suggestions,
                key=lambda suggestion: suggestion.generated_at,
                reverse=True,
            )[:limit]
        )
