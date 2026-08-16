"""Local filesystem project adapter."""

from __future__ import annotations

from pathlib import Path

from orchai.application.projects.ports import ProjectAdapter
from orchai.domain.capabilities import CapabilityName
from orchai.domain.context import ContextItem, ContextReference, ContextSource
from orchai.infrastructure.projects.errors import (
    ProjectCapabilityError,
    ProjectResourceAccessError,
    ProjectResourceNotFoundError,
)


class LocalFilesystemProjectAdapter(ProjectAdapter):
    """Project adapter that resolves authorized relative file references."""

    def __init__(
        self,
        root: Path | str,
        *,
        exposed_capabilities: frozenset[CapabilityName] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._capabilities = exposed_capabilities or frozenset(
            {
                CapabilityName.READ_PROJECT,
                CapabilityName.READ_DOCUMENTATION,
            }
        )

    async def capabilities(self) -> frozenset[CapabilityName]:
        return self._capabilities

    async def resolve_context(
        self,
        references: tuple[ContextReference, ...],
    ) -> tuple[ContextItem, ...]:
        return tuple(self._resolve_reference(reference) for reference in references)

    def _resolve_reference(self, reference: ContextReference) -> ContextItem:
        required = _required_capability(reference.source)
        if required not in self._capabilities:
            raise ProjectCapabilityError(
                f"adapter lacks required capability: {required.value}"
            )

        path = self._resolve_safe_path(reference.resource)
        if not path.exists() or not path.is_file():
            raise ProjectResourceNotFoundError(reference.resource)

        content = path.read_text(encoding="utf-8")
        return ContextItem(
            reference=reference,
            content=content,
            metadata={
                "path": str(path),
                "bytes": str(path.stat().st_size),
            },
        )

    def _resolve_safe_path(self, resource: str) -> Path:
        path = (self._root / resource).resolve()
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise ProjectResourceAccessError(
                f"resource escapes project root: {resource}"
            ) from exc
        return path


def _required_capability(source: ContextSource) -> CapabilityName:
    if source is ContextSource.PROJECT_DOCUMENTATION:
        return CapabilityName.READ_DOCUMENTATION
    return CapabilityName.READ_PROJECT

