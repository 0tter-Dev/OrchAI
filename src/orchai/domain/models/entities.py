"""Model value objects."""

from __future__ import annotations

from dataclasses import dataclass

from orchai.domain.identifiers import ModelId
from orchai.domain.models.model_classes import ModelClass


@dataclass(frozen=True, slots=True)
class ModelReference:
    """Provider-independent reference to an AI execution resource."""

    id: ModelId
    provider: str
    model_class: ModelClass

    def __post_init__(self) -> None:
        provider = self.provider.strip()
        if not provider:
            raise ValueError("model provider must not be empty")
        object.__setattr__(self, "provider", provider)

