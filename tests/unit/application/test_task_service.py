import asyncio

from orchai.application.events import InProcessEventDispatcher
from orchai.application.tasks import CreateTaskCommand, TaskService, TransitionTaskCommand
from orchai.domain.events import EventType
from orchai.domain.tasks import ExecutionMode, TaskState
from orchai.infrastructure.persistence import InMemoryTaskRepository


def test_create_task_uses_suggested_mode_and_emits_event() -> None:
    async def run() -> None:
        repository = InMemoryTaskRepository()
        events = InProcessEventDispatcher()
        service = TaskService(repository=repository, event_publisher=events)

        task = await service.create_task(
            CreateTaskCommand(
                title="First task",
                description="Exercise the task service.",
                requested_change="Create an auditable task.",
            )
        )

        assert task.state is TaskState.CREATED
        assert task.execution_mode is ExecutionMode.SUGGESTED
        assert events.published_events[0].event_type is EventType.TASK_CREATED
        assert events.published_events[0].task_id == task.id

    asyncio.run(run())


def test_transition_task_persists_state_and_emits_event() -> None:
    async def run() -> None:
        repository = InMemoryTaskRepository()
        events = InProcessEventDispatcher()
        service = TaskService(repository=repository, event_publisher=events)
        task = await service.create_task(
            CreateTaskCommand(
                title="First task",
                description="Exercise transitions.",
                requested_change="Move task into planning.",
            )
        )

        updated = await service.transition_task(
            TransitionTaskCommand(task_id=task.id, target_state=TaskState.PLANNING)
        )

        assert updated.state is TaskState.PLANNING
        assert (await repository.get(task.id)).state is TaskState.PLANNING
        assert events.published_events[-1].event_type is EventType.TASK_STATE_TRANSITIONED
        assert events.published_events[-1].payload == {
            "from_state": "CREATED",
            "to_state": "PLANNING",
        }

    asyncio.run(run())
