"""Project application service."""

from __future__ import annotations

from orchai.application.events.ports import EventPublisher
from orchai.application.projects.commands import RegisterProjectCommand
from orchai.application.projects.ports import ProjectRepository
from orchai.domain.events import DomainEvent, EventType
from orchai.domain.projects import Project


class ProjectService:
    """Coordinates project metadata without owning project content."""

    def __init__(
        self,
        *,
        repository: ProjectRepository,
        event_publisher: EventPublisher,
    ) -> None:
        self._repository = repository
        self._event_publisher = event_publisher

    async def register_project(self, command: RegisterProjectCommand) -> Project:
        project = Project(
            name=command.name,
            root_location=command.root_location,
            adapter_type=command.adapter_type,
            capabilities=frozenset(command.capabilities),
        )
        await self._repository.add(project)
        await self._event_publisher.publish(
            DomainEvent(
                event_type=EventType.PROJECT_REGISTERED,
                source="application.projects",
                project_id=project.id,
                payload={
                    "project_id": str(project.id),
                    "name": project.name,
                    "adapter_type": project.adapter_type,
                },
            )
        )
        return project

