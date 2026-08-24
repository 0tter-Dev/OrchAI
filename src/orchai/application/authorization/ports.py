"""Authorization application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.authorization import Authorization, AuthorizationDecisionStatus
from orchai.domain.identifiers import AuthorizationId
from orchai.domain.identifiers import TaskId


class AuthorizationRepository(Protocol):
    """Persistence boundary for authorization records."""

    async def add(self, authorization: Authorization) -> None:
        """Persist a newly requested authorization."""

    async def get(self, authorization_id: AuthorizationId) -> Authorization:
        """Return an authorization record by id."""

    async def save(self, authorization: Authorization) -> None:
        """Persist changes to an authorization record."""

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        status: AuthorizationDecisionStatus | None = None,
        pending_only: bool = False,
        limit: int = 20,
    ) -> tuple[Authorization, ...]:
        """Return authorization records, optionally filtered by task and decision.

        `status` filters by the most recent recorded decision (GRANTED,
        REJECTED, EXPIRED, REVOKED). `pending_only` filters to authorizations
        with no decision recorded yet; it is independent of `status` since
        "pending" is the absence of a decision, not a decision value.
        """
