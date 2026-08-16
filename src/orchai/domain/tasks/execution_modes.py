"""Task execution modes."""

from enum import StrEnum


class ExecutionMode(StrEnum):
    """Explicit execution modes supported by OrchAI."""

    MANUAL = "MANUAL"
    SUGGESTED = "SUGGESTED"
    AUTOMATIC = "AUTOMATIC"

