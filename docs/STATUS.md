# OrchAI Project Status

## Purpose

This document provides the high-level state of the OrchAI project.

It is a project-state document, not a task backlog and not a replacement
for architectural documentation.

## Status Vocabulary

  -----------------------------------------------------------------------
  Status                              Meaning
  ----------------------------------- -----------------------------------
  `DEFINED`                           The concept is documented
                                      sufficiently for the current phase.

  `DECIDED`                           An architectural or implementation
                                      decision has been explicitly
                                      accepted.

  `PARTIAL`                           The area is defined or implemented
                                      only in part.

  `IN_PROGRESS`                       Active implementation or refinement
                                      is underway.

  `IMPLEMENTED`                       The current intended scope is
                                      implemented and validated.

  `BLOCKED`                           Progress depends on an unresolved
                                      external or architectural issue.

  `PENDING`                           Intentionally deferred to a later
                                      phase.
  -----------------------------------------------------------------------

## Current State

Current version: `v0.2.0`

  Area                                 Status
  ------------------------------------ -----------
  Architectural Contract               `DEFINED`
  High-Level Architecture              `DEFINED`
  Component Boundaries                 `DEFINED`
  Implementation Map                   `DEFINED`
  Core Domain Model                    `IMPLEMENTED`
  Authorization                        `IMPLEMENTED`
  Task Lifecycle                       `IMPLEMENTED`
  Execution Model                      `IMPLEMENTED`
  Event Model                          `IMPLEMENTED`
  Roles and Actions                    `IMPLEMENTED`
  Models and Providers                 `IMPLEMENTED`
  Context Management                   `IMPLEMENTED`
  Project Integration                  `IMPLEMENTED`
  Capabilities                         `IMPLEMENTED`
  Audit and Metrics                    `IMPLEMENTED`
  Suggestions                          `IMPLEMENTED`
  Configuration                        `IMPLEMENTED`
  Modular Monolith Structure           `DECIDED`
  Physical Repository Structure        `DECIDED`
  Technology Stack                     `DECIDED`
  Persistence Strategy                 `IMPLEMENTED`
  Event Dispatch Strategy              `DECIDED`
  Async Execution Baseline             `DECIDED`
  AI Provider Boundary                 `DECIDED`
  Project Content Ownership Boundary   `DECIDED`
  Project Security / Readiness Gates   `IMPLEMENTED`
  API/UI Boundary                      `DECIDED`
  Chat-First Request Interface         `DECIDED`
  Identity and Access Management       `IMPLEMENTED`
  Execution Mode Baseline              `IMPLEMENTED`
  AI Provider Adapter (LiteLLM)        `IMPLEMENTED`
  AI Provider Streaming (execute_stream) `IMPLEMENTED` (unwired -- no Task-bounded caller yet)
  Conversation Domain Model            `IMPLEMENTED` (streaming)
  Module Concept (Forge, Studio)       `IMPLEMENTED` (Forge only)
  Desktop Single-User Identity         `IMPLEMENTED`
  Desktop Application Shell            `IMPLEMENTED` (Phases 1--5)
  Forge Task Escalation (Approval Card) `IMPLEMENTED`
  Application Implementation           `IN_PROGRESS`
  Domain Implementation                `IMPLEMENTED`
  Infrastructure Implementation        `IN_PROGRESS`
  API Implementation (operational)     `IMPLEMENTED`
  API Implementation (chat-first)      `IMPLEMENTED`
  CLI Implementation                   `IMPLEMENTED`
  Automated Test Suite                 `IMPLEMENTED`
  Deployment Implementation            `PENDING`

## Current Phase

**Phase: OrchAI Desktop --- Phases 1--7 Implemented (post-v0.1.11)**

The project's direction changed materially after v0.1.11: OrchAI is
becoming a Windows desktop chat application with a general layer and
specialized Modules (Forge, Studio), rather than a backend awaiting an
unspecified future client. Five design decisions were accepted to
enable this --- ADR-013 (LiteLLM provider adapter and streaming),
ADR-014 (Conversation/Message domain model), ADR-015 (the Module
concept), ADR-016 (single local user identity for the desktop shell),
and ADR-017 (the `pywebview` desktop shell itself) --- along with two
new documents: `docs/VISION.md` (the product-level narrative that did
not previously exist anywhere) and
`docs/architecture/DESKTOP-APPLICATION.md` (the phased implementation
plan). `docs/architecture/MODULES.md` documents the Module registry
mechanism. See `docs/decisions/INDEX.md` for all five ADRs and
`docs/TO-DO.md`'s "OrchAI Desktop Initiative" section for how this
reconciles with the pre-existing backlog (the previously planned manual
Anthropic adapter is now obsolete, superseded by LiteLLM; execution
cancellation is resequenced to follow streaming).

Phases 1 through 3 of `docs/architecture/DESKTOP-APPLICATION.md` are
now implemented and verified end-to-end (headless smoke tests, the
automated suite, and a real `pywebview`/browser click-through):

