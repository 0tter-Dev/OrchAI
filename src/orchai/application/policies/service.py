"""Initial orchestration policy service."""

from __future__ import annotations

from dataclasses import dataclass

from orchai.application.events.ports import EventPublisher
from orchai.application.policies.ports import (
    AutomaticPolicyRepository,
    PolicyDecision,
    PolicyOperation,
    PolicyPort,
)
from orchai.domain.actions import ActionName
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.projects import (
    ProjectOperation,
    ProjectReadinessLevel,
    ProviderSharingLevel,
    ProviderTarget,
)
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode


@dataclass(frozen=True, slots=True)
class AutomaticExecutionPolicy:
    """Local automatic-mode limits for the initial orchestration flow."""

    allowed_operations: tuple[tuple[RoleName, ActionName], ...] = (
        (RoleName.DEVELOPER, ActionName.IMPLEMENT),
    )
    allowed_cross_role_transitions: tuple[tuple[RoleName, RoleName], ...] = ()
    allow_model_substitution: bool = False
    allow_context_expansion: bool = False

    def allows_operation(self, role: RoleName, action: ActionName) -> bool:
        return (role, action) in self.allowed_operations

    def allows_cross_role_transition(
        self,
        previous_role: RoleName,
        next_role: RoleName,
    ) -> bool:
        return (previous_role, next_role) in self.allowed_cross_role_transitions


class LocalPolicyService(PolicyPort):
    """Decision layer that remains separate from authorization.

    ``automatic_policy`` freezes a static policy for the lifetime of the
    instance (used by callers that construct an ad-hoc, per-call override,
    e.g. ``Orchestrator``'s ``command.automatic_policy`` path, and by tests
    that want a deterministic policy without touching persistence).
    ``automatic_policy_repository`` instead makes the policy runtime-mutable:
    ``evaluate()`` re-reads it from the repository on every call, so a
    ``PUT /policies/automatic`` takes effect immediately, without a process
    restart. Passing neither keeps the previous default behavior (a
    conservative, code-level ``AutomaticExecutionPolicy()``). Passing both is
    not meaningful; ``automatic_policy`` wins if both are given.
    """

    def __init__(
        self,
        *,
        automatic_policy: AutomaticExecutionPolicy | None = None,
        automatic_policy_repository: AutomaticPolicyRepository | None = None,
    ) -> None:
        self._static_policy = automatic_policy
        self._automatic_policy_repository = automatic_policy_repository

    async def _resolve_automatic_policy(self) -> AutomaticExecutionPolicy:
        if self._static_policy is not None:
            return self._static_policy
        if self._automatic_policy_repository is not None:
            return await self._automatic_policy_repository.get()
        return AutomaticExecutionPolicy()

    async def evaluate(self, operation: PolicyOperation) -> PolicyDecision:
        automatic_policy = await self._resolve_automatic_policy()

        model_decision = self._evaluate_model_selection(operation, automatic_policy)
        if not model_decision.allowed:
            return model_decision

        context_decision = self._evaluate_context_scope(operation, automatic_policy)
        if not context_decision.allowed:
            return context_decision

        provider_decision = self._evaluate_provider_boundary(operation)
        if not provider_decision.allowed:
            return provider_decision

        if (
            operation.previous_role is not None
            and operation.previous_role is not operation.role
            and not automatic_policy.allows_cross_role_transition(
                operation.previous_role,
                operation.role,
            )
        ):
            return PolicyDecision(
                allowed=False,
                reason="cross_role_transition_requires_policy",
                metadata={
                    "previous_role": operation.previous_role.value,
                    "next_role": operation.role.value,
                },
            )

        if operation.execution_mode is ExecutionMode.MANUAL:
            if not operation.explicit_user_command:
                return PolicyDecision(
                    allowed=False,
                    reason="manual_mode_requires_direct_command",
                )
            readiness_decision = self._evaluate_project_readiness(operation)
            if not readiness_decision.allowed:
                return readiness_decision
            return PolicyDecision(
                allowed=True,
                reason="manual_mode_direct_command",
            )

        if operation.execution_mode is ExecutionMode.SUGGESTED:
            if not operation.approve_suggestion:
                return PolicyDecision(
                    allowed=False,
                    reason="suggested_mode_requires_approval",
                )
            readiness_decision = self._evaluate_project_readiness(operation)
            if not readiness_decision.allowed:
                return readiness_decision
            return PolicyDecision(allowed=True, reason="suggested_mode_approved")

        if automatic_policy.allows_operation(operation.role, operation.action):
            readiness_decision = self._evaluate_project_readiness(operation)
            if not readiness_decision.allowed:
                return readiness_decision
            return PolicyDecision(
                allowed=True,
                reason="automatic_policy_allowed",
            )

        return PolicyDecision(
            allowed=False,
            reason="automatic_policy_denied",
        )

    def _evaluate_model_selection(
        self,
        operation: PolicyOperation,
        automatic_policy: AutomaticExecutionPolicy,
    ) -> PolicyDecision:
        if operation.requested_model == operation.effective_model:
            return PolicyDecision(allowed=True, reason="model_selection_allowed")
        if automatic_policy.allow_model_substitution:
            return PolicyDecision(allowed=True, reason="model_substitution_allowed")
        return PolicyDecision(
            allowed=False,
            reason="model_substitution_requires_policy",
            metadata={
                "requested_model": operation.requested_model,
                "effective_model": operation.effective_model,
            },
        )

    def _evaluate_context_scope(
        self,
        operation: PolicyOperation,
        automatic_policy: AutomaticExecutionPolicy,
    ) -> PolicyDecision:
        requested = set(operation.requested_context)
        authorized = set(operation.authorized_context)
        if not authorized.issubset(requested):
            return PolicyDecision(
                allowed=False,
                reason="authorized_context_must_be_subset_of_requested",
            )
        if authorized == requested or automatic_policy.allow_context_expansion:
            return PolicyDecision(allowed=True, reason="context_scope_allowed")
        return PolicyDecision(allowed=True, reason="context_scope_allowed")

    def _evaluate_provider_boundary(self, operation: PolicyOperation) -> PolicyDecision:
        if operation.provider_target == ProviderTarget.LOCAL:
            return PolicyDecision(allowed=True, reason="provider_boundary_allowed")
        if not operation.project_security_profile.allow_cloud_provider_sharing:
            return PolicyDecision(
                allowed=False,
                reason="cloud_provider_sharing_requires_project_authorization",
            )
        if any(
            level != ProviderSharingLevel.CLOUD_ALLOWED_WITH_AUTHORIZATION
            for level in operation.context_sharing_levels
        ):
            return PolicyDecision(
                allowed=False,
                reason="context_disallows_cloud_provider_sharing",
            )
        return PolicyDecision(allowed=True, reason="provider_boundary_allowed")

    def _evaluate_project_readiness(self, operation: PolicyOperation) -> PolicyDecision:
        required_level: ProjectReadinessLevel | None = None
        blocked_reason = ""
        if operation.project_operation == ProjectOperation.WRITE_SOURCE:
            required_level = ProjectReadinessLevel.LEVEL_1_CHANGEABLE
            blocked_reason = "source_write_requires_level_1"
        elif operation.project_operation in {
            ProjectOperation.RUN_TESTS,
            ProjectOperation.RUN_VALIDATION,
            ProjectOperation.RUN_COMMAND,
        }:
            required_level = ProjectReadinessLevel.LEVEL_2_VALIDATABLE
            blocked_reason = "validation_requires_level_2"
        elif operation.project_operation == ProjectOperation.CONFIGURE_CICD:
            required_level = ProjectReadinessLevel.LEVEL_3_AUTOMATABLE
            blocked_reason = "cicd_requires_level_3"

        if required_level is None:
            return PolicyDecision(allowed=True, reason="project_readiness_allowed")

        if operation.project_readiness_level.rank < required_level.rank:
            return PolicyDecision(
                allowed=False,
                reason=blocked_reason,
                metadata={
                    "required_level": required_level.value,
                    "current_level": operation.project_readiness_level.value,
                },
            )

        return PolicyDecision(allowed=True, reason="project_readiness_allowed")


