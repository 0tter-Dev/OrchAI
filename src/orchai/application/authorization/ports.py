"""Authorization application ports."""

from __future__ import annotations

from typing import Protocol

from orchai.domain.authorization import Authorization
from orchai.domain.identifiers import AuthorizationId


class AuthorizationRepository(Protocol):
    """Persistence boundary for authorization records."""

    async def add(self, authorization: Authorization) -> None:
        """Persist a newly requested authorization."""

    async def get(self, authorization_id: AuthorizationId) -> Authorization:
        """Return an authorization record by id."""

    async def save(self, authorization: Authorization) -> None:
        """Persist changes to an authorization record."""

