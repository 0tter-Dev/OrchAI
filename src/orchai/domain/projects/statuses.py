"""Project statuses."""

from enum import StrEnum


class ProjectStatus(StrEnum):
    """Operational status for a connected project."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UNAVAILABLE = "UNAVAILABLE"