class AutomaticPolicyService:
    """Read/write use cases for the persisted automatic-mode policy.

    Kept separate from `LocalPolicyService`, which only ever *reads* the
    policy (via `AutomaticPolicyRepository.get()`) while evaluating an
    operation: `evaluate()` runs on every gated request and must never have
    a side effect like publishing an event. Writing a new policy is a
    deliberate, occasional administrative action, so it goes through this
    service instead, mirroring how every other application service
    (`TaskService`, `ProjectService`, ...) pairs a repository write with a
    domain event for `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md`'s
    auditability guarantee.
    """

    def __init__(
        self,
        *,
        repository: AutomaticPolicyRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    async def get_automatic_policy(self) -> AutomaticExecutionPolicy:
        return await self._repository.get()

    async def set_automatic_policy(
        self,
        policy: AutomaticExecutionPolicy,
    ) -> AutomaticExecutionPolicy:
        await self._repository.set(policy)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.AUTOMATIC_POLICY_UPDATED,
                source="application.policies",
                payload={
                    "allowed_operations": [
                        f"{role.value}:{action.value}"
                        for role, action in policy.allowed_operations
                    ],
                    "allowed_cross_role_transitions": [
                        f"{previous.value}:{next_role.value}"
                        for previous, next_role in policy.allowed_cross_role_transitions
                    ],
                    "allow_model_substitution": str(policy.allow_model_substitution),
                    "allow_context_expansion": str(policy.allow_context_expansion),
                },
            )
        )
        return policy
