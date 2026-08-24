"""In-memory authorization repository for tests and local bootstrap."""

from __future__ import annotations

from orchai.application.authorization.ports import AuthorizationRepository
from orchai.domain.authorization import Authorization, AuthorizationDecisionStatus
from orchai.domain.identifiers import AuthorizationId
from orchai.domain.identifiers import TaskId


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

    async def list(
        self,
        *,
        task_id: TaskId | None = None,
        status: AuthorizationDecisionStatus | None = None,
        pending_only: bool = False,
        limit: int = 20,
    ) -> tuple[Authorization, ...]:
        authorizations = tuple(
            authorization
            for authorization in self._authorizations.values()
            if task_id is None or authorization.task_id == task_id
            if status is None or authorization.status is status
            if not pending_only or authorization.status is None
        )
        return authorizations[: max(1, min(limit, 100))]
