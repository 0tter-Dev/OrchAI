"""Non-authoritative operational suggestions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

from orchai.domain.actions import ActionName
from orchai.domain.capabilities import CapabilityName
from orchai.domain.identifiers import ExecutionId, SuggestionId, TaskId
from orchai.domain.roles import RoleName
from orchai.domain.suggestions.statuses import SuggestionStatus


@dataclass(frozen=True, slots=True)
class Suggestion:
    """Optional recommendation that does not authorize execution."""

    task_id: TaskId
    suggested_role: RoleName
    suggested_action: ActionName
    rationale: str
    id: SuggestionId = field(default_factory=SuggestionId.new)
    related_execution_id: ExecutionId | None = None
    required_capabilities: frozenset[CapabilityName] = frozenset()
    expected_impact: str = ""
    authorization_required: bool = True
    confidence: float | None = None
    status: SuggestionStatus = SuggestionStatus.GENERATED
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        rationale = self.rationale.strip()
        expected_impact = self.expected_impact.strip()
        if not rationale:
            raise ValueError("suggestion rationale must not be empty")
        if self.confidence is not None and not 0 <= self.confidence <= 1:
            raise ValueError("suggestion confidence must be between 0 and 1")
        object.__setattr__(self, "rationale", rationale)
        object.__setattr__(self, "expected_impact", expected_impact)
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def with_status(self, status: SuggestionStatus) -> "Suggestion":
        return Suggestion(
            id=self.id,
            task_id=self.task_id,
            related_execution_id=self.related_execution_id,
            suggested_role=self.suggested_role,
            suggested_action=self.suggested_action,
            rationale=self.rationale,
            required_capabilities=self.required_capabilities,
            expected_impact=self.expected_impact,
            authorization_required=self.authorization_required,
            confidence=self.confidence,
            status=status,
            generated_at=self.generated_at,
            metadata=self.metadata,
        )
