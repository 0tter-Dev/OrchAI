"""The policy-evaluate -> suggestion-mark -> authorize -> grant gate.

Extracted (Phase 7.5): this exact sequence appeared, near-identically,
three times in `orchestrator.py` (in `_advance_task_to_planned`,
`run_project_operation`, and `run_task_workflow_stage`) -- the single
biggest duplication `Orchestrator` had. Each call site still owns its own
early-return behavior when the policy denies the operation (which result
to build, which "blocked" event to publish); this module only owns the
identical part in between.
"""

from __future__ import annotations

from dataclasses import dataclass

from orchai.application.authorization import (
    AuthorizationService,
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.policies import PolicyDecision, PolicyOperation, PolicyPort
from orchai.application.suggestions import SuggestionEngine
from orchai.domain.actions import ActionName
from orchai.domain.authorization import Authorization, AuthorizationDecisionStatus
from orchai.domain.identifiers import ModelId, TaskId
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion, SuggestionStatus


@dataclass(frozen=True, slots=True)
class GateResult:
    """Outcome of one evaluate-then-authorize gate.

    ``authorization`` is ``None`` exactly when ``policy_decision.allowed``
    is ``False`` -- callers are expected to check that first.
    """

    policy_decision: PolicyDecision
    suggestion: Suggestion | None
    authorization: Authorization | None


async def evaluate_and_authorize(
    *,
    policy_service: PolicyPort,
    authorization_service: AuthorizationService,
    suggestion_engine: SuggestionEngine | None,
    suggestion: Suggestion | None,
    operation: PolicyOperation,
    task_id: TaskId,
    role: RoleName,
    action: ActionName,
    model_id: ModelId | None,
    context_scope: tuple[str, ...],
    reason: str,
    requester: str,
    decider: str,
    decision_reason: str,
) -> GateResult:
    """Evaluate ``operation``, mark any suggestion, and auto-grant if allowed.

    ``suggestion``/``suggestion_engine`` are both ``None`` at call sites
    with no suggestion to mark (e.g. a directly-requested project
    operation, as opposed to a task advancing through a suggested stage).
    ``role``/``action`` (and every other authorization-request field) are
    taken as explicit parameters rather than read off ``operation``, so a
    caller stays free to authorize a different ``(role, action)`` than the
    one just evaluated -- true today only for the bootstrap PLAN gate,
    which evaluates the *suggested* stage but authorizes the same pair.
    """

    policy_decision = await policy_service.evaluate(operation)
    if suggestion is not None and suggestion_engine is not None:
        suggestion = await suggestion_engine.mark_status(
            suggestion,
            SuggestionStatus.ACCEPTED
            if policy_decision.allowed
            else SuggestionStatus.PRESENTED,
        )
    if not policy_decision.allowed:
        return GateResult(
            policy_decision=policy_decision,
            suggestion=suggestion,
            authorization=None,
        )

    authorization = await authorization_service.request_authorization(
        RequestAuthorizationCommand(
            task_id=task_id,
            role=role,
            action=action,
            model_id=model_id,
            context_scope=context_scope,
            reason=reason,
            requester=requester,
            execution_mode=operation.execution_mode,
        )
    )
    await authorization_service.decide_authorization(
        DecideAuthorizationCommand(
            authorization_id=authorization.id,
            status=AuthorizationDecisionStatus.GRANTED,
            decided_by=decider,
            reason=decision_reason,
        )
    )
    return GateResult(
        policy_decision=policy_decision,
        suggestion=suggestion,
        authorization=authorization,
    )
