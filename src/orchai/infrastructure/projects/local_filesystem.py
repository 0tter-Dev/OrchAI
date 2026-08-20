"""Local filesystem project adapter."""

from __future__ import annotations

import asyncio
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
    ProjectCommandExecutionError,
    ProjectGitError,
    ProjectResourceAccessError,
    ProjectResourceNotFoundError,
    ProjectWriteError,
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
                    CapabilityName.ACCESS_GIT,
                    CapabilityName.READ_PROJECT,
                    CapabilityName.READ_DOCUMENTATION,
                    CapabilityName.RUN_COMMANDS,
                    CapabilityName.RUN_TESTS,
                    CapabilityName.WRITE_DOCUMENTATION,
                    CapabilityName.WRITE_SOURCE,
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
            resource = await self.classify_resource(
                ContextReference(
                    source=_source_for_path(path),
                    resource=path.relative_to(self._root).as_posix(),
                )
            )
            resources.append(resource)
        return ProjectDiscovery(
            resources=tuple(resources),
            metadata={
                "adapter_type": "local_filesystem",
                "root_name": self._root.name,
                "limit": str(normalized_limit),
            },
        )

    async def assess_readiness(self) -> ProjectReadinessAssessment:
        has_git = (self._root / ".git").exists()
        has_documentation = _has_documentation(self._root)
        has_tests = _has_tests(self._root)
        readiness_level = ProjectReadinessLevel.LEVEL_0_CONNECTABLE
        reasons = ["project root is readable"]
        if has_git:
            readiness_level = ProjectReadinessLevel.LEVEL_1_CHANGEABLE
            reasons.append("git repository detected")
        if has_git and has_documentation:
            readiness_level = ProjectReadinessLevel.LEVEL_2_VALIDATABLE
            reasons.append("minimum documentation detected")
        if has_git and has_documentation and has_tests:
            readiness_level = ProjectReadinessLevel.LEVEL_3_AUTOMATABLE
            reasons.append("tests or testing strategy detected")

        security_profile = ProjectSecurityProfile(
            readiness_level=readiness_level,
            access_scope=tuple(sorted(capability.value for capability in self._capabilities)),
            restricted_areas=("secrets", "credentials", "private", "personal_data"),
            metadata={
                "root_name": self._root.name,
                "has_git": str(has_git),
                "has_documentation": str(has_documentation),
                "has_tests": str(has_tests),
            },
        )
        return ProjectReadinessAssessment(
            readiness_level=readiness_level,
            security_profile=security_profile,
            reasons=tuple(reasons),
            has_git=has_git,
            has_documentation=has_documentation,
            has_tests=has_tests,
            metadata={
                "root_name": self._root.name,
            },
        )

    async def classify_resource(self, reference: ContextReference) -> ProjectResource:
        path = self._resolve_safe_path(reference.resource)
        source = reference.source or _source_for_path(path)
        provider_sharing_level = await self.classify_provider_sharing(reference)
        persistence_classification = await self.classify_persistence(reference)
        return ProjectResource(
            resource=reference.resource,
            source=source,
            capabilities=frozenset({_required_capability(source)}),
            provider_sharing_level=provider_sharing_level,
            persistence_classification=persistence_classification,
            restricted=_is_restricted_resource(reference.resource),
            metadata={
                "bytes": str(path.stat().st_size) if path.exists() and path.is_file() else "",
                "suffix": path.suffix,
            },
        )

    async def classify_persistence(
        self,
        reference: ContextReference,
    ) -> PersistenceClassification:
        resource = reference.resource.lower()
        if _is_never_externalized_resource(resource):
            return PersistenceClassification.DISALLOWED_BY_DEFAULT
        if reference.source is ContextSource.CONFIGURATION:
            return PersistenceClassification.EXPLICIT_AUTHORIZATION_REQUIRED
        return PersistenceClassification.DEFAULT_ALLOWED

    async def classify_provider_sharing(
        self,
        reference: ContextReference,
    ) -> ProviderSharingLevel:
        resource = reference.resource.lower()
        if _is_never_externalized_resource(resource):
            return ProviderSharingLevel.NEVER_EXTERNALIZED
        if reference.source is ContextSource.CONFIGURATION:
            return ProviderSharingLevel.LOCAL_ONLY
        return ProviderSharingLevel.CLOUD_ALLOWED_WITH_AUTHORIZATION

    async def write(
        self,
        reference: ContextReference,
        content: str,
    ) -> ProjectWriteResult:
        self._require_capability(CapabilityName.WRITE_SOURCE)
        return self._write_reference(reference, content)

    async def write_documentation(
        self,
        reference: ContextReference,
        content: str,
    ) -> ProjectWriteResult:
        self._require_capability(CapabilityName.WRITE_DOCUMENTATION)
        return self._write_reference(reference, content)

    async def run_tests(
        self,
        *,
        args: tuple[str, ...] = (),
    ) -> ProjectCommandResult:
        self._require_capability(CapabilityName.RUN_TESTS)
        return await self._execute_project_command(("pytest", *args))

    async def run_command(
        self,
        command: tuple[str, ...],
    ) -> ProjectCommandResult:
        self._require_capability(CapabilityName.RUN_COMMANDS)
        return await self._execute_project_command(command)

    async def _execute_project_command(
        self,
        command: tuple[str, ...],
    ) -> ProjectCommandResult:
        if not command:
            raise ProjectCommandExecutionError("command must not be empty")
        executable = command[0].lower()
        if executable not in ALLOWED_PROJECT_COMMANDS:
            raise ProjectCommandExecutionError(
                f"command is not allowed by the local adapter: {command[0]}"
            )
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
        except OSError as exc:
            raise ProjectCommandExecutionError(
                f"failed to execute project command: {command[0]}"
            ) from exc
        return ProjectCommandResult(
            command=command,
            exit_code=process.returncode or 0,
            stdout=stdout.decode("utf-8", errors="ignore"),
            stderr=stderr.decode("utf-8", errors="ignore"),
            metadata={"root_name": self._root.name},
        )

    async def git_status(self) -> ProjectGitStatus:
        self._require_capability(CapabilityName.ACCESS_GIT)
        if not (self._root / ".git").exists():
            raise ProjectGitError("git repository is not initialized for this project")
        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                "status",
                "--porcelain=2",
                "--branch",
                cwd=str(self._root),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()
        except OSError as exc:
            raise ProjectGitError("failed to execute git status") from exc
        if process.returncode not in {0, None}:
            raise ProjectGitError(stderr.decode("utf-8", errors="ignore").strip())
        return _parse_git_status(stdout.decode("utf-8", errors="ignore"))

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

    def _require_capability(self, capability: CapabilityName) -> None:
        if capability not in self._capabilities:
            raise ProjectCapabilityError(
                f"adapter lacks required capability: {capability.value}"
            )

    def _write_reference(
        self,
        reference: ContextReference,
        content: str,
    ) -> ProjectWriteResult:
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


