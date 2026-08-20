"""Project readiness levels."""

from enum import StrEnum


class ProjectReadinessLevel(StrEnum):
    """Operational readiness levels for connected projects."""

    LEVEL_0_CONNECTABLE = "LEVEL_0_CONNECTABLE"
    LEVEL_1_CHANGEABLE = "LEVEL_1_CHANGEABLE"
    LEVEL_2_VALIDATABLE = "LEVEL_2_VALIDATABLE"
    LEVEL_3_AUTOMATABLE = "LEVEL_3_AUTOMATABLE"

    @property
    def rank(self) -> int:
        return {
            ProjectReadinessLevel.LEVEL_0_CONNECTABLE: 0,
            ProjectReadinessLevel.LEVEL_1_CHANGEABLE: 1,
            ProjectReadinessLevel.LEVEL_2_VALIDATABLE: 2,
            ProjectReadinessLevel.LEVEL_3_AUTOMATABLE: 3,
        }[self]

