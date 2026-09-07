import asyncio

from orchai.application.authorization import AuthorizationService
from orchai.application.events import InProcessEventDispatcher
from orchai.application.orchestration.gating import evaluate_and_authorize
from orchai.application.policies import PolicyDecision, PolicyOperation
from orchai.application.suggestions import SuggestionEngine
from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.identifiers import ModelId, TaskId
from orchai.domain.projects import ProjectReadinessLevel
from orchai.domain.roles import RoleName
from orchai.domain.suggestions import Suggestion, SuggestionStatus
from orchai.domain.tasks import ExecutionMode, TaskState
from orchai.infrastructure.persistence import (
    InMemoryAuthorizationRepository,
    InMemorySuggestionRepository,
)


class _FakePolicyService:
    def __init__(self, decision: PolicyDecision) -> None:
        self.decision = decision
        self.received_operations: list[PolicyOperation] = []

    async def evaluate(self, operation: PolicyOperation) -> PolicyDecision:
        self.received_operations.append(operation)
        return self.decision


def _operation(*, approve: bool = True) -> PolicyOperation:
    return PolicyOperation(
        execution_mode=ExecutionMode.SUGGESTED,
        role=RoleName.DEVELOPER,
        action=ActionName.IMPLEMENT,
        requested_model="m1",
        effective_model="m1",
        requested_context=("src/app.py",),
        authorized_context=("src/app.py",),
        current_task_state=TaskState.PLANNED,
        project_readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
        approve_suggestion=approve,
    )


def _build_services() -> tuple[AuthorizationService, SuggestionEngine]:
    authorization_service = AuthorizationService(
        repository=InMemoryAuthorizationRepository(),
        event_publisher=InProcessEventDispatcher(),
    )
    suggestion_engine = SuggestionEngine(InMemorySuggestionRepository())
    return authorization_service, suggestion_engine


def test_gate_denies_and_never_requests_authorization_when_policy_denies() -> None:
    async def run() -> None:
        authorization_service, suggestion_engine = _build_services()
        policy_service = _FakePolicyService(
            PolicyDecision(allowed=False, reason="denied_for_test")
        )
        task_id = TaskId.new()

        gate = await evaluate_and_authorize(
            policy_service=policy_service,
            authorization_service=authorization_service,
            suggestion_engine=suggestion_engine,
            suggestion=None,
            operation=_operation(),
            task_id=task_id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=ModelId("m1"),
            context_scope=("src/app.py",),
            reason="test",
            requester="tester",
            decider="tester",
            decision_reason="test",
        )

        assert gate.policy_decision.allowed is False
        assert gate.policy_decision.reason == "denied_for_test"
        assert gate.authorization is None
        assert gate.suggestion is None
        assert await authorization_service.list_authorizations(task_id=task_id) == ()

    asyncio.run(run())


def test_gate_marks_a_suggestion_presented_when_policy_denies() -> None:
    async def run() -> None:
        authorization_service, suggestion_engine = _build_services()
        policy_service = _FakePolicyService(
            PolicyDecision(allowed=False, reason="denied_for_test")
        )
        suggestion = Suggestion(
            task_id=TaskId.new(),
            suggested_role=RoleName.DEVELOPER,
            suggested_action=ActionName.IMPLEMENT,
            rationale="test",
        )

        gate = await evaluate_and_authorize(
            policy_service=policy_service,
            authorization_service=authorization_service,
            suggestion_engine=suggestion_engine,
            suggestion=suggestion,
            operation=_operation(),
            task_id=suggestion.task_id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=ModelId("m1"),
            context_scope=("src/app.py",),
            reason="test",
            requester="tester",
            decider="tester",
            decision_reason="test",
        )

        assert gate.suggestion is not None
        assert gate.suggestion.status is SuggestionStatus.PRESENTED
        assert gate.authorization is None

    asyncio.run(run())


