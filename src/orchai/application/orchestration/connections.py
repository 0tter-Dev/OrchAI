"""Project-adapter connection helpers used by the orchestrator.

Extracted (Phase 7.5) from `Orchestrator._connect_project` and
`._connect_registered_project` -- both register a project and announce its
readiness via a domain event, differing only in where the adapter and the
project's *effective* readiness/security fields come from (freshly
observed for a first-time connect, vs. the already-registered project's
own values, refreshed only in their *observed* fields, for a reconnect).
`run_adapter_operation` (formerly `_run_adapter_operation`) moves here
unchanged: it was already a pure, `self`-free function.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from orchai.application.events.ports import EventPublisher
from orchai.application.orchestration.events import publish_project_readiness
from orchai.application.orchestration.ports import ProjectAdapterFactory
from orchai.application.projects import ProjectService, RegisterProjectCommand
from orchai.application.projects.ports import (
    ProjectAdapter,
    ProjectAdapterRegistry,
    ProjectReadinessAssessment,
)
from orchai.domain.identifiers import ProjectId
from orchai.domain.projects import Project

if TYPE_CHECKING:
    # Only for the parameter annotation below -- importing this for real
    # would be circular, since orchestrator.py (where it's defined)
    # imports this module.
    from orchai.application.orchestration.orchestrator import RunProjectOperationCommand


async def connect_project(
    *,
    create_project_adapter: ProjectAdapterFactory,
    project_service: ProjectService,
    event_publisher: EventPublisher,
    project_root: Path,
) -> tuple[ProjectAdapter, ProjectReadinessAssessment, Project]:
    """Register a project for the first time from a filesystem root."""

    adapter = create_project_adapter(project_root)
    readiness = await adapter.assess_readiness()
    project = await _register_and_announce(
        project_service=project_service,
        event_publisher=event_publisher,
        readiness=readiness,
        command=RegisterProjectCommand(
            name=project_root.name,
            root_location=str(project_root),
            capabilities=await adapter.capabilities(),
            readiness_level=readiness.readiness_level,
            security_profile=readiness.security_profile,
            observed_readiness_level=readiness.readiness_level,
            observed_security_profile=readiness.security_profile,
        ),
    )
    return adapter, readiness, project


async def connect_registered_project(
    *,
    create_project_adapter: ProjectAdapterFactory,
    project_service: ProjectService,
    project_adapters: ProjectAdapterRegistry,
    event_publisher: EventPublisher,
    project_id: ProjectId,
) -> tuple[ProjectAdapter, Project]:
    """Reconnect an already-registered project, refreshing its observed state."""

    project = await project_service.get_project(project_id)
    adapter = create_project_adapter(Path(project.root_location))
    readiness = await adapter.assess_readiness()
    refreshed_project = await _register_and_announce(
        project_service=project_service,
        event_publisher=event_publisher,
        readiness=readiness,
        command=RegisterProjectCommand(
            name=project.name,
            root_location=project.root_location,
            capabilities=await adapter.capabilities(),
            readiness_level=project.readiness_level,
            security_profile=project.security_profile,
            observed_readiness_level=readiness.readiness_level,
            observed_security_profile=readiness.security_profile,
        ),
    )
    await project_adapters.register(refreshed_project.id, adapter)
    return adapter, refreshed_project


async def _register_and_announce(
    *,
    project_service: ProjectService,
    event_publisher: EventPublisher,
    command: RegisterProjectCommand,
    readiness: ProjectReadinessAssessment,
) -> Project:
    project = await project_service.register_project(command)
    await publish_project_readiness(
        event_publisher=event_publisher,
        project=project,
        readiness=readiness,
    )
    return project


async def run_adapter_operation(
    adapter: ProjectAdapter,
    command: RunProjectOperationCommand,
) -> dict[str, str]:
    from orchai.domain.context import ContextReference, ContextSource
    from orchai.domain.projects import ProjectOperation

    if command.operation is ProjectOperation.WRITE_SOURCE:
        result = await adapter.write(
            ContextReference(source=ContextSource.SOURCE_FILE, resource=command.resource),
            command.content,
        )
        return {
            "resource": result.resource,
            "bytes_written": str(result.bytes_written),
            "output": f"wrote {result.bytes_written} byte(s)",
        }
    if command.operation is ProjectOperation.WRITE_DOCUMENTATION:
        result = await adapter.write_documentation(
            ContextReference(
                source=ContextSource.PROJECT_DOCUMENTATION,
                resource=command.resource,
            ),
            command.content,
        )
        return {
            "resource": result.resource,
            "bytes_written": str(result.bytes_written),
            "output": f"wrote {result.bytes_written} byte(s)",
        }
    if command.operation is ProjectOperation.RUN_TESTS:
        result = await adapter.run_tests(args=command.test_args)
        return {
            "command": " ".join(result.command),
            "exit_code": str(result.exit_code),
            "output": result.stdout,
            "stderr": result.stderr,
        }
    if command.operation in {
        ProjectOperation.RUN_VALIDATION,
        ProjectOperation.RUN_COMMAND,
    }:
        result = await adapter.run_command(command.command)
        return {
            "command": " ".join(result.command),
            "exit_code": str(result.exit_code),
            "output": result.stdout,
            "stderr": result.stderr,
        }
    if command.operation is ProjectOperation.GIT_STATUS:
        result = await adapter.git_status()
        return {
            "branch": result.branch,
            "is_dirty": str(result.is_dirty),
            "ahead": str(result.ahead),
            "behind": str(result.behind),
            "output": f"branch={result.branch} dirty={str(result.is_dirty).lower()}",
        }
    raise ValueError(f"unsupported project operation: {command.operation.value}")
