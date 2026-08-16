import asyncio

from orchai.application.authorization import (
    AuthorizationService,
    DecideAuthorizationCommand,
    RequestAuthorizationCommand,
)
from orchai.application.events import InProcessEventDispatcher
from orchai.application.executions import (
    CompleteExecutionCommand,
    ExecutionService,
    RequestExecutionCommand,
    TransitionExecutionCommand,
)
from orchai.application.projects import ProjectService, RegisterProjectCommand
from orchai.application.tasks import CreateTaskCommand, TaskService, TransitionTaskCommand
from orchai.domain.actions import ActionName
from orchai.domain.authorization import AuthorizationDecisionStatus
from orchai.domain.capabilities import CapabilityName
from orchai.domain.executions import ExecutionState
from orchai.domain.identifiers import ModelId
from orchai.domain.roles import RoleName
from orchai.domain.tasks import ExecutionMode, TaskState
from orchai.infrastructure.persistence import (
    SQLAlchemyAuthorizationRepository,
    SQLAlchemyDatabase,
    SQLAlchemyExecutionRepository,
    SQLAlchemyProjectRepository,
    SQLAlchemyTaskRepository,
)


def test_sqlite_repositories_survive_application_restart(tmp_path) -> None:
    async def run() -> None:
        database_url = f"sqlite:///{tmp_path / 'orchai.db'}"
        database = SQLAlchemyDatabase(database_url)
        database.migrate()

        events = InProcessEventDispatcher()
        project_repository = SQLAlchemyProjectRepository(database)
        task_repository = SQLAlchemyTaskRepository(database)
        authorization_repository = SQLAlchemyAuthorizationRepository(database)
        execution_repository = SQLAlchemyExecutionRepository(database)
        project_service = ProjectService(
            repository=project_repository,
            event_publisher=events,
        )
        task_service = TaskService(
            repository=task_repository,
            event_publisher=events,
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

        project = await project_service.register_project(
            RegisterProjectCommand(
                name="Persisted",
                root_location=str(tmp_path),
                capabilities=(CapabilityName.READ_PROJECT,),
            )
        )
        task = await task_service.create_task(
            CreateTaskCommand(
                title="Persisted task",
                description="Verify durable task state.",
                requested_change="Store operational state in SQLite.",
                project_id=project.id,
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        task = await task_service.transition_task(
            TransitionTaskCommand(
                task_id=task.id,
                target_state=TaskState.PLANNING,
            )
        )
        model_id = ModelId("local-demo")
        authorization = await authorization_service.request_authorization(
            RequestAuthorizationCommand(
                task_id=task.id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                context_scope=("README.md",),
                reason="Need implementation authorization.",
                requester="test",
                execution_mode=ExecutionMode.SUGGESTED,
            )
        )
        authorization = await authorization_service.decide_authorization(
            DecideAuthorizationCommand(
                authorization_id=authorization.id,
                status=AuthorizationDecisionStatus.GRANTED,
                decided_by="test",
                reason="Approved.",
            )
        )
        execution = await execution_service.request_execution(
            RequestExecutionCommand(
                task_id=task.id,
                role=RoleName.DEVELOPER,
                action=ActionName.IMPLEMENT,
                model_id=model_id,
                authorization_id=authorization.id,
                project_id=project.id,
                requested_context=("README.md",),
                authorized_context=("README.md",),
            )
        )
        await execution_service.transition_execution(
            TransitionExecutionCommand(
                execution_id=execution.id,
                target_state=ExecutionState.PREPARING,
            )
        )
        await execution_service.transition_execution(
            TransitionExecutionCommand(
                execution_id=execution.id,
                target_state=ExecutionState.STARTED,
            )
        )
        await execution_service.complete_execution(
            CompleteExecutionCommand(
                execution_id=execution.id,
                output="Stored execution result.",
            )
        )

        restarted_database = SQLAlchemyDatabase(database_url)
        restarted_database.migrate()
        persisted_task = await SQLAlchemyTaskRepository(restarted_database).get(task.id)
        persisted_authorization = await SQLAlchemyAuthorizationRepository(
            restarted_database
        ).get(authorization.id)
        persisted_execution = await SQLAlchemyExecutionRepository(
            restarted_database
        ).get(execution.id)

        assert persisted_task.state is TaskState.PLANNING
        assert persisted_authorization.status is AuthorizationDecisionStatus.GRANTED
        assert persisted_execution.state is ExecutionState.COMPLETED
        assert persisted_execution.result is not None
        assert persisted_execution.result.output == "Stored execution result."

    asyncio.run(run())