def _required_capability(source: ContextSource) -> CapabilityName:
    if source is ContextSource.PROJECT_DOCUMENTATION:
        return CapabilityName.READ_DOCUMENTATION
    return CapabilityName.READ_PROJECT


SENSITIVE_RESOURCE_PATTERNS: Final[tuple[str, ...]] = (
    ".env",
    "secret",
    "credential",
    "id_rsa",
    ".pem",
    ".key",
    "personal",
)

ALLOWED_PROJECT_COMMANDS: Final[frozenset[str]] = frozenset(
    {"pytest", "python", "uv"}
)


def _source_for_path(path: Path) -> ContextSource:
    if path.suffix.lower() in {".md", ".rst", ".txt"}:
        return ContextSource.PROJECT_DOCUMENTATION
    if path.name.lower() in {"pyproject.toml", "package.json", "uv.lock"}:
        return ContextSource.CONFIGURATION
    return ContextSource.SOURCE_FILE


def _is_hidden_or_internal(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return any(part.startswith(".") for part in relative_parts)


def _has_documentation(root: Path) -> bool:
    for path in root.rglob("*"):
        if _is_hidden_or_internal(path, root):
            continue
        if path.is_dir() and path.name.lower() == "docs":
            return True
        if path.is_file() and path.suffix.lower() in {".md", ".rst", ".txt"}:
            return True
    return False


def _has_tests(root: Path) -> bool:
    for path in root.rglob("*"):
        if _is_hidden_or_internal(path, root):
            continue
        if path.is_dir() and path.name.lower() in {"tests", "test"}:
            return True
        if path.is_file() and path.name.lower() in {"pytest.ini", "tox.ini"}:
            return True
        if path.is_file() and path.name.lower() == "pyproject.toml":
            content = path.read_text(encoding="utf-8", errors="ignore").lower()
            if "pytest" in content:
                return True
    return False


def _is_restricted_resource(resource: str) -> bool:
    lowered = resource.lower()
    return any(pattern in lowered for pattern in SENSITIVE_RESOURCE_PATTERNS)


def _is_never_externalized_resource(resource: str) -> bool:
    lowered = resource.lower()
    return _is_restricted_resource(lowered)


def _parse_git_status(output: str) -> ProjectGitStatus:
    branch = ""
    ahead = 0
    behind = 0
    is_dirty = False
    for line in output.splitlines():
        if line.startswith("# branch.head "):
            branch = line.removeprefix("# branch.head ").strip()
            continue
        if line.startswith("# branch.ab "):
            parts = line.removeprefix("# branch.ab ").split()
            for part in parts:
                if part.startswith("+"):
                    ahead = int(part.removeprefix("+"))
                elif part.startswith("-"):
                    behind = int(part.removeprefix("-"))
            continue
        if line and not line.startswith("#"):
            is_dirty = True
    return ProjectGitStatus(
        branch="" if branch == "(detached)" else branch,
        is_dirty=is_dirty,
        ahead=ahead,
        behind=behind,
        metadata={"raw": output},
    )
