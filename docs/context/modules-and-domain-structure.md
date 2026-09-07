# Modules And Domain Structure

## Purpose

Defines the physical source-tree organization of the OrchAI modular
monolith, the domain-purity rules that keep it that way, and the
Module concept (Forge, Studio, and future modules) that lets the
desktop client specialize the shared orchestration core.

## Objective

Keep one domain rule owned by exactly one module, keep infrastructure
out of the domain entirely, and let a new specialized experience (a
Module) be added through pure configuration rather than a change to
Task/Execution/Authorization or the Orchestrator's state machine.

## Current Status

`implemented`

## Repository Layout

```text
src/
└── orchai/
    ├── domain/          tasks/ executions/ authorization/ policies/ roles/
    │                    actions/ models/ context/ projects/ capabilities/ events/
    ├── application/      tasks/ executions/ orchestration/ agents/ models/
    │                    context/ projects/ events/
    ├── infrastructure/   persistence/ messaging/ ai/ projects/ filesystem/
    │                    configuration/ observability/
    ├── interfaces/       api/ cli/
    └── bootstrap/
```

Empty modules are not created merely to match this diagram — a
directory becomes implementation-relevant only when a concrete
responsibility exists. This applies Clean/Hexagonal Architecture
principles without requiring every logical component to become an
independent package or service; these are logical boundaries inside
one deployable application, never independent processes or
microservices unless a future architectural decision explicitly
introduces service decomposition.

## Dependency Direction

```text
Interfaces → Application → Domain
Infrastructure → Domain / Application Contracts
Bootstrap → Everything required to compose the runtime
```

Domain code never imports infrastructure implementations, FastAPI,
Typer, SQLAlchemy, HTTPX, provider SDKs, or filesystem/database
drivers. The composition root (`bootstrap/`) loads configuration,
constructs dependencies, selects implementations, initializes
infrastructure, and starts the runtime.

## Domain Purity And Cross-Domain References

Each domain module (Task, Execution, Role, Action, Model,
Authorization, Policy, Context, Project, Capability, Event) owns the
rules of its own concept; application orchestration must not duplicate
domain invariants. Task and Execution state machines live with their
respective lifecycle domains (`domain/tasks/`, `domain/executions/`),
deterministic and independently testable — a completed Task cannot
move to an earlier state, and a terminal Execution cannot become
completed, unless the respective State Machine explicitly defines that
transition. Cross-domain references prefer stable identifiers and
explicit contracts over cyclic object graphs (e.g. `Execution →
TaskId/RoleId/ActionId/ModelId/ProjectId/AuthorizationId`). The domain
represents the concept of a Project and context requirements/
authorization scope/references/resolved metadata — it never owns the
project's source tree, documentation, or external artifacts, and
complete project content is never a required domain persistence
concern.

## Implementation Boundary Mapping

The logical components described across `docs/context/*.md` map to
the physical architecture as follows:

| Logical Component | Primary Layer | Typical Module |
|---|---|---|
| Task Engine | Application | `application/tasks/` |
| Execution Engine | Application | `application/executions/` |
| Orchestration | Application | `application/orchestration/` |
| Agent Coordination | Application | `application/agents/` |
| Model Manager | Application | `application/models/` |
| Context Manager | Application | `application/context/` |
| Project Coordination | Application | `application/projects/` |
| Event Coordination | Application | `application/events/` |
| Task State Machine | Domain | `domain/tasks/` |
| Execution State Machine | Domain | `domain/executions/` |
| Authorization | Domain + Application | `domain/authorization/` |
| Policies | Domain + Application | `domain/policies/` |
| Roles / Actions / Models | Domain | `domain/roles/`, `domain/actions/`, `domain/models/` |
| Context / Projects / Capabilities | Domain | `domain/context/`, `domain/projects/`, `domain/capabilities/` |
| Events | Domain | `domain/events/` |
| Persistence | Infrastructure | `infrastructure/persistence/` |
| AI Providers | Infrastructure | `infrastructure/ai/` |
| Project Adapters | Infrastructure | `infrastructure/projects/` |
| Observability | Infrastructure | `infrastructure/observability/` |
| API / CLI | Interfaces | `interfaces/api/`, `interfaces/cli/` |
| Composition Root | Bootstrap | `bootstrap/` |

This mapping is intentionally not one-to-one — a logical component may
span multiple layers when its domain contract, application
coordination, and infrastructure implementation are separate concerns.

## The Module Concept (ADR-015)

A Module is a code-defined bundle of configuration that focuses the
general OrchAI chat/orchestration layer toward one kind of work — not
a domain aggregate with its own persistence or lifecycle, but
architecture-shaped configuration (a closed vocabulary in code,
reviewed like any other architectural change, never editable at
runtime):

```text
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
(`ModuleId → ModuleDefinition`), assembled once in
`bootstrap/runtime.py`.

**Forge** (`local_filesystem` / `full_workflow`): code-focused, maps
directly onto the existing Task/Role/Action/Execution/Authorization
pipeline. **Studio** (`media_workspace` /
`conversational_with_protected_operations`): multimedia
planning/generation, using `MediaWorkspaceProjectAdapter` to discover
and classify files by `media_type` rather than source-code role;
`RUN_TESTS`/`RUN_COMMANDS`/`ACCESS_GIT` are never exposed,
`WRITE_SOURCE` is reused for saving generated assets. Both reuse the
existing `TASK_PLANNER`/`PLAN` pair rather than introducing new
Role/Action vocabulary (see ADR-015's "Implementation Note (Phase
6)"); a dedicated vocabulary remains open for whenever a module needs
an action `PLAN` cannot reasonably describe.

`GET /modules` / `GET /modules/{id}` / `orchai modules list` expose
module metadata (never the raw `system_prompt`) — the desktop frontend
builds its module switcher entirely from this response. Every
`Conversation` is scoped to exactly one `module_id`; the module's
`allowed_roles`/`allowed_actions` bound which `/requests` calls a
message in that conversation may escalate to.

**Adding a new module** never requires changing `Task`, `Execution`,
`Authorization`, or the Orchestrator's state machine — if it seems to,
that's a signal the Module concept itself needs revisiting, not that
the exception is acceptable. A new kind of project connection needs a
new `ProjectAdapter`; new work outside the existing Role/Action
vocabulary needs its own explicit, user-authorized decision (recorded
in this document, not a new module's own definition change) before the
module can use it.

This document folds in the still-relevant decision from the former
ADR-015 (Module Concept) — the Module concept above; full rationale
remains in `docs/archive/decisions/`.

## Key Rules

- one domain module owns each domain rule; infrastructure is never imported by the domain
- cross-domain behavior uses explicit contracts, never cyclic references
- state transitions are controlled only by State Machines
- project content remains external to the OrchAI domain
- `ModuleDefinition` is immutable and code-defined; no runtime API creates, edits, or deletes one
- no module may bypass Authorization/policy/suggestion enforcement — `task_pipeline_mode` only selects which existing mechanism applies

## Main Relationships

- hosts `Tasks And Lifecycle`, `Execution Engine`, and every other domain module physically
- Forge and Studio route through `Project Adapter And Security` via `project_adapter_kind`
- discovered and selected through `Chat-First And Interfaces` (`/modules`) and scoped by Conversation (see `Chat-First And Interfaces`)
