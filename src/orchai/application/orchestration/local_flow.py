"""Compatibility facade for the initial local orchestration flow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from orchai.application.orchestration.orchestrator import (
    AutomaticExecutionPolicy,
    Orchestrator,
    RunLocalFlowCommand,
)
from orchai.domain.tasks import ExecutionMode


async def run_local_flow(
    *,
    project_root: Path,
    context_path: str,
    title: str,
    model: str,
    dependencies: LocalFlowDependencies,
    storage_label: str = "provided",
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
            execution_mode=execution_mode,
            approve_suggestion=approve_suggestion,
            automatic_policy=automatic_policy or AutomaticExecutionPolicy(),
        )
    )
    return result.as_dict()


@dataclass(frozen=True, slots=True)
class LocalFlowDependencies:
    orchestrator: Orchestrator
