"""Model classes."""

from enum import StrEnum


class ModelClass(StrEnum):
    """Provider-independent model execution classes."""

    LOCAL = "LOCAL"
    CLOUD = "CLOUD"
    EXTERNAL_AGENT = "EXTERNAL_AGENT"
    FUTURE_PROVIDER = "FUTURE_PROVIDER"

