"""Compatibility facade for the initial local orchestration flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orchai.application.orchestration.orchestrator import (
    AutomaticExecutionPolicy,
    Orchestrator,
    RunProjectOperationCommand,
    RunLocalFlowCommand,
)
from orchai.domain.projects import ProviderTarget
from orchai.domain.projects import ProjectOperation
from orchai.domain.tasks import ExecutionMode


async def run_local_flow(
    *,
    project_root: Path,
    context_path: str,
    title: str,
    model: str,
    dependencies: LocalFlowDependencies,
    storage_label: str = "provided",
    provider_target: ProviderTarget = ProviderTarget.LOCAL,
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED,
    approve_suggestion: bool = False,
    automatic_policy: AutomaticExecutionPolicy | None = None,
) -> dict[str, str]:
    """Run a minimal authorized task/execution/context flow."""

    result = await dependencies.orchestrator.run_local_flow(
        RunLocalFlowCommand(
            project_root=project_root,
            context_path=context_path,
            title=title,
            model=model,
            storage_label=storage_label,
            provider_target=provider_target,
            execution_mode=execution_mode,
            approve_suggestion=approve_suggestion,
            automatic_policy=automatic_policy or AutomaticExecutionPolicy(),
        )
    )
    return result.as_dict()


async def run_project_operation(
    *,
    project_root: Path,
    operation: ProjectOperation,
    title: str,
    dependencies: LocalFlowDependencies,
    storage_label: str = "provided",
    resource: str = "",
    content: str = "",
    command: tuple[str, ...] = (),
    test_args: tuple[str, ...] = (),
    model: str = "local-project-operation",
    provider_target: ProviderTarget = ProviderTarget.LOCAL,
    execution_mode: ExecutionMode = ExecutionMode.SUGGESTED,
    approve_operation: bool = False,
    automatic_policy: AutomaticExecutionPolicy | None = None,
) -> dict[str, str]:
    """Run a protected project-adapter operation."""

    result = await dependencies.orchestrator.run_project_operation(
        RunProjectOperationCommand(
            project_root=project_root,
            operation=operation,
            title=title,
            storage_label=storage_label,
            resource=resource,
            content=content,
            command=command,
            test_args=test_args,
            model=model,
            provider_target=provider_target,
            execution_mode=execution_mode,
            approve_operation=approve_operation,
            automatic_policy=automatic_policy or AutomaticExecutionPolicy(),
        )
    )
    return result.as_dict()


@dataclass(frozen=True, slots=True)
class LocalFlowDependencies:
    orchestrator: Orchestrator