- **Phase 1 --- shell skeleton.** `apps/desktop/shell/` starts the
  existing `create_app()` in-process on a free `127.0.0.1` port,
  provisions the single local user (ADR-016) silently, and opens a
  native `pywebview` window. `interfaces/api/main.py::create_app()`
  gained a conditional `StaticFiles` mount at `/app` (not `/`, which
  remains the API's own JSON index) for the built frontend.
- **Phase 2 --- Project Picker + Module registry (Forge only).**
  `domain/modules`, `application/modules/registry.py` (`FORGE`
  registered; `STUDIO` deliberately not yet, per ADR-015 §5),
  `GET /modules`/`GET /modules/{id}`, `orchai modules list`; the
  desktop frontend (Vite + React, `apps/desktop/frontend/`) gained a
  folder picker (`apps/desktop/shell/native_bridge.py`) with
  readiness/security badges and a module-selection screen.
- **Phase 3 --- persistent conversation, non-streaming.**
  `domain/conversations` (`Conversation`, `Message`), a new
  `ConversationAIProviderPort` (application/conversations/ports.py,
  deliberately separate from the Task-shaped `AIProviderPort` -- see
  ADR-014's implementation note), migration `0009_conversations.sql`,
  `POST/GET /conversations`, `POST/GET /conversations/{id}/messages`,
  and a full Forge chat screen. `infrastructure/ai/litellm_provider.py`
  now implements both `AIProviderPort` and `ConversationAIProviderPort`
  (ADR-013); `ollama.py` and `openai_codex.py` and their tests are
  deleted, and `AIProviderSettings.provider` is now
  `Literal["stub", "litellm"]`, with provider routing moved into
  `ORCHAI_AI_MODEL`'s `"<provider>/<model>"` prefix.

Two correctness issues were found and fixed while verifying Phase 3
end-to-end through the actual desktop frontend (not just the API
directly): the Project Picker was passing a project's filesystem path
as `project_id` to `POST /conversations` instead of the backend's
registered Project UUID, which violates `conversations.project_id`'s
foreign key (`ProjectPicker.jsx` now carries the registered `id`
alongside `path`); and `apps/desktop/shell/server_runner.py`'s
SQLite-by-default logic only checked `os.environ`, so a repository's
own development `.env` (loaded into the process environment by `uv run`
itself before the desktop shell's own code runs) could silently point
the desktop build at a PostgreSQL server instead of the intended local
SQLite file -- it now compares the fully-resolved effective URL against
`DatabaseSettings.DEFAULT_URL` instead, which is correct regardless of
whether an override came from an environment variable or a `.env` file.

- **Phase 4 --- streaming.** `AIProviderStreamChunk`/`ConversationStreamChunk`
  and `execute_stream()`/`complete_stream()` on both provider ports;
  `LiteLLMProvider` implements both via a shared `_stream_litellm()`
  helper (`stream_options={"include_usage": True}` for token counts on
  the final chunk); `StubAIProviderAdapter` gained trivial word-by-word
  fake streaming for tests. `ConversationService.send_message_stream()`
  yields `user_message` → `delta`* → `done`/`error` events, reusing the
  same `_start_turn()` persistence logic as the non-streaming
  `send_message()`. `POST /conversations/{id}/messages` now always
  returns `text/event-stream` (the conversation is looked up and 404'd
  *before* the stream starts, so an unknown conversation still gets a
  real 404 rather than an in-band error event); the endpoint's previous
  single-JSON-response shape from Phase 3 is gone. The Forge chat
  screen consumes this via `fetch()` + a manual `ReadableStream` reader
  (`apps/desktop/frontend/src/api/client.js::streamMessage` --
  `EventSource` cannot POST), rendering each `delta` onto a placeholder
  bubble and swapping in the final message on `done`. Verified
  end-to-end through the real SSE wire format (raw `data:` lines
  captured mid-test showed the actual `user_message` → five `delta` →
  `done` sequence, not just the rendered end state) and confirmed to
  survive a full page reload, same as Phase 3.
  `AIProviderPort.execute_stream()` (the Task-bounded variant) is
  implemented and unit-tested but has no caller yet -- nothing routes a
  Task execution through it until Forge messages can escalate to real
  Tasks (Phase 5). Cost estimation is skipped for streamed replies
  (`resource_usage.estimated_cost` is always `None`) -- see ADR-013's
  Phase 4 implementation note for why.

- **Phase 5 --- Forge integrated with the real Task pipeline.**
  `POST /conversations/{id}/escalate` (`ConversationEscalateRequest`)
  resolves the conversation's project and calls the exact same
  `run_local_flow()` `POST /requests` uses --- no parallel authorization
  path. `ConversationService.escalate_message()` only records
  `linked_task_id`/`linked_execution_id` on the triggering user
  message and has no dependency on `application/orchestration` (Task
  creation stays in the API route, mirroring `create_request`). The
  Approval Card (`apps/desktop/frontend/src/screens/ApprovalCard.jsx`)
  renders in place of an ordinary chat bubble for any message with
  `linked_task_id` and calls `POST /requests/{id}/approve` /
  `POST /suggestions/{id}/reject` --- verified end-to-end live
  (escalate → card shows the real suggestion/rationale → approve →
  card updates to `PLANNED` and hides the actions) and surviving a
  reload.

  Verification surfaced, and this phase fixed, a pre-existing bug in
  the core Task/Suggestion pipeline (not introduced by the desktop
  work): `Orchestrator._resolve_task_stage()` generated a fresh
  `Suggestion` on every advance/approve call without marking the
  previous `PRESENTED` one as resolved, so `GET /requests/{id}/flow`'s
  top-level `suggestion`/`status` fields could keep reporting
  `PRESENTED`/`PENDING_SUGGESTION` after a stage was actually resolved.
  Fixed in `SuggestionEngine.suggest_next()`
  (`application/suggestions/engine.py`): it now reuses an existing
  `PRESENTED` suggestion matching the task's current `(role, action)`
  instead of creating a duplicate, and correctly ignores a stale
  `PRESENTED` suggestion left over for a different, already-superseded
  stage. See ADR-011's "Amendment (OrchAI Desktop Phase 5)" and
  `tests/unit/application/test_suggestion_engine.py` (5 new tests).
  `ApprovalCard.jsx`'s earlier `flow.task.state`-based workaround was
  removed; it reads `suggestion.status` directly again.

  Separately, this session also fixed two long-standing environment
  papercuts unrelated to any of the above, both the same root cause
  (a directory with a broken ACL, created under a different Windows
  account/session, denying access -- including listing, renaming, or
  deleting it -- to every account tested since): `.pytest_cache`
  produced a `PytestCacheWarning: ... Acesso negado` on every single
  test run, and the system-wide default base temp directory
  (`%TEMP%/pytest-of-<user>`) made every test using `tmp_path`/
  `tmp_path_factory` fail outright unless `--basetemp` was passed
  explicitly on every invocation. `pyproject.toml`'s
  `[tool.pytest.ini_options]` now points `cache_dir` at `.cache/pytest`
  (a fresh, never-broken path); a new root `conftest.py` defaults
  `--basetemp` to `.cache/pytest-tmp` via a `tryfirst=True`
  `pytest_configure` hook (running before `_pytest.tmpdir`'s own,
  which builds the session's `tmp_path_factory` from that option) when
  the caller hasn't passed `--basetemp` explicitly. Plain `uv run
  pytest -q` (no flags at all) now runs cleanly; `.gitignore` covers
  the new `.cache/` directory.

- **Phase 6 --- Studio skeleton.** A second module alongside Forge:
  `infrastructure/projects/media_workspace.py`
  (`MediaWorkspaceProjectAdapter`) discovers a connected folder's files
  and classifies each by `media_type` (`image`/`audio`/`video`/`text`/
  `other`) rather than by source-code role; `read_context()` returns
  real UTF-8 text for text-like files and a plain
  `"[<type> file, N bytes -- binary content not inlined]"` description
  for binary media (no multimodal provider integration yet);
  `run_tests`/`run_command`/`git_status`/`write_documentation` all
  raise `ProjectCapabilityError` (never exposed), and `WRITE_SOURCE` is
  reused rather than adding a new capability. The `STUDIO`
  `ModuleDefinition` (`application/modules/registry.py`) sets
  `project_adapter_kind="media_workspace"`,
  `task_pipeline_mode="conversational_with_protected_operations"`,
  `requires_project=True`, and suggests `openai/gpt-5` /
  `anthropic/claude-sonnet-4-5`. A new
  `GET /projects/{project_id}/attachments` endpoint constructs
  `MediaWorkspaceProjectAdapter` directly from the project's
  `root_location` and returns discovered resources --- deliberately
  independent of `Project.adapter_type`, `ProjectAdapterRegistry`, and
  the Orchestrator, so Studio's discovery-plus-chat skeleton stays
  additive with no change to how Forge's pipeline resolves an adapter.

  ADR-015 §5's open question (whether Studio needs its own Role/Action
  vocabulary, e.g. a new `RoleName.CREATOR`) was resolved for this
  phase, not closed outright: asked directly, the user chose to reuse
  the existing `TASK_PLANNER`/`PLAN` pair unchanged rather than
  introduce new vocabulary, keeping the Phase 6 skeleton fully
  expressible without touching `AutomaticExecutionPolicy` or any
  `Authorization` record's shared vocabulary. See ADR-015's
  "Implementation Note (Phase 6)".

  On the frontend, `apps/desktop/frontend/src/hooks/useConversationChat.js`
  was extracted from `ForgeHome.jsx` (conversation list, message send,
  and SSE streaming state --- module- and project-agnostic) so the new
  `StudioHome.jsx` screen could reuse it without duplicating that logic;
  `StudioHome.jsx` adds a read-only attachments panel
  (`api.listAttachments(project.id)`) listing each discovered
  resource's path, `media_type`, and byte size, and has no escalation
  affordance (Studio has no Approval Card in this phase --- it never
  produces a pending suggestion or authorization yet). `App.jsx` now
  routes to either `ForgeHome` or `StudioHome` via a
  `module_id -> component` map instead of hardcoding Forge.

  Verified live: a demo folder with a text brief and placeholder
  image/audio files showed up in the attachments panel correctly
  classified by `media_type` and byte size, and Studio chat streamed a
  reply using Studio's own suggested model
  (`openai/gpt-5`). Full suite: 238 passed (6 pre-existing, unrelated
  failures), zero warnings.

- **Phase 7 --- Hardening**, done as 7 independently-verified sub-phases
  (7.1--7.7), each with its own full-suite run before moving to the next:

  - **7.1 Automatic-policy runtime configuration.** `AutomaticExecutionPolicy`
    (`application/policies/service.py`) was previously only configurable
    by constructing it in Python code. A new singleton-row
    `AutomaticPolicyRepository` (migration `0010_automatic_policy.sql`,
    `SQLAlchemyAutomaticPolicyRepository`/`InMemoryAutomaticPolicyRepository`)
    makes it runtime-mutable: `LocalPolicyService.evaluate()` now re-reads
    the current policy from the repository on every call (without
    mutating shared state, so concurrent requests stay correct) instead
    of freezing it at construction. A new `AutomaticPolicyService`
    separates that read path from writes, which publish
    `AUTOMATIC_POLICY_UPDATED` for the audit trail. `GET`/`PUT
    /policies/automatic` (new `policies:manage` permission for the
    write) and `orchai policies automatic show|set` expose it.
    `Orchestrator` itself required zero changes --- its existing
    per-call `automatic_policy` override (used by tests) still works
    exactly as before.
  - **7.2 Execution cancellation.** `AIProviderPort.cancel()` existed but
    nothing called it. `ExecutionEngine.cancel()` now cancels the
    tracked `asyncio.Task` (populated only by `.dispatch()`, not by the
    orchestrator's own synchronous `.run()` calls), treats the
    provider's own `.cancel()` as a secondary best-effort signal, and
    always finishes by transitioning the execution to the new
    `EventType.EXECUTION_CANCELLED`-emitting `CANCELLED` state directly
    (`asyncio.CancelledError` is a `BaseException`, so it bypasses
    `run()`'s own exception handling and would otherwise leave the
    execution's persisted state stuck). Cancelling an already-terminal
    execution is a no-op, not an error. `LiteLLMProvider.cancel()`
    changed from raising `AIProviderError` to a documented no-op, since
    the real cancellation mechanism is the tracked task, not the
    provider. `POST /executions/{id}/cancel` and `orchai executions
    cancel` expose it.
  - **7.3 Metrics aggregation.** `MetricsRepository` only ever supported
    `list()` (raw records). A new `summarize()` (plus the pure,
    repository-independent `application/metrics/aggregation.py` used by
    both the SQLAlchemy and in-memory implementations) computes
    count/sum/avg per metric name, grouped by any combination of
    `project_id`/`role`/`action`/`model_id`/`outcome`, over an optional
    time window --- deliberately scoped to what's already emitted today,
    not the full aspirational metric set (retry rate, suggestion
    acceptance rate, etc. would need cross-referencing suggestions/audit,
    out of scope). `GET /metrics/summary` and `orchai metrics summary`
    expose it.
  - **7.4 Metrics/audit dashboard in the desktop UI.** A new cross-cutting
    `Dashboard.jsx` screen (reachable from a button next to "Trocar
    Pasta" on `ModuleSelect.jsx` --- not a Module per ADR-015, since it
    has nothing to do with an AI workflow) renders a Chart.js bar chart
    of execution success/failure counts by role+action, a metrics
    summary table, and a recent-audit table, via two new
    `api/client.js` functions and a `useDashboardData` hook. Verified
    live: registered a demo project, ran a real `local-flow` plus a
    task-stage advance through the actual backend, and confirmed the
    chart and both tables rendered correctly from the real data ---
    this surfaced and fixed a real bug where the chart used `count`
    instead of `sum` for the success/failure metrics (both are emitted
    on *every* execution, 1.0/0.0 by outcome, so `count` alone always
    read "1" regardless of which way it went).
  - **7.5 Decomposition of `orchestrator.py`** (highest-risk item,
    tackled after 7.1--7.4 so the refactor accounts for their new call
    sites). 1437 lines split into `orchestrator.py` (1016 lines) plus
    five new sibling modules in `application/orchestration/`: `ports.py`
    (the two Protocols, to avoid a circular import), `results.py`
    (unifying three near-identical `as_dict()` methods and the
    suggestion/audit-count bookkeeping every result attached), `events.py`
    (the four domain-event publishers, now plain functions), `connections.py`
    (`connect_project`/`connect_registered_project`, plus the
    already-pure `run_adapter_operation` --- and `run_local_flow`, found
    to be inlining the same connect logic a third time, now reuses
    `connect_project` too), `stages.py` (the `TaskWorkflowStage`
    vocabulary and its pure mapping functions), and `gating.py`
    (`evaluate_and_authorize()`, unifying the "evaluate policy → mark
    suggestion → authorize → auto-grant" sequence that had been
    duplicated three times --- the single biggest duplication in the
    file). The `Orchestrator` constructor's 12-collaborator signature
    and all three public method signatures
    (`run_local_flow`/`run_project_operation`/`run_task_workflow_stage`)
    are verified byte-for-byte unchanged. 25 new unit tests were added
    (one file per extracted module) --- the file had no dedicated test
    file at all before this phase. The full suite was run after every
    single extraction, not just at the end; zero regressions throughout.
  - **7.6 Desktop packaging (PyInstaller).** `apps/desktop/shell/` became
    a real Python package (`apps/__init__.py`, `apps/desktop/__init__.py`,
    `apps/desktop/shell/__init__.py`) so `main.py`/`native_bridge.py`
    could use absolute `apps.desktop.shell.*` imports instead of
    sibling-module imports that only resolved by relying on a plain
    script's own directory landing on `sys.path` --- correct under `-m`
    invocation and under a frozen build alike, not just a packaging-only
    workaround. `server_runner.py`'s `FRONTEND_DIST` lookup became
    `sys._MEIPASS`-aware. A new `apps/desktop/shell/packaging/orchai_desktop.spec`
    builds a onedir executable, bundling the migration `.sql` files and
    the built frontend at the exact relative paths the frozen app looks
    them up at. This was validated by actually building and running the
    frozen executable (not just reviewing the spec), which surfaced and
    fixed two real, otherwise-invisible packaging gaps: `litellm` reads
    its own `model_prices_and_context_window_backup.json` off disk at
    import time (added via `collect_data_files("litellm")`), and its
    `tiktoken` dependency registers built-in encodings through a
    `tiktoken_ext` plugin discovered via runtime `pkgutil` scanning that
    static analysis cannot follow (added as explicit `hiddenimports`).
    After both fixes, the built `.exe` started the backend, ran all 10
    migrations against a real database, served the bundled frontend, and
    opened a real native window. A `[project.scripts]` desktop entry
    point was deliberately not added: it would require `apps/` to become
    part of the installed `orchai` distribution, contradicting ADR-017's
    "`apps/desktop/` is a sibling of `src/orchai/`, never installed with
    it" layout, and PyInstaller does not need one anyway (it points at a
    script file, not an installed console-script name).
  - **7.7 Dockerfile for headless/server mode.** A new root-level
    `Dockerfile` (multi-stage, `uv sync --locked --no-dev` without the
    `desktop` extra, non-root user, `HEALTHCHECK` against the existing
    `GET /health`) and `.dockerignore`. Confirmed via the earlier
    research (not a new code change) that `create_app()` already
    produces the correct headless behavior with zero source changes ---
    the desktop UI's static mount is conditional on
    `ORCHAI_DESKTOP_STATIC_DIR`, which nothing sets outside the desktop
    shell.

  Full suite after every sub-phase: `ruff check` clean throughout; test
  count grew from 269 (start of Phase 7) to 294 (end of 7.5; 7.6/7.7
  added no new automated tests, matching their own stated verification
  approach of an actual build/run rather than a synthetic test),
  zero warnings, `test_dependency_boundaries.py` green at every step.

The OrchAI Desktop initiative (Phases 1--7) is now complete. The
existing, previously implemented core (Task/Role/Action/Execution/
Authorization/Project/Identity/Audit/Metrics) is unchanged in shape
throughout and was extended, not replaced, per these decisions.

**Previous phase: Chat-First Request Interface v0.1.11**

The project has a consolidated architecture and domain foundation, an
accepted technology baseline, a defined physical code structure, and
ADRs for the major implementation decisions.

The operational foundation is implemented: task lifecycle, authorization,
execution, context resolution, project adapter boundaries, a central
application Orchestrator for local flows and protected project operations,
an async Execution Engine with a replaceable AI Provider Adapter
boundary, filesystem Project Adapter discovery and protected operations,
context-resolution metadata, event-derived audit and metrics records,
state-aware suggestions, execution-mode enforcement for `MANUAL`,
`SUGGESTED`, and `AUTOMATIC`, an initial policy slice kept separate from
authorization, persisted effective-vs-observed project
readiness/security, and SQLAlchemy-backed durable persistence for the
initial operational and historical aggregates.

A Chat-First Request Interface has been introduced (ADR-011) as the
primary API surface for external clients modeled after a conversational
AI interface. The `/requests` resource projects the Task domain toward
a user who provides a project, model, role, action, and prompt — without
requiring knowledge of the internal orchestration steps.

PostgreSQL is now the explicit production default throughout
configuration, the CLI, and the API: `ORCHAI_DATABASE_URL` resolves to a
local PostgreSQL connection string when left unset entirely. SQLite
remains fully supported, but strictly as a secondary option for fast,
dependency-free local development and automated tests, opted into with a
`sqlite:///...` URL or the shorter `sqlite`/`local` alias.

The CLI and API surfaces have been expanded to correctly cover every
already-implemented application capability across tasks, executions,
authorization, suggestions, audit, and metrics, while keeping the
`/requests` chat-first surface as the primary usage concept:

- `orchai audit show` / `GET /audit/{audit_id}` retrieve a single audit
  record, and correlation/causation identifiers are now surfaced in both
  `audit list` output and the audit serialization;
- `orchai suggestions show|generate|accept|reject` and their
  `GET /suggestions/{id}`, `POST /tasks/{task_id}/suggestions`,
  `POST /suggestions/{id}/accept`, `POST /suggestions/{id}/reject`
  API counterparts round out suggestion lifecycle management, which was
  previously read-only through the interfaces;
- `orchai executions complete` gained `--metadata` /
  `--resource-metadata` JSON options so execution outcomes can carry the
  same metadata the domain model already supports;
- authorization listing (`orchai authorizations list`,
  `GET /authorizations`) now supports filtering by decision `status` and
  by `pending_only`, pushed down to the repository layer instead of
  requiring callers to filter client-side.

Two correctness bugs were found and fixed while doing this work, both in
the primary chat-first flow:

- `POST /requests/{id}/approve` compared authorization/suggestion status
  against a literal `"PENDING"` string that neither
  `AuthorizationDecisionStatus` nor `SuggestionStatus` defines, so the
  endpoint could never find a pending authorization to approve. It now
  checks `status is None` (authorization) and
  `status is SuggestionStatus.PRESENTED` (suggestion), matching the
  actual domain semantics of "pending".
- Selection of "the most recent" authorization, suggestion, or execution
  in `_serialize_request_flow` and in the approve handler relied on list
  position (`[-1]`, `reversed()`), which silently picks the wrong record
  under the SQLAlchemy repositories (which order `list()` results
  newest-first) versus the in-memory repositories (which preserve
  insertion order). Selection is now explicit by timestamp
  (`max(..., key=lambda r: r.created_at)`), independent of repository
  ordering.

A third, more consequential correctness bug was found and fixed in v0.1.5,
in the same chat-first flow: `POST /requests` (and its `POST /flows/local`
and `POST /projects/operations` siblings, which share the same
`run_local_flow`/`run_project_operation` orchestration code) transitioned a
freshly created task `CREATED -> PLANNING -> PLANNED` unconditionally and
without any suggestion/policy evaluation, regardless of execution mode.
This was a genuine deviation from
`docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` (section 3) and ADR-011
invariant #2, not merely an implementation nuance: the first suggestion a
caller ever saw was `IMPLEMENT` (the task was already `PLANNED`), never
`PLAN`, and the PLAN stage carried no authorization, execution, or audit
trail of its own. Both entry points now delegate to the same gated,
single-stage-advance mechanism already used by `POST /tasks/{id}/advance`
(`run_task_workflow_stage`), so no code path — regardless of storage
backend — can silently complete a stage. `AUTOMATIC` execution mode is the
only way to skip the approval step for a given stage, and only for a
`(role, action)` pair explicitly present in
`AutomaticExecutionPolicy.allowed_operations`, configured in advance. See
the ADR-011 amendment note and `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md`
sections 3 and 8 for the corrected behavior, and
`docs/API-ENDPOINTS-REPORT.md` for the updated worked example.

One practical consequence surfaced by this fix: since `AutomaticExecutionPolicy`
still has zero runtime configuration exposure in the CLI or API (a
previously known gap), `AUTOMATIC` mode can no longer complete *any* stage
through the public CLI/API surface out of the box — the default policy only
allows `(DEVELOPER, IMPLEMENT)`, and PLAN is now correctly gated too. It
still works when driven through the Python API with a custom
`AutomaticExecutionPolicy`, which is how the new regression tests validate
it.

The `alembic` dependency was removed from `pyproject.toml` in v0.1.5: it
was declared but never imported anywhere in `src/` (the project uses a
hand-rolled raw-SQL migration runner, `SQLAlchemyDatabase.migrate()`, not
Alembic). `uv.lock` was regenerated accordingly.

Two follow-up findings were investigated and closed out after v0.1.5:

- A suspected incompatibility between `pydantic==2.13.4` and Python 3.14
  (`TypeError: _eval_type() got an unexpected keyword argument
  'prefer_fwd_module'`) turned out **not** to be a real project issue: it
  only reproduced against Python `3.14.0rc2`, a stale pre-release build
  that this sandbox's local `uv` Python index happened to offer. Against
  the actual final release, `3.14.7`, the full test suite passes cleanly
  with the project's exact pinned dependencies unchanged. No code or
  dependency change was needed; this is recorded here so it is not
  re-investigated as a live bug in a future session.
- The `StarletteDeprecationWarning: Using httpx with starlette.testclient
  is deprecated; install httpx2 instead` warning seen in test runs was
  real and is now fixed: `httpx2` (a separate package from `httpx`, not a
  version of it) is added to the `dev` dependency group in
  `pyproject.toml`, since it is only needed by `starlette.testclient`
  in tests — the runtime `httpx` dependency used by the Ollama/OpenAI
  provider adapters is untouched. Verified with
  `pytest -W error::DeprecationWarning`: zero warnings remain.

Two more gaps, both already known and flagged as candidates in
`docs/API-ENDPOINTS-REPORT.md`, were reassessed and closed in v0.1.6:

- `POST /requests/{id}/approve` could not resolve the common SUGGESTED-mode
  case: `run_task_workflow_stage` returns before ever creating an
  Authorization when policy blocks (the normal outcome right after the
  v0.1.5 PLAN-gate fix), leaving only a suggestion in `PRESENTED` status —
  so `/approve`, which only ever looked for a pending Authorization, always
  reported `no_pending_authorization` in that case. It now covers both
  cases: a standalone pending Authorization (e.g. one created directly via
  `POST /authorizations/request`) is still granted directly; otherwise, if
  a `PRESENTED` suggestion exists, `/approve` delegates internally to the
  same gated single-stage-advance mechanism used by `/advance`
  (`approve_stage=true`) — still evaluated by policy, not a bypass. Because
  of this, `/approve` now optionally accepts the same passthrough fields as
  `/advance` (`context_paths`, `documentation_path`, `test_args`, `model`,
  `provider_target`), needed only when the currently blocked stage itself
  requires them (e.g. PLAN requires `context_paths`).
- `POST /admin/db/create` returned a soft, informative response for a
  non-PostgreSQL target, but the CLI's `orchai db create` raised a hard
  error (`typer.BadParameter`) for the exact same case. Both now behave the
  same way: they validate, then simply inform the user that the operation
  does not apply to the currently selected local-flow/SQLite database, with
  no error. A new `db sync` operation (`POST /admin/db/sync`,
  `orchai db sync`) was also added, combining `create` and `migrate` into
  the single step operators actually want when bringing a database up to
  date: create it if needed (skipped, not an error, for a non-PostgreSQL
  target) and then apply migrations unconditionally.

In v0.1.7, `db create` and `db migrate` were reassessed again and this
time **fully removed** rather than aligned: `POST /admin/db/create`,
`POST /admin/db/migrate`, `orchai db create`, and `orchai db migrate` no
longer exist as endpoints or commands anywhere in the project.
`db sync`/`POST /admin/db/sync` is now the single, sole database
administration operation, covering both cases (create-if-needed, then
migrate) in one step; its informational messaging for non-PostgreSQL
targets (added in v0.1.6) is preserved. Every mention of the removed
`create`/`migrate` operations was swept from the CLI, the API, the test
suite, and the documentation (`README.md`,
`docs/API-ENDPOINTS-REPORT.md`, `docs/USER-ONBOARDING.md`,
`docs/USER-OPERATIONS-GUIDE.md`,
`docs/architecture/API-UI-BOUNDARY.md`,
`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`,
`docs/architecture/PERSISTENCE-STRATEGY.md`).

This same v0.1.7 pass also found and fixed a data-integrity problem in
the working copy this project was being developed against: it was
missing 38 documentation files and 18 unit test files that exist in the
authoritative, git-tracked repository (no application source code was
missing — the handful of genuinely empty `src/` directories were
confirmed empty in the authoritative repository too). Once the missing
unit tests were restored, 8 of them failed immediately, all as a direct
and previously invisible consequence of the v0.1.5 PLAN-stage gate fix
described above (`run_task_workflow_stage` now stops a `CREATED` task at
`PLANNING`/`BLOCKED` instead of silently completing PLAN, and
`run_local_flow` now correctly transitions a failed execution to
`BLOCKED` instead of leaving it stuck in `IMPLEMENTING`). These 8 tests
were updated to assert the corrected, already-intended behavior; no
production code changed as a result. The full suite — now 124 tests
after also deduplicating overlapping `db sync` coverage — passes
cleanly, including under `pytest -W error::DeprecationWarning`.

In v0.1.8, `docs/domains/STATUS.md` — found stale during the v0.1.7 audit
(it still marked every domain `PARTIAL` from a 2026-08-20 snapshot, while
this document and the individual domain documents already reflected their
current implemented-and-tested state) — was reconciled: 13 of its 14
domains now read `IMPLEMENTED`, matching this document; Metrics stays
`PARTIAL` (see that file for why). This closes the one documentation
defect the v0.1.7 audit found.

Also in v0.1.8, `infrastructure/persistence/sqlite/` and
`infrastructure/persistence/postgresql/` were merged into a single
`infrastructure/persistence/db/` (`db/admin.py` + `db/migrations/`), and
`PostgreSQLDatabaseAdmin`/`PostgreSQLDatabaseTarget`/
`parse_postgresql_target` were renamed to the generic `DatabaseAdmin`/
`DatabaseTarget`/`parse_database_target`: the project's persistence model
already applies the same dialect-portable SQL migrations to SQLite and
PostgreSQL alike (see `docs/architecture/PERSISTENCE-STRATEGY.md`), so a
two-folder, engine-named split did not reflect that abstraction. Every
reference across `src/`, `tests/`, and docs was updated accordingly.

Identity and Access Management moved from `DEFINED` to `PARTIAL` in
v0.1.8 with the first implementation slice, Phase 1 of the plan in
`docs/TO-DO.md`: an isolated `domain/identity` (`User`, `AccessRole`,
`Permission`, `RefreshToken`), `application/identity` (`IdentityService`
and its ports), an Argon2id password-hashing adapter, in-memory and
SQLAlchemy repositories, and migration `0007_identity_and_access.sql`.
Deliberately isolated, per the user's own explicit instruction: nothing
here is called from any FastAPI route or CLI command yet, and no
existing execution/action/role/model permission check consults it — it
is a self-contained vertical slice exercised only by its own tests. The
full suite is now **143 tests** (124 + 19 new), still clean under
`pytest -W error::DeprecationWarning`.

Identity and Access Management stays `PARTIAL` in v0.1.9 with Phase 2 of
the same plan: JWT access-token issuance/validation
(`JWTAccessTokenIssuer`, PyJWT, HS256, ~15 minute TTL) and SHA-256
refresh-token hashing (`Sha256RefreshTokenHasher` — deliberately distinct
from the Argon2id `PasswordHasher`, since refresh tokens are high-entropy
random strings rather than user-chosen secrets), plus `login()` /
`refresh()` / `logout()` on `IdentityService` (single-use refresh-token
rotation, idempotent logout). Still deliberately isolated: nothing here
is called from any FastAPI route or CLI command, and there is still no
`/auth/*` surface or `ORCHAI_AUTH_ENFORCED` flag — that remains Phase 3.
The full suite is now **160 tests** (143 + 17 new), still clean under
`pytest -W error::DeprecationWarning`.

Identity and Access Management moved from `PARTIAL` to `IMPLEMENTED` in
v0.1.10 with Phase 3 of the same plan — the phase that actually changes
runtime behavior, closing out `docs/TO-DO.md` Priority 1: a shared FastAPI
dependency (`require_permission(key)` in `interfaces/api/main.py`) and its
CLI counterpart (`require_cli_permission(key)`, called explicitly as the
first statement of each command body rather than as a decorator, so
Typer/Click's signature-introspection-based argument parser is never at
risk); `POST /auth/login` / `POST /auth/refresh` / `POST /auth/logout` and
`orchai auth login` / `orchai auth logout` / `orchai auth bootstrap-admin`;
declarative per-route/per-command permission requirements wired into every
pre-existing route (50 of 54 app routes) and command (46 of 49 commands —
`auth login`, `auth bootstrap-admin`, and `api serve` are the exceptions,
the first two being the bootstrap path itself and the third having no HTTP
route counterpart to mirror); and the bootstrap-superuser path (ADR-012
§8, via `orchai auth bootstrap-admin` or `ORCHAI_ADMIN_USERNAME`/
`ORCHAI_ADMIN_PASSWORD`). All of this is gated behind `ORCHAI_AUTH_ENFORCED`,
default `false` per the rollout plan in
`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6 — so no existing
caller's behavior changed by landing this code; enforcement is wired in
but inert until deliberately turned on. User management
(`admin:manage_users`, a `/users` HTTP surface, `orchai users *`) is
deliberately out of scope for this phase, per the permission inventory in
`IDENTITY-AND-ACCESS-MODEL.md` §4. The full suite is now **178 tests**
(160 + 18 new: unit coverage for `AuthSettings` loading/validation, plus
integration coverage for the `/auth/*` routes and enforced/unenforced
behavior on both the API and CLI, including the superuser-bypass and
missing-permission-403/exit-1 cases), still clean under
`pytest -W error::DeprecationWarning`.

Identity and Access Management gained a fourth, purely additive phase in
v0.1.11: a user-configuration CRUD layer, requested by the user as an
explicit prerequisite to the broader per-user authorization refactor
("primeiro deixar o cadastro/configuração de usuários mais robusto").
Admin-only management of users and access roles
(`GET/POST /admin/users`, `PUT /admin/users/{id}/access-roles`,
`GET/POST /admin/access-roles`, `PUT /admin/access-roles/{id}/permissions`;
`orchai users list|create|set-access-roles`,
`orchai access-roles list|create|set-permissions`), gated by
`admin:manage_users`; an admin project directory
(`GET /admin/projects`, `orchai projects list-all`) gated by a new
`admin:manage_projects` permission, listing every project's capabilities,
readiness, and connected users; and a self-service surface (`GET`/`PATCH
/me`, `GET /me/projects`, `orchai me show|update|projects`) that always
requires a real authenticated caller via a new
`require_authenticated_user()` / `require_authenticated_cli_user()`
dependency — deliberately distinct from `require_permission`'s
inert-when-`ORCHAI_AUTH_ENFORCED=false` behavior, since "show my own
profile" has no meaningful no-op reading.

The existing N:N `AccessRole` model (Phase 1) was kept entirely
unchanged — no schema migration, no single-scalar-role-per-user column,
no `-1` sentinel. An earlier "Default AccessRole" design (a system-wide
fallback role for a user created without one) was proposed and then
dropped by the user in favor of a simpler rule with the same practical
guarantee: creating a non-superuser now requires specifying at least one
`AccessRoleId` up front (`UserRequiresAccessRoleError` otherwise).
Superusers remain exempt, since `is_superuser=True` already bypasses
every permission check. `PUT .../access-roles` and `PUT .../permissions`
are both replace-all operations.

A new, purely informational `project_connections` table
(`0008_project_connections.sql`) records which users connected which
project to OrchAI — explicitly not an access-control boundary, and
living in the same database as `projects` (not the pinned identity
database), since it is descriptive project metadata, not a security
concern. `POST /projects` now auto-links the caller when authenticated,
by capturing `require_permission`'s claims as a parameter instead of
discarding them via the `dependencies=[...]` list form — the one change
to a pre-existing route's code in this phase, and it does not alter that
route's permission check or response shape for any existing caller.

This phase also closed a latent correctness gap that predates it:
`permissions` and `access_roles` started completely empty in a fresh
database, with no seeding anywhere in the codebase, which meant no
non-superuser could ever pass a permission check even with
`ORCHAI_AUTH_ENFORCED=true`. The full permission-key catalog (the eleven
keys from `IDENTITY-AND-ACCESS-MODEL.md` §4 plus the new
`admin:manage_projects`) is now auto-seeded idempotently — via a
synchronous SQLAlchemy Core helper, not the async `PermissionRepository`
port, since the identity-runtime builders are plain sync functions called
from both async FastAPI startup and sync CLI entry points — on every
`build_sqlalchemy_identity_runtime` call, immediately after
`database.migrate()`. See `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`
§8 for the full design. The full suite is now **203 tests** (178 + 25
new), still clean under `pytest -W error::DeprecationWarning`.

The next implementation focus is:

- an Anthropic (Claude) provider adapter — Ollama and OpenAI are already
  real, HTTP-backed, tested, and wired via `ORCHAI_AI_PROVIDER`;
- the broader per-user action/role/model authorization and multi-user
  Project Adapter binding change the user has described (the "refatoração
  para usuários"), now that its explicit prerequisite (this
  user-configuration CRUD layer) is in place. Its one hard technical
  dependency — a request-scoped "current logged-in user" to check
  permissions against — has been resolved since Phase 3, but starting it
  is still an explicit decision the user has not yet made (per the user's
  own standing instruction, changes to the project's established
  foundation require explicit authorization before implementation, not
  just before-the-fact reporting) — see `docs/TO-DO.md` Priority 1's
  "Scope note" for the full framing;
- flipping `ORCHAI_AUTH_ENFORCED` to `true` by default, once a decision
  is made on whether/when to do so — also not yet authorized;
- richer policy configuration, including `AUTOMATIC` execution policy
  runtime configuration (now a sharper gap given the PLAN-stage fix above);
- execution cancellation and metrics aggregation as first-class
  application capabilities;
- deployment and container automation.

## Source of Truth

This document tracks project state.

It does not redefine architectural rules.

For architectural rules, consult:

-   `ARCHITECTURAL-CONTRACT.md`
-   `ARCHITECTURE.md`
-   `architecture/COMPONENTS.md`
-   relevant domain documentation
-   relevant ADRs
-   `IMPLEMENTATION-MAP.md`

## Important Distinction

``` text
DEFINED
    ≠
IMPLEMENTED

DECIDED
    ≠
IMPLEMENTED

DOCUMENTED
    ≠
VALIDATED
```
