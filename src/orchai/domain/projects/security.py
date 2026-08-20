"""Project security profile concepts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from orchai.domain.projects.readiness import ProjectReadinessLevel


class ProjectOperation(StrEnum):
    """Project operation identifiers used by policy and readiness gates."""

    CONNECT_PROJECT = "CONNECT_PROJECT"
    READ_CONTEXT = "READ_CONTEXT"
    WRITE_SOURCE = "WRITE_SOURCE"
    WRITE_DOCUMENTATION = "WRITE_DOCUMENTATION"
    RUN_VALIDATION = "RUN_VALIDATION"
    RUN_TESTS = "RUN_TESTS"
    RUN_COMMAND = "RUN_COMMAND"
    GIT_STATUS = "GIT_STATUS"
    CONFIGURE_GIT = "CONFIGURE_GIT"
    CONFIGURE_CICD = "CONFIGURE_CICD"
    RESTRUCTURE_ARCHITECTURE = "RESTRUCTURE_ARCHITECTURE"


class ProviderSharingLevel(StrEnum):
    """Whether project information may cross a provider boundary."""

    LOCAL_ONLY = "LOCAL_ONLY"
    CLOUD_ALLOWED_WITH_AUTHORIZATION = "CLOUD_ALLOWED_WITH_AUTHORIZATION"
    NEVER_EXTERNALIZED = "NEVER_EXTERNALIZED"


class PersistenceClassification(StrEnum):
    """Whether project knowledge may be persisted by OrchAI."""

    DEFAULT_ALLOWED = "DEFAULT_ALLOWED"
    EXPLICIT_AUTHORIZATION_REQUIRED = "EXPLICIT_AUTHORIZATION_REQUIRED"
    DISALLOWED_BY_DEFAULT = "DISALLOWED_BY_DEFAULT"


class ProviderTarget(StrEnum):
    """Execution target class used by security policy."""

    LOCAL = "local"
    CLOUD = "cloud"


@dataclass(frozen=True, slots=True)
class ProjectSecurityProfile:
    """Persisted trust/security settings for one connected project."""

    readiness_level: ProjectReadinessLevel = ProjectReadinessLevel.LEVEL_0_CONNECTABLE
    access_scope: tuple[str, ...] = ()
    restricted_areas: tuple[str, ...] = ()
    sensitive_patterns: tuple[str, ...] = (
        ".env",
        "secret",
        "credential",
        "id_rsa",
        ".pem",
        ".key",
        "personal",
    )
    allow_git_bootstrap: bool = False
    allow_architecture_restructure: bool = False
    allow_cicd_changes: bool = False
    allow_cloud_provider_sharing: bool = False
    persist_architecture_summaries: bool = False
    persist_naming_summaries: bool = False
    persist_functional_summaries: bool = False
    persist_context_snapshots: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "access_scope", tuple(sorted(set(self.access_scope))))
        object.__setattr__(
            self,
            "restricted_areas",
            tuple(sorted(set(area.strip() for area in self.restricted_areas if area.strip()))),
        )
        object.__setattr__(
            self,
            "sensitive_patterns",
            tuple(
                sorted(
                    set(
                        pattern.strip().lower()
                        for pattern in self.sensitive_patterns
                        if pattern.strip()
                    )
                )
            ),
        )
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def as_dict(self) -> dict[str, Any]:
        return {
            "readiness_level": self.readiness_level.value,
            "access_scope": list(self.access_scope),
            "restricted_areas": list(self.restricted_areas),
            "sensitive_patterns": list(self.sensitive_patterns),
            "allow_git_bootstrap": self.allow_git_bootstrap,
            "allow_architecture_restructure": self.allow_architecture_restructure,
            "allow_cicd_changes": self.allow_cicd_changes,
            "allow_cloud_provider_sharing": self.allow_cloud_provider_sharing,
            "persist_architecture_summaries": self.persist_architecture_summaries,
            "persist_naming_summaries": self.persist_naming_summaries,
            "persist_functional_summaries": self.persist_functional_summaries,
            "persist_context_snapshots": self.persist_context_snapshots,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProjectSecurityProfile":
        return cls(
            readiness_level=ProjectReadinessLevel(
                data.get("readiness_level", ProjectReadinessLevel.LEVEL_0_CONNECTABLE)
            ),
            access_scope=tuple(data.get("access_scope", ())),
            restricted_areas=tuple(data.get("restricted_areas", ())),
            sensitive_patterns=tuple(
                data.get(
                    "sensitive_patterns",
                    (
                        ".env",
                        "secret",
                        "credential",
                        "id_rsa",
                        ".pem",
                        ".key",
                        "personal",
                    ),
                )
            ),
            allow_git_bootstrap=bool(data.get("allow_git_bootstrap", False)),
            allow_architecture_restructure=bool(
                data.get("allow_architecture_restructure", False)
            ),
            allow_cicd_changes=bool(data.get("allow_cicd_changes", False)),
            allow_cloud_provider_sharing=bool(
                data.get("allow_cloud_provider_sharing", False)
            ),
            persist_architecture_summaries=bool(
                data.get("persist_architecture_summaries", False)
            ),
            persist_naming_summaries=bool(data.get("persist_naming_summaries", False)),
            persist_functional_summaries=bool(
                data.get("persist_functional_summaries", False)
            ),
            persist_context_snapshots=bool(data.get("persist_context_snapshots", False)),
            metadata=data.get("metadata", {}),
        )
