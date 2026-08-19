"""Initial orchestration policy service."""

from __future__ import annotations

from dataclasses import dataclass

from orchai.application.policies.ports import PolicyDecision, PolicyOperation, PolicyPort
from orchai.domain.actions import ActionName
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
    """Decision layer that remains separate from authorization."""

    def __init__(
        self,
        *,
        automatic_policy: AutomaticExecutionPolicy | None = None,
    ) -> None:
        self._automatic_policy = automatic_policy or AutomaticExecutionPolicy()

    async def evaluate(self, operation: PolicyOperation) -> PolicyDecision:
        model_decision = self._evaluate_model_selection(operation)
        if not model_decision.allowed:
            return model_decision

        context_decision = self._evaluate_context_scope(operation)
        if not context_decision.allowed:
            return context_decision

        if (
            operation.previous_role is not None
            and operation.previous_role is not operation.role
            and not self._automatic_policy.allows_cross_role_transition(
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
            return PolicyDecision(
                allowed=False,
                reason="manual_mode_requires_direct_command",
            )

        if operation.execution_mode is ExecutionMode.SUGGESTED:
            if not operation.approve_suggestion:
                return PolicyDecision(
                    allowed=False,
                    reason="suggested_mode_requires_approval",
                )
            return PolicyDecision(
                allowed=True,
                reason="suggested_mode_approved",
            )

        if self._automatic_policy.allows_operation(operation.role, operation.action):
            return PolicyDecision(
                allowed=True,
                reason="automatic_policy_allowed",
            )

        return PolicyDecision(
            allowed=False,
            reason="automatic_policy_denied",
        )

    def _evaluate_model_selection(self, operation: PolicyOperation) -> PolicyDecision:
        if operation.requested_model == operation.effective_model:
            return PolicyDecision(allowed=True, reason="model_selection_allowed")
        if self._automatic_policy.allow_model_substitution:
            return PolicyDecision(allowed=True, reason="model_substitution_allowed")
        return PolicyDecision(
            allowed=False,
            reason="model_substitution_requires_policy",
            metadata={
                "requested_model": operation.requested_model,
                "effective_model": operation.effective_model,
            },
        )

    def _evaluate_context_scope(self, operation: PolicyOperation) -> PolicyDecision:
        requested = set(operation.requested_context)
        authorized = set(operation.authorized_context)
        if not authorized.issubset(requested):
            return PolicyDecision(
                allowed=False,
                reason="authorized_context_must_be_subset_of_requested",
            )
        if authorized == requested or self._automatic_policy.allow_context_expansion:
            return PolicyDecision(allowed=True, reason="context_scope_allowed")
        return PolicyDecision(allowed=True, reason="context_scope_allowed")
