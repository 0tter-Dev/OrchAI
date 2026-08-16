"""Role vocabulary."""

from enum import StrEnum


class RoleName(StrEnum):
    """Initial role vocabulary."""

    TASK_PLANNER = "TASK_PLANNER"
    DEVELOPER = "DEVELOPER"
    QUALITY_AGENT = "QUALITY_AGENT"

