"""Policy application ports and value objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from orchai.domain.actions import ActionName
from orchai.domain.projects import (
    ProjectOperation,
    ProjectReadinessLevel,
    ProjectSecurityProfile,
    ProviderSharingLevel,
    ProviderTarget,
)
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode, TaskState


@dataclass(frozen=True, slots=True)
class PolicyOperation:
    """Operation the policy layer evaluates before authorization/execution."""

    execution_mode: ExecutionMode
    role: RoleName
    action: ActionName
    requested_model: str
    effective_model: str
    requested_context: tuple[str, ...]
    authorized_context: tuple[str, ...]
    current_task_state: TaskState
    project_operation: ProjectOperation = ProjectOperation.READ_CONTEXT
    provider_target: ProviderTarget = ProviderTarget.LOCAL
    project_readiness_level: ProjectReadinessLevel = (
        ProjectReadinessLevel.LEVEL_0_CONNECTABLE
    )
    project_security_profile: ProjectSecurityProfile = field(
        default_factory=ProjectSecurityProfile
    )
    context_sharing_levels: tuple[ProviderSharingLevel, ...] = ()
    approve_suggestion: bool = False
    explicit_user_command: bool = False
    previous_role: RoleName | None = None
    previous_action: ActionName | None = None


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """Stable policy evaluation result."""

    allowed: bool
    reason: str
    requires_authorization: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)


class PolicyPort(Protocol):
    """Boundary for orchestration policy decisions."""

    async def evaluate(self, operation: PolicyOperation) -> PolicyDecision:
        """Return whether an operation is allowed to proceed."""
