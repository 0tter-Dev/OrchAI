import asyncio

from orchai.application.policies import AutomaticExecutionPolicy, LocalPolicyService, PolicyOperation
from orchai.domain.actions import ActionName
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode, TaskState


def test_policy_suggested_mode_requires_explicit_approval() -> None:
    async def run() -> None:
        service = LocalPolicyService()
        decision = await service.evaluate(
            PolicyOperation(
                execution_mode=ExecutionMode.SUGGESTED,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                requested_model="m1",
                effective_model="m1",
                requested_context=("docs/INDEX.md",),
                authorized_context=("docs/INDEX.md",),
                current_task_state=TaskState.PLANNED,
            )
        )
        assert decision.allowed is False
        assert decision.reason == "suggested_mode_requires_approval"

    asyncio.run(run())


def test_policy_automatic_mode_blocks_cross_role_without_policy() -> None:
    async def run() -> None:
        service = LocalPolicyService(
            automatic_policy=AutomaticExecutionPolicy(
                allowed_operations=((RoleName.QUALITY_AGENT, ActionName.REVIEW),)
            )
        )
        decision = await service.evaluate(
            PolicyOperation(
                execution_mode=ExecutionMode.AUTOMATIC,
                role=RoleName.QUALITY_AGENT,
                action=ActionName.REVIEW,
                requested_model="m1",
                effective_model="m1",
                requested_context=("docs/INDEX.md",),
                authorized_context=("docs/INDEX.md",),
                current_task_state=TaskState.IMPLEMENTED,
                previous_role=RoleName.DEVELOPER,
                previous_action=ActionName.IMPLEMENT,
            )
        )
        assert decision.allowed is False
        assert decision.reason == "cross_role_transition_requires_policy"

    asyncio.run(run())


def test_policy_rejects_model_substitution_without_policy() -> None:
    async def run() -> None:
        service = LocalPolicyService(
            automatic_policy=AutomaticExecutionPolicy(
                allowed_operations=((RoleName.DEVELOPER, ActionName.IMPLEMENT),)
            )
        )
        decision = await service.evaluate(
            PolicyOperation(
                execution_mode=ExecutionMode.AUTOMATIC,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                requested_model="m1",
                effective_model="m2",
                requested_context=("docs/INDEX.md",),
                authorized_context=("docs/INDEX.md",),
                current_task_state=TaskState.PLANNED,
            )
        )
        assert decision.allowed is False
        assert decision.reason == "model_substitution_requires_policy"

    asyncio.run(run())
