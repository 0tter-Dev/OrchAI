import asyncio

from orchai.application.policies import AutomaticExecutionPolicy, LocalPolicyService, PolicyOperation
from orchai.domain.actions import ActionName
from orchai.domain.projects import (
    ProjectOperation,
    ProjectReadinessLevel,
    ProjectSecurityProfile,
    ProviderTarget,
)
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


def test_policy_suggested_mode_allows_explicit_approval() -> None:
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
                approve_suggestion=True,
            )
        )
        assert decision.allowed is True
        assert decision.reason == "suggested_mode_approved"

    asyncio.run(run())


def test_policy_manual_mode_allows_explicit_direct_command() -> None:
    async def run() -> None:
        service = LocalPolicyService()
        decision = await service.evaluate(
            PolicyOperation(
                execution_mode=ExecutionMode.MANUAL,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                requested_model="m1",
                effective_model="m1",
                requested_context=("src/app.py",),
                authorized_context=("src/app.py",),
                current_task_state=TaskState.PLANNED,
                project_operation=ProjectOperation.WRITE_SOURCE,
                project_readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
                explicit_user_command=True,
            )
        )
        assert decision.allowed is True
        assert decision.reason == "manual_mode_direct_command"

    asyncio.run(run())


def test_policy_manual_mode_requires_direct_command() -> None:
    async def run() -> None:
        service = LocalPolicyService()
        decision = await service.evaluate(
            PolicyOperation(
                execution_mode=ExecutionMode.MANUAL,
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
        assert decision.reason == "manual_mode_requires_direct_command"

    asyncio.run(run())


def test_policy_automatic_mode_allows_configured_operation() -> None:
    async def run() -> None:
        service = LocalPolicyService()
        decision = await service.evaluate(
            PolicyOperation(
                execution_mode=ExecutionMode.AUTOMATIC,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                requested_model="m1",
                effective_model="m1",
                requested_context=("src/app.py",),
                authorized_context=("src/app.py",),
                current_task_state=TaskState.PLANNED,
                project_operation=ProjectOperation.WRITE_SOURCE,
                project_readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
            )
        )
        assert decision.allowed is True
        assert decision.reason == "automatic_policy_allowed"

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


def test_policy_blocks_source_write_without_minimum_readiness() -> None:
    async def run() -> None:
        service = LocalPolicyService()
        decision = await service.evaluate(
            PolicyOperation(
                execution_mode=ExecutionMode.SUGGESTED,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                requested_model="m1",
                effective_model="m1",
                requested_context=("src/app.py",),
                authorized_context=("src/app.py",),
                current_task_state=TaskState.PLANNED,
                project_operation=ProjectOperation.WRITE_SOURCE,
                project_readiness_level=ProjectReadinessLevel.LEVEL_0_CONNECTABLE,
                approve_suggestion=True,
            )
        )
        assert decision.allowed is False
        assert decision.reason == "source_write_requires_level_1"

    asyncio.run(run())


def test_policy_blocks_cloud_provider_when_project_forbids_sharing() -> None:
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
                provider_target=ProviderTarget.CLOUD,
                project_operation=ProjectOperation.READ_CONTEXT,
                project_security_profile=ProjectSecurityProfile(
                    allow_cloud_provider_sharing=False
                ),
                approve_suggestion=True,
            )
        )
        assert decision.allowed is False
        assert decision.reason == "cloud_provider_sharing_requires_project_authorization"

    asyncio.run(run())
