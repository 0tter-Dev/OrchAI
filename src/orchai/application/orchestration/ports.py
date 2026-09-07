"""Ports local to the orchestration package.

Kept separate from `orchestrator.py` (Phase 7.5) so the sibling modules it
was decomposed into (`results.py`, `connections.py`, ...) can depend on
these two small Protocols without importing from `orchestrator` itself and
risking a circular import.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from orchai.application.projects.ports import ProjectAdapter
from orchai.domain.events import DomainEvent


class PublishedEventHistory(Protocol):
    """Event publisher capability used only for reporting flow results."""

    @property
    def published_events(self) -> tuple[DomainEvent, ...]:
        """Events published during the current process lifetime."""


class ProjectAdapterFactory(Protocol):
    def __call__(self, project_root: Path) -> ProjectAdapter:
        """Build a project adapter for a local project root."""
