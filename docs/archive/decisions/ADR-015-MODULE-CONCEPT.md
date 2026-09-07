# ADR-015 --- Module Concept (Forge, Studio, and Future Modules)

## Status

Accepted --- Implemented. Phase 2 (Forge) landed with the LiteLLM/
conversation/streaming/escalation phases; Phase 6 (Studio skeleton)
adds `infrastructure/projects/media_workspace.py` and the `STUDIO`
`ModuleDefinition`. See `docs/architecture/DESKTOP-APPLICATION.md` and
the companion `docs/architecture/MODULES.md`, and the "Implementation
Note (Phase 6)" below for how §5's open question was resolved for now.

## Context

OrchAI Desktop is structured as a general layer (chat, conversation and
project management, a single local user profile, metrics/audit) plus
specialized **Modules** the user selects when starting or continuing
work --- analogous to the distinction between a general chat product and
a code-specialized one in comparable tools. Two modules are defined now:

- **Forge** --- code-focused: connects to a local project/folder to
  analyze, document, maintain, and continue development. This maps
  directly onto the existing Task/Role/Action/Execution/Authorization
  pipeline (`PLAN → IMPLEMENT → REVIEW → VALIDATE → TEST → DOCUMENT`,
  `application/orchestration/orchestrator.py`) and the existing
  `infrastructure/projects/local_filesystem.py` `ProjectAdapter`.
- **Studio** --- multimedia planning, generation, and manipulation:
  connects to folders, attaches and reads files. Nothing in the current
  codebase serves this today; it needs a new `ProjectAdapter`.

The architecture must let a third, fourth, or later module be added
without a fundamental redesign, per `ARCHITECTURAL-CONTRACT.md` §2.19
(Extensibility) and §2.17 (Model Agnosticism, extended here to module
scope).

A subordinate question this ADR must resolve: `RoleName`
(`domain/roles/names.py`: `TASK_PLANNER`, `DEVELOPER`, `QUALITY_AGENT`)
and `ActionName` (`domain/actions/names.py`: `PLAN`, `IMPLEMENT`, `FIX`,
`REFACTOR`, `REVIEW`, `VALIDATE`, `TEST`, `DOCUMENT`) are a
software-development-shaped vocabulary. Studio's domain (multimedia)
does not map onto it naturally, but multiplying a second, parallel
vocabulary per module risks fragmenting the orchestration model that
`ARCHITECTURAL-CONTRACT.md` §2.4 requires to stay a single, independent
Role/Action/Model system.

## Decision

1. **`ModuleDefinition` is a code-level, closed vocabulary artifact**,
   not a database-backed configurable entity --- the same treatment
   already given to `RoleName`/`ActionName`. It is architecture/product
   configuration, not transactional data:

   ```python
   # domain/modules/entities.py
   ModuleId(Identifier)   # domain/identifiers.py

   @dataclass(frozen=True, slots=True)
   class ModuleDefinition:
       id: ModuleId
       name: str
       description: str
       system_prompt: str
       default_role: RoleName
       allowed_roles: frozenset[RoleName]
       allowed_actions: frozenset[ActionName]
       suggested_models: tuple[str, ...]
       project_adapter_kind: Literal["local_filesystem", "media_workspace", "none"]
       task_pipeline_mode: Literal[
           "full_workflow",                       # Forge: full PLAN..DOCUMENT pipeline
           "conversational_with_protected_operations",  # Studio: chat + gated save/persist ops
           "conversational_only",                 # a future module with no project pipeline at all
       ]
       requires_project: bool
   ```

2. **A static registry, assembled at bootstrap.**
   `application/modules/registry.py` defines `ModuleRegistry`, a plain
   mapping of `ModuleId → ModuleDefinition` constructed once in
   `bootstrap/runtime.py` alongside `provider_from_settings()`. Adding a
   module is a code change to this registry, not a runtime
   configuration operation --- consistent with how `RoleName`/
   `ActionName` are extended today. `ARCHITECTURAL-CONTRACT.md` §2.19
   already anticipates "additional roles," "additional actions," and
   now "additional modules" as the same category of accepted future
   extension.

3. **Forge reuses the existing pipeline and adapter unchanged.**
   `project_adapter_kind="local_filesystem"`,
   `task_pipeline_mode="full_workflow"`. No changes to
   `local_filesystem.py`, the Orchestrator, or the Task/Role/Action
   vocabulary are required for Forge.

