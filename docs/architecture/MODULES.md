# OrchAI --- Modules

## Purpose

This document describes the Module concept introduced by ADR-015: how
OrchAI Desktop organizes specialized experiences (Forge, Studio, and
future modules) on top of the shared orchestration core, and how to add
a new one.

## What a Module Is

A Module is a code-defined bundle of configuration that focuses the
general OrchAI chat/orchestration layer toward one kind of work. It is
not a domain aggregate with its own persistence or lifecycle --- it is
architecture-shaped configuration, defined the same way `RoleName` and
`ActionName` are: a closed vocabulary in code, reviewed like any other
architectural change, not editable at runtime.

```text
domain/modules/entities.py
  ModuleId (domain/identifiers.py)
  ModuleDefinition:
    id, name, description, system_prompt
    default_role: RoleName
    allowed_roles: frozenset[RoleName]
    allowed_actions: frozenset[ActionName]
    suggested_models: tuple[str, ...]
    project_adapter_kind: "local_filesystem" | "media_workspace" | "none"
    task_pipeline_mode: "full_workflow"
                       | "conversational_with_protected_operations"
                       | "conversational_only"
    requires_project: bool
```

`application/modules/registry.py` holds the static `ModuleRegistry`
(`ModuleId → ModuleDefinition`), assembled once in `bootstrap/runtime.py`
alongside `provider_from_settings()`.

## Current Modules

### Forge

```text
project_adapter_kind:  local_filesystem
task_pipeline_mode:    full_workflow
```

Code-focused: connects to a local project/folder to analyze, document,
maintain, and continue development. Maps directly onto the existing
Task/Role/Action/Execution/Authorization pipeline
(`PLAN → IMPLEMENT → REVIEW → VALIDATE → TEST → DOCUMENT`, driven by
`application/orchestration/orchestrator.py`) and the existing
`infrastructure/projects/local_filesystem.py` `ProjectAdapter`.
Requires nothing new in `domain/` or `application/executions|projects`.

### Studio

```text
project_adapter_kind:  media_workspace
task_pipeline_mode:    conversational_with_protected_operations
```

Multimedia planning, generation, and manipulation: connects to folders,
attaches and reads files. Uses `infrastructure/projects/media_workspace.py`
(`MediaWorkspaceProjectAdapter`) -- discovers files and classifies them
by `media_type` (`image`/`audio`/`video`/`text`/`other`) rather than by
source-code role; `read_context` returns real text for text-like files
and a plain `"[<type> file, N bytes -- binary content not inlined]"`
description for binary media (no multimodal provider integration yet).
`RUN_TESTS`/`RUN_COMMANDS`/`ACCESS_GIT` are simply never exposed, per
`ADAPTER-CONTRACTS.md`; `WRITE_SOURCE` is reused (not a new capability)
for saving a generated asset back into the project.

`GET /projects/{project_id}/attachments` exposes discovery
independently of the project's registered `adapter_type` -- Studio
browses the same connected folder Forge sees, just through
`MediaWorkspaceProjectAdapter` instead of `LocalFilesystemProjectAdapter`,
without touching project registration, the `ProjectAdapterRegistry`, or
the Orchestrator at all. Phase 6's scope is this discovery-plus-chat
skeleton; the "one protected operation" (persisting a generated asset,
reusing `POST /projects/operations` / `ProjectOperation` per
`CHAT-FIRST-REQUEST-MODEL.md` §8) is designed but not yet wired to a UI
action.

Studio's Role/Action vocabulary (how `RoleName`/`ActionName` apply to a
non-development domain) was resolved for Phase 6 by reusing the
existing `TASK_PLANNER`/`PLAN` pair unchanged, rather than introducing
a new role -- see ADR-015's "Implementation Note (Phase 6)". Whether a
dedicated vocabulary (e.g. `RoleName.CREATOR`) is worth introducing
remains open for whenever Studio needs an action `PLAN` cannot
reasonably describe.

## Discovery

```text
GET  /modules            List module metadata (never the raw system_prompt)
GET  /modules/{id}       One module's metadata
orchai modules list      CLI equivalent
```

The desktop frontend builds its module switcher/sidebar entirely from
this response --- no module name beyond a generic "Chat" (general layer,
no module, no project selected) is hardcoded in the frontend.

## Relationship to Conversations

Every `Conversation` (ADR-014) is scoped to exactly one `module_id`.
The module's `system_prompt` and `suggested_models` inform how a new
conversation in that module is initialized; the module's
`allowed_roles`/`allowed_actions` bound which `/requests` calls a
message in that conversation may escalate to (ADR-014 §2).

## Adding a New Module

1. Define a new `ModuleDefinition` in `application/modules/registry.py`.
2. If the module needs a new kind of project connection, implement a
   new `ProjectAdapter` (`application/projects/ports.py` contract) and
   reference it via a new `project_adapter_kind` literal.
3. Decide `task_pipeline_mode`: reuse `full_workflow` if the module
   fits the existing PLAN..DOCUMENT pipeline unchanged; reuse
   `conversational_with_protected_operations` if it needs occasional
   authorized project writes without the full pipeline; use
   `conversational_only` if it never touches a project at all.
4. If the module's work doesn't fit the existing `RoleName`/
   `ActionName` vocabulary, propose the vocabulary change in its own
   ADR before wiring the module to use it --- per ADR-015 §5, this is
   never folded into the module's own definition change.
5. No change to `Task`, `Execution`, `Authorization`, or the
   Orchestrator's state machine should ever be required just to add a
   module. If one seems necessary, treat that as a signal the module
   concept itself needs revisiting, not that the exception is
   acceptable.

## Invariants

1. `ModuleDefinition` is immutable, code-defined, and enumerated by
   `ModuleRegistry` --- no runtime API creates, edits, or deletes one.
2. A module's `system_prompt` is never exposed through the module
   discovery endpoints.
3. No module may bypass `Authorization`/policy/suggestion enforcement;
   `task_pipeline_mode` only selects which existing mechanism applies.
