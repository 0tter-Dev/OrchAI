"""In-memory authorization repository for tests and local bootstrap."""

from __future__ import annotations

from orchai.application.authorization.ports import AuthorizationRepository
from orchai.domain.authorization import Authorization
from orchai.domain.identifiers import AuthorizationId


class AuthorizationNotFoundError(LookupError):
    """Raised when an authorization is not present in the repository."""


class InMemoryAuthorizationRepository(AuthorizationRepository):
    """Simple non-durable authorization repository."""

    def __init__(self) -> None:
        self._authorizations: dict[AuthorizationId, Authorization] = {}

    async def add(self, authorization: Authorization) -> None:
        self._authorizations[authorization.id] = authorization

    async def get(self, authorization_id: AuthorizationId) -> Authorization:
        try:
            return self._authorizations[authorization_id]
        except KeyError as exc:
            raise AuthorizationNotFoundError(str(authorization_id)) from exc

    async def save(self, authorization: Authorization) -> None:
        if authorization.id not in self._authorizations:
            raise AuthorizationNotFoundError(str(authorization.id))
        self._authorizations[authorization.id] = authorization

    async def list(self) -> tuple[Authorization, ...]:
        return tuple(self._authorizations.values())

