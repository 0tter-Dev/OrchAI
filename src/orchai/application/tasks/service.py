"""Task application service."""

from __future__ import annotations

from orchai.application.events.ports import EventPublisher
from orchai.application.tasks.commands import CreateTaskCommand, TransitionTaskCommand
from orchai.application.tasks.ports import TaskRepository
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.tasks import Task, TaskScope, TaskState, TaskStateMachine, TaskTransition


class TaskService:
    """Coordinates task use cases without owning domain rules."""

    def __init__(
        self,
        *,
        repository: TaskRepository,
        event_publisher: EventPublisher,
        state_machine: TaskStateMachine | None = None,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher
        self._state_machine = state_machine or TaskStateMachine.default()

    async def create_task(self, command: CreateTaskCommand) -> Task:
        task = Task(
            title=command.title,
            description=command.description,
            project_id=command.project_id,
            execution_mode=command.execution_mode,
            scope=TaskScope(
                requested_change=command.requested_change,
                acceptance_criteria=tuple(command.acceptance_criteria),
                constraints=tuple(command.constraints),
                exclusions=tuple(command.exclusions),
            ),
        )
        await self._repository.add(task)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.TASK_CREATED,
                source="application.tasks",
                task_id=task.id,
                project_id=task.project_id,
                payload={
                    "title": task.title,
                    "state": task.state.value,
                    "execution_mode": task.execution_mode.value,
                },
            )
        )
        return task

    async def transition_task(self, command: TransitionTaskCommand) -> Task:
        task = await self._repository.get(command.task_id)
        transition = task.transition_to(
            command.target_state,
            state_machine=self._state_machine,
        )
        await self._repository.save(task)
        await self._event_publisher.publish(
            _state_transition_event(
                task=task,
                transition=transition,
                source=command.source,
            )
        )
        return task


def _state_transition_event(
    *,
    task: Task,
    transition: TaskTransition,
    source: str,
) -> DomainEvent:
    event_type = EventType.TASK_STATE_TRANSITIONED
    if transition.target is TaskState.COMPLETED:
        event_type = EventType.TASK_COMPLETED
    elif transition.target is TaskState.CANCELLED:
        event_type = EventType.TASK_CANCELLED

    return DomainEvent(
        event_type=event_type,
        source=source,
        task_id=task.id,
        project_id=task.project_id,
        payload={
            "from_state": transition.source.value,
            "to_state": transition.target.value,
        },
    )
