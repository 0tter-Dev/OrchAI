"""Local filesystem project adapter."""

from __future__ import annotations

from pathlib import Path

from orchai.application.projects.ports import (
    ProjectAdapter,
    ProjectDiscovery,
    ProjectResource,
)
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
        if exposed_capabilities is None:
            exposed_capabilities = frozenset(
                {
                    CapabilityName.READ_PROJECT,
                    CapabilityName.READ_DOCUMENTATION,
                }
            )
        self._capabilities = exposed_capabilities

    async def capabilities(self) -> frozenset[CapabilityName]:
        return self._capabilities

    async def discover(self, *, limit: int = 100) -> ProjectDiscovery:
        resources: list[ProjectResource] = []
        normalized_limit = max(1, min(limit, 500))
        for path in sorted(self._root.rglob("*")):
            if len(resources) >= normalized_limit:
                break
            if not path.is_file() or _is_hidden_or_internal(path, self._root):
                continue
            resource = path.relative_to(self._root).as_posix()
            source = _source_for_path(path)
            resources.append(
                ProjectResource(
                    resource=resource,
                    source=source,
                    capabilities=frozenset({_required_capability(source)}),
                    metadata={
                        "bytes": str(path.stat().st_size),
                        "suffix": path.suffix,
                    },
                )
            )
        return ProjectDiscovery(
            resources=tuple(resources),
            metadata={
                "adapter_type": "local_filesystem",
                "root_name": self._root.name,
                "limit": str(normalized_limit),
            },
        )

    async def read_context(self, reference: ContextReference) -> ContextItem:
        return self._resolve_reference(reference)

    async def resolve_context(
        self,
        references: tuple[ContextReference, ...],
    ) -> tuple[ContextItem, ...]:
        items: list[ContextItem] = []
        for reference in references:
            items.append(await self.read_context(reference))
        return tuple(items)

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
                "resource": path.relative_to(self._root).as_posix(),
                "bytes": str(path.stat().st_size),
                "modified_at": str(path.stat().st_mtime_ns),
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


def _source_for_path(path: Path) -> ContextSource:
    if path.suffix.lower() in {".md", ".rst", ".txt"}:
        return ContextSource.PROJECT_DOCUMENTATION
    if path.name.lower() in {"pyproject.toml", "package.json", "uv.lock"}:
        return ContextSource.CONFIGURATION
    return ContextSource.SOURCE_FILE


def _is_hidden_or_internal(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part.startswith(".") for part in relative_parts)
