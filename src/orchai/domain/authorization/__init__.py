"""Authorization domain."""

from orchai.domain.authorization.entities import (
    Authorization,
    AuthorizationDecision,
    AuthorizationRequest,
    RequestedOperation,
)
from orchai.domain.authorization.errors import (
    AuthorizationAlreadyDecidedError,
    AuthorizationMismatchError,
    AuthorizationNotGrantedError,
)
from orchai.domain.authorization.statuses import AuthorizationDecisionStatus

__all__ = [
    "Authorization",
    "AuthorizationAlreadyDecidedError",
    "AuthorizationDecision",
    "AuthorizationDecisionStatus",
    "AuthorizationMismatchError",
    "AuthorizationNotGrantedError",
    "AuthorizationRequest",
    "RequestedOperation",
]

