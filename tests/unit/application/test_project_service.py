import asyncio

from orchai.application.events import InProcessEventDispatcher
from orchai.application.projects import ProjectService, RegisterProjectCommand
from orchai.domain.capabilities import CapabilityName
from orchai.domain.events import EventType
from orchai.infrastructure.persistence import InMemoryProjectRepository


def test_project_service_registers_external_project_metadata() -> None:
    async def run() -> None:
        repository = InMemoryProjectRepository()
        events = InProcessEventDispatcher()
        service = ProjectService(repository=repository, event_publisher=events)

        project = await service.register_project(
            RegisterProjectCommand(
                name="Example",
                root_location="E:/external/example",
                capabilities=(CapabilityName.READ_PROJECT,),
            )
        )

        assert (await repository.get(project.id)).name == "Example"
        assert project.capabilities == frozenset({CapabilityName.READ_PROJECT})
        assert events.published_events[0].event_type is EventType.PROJECT_REGISTERED

    asyncio.run(run())

