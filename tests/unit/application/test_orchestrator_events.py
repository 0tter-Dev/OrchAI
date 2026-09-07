import asyncio

from orchai.application.events import InProcessEventDispatcher
from orchai.application.orchestration.events import (
    publish_project_operation_blocked,
    publish_project_operation_completed,
    publish_project_operation_failed,
    publish_project_readiness,
)
from orchai.application.projects.ports import ProjectReadinessAssessment
from orchai.domain.events import EventType
from orchai.domain.identifiers import ProjectId
from orchai.domain.projects import (
    Project,
    ProjectOperation,
    ProjectReadinessLevel,
    ProjectSecurityProfile,
    ProviderTarget,
)


def test_publish_project_readiness_carries_observed_and_effective_levels() -> None:
    async def run() -> None:
        publisher = InProcessEventDispatcher()
        project = Project(
            name="demo",
            root_location="/tmp/demo",
            adapter_type="local_filesystem",
            capabilities=frozenset(),
            readiness_level=ProjectReadinessLevel.LEVEL_2_VALIDATABLE,
        )
        readiness = ProjectReadinessAssessment(
            readiness_level=ProjectReadinessLevel.LEVEL_1_CHANGEABLE,
            security_profile=ProjectSecurityProfile(),
            has_git=True,
            has_documentation=False,
            has_tests=True,
        )

        await publish_project_readiness(
            event_publisher=publisher,
            project=project,
            readiness=readiness,
        )

        assert len(publisher.published_events) == 1
        event = publisher.published_events[0]
        assert event.event_type is EventType.PROJECT_READINESS_ASSESSED
        assert event.project_id == project.id
        assert event.payload["observed_readiness_level"] == "LEVEL_1_CHANGEABLE"
        assert event.payload["effective_readiness_level"] == "LEVEL_2_VALIDATABLE"
        assert event.payload["has_git"] == "True"
        assert event.payload["has_tests"] == "True"

    asyncio.run(run())


def test_publish_project_operation_blocked_carries_the_reason() -> None:
    async def run() -> None:
        publisher = InProcessEventDispatcher()
        project_id = ProjectId.new()

        await publish_project_operation_blocked(
            event_publisher=publisher,
            project_id=project_id,
            readiness="LEVEL_0_CONNECTABLE",
            provider_target=ProviderTarget.LOCAL,
            reason="automatic_policy_denied",
        )

        event = publisher.published_events[0]
        assert event.event_type is EventType.PROJECT_OPERATION_BLOCKED
        assert event.project_id == project_id
        assert event.payload["reason"] == "automatic_policy_denied"
        assert event.payload["provider_target"] == "local"

    asyncio.run(run())


def test_publish_project_operation_completed_merges_the_extra_payload() -> None:
    async def run() -> None:
        publisher = InProcessEventDispatcher()
        project_id = ProjectId.new()

        await publish_project_operation_completed(
            event_publisher=publisher,
            project_id=project_id,
            operation=ProjectOperation.WRITE_SOURCE,
            payload={"resource": "src/app.py", "bytes_written": "12"},
        )

        event = publisher.published_events[0]
        assert event.event_type is EventType.PROJECT_OPERATION_COMPLETED
        assert event.payload["project_operation"] == "WRITE_SOURCE"
        assert event.payload["resource"] == "src/app.py"
        assert event.payload["bytes_written"] == "12"

    asyncio.run(run())


def test_publish_project_operation_failed_carries_operation_and_reason() -> None:
    async def run() -> None:
        publisher = InProcessEventDispatcher()
        project_id = ProjectId.new()

        await publish_project_operation_failed(
            event_publisher=publisher,
            project_id=project_id,
            operation=ProjectOperation.RUN_TESTS,
            reason="tests exited with code 1",
        )

        event = publisher.published_events[0]
        assert event.event_type is EventType.PROJECT_OPERATION_FAILED
        assert event.payload["project_operation"] == "RUN_TESTS"
        assert event.payload["reason"] == "tests exited with code 1"

    asyncio.run(run())
