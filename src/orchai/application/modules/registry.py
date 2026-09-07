"""Static Module registry (ADR-015).

Assembled once, at import time, from code -- not settings or the
database, since a `ModuleDefinition` is architecture-shaped
configuration (see `domain/modules/entities.py`). Adding a module is a
code change here, reviewed like any other, per
`docs/architecture/MODULES.md`.
"""

from __future__ import annotations

from orchai.domain.actions import ActionName
from orchai.domain.identifiers import ModuleId
from orchai.domain.modules import ModuleDefinition
from orchai.domain.roles import RoleName

FORGE = ModuleDefinition(
    id=ModuleId("forge"),
    name="Forge",
    description=(
        "Code-focused module: connect a local project or folder to "
        "analyze, document, maintain, and continue its development."
    ),
    system_prompt=(
        "You are OrchAI Forge, a focused software development assistant "
        "operating on a connected local project. Stay within the "
        "project's existing conventions and architecture. Any change to "
        "the project's files must go through OrchAI's Task/Authorization "
        "pipeline as a suggestion the user explicitly approves -- never "
        "assume approval, and never bypass the review/validate/test "
        "stages that apply to the requested change."
    ),
    default_role=RoleName.TASK_PLANNER,
    allowed_roles=frozenset(RoleName),
    allowed_actions=frozenset(ActionName),
    suggested_models=(
        "ollama/qwen2.5-coder:latest",
        "anthropic/claude-sonnet-4-5",
        "openai/gpt-5",
    ),
    project_adapter_kind="local_filesystem",
    task_pipeline_mode="full_workflow",
    requires_project=True,
)

STUDIO = ModuleDefinition(
    id=ModuleId("studio"),
    name="Studio",
    description=(
        "Multimedia planning module: connect a folder, attach and "
        "discuss files, and plan or produce visual, audio, or written "
        "assets."
    ),
    system_prompt=(
        "You are OrchAI Studio, an assistant for multimedia planning and "
        "generation. Discuss the attached files and help plan or "
        "describe visual, audio, or written assets. Saving anything back "
        "into the connected project is a protected operation requiring "
        "explicit user approval -- never assume it is authorized."
    ),
    # ADR-015 §5 leaves Studio's own Role/Action vocabulary (e.g. a
    # dedicated RoleName.CREATOR) as an open decision requiring its own
    # explicit approval before implementation. Phase 6 deliberately does
    # not make that decision: it reuses the existing TASK_PLANNER/PLAN
    # pair -- the same one the protected-operation bootstrap hop already
    # uses for Forge (`docs/architecture/CHAT-FIRST-REQUEST-MODEL.md`
    # §8) -- so Studio's conversational skeleton and its one protected
    # "save an asset" operation both stay expressible without
    # introducing any new shared vocabulary. Revisit once Studio needs
    # an action `PLAN` cannot reasonably describe.
    default_role=RoleName.TASK_PLANNER,
    allowed_roles=frozenset({RoleName.TASK_PLANNER}),
    allowed_actions=frozenset({ActionName.PLAN}),
    suggested_models=(
        "openai/gpt-5",
        "anthropic/claude-sonnet-4-5",
    ),
    project_adapter_kind="media_workspace",
    task_pipeline_mode="conversational_with_protected_operations",
    requires_project=True,
)

MODULE_REGISTRY: dict[ModuleId, ModuleDefinition] = {
    module.id: module for module in (FORGE, STUDIO)
}


def list_modules() -> tuple[ModuleDefinition, ...]:
    """Return every registered module, in registration order."""

    return tuple(MODULE_REGISTRY.values())


def get_module(module_id: ModuleId) -> ModuleDefinition | None:
    """Return one registered module, or `None` if unknown."""

    return MODULE_REGISTRY.get(module_id)