4. **Studio gets a new adapter, and reuses the existing "protected
   operation" mechanism instead of a new domain concept.**
   `project_adapter_kind="media_workspace"` names a new
   `infrastructure/projects/media_workspace.py` `ProjectAdapter`
   implementation (discover/read/write for media and attachment types;
   `run_tests`/`git_status` capabilities simply not exposed, per
   `ADAPTER-CONTRACTS.md`'s "only supported capabilities should be
   exposed"). Most Studio interaction is conversational
   (`task_pipeline_mode="conversational_with_protected_operations"`);
   the one operation that must be authorized and audited --- persisting
   a generated asset into the connected project --- reuses the existing
   `POST /projects/operations` / `ProjectOperation` mechanism
   documented in `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` §8,
   rather than inventing a parallel authorization path for Studio.

5. **Role/Action vocabulary for Studio is deferred to its own decision,
   not resolved here.** The recommended direction --- adding
   `RoleName.CREATOR` and reusing `IMPLEMENT` ("produce an artifact"),
   `REVIEW` ("critique/iterate"), and `DOCUMENT` ("annotate an asset")
   rather than a second action vocabulary --- is recorded here as a
   recommendation only. Because it changes a shared vocabulary that
   `AutomaticExecutionPolicy` and every `Authorization` record already
   depend on, it requires its own explicit approval and its own ADR
   before implementation, per `ARCHITECTURAL-CONTRACT.md` §5 (a
   conflicting future decision must be explicitly resolved, not
   silently folded into an unrelated change). Studio's Phase 6
   implementation (`docs/architecture/DESKTOP-APPLICATION.md`) must not
   proceed past its conversational skeleton until this sub-decision is
   made.

6. **Discovery is dynamic on the client side.** `GET /modules` (list,
   metadata only --- never the raw `system_prompt`) and
   `GET /modules/{id}`; CLI `orchai modules list`. The desktop frontend
   builds its module switcher/sidebar from this response; no module
   name beyond a generic "Chat" (general layer, no module, no project)
   is hardcoded in the frontend.

## Rationale

- **Code-level registry, not a database table**: modules define system
  prompts, allowed roles/actions, and adapter wiring --- all
  architecture-shaped decisions that belong under review and version
  control, the same way `RoleName`/`ActionName` already do, not
  runtime-editable data a user could silently drift out of sync with
  the orchestration rules that depend on it.
- **Reusing `ProjectOperation` for Studio's protected save step** avoids
  a second authorization/audit pathway solely for multimedia
  persistence, keeping `ARCHITECTURAL-CONTRACT.md` §2.15
  (Auditability) uniform across modules.
- **Deferring the Role/Action vocabulary question** keeps this ADR
  scoped to the module *mechanism*; the vocabulary question has its own
  blast radius (`AutomaticExecutionPolicy`, every future `Authorization`
  record) and deserves independent scrutiny and explicit user
  authorization, consistent with how the deeper multi-user
  authorization refactor was deliberately gated in `docs/TO-DO.md`.

## Consequences

Positive:

- Forge ships with zero changes to already-implemented, tested domain
  code;
- a third module can be added later by writing one `ModuleDefinition`
  and, if needed, one new `ProjectAdapter` --- no change to
  `Task`/`Execution`/`Authorization`;
- the module boundary gives each specialized experience its own system
  prompt and suggested-model list without touching the shared
  orchestration core.

Trade-offs:

- Studio cannot reach full workflow parity with Forge until the
  Role/Action vocabulary question (point 5) is explicitly resolved;
  its Phase 6 scope is deliberately limited to a conversational
  skeleton plus the existing protected-operation mechanism until then;
- a code-level registry means adding a module requires a code change
  and review, not a configuration change --- an intentional trade-off
  favoring architectural review over runtime flexibility.

## Invariants

1. `ModuleDefinition` instances are immutable and defined in code; no
   runtime API creates or mutates a module.
2. A module's `system_prompt` is never exposed through `GET /modules`
   or `GET /modules/{id}` --- only display metadata.
3. Forge's `project_adapter_kind`/`task_pipeline_mode` never diverge
   from the existing `local_filesystem` adapter and `full_workflow`
   pipeline without a superseding ADR.
4. No module may bypass `Authorization`/policy/suggestion enforcement;
   a module's `task_pipeline_mode` selects which existing mechanism
   applies (full workflow vs. protected operation), never a shortcut
   around either.

## Implementation Note (Phase 6): Studio's Role/Action vocabulary

§5 above named a dedicated `RoleName.CREATOR` as the recommended
long-term direction but explicitly deferred it pending the user's own
approval. Asked directly during Phase 6, the user chose the minimal
option instead: `STUDIO.default_role`/`allowed_roles`/`allowed_actions`
reuse the existing `TASK_PLANNER`/`PLAN` pair unchanged --- the same
pair the protected-operation bootstrap hop already uses for Forge
(`docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` §8). No new
`RoleName`/`ActionName` member was introduced. This keeps Studio's
Phase 6 scope (conversational skeleton plus attachment discovery) fully
expressible without touching the shared Role/Action vocabulary at all,
and keeps the `RoleName.CREATOR` question open and unresolved for
whenever Studio needs an action `PLAN` cannot reasonably describe ---
this note does not close §5, it only records what Phase 6 itself
needed.

## Supersedes

None. Extends ADR-011 (Chat-First Request Interface) and
`docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` §8 (protected project
operations) to a multi-module context, and depends on ADR-014 for how
conversations are scoped to a module.
