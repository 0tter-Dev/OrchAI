"""Policy application ports and value objects."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

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

if TYPE_CHECKING:
    from orchai.application.policies.service import AutomaticExecutionPolicy


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


class AutomaticPolicyRepository(Protocol):
    """Durable storage for the single, runtime-mutable automatic-mode policy.

    Unlike every other repository in this codebase, this one always holds
    exactly one logical record (a global configuration singleton, not a
    collection of aggregates) -- `get()` must never raise for a missing
    row, returning the conservative default instead, so a fresh database
    behaves identically to one that has never had `set()` called on it.
    """

    async def get(self) -> AutomaticExecutionPolicy:
        """Return the current automatic-mode policy, or the default."""

    async def set(self, policy: AutomaticExecutionPolicy) -> None:
        """Persist a new automatic-mode policy, replacing the current one."""
