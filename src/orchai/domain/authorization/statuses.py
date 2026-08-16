"""Authorization decision statuses."""

from enum import StrEnum


class AuthorizationDecisionStatus(StrEnum):
    """Recorded authorization decisions."""

    GRANTED = "GRANTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

