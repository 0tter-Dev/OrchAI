import asyncio

from orchai.application.events import InProcessEventDispatcher
from orchai.application.projects import (
    ProjectService,
    RegisterProjectCommand,
    UpdateProjectSecurityCommand,
)
from orchai.domain.capabilities import CapabilityName
from orchai.domain.events import EventType
from orchai.domain.projects import ProjectReadinessLevel, ProjectSecurityProfile
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
                readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
                security_profile=ProjectSecurityProfile(
                    readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
                    access_scope=("READ_PROJECT",),
                ),
            )
        )

        assert (await repository.get(project.id)).name == "Example"
        assert project.capabilities == frozenset({CapabilityName.READ_PROJECT})
        assert project.readiness_level is ProjectReadinessLevel.LEVEL_1_CHANGEABLE
        assert (
            project.observed_readiness_level is ProjectReadinessLevel.LEVEL_1_CHANGEABLE
        )
        assert project.security_profile.access_scope == ("READ_PROJECT",)
        assert events.published_events[0].event_type is EventType.PROJECT_REGISTERED
        assert (
            events.published_events[0].payload["readiness_level"]
            == "LEVEL_1_CHANGEABLE"
        )

    asyncio.run(run())


def test_project_service_preserves_effective_profile_when_refreshing_observation() -> None:
    async def run() -> None:
        repository = InMemoryProjectRepository()
        events = InProcessEventDispatcher()
        service = ProjectService(repository=repository, event_publisher=events)

        project = await service.register_project(
            RegisterProjectCommand(
                name="Example",
                root_location="E:/external/example",
                capabilities=(CapabilityName.READ_PROJECT,),
                readiness_level=ProjectReadinessLevel.LEVEL_3_AUTOMATABLE,
                security_profile=ProjectSecurityProfile(
                    readiness_level=ProjectReadinessLevel.LEVEL_3_AUTOMATABLE,
                    allow_cloud_provider_sharing=True,
                ),
            )
        )

        refreshed = await service.register_project(
            RegisterProjectCommand(
                name="Example",
                root_location="E:/external/example",
                capabilities=(CapabilityName.READ_PROJECT,),
                readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
                security_profile=ProjectSecurityProfile(
                    readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
                    allow_cloud_provider_sharing=False,
                ),
                observed_readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
                observed_security_profile=ProjectSecurityProfile(
                    readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
                    allow_cloud_provider_sharing=False,
                ),
            )
        )

        assert refreshed.id == project.id
        assert refreshed.readiness_level is ProjectReadinessLevel.LEVEL_3_AUTOMATABLE
        assert refreshed.observed_readiness_level is ProjectReadinessLevel.LEVEL_1_CHANGEABLE
        assert refreshed.security_profile.allow_cloud_provider_sharing is True
        assert refreshed.observed_security_profile.allow_cloud_provider_sharing is False

    asyncio.run(run())


def test_project_service_updates_persisted_security_profile() -> None:
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

        updated = await service.update_security_profile(
            UpdateProjectSecurityCommand(
                project_id=project.id,
                readiness_level=ProjectReadinessLevel.LEVEL_2_VALIDATABLE,
                access_scope=("READ_PROJECT", "READ_DOCUMENTATION"),
                allow_cloud_provider_sharing=True,
                persist_context_snapshots=True,
            )
        )

        persisted = await repository.get(project.id)
        assert updated.readiness_level is ProjectReadinessLevel.LEVEL_2_VALIDATABLE
        assert persisted.security_profile.allow_cloud_provider_sharing is True
        assert persisted.security_profile.persist_context_snapshots is True
        assert persisted.security_profile.access_scope == (
            "READ_DOCUMENTATION",
            "READ_PROJECT",
        )
        assert (
            events.published_events[-1].event_type
            is EventType.PROJECT_SECURITY_PROFILE_UPDATED
        )

    asyncio.run(run())
