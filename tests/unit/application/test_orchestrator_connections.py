import asyncio
import subprocess

from orchai.application.events import InProcessEventDispatcher
from orchai.application.orchestration.connections import (
    connect_project,
    connect_registered_project,
    run_adapter_operation,
)
from orchai.application.orchestration.orchestrator import RunProjectOperationCommand
from orchai.application.projects import ProjectService
from orchai.domain.events import EventType
from orchai.domain.projects import ProjectOperation, ProjectReadinessLevel
from orchai.infrastructure.persistence import InMemoryProjectRepository
from orchai.infrastructure.projects import (
    InMemoryProjectAdapterRegistry,
    LocalFilesystemProjectAdapter,
)


def test_connect_project_registers_using_freshly_observed_readiness(tmp_path) -> None:
    async def run() -> None:
        (tmp_path / ".git").mkdir()
        (tmp_path / "README.md").write_text("# Docs", encoding="utf-8")
        events = InProcessEventDispatcher()
        project_service = ProjectService(
            repository=InMemoryProjectRepository(),
            event_publisher=events,
        )

        adapter, readiness, project = await connect_project(
            create_project_adapter=LocalFilesystemProjectAdapter,
            project_service=project_service,
            event_publisher=events,
            project_root=tmp_path,
        )

        assert isinstance(adapter, LocalFilesystemProjectAdapter)
        assert project.readiness_level == readiness.readiness_level
        assert project.observed_readiness_level == readiness.readiness_level
        assert any(
            event.event_type is EventType.PROJECT_READINESS_ASSESSED
            for event in events.published_events
        )

    asyncio.run(run())


def test_connect_registered_project_keeps_effective_readiness_but_refreshes_observed(
    tmp_path,
) -> None:
    async def run() -> None:
        events = InProcessEventDispatcher()
        project_service = ProjectService(
            repository=InMemoryProjectRepository(),
            event_publisher=events,
        )
        project_adapters = InMemoryProjectAdapterRegistry()

        # First connect happens with no .git yet -- LEVEL_0_CONNECTABLE is
        # persisted as this project's *effective* readiness.
        _, _, first_project = await connect_project(
            create_project_adapter=LocalFilesystemProjectAdapter,
            project_service=project_service,
            event_publisher=events,
            project_root=tmp_path,
        )
        assert first_project.readiness_level == ProjectReadinessLevel.LEVEL_0_CONNECTABLE

        # The folder gains a .git directory afterwards, purely on disk --
        # ProjectService.register_project() never changes an already-known
        # project's *effective* readiness on its own (only an explicit
        # UpdateProjectSecurityCommand does that); a reconnect's fresh
        # assessment should only ever update the *observed* fields.
        (tmp_path / ".git").mkdir()

        adapter, refreshed = await connect_registered_project(
            create_project_adapter=LocalFilesystemProjectAdapter,
            project_service=project_service,
            project_adapters=project_adapters,
            event_publisher=events,
            project_id=first_project.id,
        )

        assert isinstance(adapter, LocalFilesystemProjectAdapter)
        assert refreshed.readiness_level == ProjectReadinessLevel.LEVEL_0_CONNECTABLE
        assert refreshed.observed_readiness_level == ProjectReadinessLevel.LEVEL_1_CHANGEABLE
        assert await project_adapters.get(refreshed.id) is adapter

    asyncio.run(run())


def test_run_adapter_operation_write_source(tmp_path) -> None:
    async def run() -> None:
        adapter = LocalFilesystemProjectAdapter(tmp_path)
        command = RunProjectOperationCommand(
            project_root=tmp_path,
            operation=ProjectOperation.WRITE_SOURCE,
            title="Write test",
            storage_label="memory",
            resource="src/generated.py",
            content="print('hi')\n",
        )

        result = await run_adapter_operation(adapter, command)

        assert result["resource"] == "src/generated.py"
        assert (tmp_path / "src" / "generated.py").read_text(encoding="utf-8") == (
            "print('hi')\n"
        )

    asyncio.run(run())


def test_run_adapter_operation_git_status(tmp_path) -> None:
    async def run() -> None:
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        adapter = LocalFilesystemProjectAdapter(tmp_path)
        command = RunProjectOperationCommand(
            project_root=tmp_path,
            operation=ProjectOperation.GIT_STATUS,
            title="Git status test",
            storage_label="memory",
        )

        result = await run_adapter_operation(adapter, command)

        assert "branch" in result
        assert "is_dirty" in result

    asyncio.run(run())


def test_run_adapter_operation_rejects_an_unsupported_operation(tmp_path) -> None:
    async def run() -> None:
        adapter = LocalFilesystemProjectAdapter(tmp_path)
        command = RunProjectOperationCommand(
            project_root=tmp_path,
            operation=ProjectOperation.READ_CONTEXT,
            title="Unsupported",
            storage_label="memory",
        )

        try:
            await run_adapter_operation(adapter, command)
            raise AssertionError("expected ValueError")
        except ValueError as exc:
            assert "unsupported project operation" in str(exc)

    asyncio.run(run())
