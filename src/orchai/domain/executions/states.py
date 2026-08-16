"""Execution lifecycle states."""

from enum import StrEnum


class ExecutionState(StrEnum):
    """Authoritative execution lifecycle states."""

    REQUESTED = "REQUESTED"
    AUTHORIZED = "AUTHORIZED"
    PREPARING = "PREPARING"
    STARTED = "STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"

