import asyncio

import pytest

from orchai.application.authorization import (
    AuthorizationService,
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.context import ContextService, ResolveExecutionContextCommand
from orchai.application.events import InProcessEventDispatcher
from orchai.application.executions import ExecutionService, RequestExecutionCommand
from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.context import UnauthorizedContextError
from orchai.domain.identifiers import ModelId, ProjectId, TaskId
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode
from orchai.infrastructure.persistence import (
    InMemoryAuthorizationRepository,
    InMemoryExecutionRepository,
)
from orchai.infrastructure.projects import (
    InMemoryProjectAdapterRegistry,
    LocalFilesystemProjectAdapter,
)


def test_context_service_resolves_only_authorized_context(tmp_path) -> None:
    async def run() -> None:
        project_file = tmp_path / "README.md"
        project_file.write_text("Project docs", encoding="utf-8")
        events = InProcessEventDispatcher()
        authorization_repository = InMemoryAuthorizationRepository()
        execution_repository = InMemoryExecutionRepository()
        project_adapters = InMemoryProjectAdapterRegistry()
        project_id = ProjectId.new()
        await project_adapters.register(
            project_id,
            LocalFilesystemProjectAdapter(tmp_path),
        )
        authorization_service = AuthorizationService(
            repository=authorization_repository,
            event_publisher=events,
        )
        execution_service = ExecutionService(
            repository=execution_repository,
            authorization_repository=authorization_repository,
            event_publisher=events,
        )
        context_service = ContextService(
            execution_repository=execution_repository,
            project_adapters=project_adapters,
            event_publisher=events,
        )
        task_id = TaskId.new()
        model_id = ModelId("local-demo")
        authorization = await authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                context_scope=("README.md",),
                reason="Need docs.",
                requester="test",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        await authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="test",
                reason="Approved.",
            )
        )
        execution = await execution_service.request_execution(
            RequestExecutionCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                authorization_id=authorization.id,
                project_id=project_id,
                requested_context=("README.md", "secret.txt"),
                authorized_context=("README.md",),
            )
        )

        package = await context_service.resolve_execution_context(
            ResolveExecutionContextCommand(execution_id=execution.id)
        )

        assert len(package.items) == 1
        assert package.items[0].content == "Project docs"
        assert package.items[0].reference.resource == "README.md"

    asyncio.run(run())


def test_context_service_rejects_authorized_context_not_requested(tmp_path) -> None:
    async def run() -> None:
        events = InProcessEventDispatcher()
        authorization_repository = InMemoryAuthorizationRepository()
        execution_repository = InMemoryExecutionRepository()
        project_adapters = InMemoryProjectAdapterRegistry()
        project_id = ProjectId.new()
        await project_adapters.register(project_id, LocalFilesystemProjectAdapter(tmp_path))
        authorization_service = AuthorizationService(
            repository=authorization_repository,
            event_publisher=events,
        )
        execution_service = ExecutionService(
            repository=execution_repository,
            authorization_repository=authorization_repository,
            event_publisher=events,
        )
        context_service = ContextService(
            execution_repository=execution_repository,
            project_adapters=project_adapters,
            event_publisher=events,
        )
        task_id = TaskId.new()
        model_id = ModelId("local-demo")
        authorization = await authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                context_scope=("extra.txt",),
                reason="Need one file.",
                requester="test",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        await authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="test",
                reason="Approved.",
            )
        )
        execution = await execution_service.request_execution(
            RequestExecutionCommand(
                task_id=task_id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                authorization_id=authorization.id,
                project_id=project_id,
                requested_context=("README.md",),
                authorized_context=("extra.txt",),
            )
        )

        with pytest.raises(UnauthorizedContextError):
            await context_service.resolve_execution_context(
                ResolveExecutionContextCommand(execution_id=execution.id)
            )

    asyncio.run(run())

