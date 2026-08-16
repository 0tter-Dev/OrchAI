"""Authorization entities and value objects."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from orchai.domain.actions import ActionName
from orchai.domain.authorization.errors import (
    AuthorizationAlreadyDecidedError,
    AuthorizationMismatchError,
    AuthorizationNotGrantedError,
)
from orchai.domain.authorization.statuses import AuthorizationDecisionStatus
from orchai.domain.identifiers import (
    AuthorizationDecisionId,
    AuthorizationId,
    ModelId,
    TaskId,
)
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode, TaskState


@dataclass(frozen=True, slots=True)
class RequestedOperation:
    """Operation scope that a user or policy is asked to authorize."""

    role: RoleName
    action: ActionName
    model_id: ModelId | None = None
    context_scope: tuple[str, ...] = ()
    proposed_state: TaskState | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "context_scope",
            tuple(scope.strip() for scope in self.context_scope if scope.strip()),
        )

    def matches(self, other: "RequestedOperation") -> bool:
        return self == other


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """Explicit request for permission to perform an operation."""

    task_id: TaskId
    operation: RequestedOperation
    reason: str
    requester: str
    execution_mode: ExecutionMode
    id: AuthorizationId = field(default_factory=AuthorizationId.new)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        reason = self.reason.strip()
        requester = self.requester.strip()
        if not reason:
            raise ValueError("authorization reason must not be empty")
        if not requester:
            raise ValueError("authorization requester must not be empty")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("authorization expires_at must be after created_at")

        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "requester", requester)


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Recorded decision for an authorization request."""

    request_id: AuthorizationId
    status: AuthorizationDecisionStatus
    decided_by: str
    reason: str
    id: AuthorizationDecisionId = field(default_factory=AuthorizationDecisionId.new)
    decided_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        decided_by = self.decided_by.strip()
        reason = self.reason.strip()
        if not decided_by:
            raise ValueError("authorization decided_by must not be empty")
        if not reason:
            raise ValueError("authorization decision reason must not be empty")
        object.__setattr__(self, "decided_by", decided_by)
        object.__setattr__(self, "reason", reason)


@dataclass(slots=True)
class Authorization:
    """Authorization aggregate preserving request and decision history."""

    request: AuthorizationRequest
    decisions: tuple[AuthorizationDecision, ...] = ()

    @property
    def id(self) -> AuthorizationId:
        return self.request.id

    @property
    def task_id(self) -> TaskId:
        return self.request.task_id

    @property
    def current_decision(self) -> AuthorizationDecision | None:
        if not self.decisions:
            return None
        return self.decisions[-1]

    @property
    def status(self) -> AuthorizationDecisionStatus | None:
        decision = self.current_decision
        return decision.status if decision is not None else None

    @classmethod
    def request_authorization(cls, request: AuthorizationRequest) -> "Authorization":
        return cls(request=request)

    def record_decision(self, decision: AuthorizationDecision) -> None:
        if decision.request_id != self.id:
            raise AuthorizationMismatchError("decision does not belong to request")
        if self.status in {
            AuthorizationDecisionStatus.REJECTED,
            AuthorizationDecisionStatus.EXPIRED,
            AuthorizationDecisionStatus.REVOKED,
        }:
            raise AuthorizationAlreadyDecidedError(
                "terminal authorization decisions cannot be changed"
            )
        if self.status is AuthorizationDecisionStatus.GRANTED and decision.status in {
            AuthorizationDecisionStatus.GRANTED,
            AuthorizationDecisionStatus.REJECTED,
        }:
            raise AuthorizationAlreadyDecidedError(
                "granted authorization cannot be granted or rejected again"
            )

        self.decisions = (*self.decisions, decision)

    def is_expired(self, at: datetime | None = None) -> bool:
        if self.request.expires_at is None:
            return False
        checked_at = at or datetime.now(UTC)
        return checked_at >= self.request.expires_at

    def ensure_grants(
        self,
        *,
        operation: RequestedOperation,
        at: datetime | None = None,
    ) -> None:
        if not self.request.operation.matches(operation):
            raise AuthorizationMismatchError(
                "authorization does not match requested operation"
            )
        if self.is_expired(at):
            raise AuthorizationNotGrantedError("authorization has expired")
        if self.status is not AuthorizationDecisionStatus.GRANTED:
            raise AuthorizationNotGrantedError("authorization is not granted")


def normalize_context_scope(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(value.strip() for value in values if value.strip())

