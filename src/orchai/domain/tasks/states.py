"""Task lifecycle states."""

from enum import StrEnum


class TaskState(StrEnum):
    """Authoritative task lifecycle states."""

    CREATED = "CREATED"
    PLANNING = "PLANNING"
    PLANNED = "PLANNED"
    IMPLEMENTING = "IMPLEMENTING"
    IMPLEMENTED = "IMPLEMENTED"
    REVIEWING = "REVIEWING"
    VALIDATING = "VALIDATING"
    TESTING = "TESTING"
    VALIDATED = "VALIDATED"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

