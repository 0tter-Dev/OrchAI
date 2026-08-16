"""Project infrastructure adapters."""

from orchai.infrastructure.projects.local_filesystem import (
    LocalFilesystemProjectAdapter,
)
from orchai.infrastructure.projects.registry import InMemoryProjectAdapterRegistry

__all__ = ["InMemoryProjectAdapterRegistry", "LocalFilesystemProjectAdapter"]

