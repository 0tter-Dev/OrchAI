"""Project use-case commands."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from orchai.domain.capabilities import CapabilityName


@dataclass(frozen=True, slots=True)
class RegisterProjectCommand:
    """Command for registering an external project."""

    name: str
    root_location: str
    adapter_type: str = "local_filesystem"
    capabilities: Iterable[CapabilityName] = ()