def test_gate_grants_authorization_when_policy_allows() -> None:
    async def run() -> None:
        authorization_service, suggestion_engine = _build_services()
        policy_service = _FakePolicyService(
            PolicyDecision(allowed=True, reason="allowed_for_test")
        )
        task_id = TaskId.new()

        gate = await evaluate_and_authorize(
            policy_service=policy_service,
            authorization_service=authorization_service,
            suggestion_engine=None,
            suggestion=None,
            operation=_operation(),
            task_id=task_id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=ModelId("m1"),
            context_scope=("src/app.py",),
            reason="test reason",
            requester="tester",
            decider="tester-manager",
            decision_reason="test decision reason",
        )

        assert gate.policy_decision.allowed is True
        assert gate.authorization is not None
        assert gate.authorization.status is AuthorizationDecisionStatus.GRANTED
        persisted = await authorization_service.get_authorization(gate.authorization.id)
        assert persisted.task_id == task_id
        assert persisted.status is AuthorizationDecisionStatus.GRANTED

    asyncio.run(run())


def test_gate_marks_a_suggestion_accepted_and_grants_when_policy_allows() -> None:
    async def run() -> None:
        authorization_service, suggestion_engine = _build_services()
        policy_service = _FakePolicyService(
            PolicyDecision(allowed=True, reason="allowed_for_test")
        )
        suggestion = Suggestion(
            task_id=TaskId.new(),
            suggested_role=RoleName.DEVELOPER,
            suggested_action=ActionName.IMPLEMENT,
            rationale="test",
        )

        gate = await evaluate_and_authorize(
            policy_service=policy_service,
            authorization_service=authorization_service,
            suggestion_engine=suggestion_engine,
            suggestion=suggestion,
            operation=_operation(),
            task_id=suggestion.task_id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=ModelId("m1"),
            context_scope=("src/app.py",),
            reason="test",
            requester="tester",
            decider="tester",
            decision_reason="test",
        )

        assert gate.suggestion is not None
        assert gate.suggestion.status is SuggestionStatus.ACCEPTED
        assert gate.authorization is not None
        assert gate.authorization.status is AuthorizationDecisionStatus.GRANTED

    asyncio.run(run())


def test_gate_leaves_a_suggestion_unmarked_when_no_suggestion_engine_is_given() -> None:
    """`run_project_operation`'s second gate has no suggestion of its own to
    mark -- passing `suggestion_engine=None` must be a safe no-op, not an
    error, even if a `suggestion` object is somehow also passed."""

    async def run() -> None:
        authorization_service, _ = _build_services()
        policy_service = _FakePolicyService(
            PolicyDecision(allowed=True, reason="allowed_for_test")
        )
        suggestion = Suggestion(
            task_id=TaskId.new(),
            suggested_role=RoleName.DEVELOPER,
            suggested_action=ActionName.IMPLEMENT,
            rationale="test",
            status=SuggestionStatus.GENERATED,
        )

        gate = await evaluate_and_authorize(
            policy_service=policy_service,
            authorization_service=authorization_service,
            suggestion_engine=None,
            suggestion=suggestion,
            operation=_operation(),
            task_id=suggestion.task_id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=ModelId("m1"),
            context_scope=("src/app.py",),
            reason="test",
            requester="tester",
            decider="tester",
            decision_reason="test",
        )

        # Unchanged -- evaluate_and_authorize never touched it.
        assert gate.suggestion is suggestion
        assert gate.suggestion.status is SuggestionStatus.GENERATED

    asyncio.run(run())


def test_gate_passes_the_operations_execution_mode_to_the_authorization_request() -> None:
    async def run() -> None:
        authorization_service, _ = _build_services()
        policy_service = _FakePolicyService(
            PolicyDecision(allowed=True, reason="allowed_for_test")
        )
        task_id = TaskId.new()

        gate = await evaluate_and_authorize(
            policy_service=policy_service,
            authorization_service=authorization_service,
            suggestion_engine=None,
            suggestion=None,
            operation=_operation(),
            task_id=task_id,
            role=RoleName.DEVELOPER,
            action=ActionName.IMPLEMENT,
            model_id=ModelId("m1"),
            context_scope=("src/app.py",),
            reason="test",
            requester="tester",
            decider="tester",
            decision_reason="test",
        )

        persisted = await authorization_service.get_authorization(gate.authorization.id)
        assert persisted.request.execution_mode is ExecutionMode.SUGGESTED

    asyncio.run(run())
