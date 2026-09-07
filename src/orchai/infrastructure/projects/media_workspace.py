"""Media workspace project adapter (Studio, ADR-015).

Discovers and reads attachment/media files in a connected folder rather
than treating it as a source-code repository -- `capabilities()`
deliberately never exposes `RUN_TESTS`/`RUN_COMMANDS`/`ACCESS_GIT`
(`docs/architecture/ADAPTER-CONTRACTS.md`: "only supported capabilities
should be exposed"). Reuses the existing `WRITE_SOURCE` capability for
saving a generated asset back into the project rather than introducing
a new one -- Studio's Phase 6 scope does not yet exercise that path
(see `docs/architecture/MODULES.md`), so a dedicated capability name is
deferred until a real use case needs one.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from orchai.application.projects.ports import (
    ProjectAdapter,
    ProjectCommandResult,
    ProjectDiscovery,
    ProjectGitStatus,
    ProjectReadinessAssessment,
    ProjectResource,
    ProjectWriteResult,
)
from orchai.domain.capabilities import CapabilityName
from orchai.domain.context import ContextItem, ContextReference, ContextSource
from orchai.domain.projects import (
    PersistenceClassification,
    ProjectReadinessLevel,
    ProjectSecurityProfile,
    ProviderSharingLevel,
)
from orchai.infrastructure.projects.errors import (
    ProjectCapabilityError,
    ProjectResourceAccessError,
    ProjectResourceNotFoundError,
    ProjectWriteError,
)

_IMAGE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
)
_AUDIO_SUFFIXES: Final[frozenset[str]] = frozenset({".mp3", ".wav", ".flac", ".ogg", ".m4a"})
_VIDEO_SUFFIXES: Final[frozenset[str]] = frozenset({".mp4", ".mov", ".webm", ".mkv", ".avi"})
_TEXT_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".md", ".txt", ".rst", ".json", ".csv", ".yaml", ".yml"}
)

SENSITIVE_RESOURCE_PATTERNS: Final[tuple[str, ...]] = (
    ".env",
    "secret",
    "credential",
    "id_rsa",
    ".pem",
    ".key",
    "personal",
)


class MediaWorkspaceProjectAdapter(ProjectAdapter):
    """Project adapter for Studio's multimedia/attachment workspaces."""

    def __init__(
        self,
        root: Path | str,
        *,
        exposed_capabilities: frozenset[CapabilityName] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        if exposed_capabilities is None:
            exposed_capabilities = frozenset(
                {CapabilityName.READ_PROJECT, CapabilityName.WRITE_SOURCE}
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
            resource = await self.classify_resource(
                ContextReference(
                    source=ContextSource.SOURCE_FILE,
                    resource=path.relative_to(self._root).as_posix(),
                )
            )
            resources.append(resource)
        return ProjectDiscovery(
            resources=tuple(resources),
            metadata={
                "adapter_type": "media_workspace",
                "root_name": self._root.name,
                "limit": str(normalized_limit),
            },
        )

    async def assess_readiness(self) -> ProjectReadinessAssessment:
        # Studio has no code-repository notion of "tests"/"documentation
        # coverage" to grade against (ProjectReadinessLevel's higher
        # tiers are about that) -- a readable, writable folder is already
        # everything a media workspace needs.
        readiness_level = (
            ProjectReadinessLevel.LEVEL_1_CHANGEABLE
            if CapabilityName.WRITE_SOURCE in self._capabilities
            else ProjectReadinessLevel.LEVEL_0_CONNECTABLE
        )
        security_profile = ProjectSecurityProfile(
            readiness_level=readiness_level,
            access_scope=tuple(sorted(capability.value for capability in self._capabilities)),
            restricted_areas=("secrets", "credentials", "private", "personal_data"),
            metadata={"root_name": self._root.name},
        )
        return ProjectReadinessAssessment(
            readiness_level=readiness_level,
            security_profile=security_profile,
            reasons=("project root is readable",),
            metadata={"root_name": self._root.name},
        )

    async def classify_resource(self, reference: ContextReference) -> ProjectResource:
        path = self._resolve_safe_path(reference.resource)
        provider_sharing_level = await self.classify_provider_sharing(reference)
        persistence_classification = await self.classify_persistence(reference)
        return ProjectResource(
            resource=reference.resource,
            source=reference.source or ContextSource.SOURCE_FILE,
            capabilities=frozenset({CapabilityName.READ_PROJECT}),
            provider_sharing_level=provider_sharing_level,
            persistence_classification=persistence_classification,
            restricted=_is_restricted_resource(reference.resource),
            metadata={
                "bytes": str(path.stat().st_size) if path.exists() and path.is_file() else "",
                "suffix": path.suffix,
                "media_type": _media_type_for(path),
            },
        )

    async def classify_persistence(
        self,
        reference: ContextReference,
    ) -> PersistenceClassification:
        if _is_restricted_resource(reference.resource):
            return PersistenceClassification.DISALLOWED_BY_DEFAULT
        return PersistenceClassification.DEFAULT_ALLOWED

    async def classify_provider_sharing(
        self,
        reference: ContextReference,
    ) -> ProviderSharingLevel:
        if _is_restricted_resource(reference.resource):
            return ProviderSharingLevel.NEVER_EXTERNALIZED
        return ProviderSharingLevel.CLOUD_ALLOWED_WITH_AUTHORIZATION

    async def write(
        self,
        reference: ContextReference,
        content: str,
    ) -> ProjectWriteResult:
        self._require_capability(CapabilityName.WRITE_SOURCE)
        path = self._resolve_safe_path(reference.resource)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise ProjectWriteError(
                f"failed to write project resource: {reference.resource}"
            ) from exc
        return ProjectWriteResult(
            resource=reference.resource,
            bytes_written=len(content.encode("utf-8")),
            metadata={"source": reference.source.value},
        )

    async def write_documentation(
        self,
        reference: ContextReference,
        content: str,
    ) -> ProjectWriteResult:
        # Not exposed: Studio has no separate "documentation" concept
        # distinct from any other saved asset.
        self._require_capability(CapabilityName.WRITE_DOCUMENTATION)
        raise ProjectCapabilityError("media workspace adapter does not support this capability")

    async def run_tests(self, *, args: tuple[str, ...] = ()) -> ProjectCommandResult:
        self._require_capability(CapabilityName.RUN_TESTS)
        raise ProjectCapabilityError("media workspace adapter does not support this capability")

    async def run_command(self, command: tuple[str, ...]) -> ProjectCommandResult:
        self._require_capability(CapabilityName.RUN_COMMANDS)
        raise ProjectCapabilityError("media workspace adapter does not support this capability")

    async def git_status(self) -> ProjectGitStatus:
        self._require_capability(CapabilityName.ACCESS_GIT)
        raise ProjectCapabilityError("media workspace adapter does not support this capability")

    async def read_context(self, reference: ContextReference) -> ContextItem:
        required = CapabilityName.READ_PROJECT
        if required not in self._capabilities:
            raise ProjectCapabilityError(f"adapter lacks required capability: {required.value}")

        path = self._resolve_safe_path(reference.resource)
        if not path.exists() or not path.is_file():
            raise ProjectResourceNotFoundError(reference.resource)

        media_type = _media_type_for(path)
        size = path.stat().st_size
        if media_type == "text":
            content = path.read_text(encoding="utf-8", errors="strict")
        else:
            # Binary media (image/audio/video/other): no multimodal
            # provider integration yet (a future extension, not this
            # skeleton) -- a plain description keeps this adapter honest
            # rather than attempting to decode binary bytes as text.
            content = f"[{media_type} file, {size} bytes -- binary content not inlined]"
        return ContextItem(
            reference=reference,
            content=content,
            metadata={
                "resource": path.relative_to(self._root).as_posix(),
                "bytes": str(size),
                "media_type": media_type,
            },
        )

    async def resolve_context(
        self,
        references: tuple[ContextReference, ...],
    ) -> tuple[ContextItem, ...]:
        items: list[ContextItem] = []
        for reference in references:
            items.append(await self.read_context(reference))
        return tuple(items)

    def _resolve_safe_path(self, resource: str) -> Path:
        path = (self._root / resource).resolve()
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise ProjectResourceAccessError(
                f"resource escapes project root: {resource}"
            ) from exc
        return path

    def _require_capability(self, capability: CapabilityName) -> None:
        if capability not in self._capabilities:
            raise ProjectCapabilityError(
                f"adapter lacks required capability: {capability.value}"
            )


def _media_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _IMAGE_SUFFIXES:
        return "image"
    if suffix in _AUDIO_SUFFIXES:
        return "audio"
    if suffix in _VIDEO_SUFFIXES:
        return "video"
    if suffix in _TEXT_SUFFIXES:
        return "text"
    return "other"


def _is_hidden_or_internal(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part.startswith(".") for part in relative_parts)


def _is_restricted_resource(resource: str) -> bool:
    lowered = resource.lower()
    return any(pattern in lowered for pattern in SENSITIVE_RESOURCE_PATTERNS)
