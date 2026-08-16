"""Action vocabulary."""

from enum import StrEnum


class ActionName(StrEnum):
    """Initial action vocabulary."""

    PLAN = "PLAN"
    IMPLEMENT = "IMPLEMENT"
    FIX = "FIX"
    REFACTOR = "REFACTOR"
    REVIEW = "REVIEW"
    VALIDATE = "VALIDATE"
    TEST = "TEST"
    DOCUMENT = "DOCUMENT"

