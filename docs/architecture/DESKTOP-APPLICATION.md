# OrchAI --- Desktop Application

## Purpose

This document describes the OrchAI Desktop client introduced by
ADR-017: how the shell is structured, how it starts the existing
backend in-process, the main screens, and the phased path to build it.
It complements ADR-016 (identity) and ADR-015 (modules) for how those
concepts surface in the desktop UI.

## Repository Layout

```text
apps/desktop/
  shell/
    main.py            entrypoint: starts uvicorn in-process, opens the native window
    server_runner.py   wires bootstrap/runtime.py + interfaces/api/main.py::create_app()
    native_bridge.py   js_api exposed to the frontend: folder picker, recent projects
    packaging/         PyInstaller spec (orchai_desktop.spec, Phase 7)
  frontend/
    package.json       Vite + React (build-time only; never shipped as a runtime)
    src/{app,screens,api,state}/
    dist/              build output, mounted as FastAPI StaticFiles
  README.md
```

`apps/desktop/` is a new top-level sibling of `src/orchai/`. The
dependency direction is one-way: the desktop shell depends on the
existing FastAPI app and application services; `src/orchai/` never
imports anything from `apps/desktop/`.

## Startup Sequence

```text
apps/desktop/shell/main.py
  1. pick a free 127.0.0.1 port
  2. build the runtime via bootstrap/runtime.py (same composition root as CLI/API)
  3. create_app() from interfaces/api/main.py, with apps/desktop/frontend/dist
     mounted as StaticFiles under /app when present (not / -- the API
     already owns / as its JSON entry-points index)
  4. start uvicorn.Server bound to 127.0.0.1:<port> in a background thread/task
  5. webview.create_window(url=f"http://127.0.0.1:{port}/app/", js_api=NativeBridge())
  6. webview.start()
```

Never binds to `0.0.0.0` --- this is a single-user local process. One
process, one HTTP origin, no CORS configuration required.

## Identity

Per ADR-016: no login screen. On first launch, `server_runner.py`
provisions exactly one local superuser if none exists yet, and every
desktop-originated request resolves through `require_desktop_local_user()`
rather than `require_permission()`/`require_authenticated_user()`.
`ORCHAI_AUTH_ENFORCED` is never set to `true` by the desktop shell.

## Screens

### Project Picker (entry screen)

- "Open Folder" --- `NativeBridge.pick_folder()` calls
  `webview.create_file_dialog(FOLDER_DIALOG)`, then `POST /projects` to
  register it.
- "Recent Projects" --- a list persisted by the shell itself at
  `%APPDATA%/OrchAI/recent_projects.json` (not backend state, per
  ADR-017 §5), each entry cross-referenced at render time with
  `GET /projects/readiness` and `GET /projects/security` for status
  badges (readiness level, security posture).

### Module Selection

After a project is chosen (or skipped, for a module with
`requires_project=False`): `GET /modules` populates the module
switcher. Selecting a module opens its chat view.

### Chat

- Sidebar: conversations for the current module/project
  (`GET /conversations?module_id=&project_id=`), grouped, with a "New
  Conversation" action (`POST /conversations`).
- Composer: free-text prompt, plus an explicit escalation affordance
  (an "Execute as Task" control, or slash-commands like `/plan`,
  `/implement`, `/review`) per ADR-014 §2 --- messages never escalate to
  a real `Task` implicitly.
- Transcript: renders `Message` records
  (`GET /conversations/{id}/messages`); `POST /conversations/{id}/messages`
  streams the assistant's reply incrementally over SSE (Phase 4,
  ADR-013) -- the transcript appends each `delta` event to a placeholder
  bubble and replaces it with the final persisted message on `done`.
- **Approval Card**: when a message's linked `Task` reaches
  `PENDING_SUGGESTION` or has a pending `Authorization`, the transcript
  renders a distinct card (not an ordinary chat bubble) showing the
  suggestion/change description, with Approve/Reject actions calling
  `POST /requests/{id}/approve` / `POST /authorizations/{id}/decision`,
  and an expander linking `GET /requests/{id}/flow` for the full
  orchestration trace. This is the visible surface of
  `ARCHITECTURAL-CONTRACT.md` §2.1/§2.2 (Human Authority, Suggested by
  Default) and the feature that distinguishes Forge's chat from a
  generic LLM chat client --- it must never be visually demoted to look
  like an optional or skippable step.

## Implementation Phases

Each phase produces something runnable and verifiable before the next
begins.

1. **Shell skeleton (done).** `apps/desktop/shell/` starts, opens a
   native window, shows `GET /health` status. Identity bootstrap
   (ADR-016) is wired in.
2. **Project Picker + Module registry, Forge only (done).**
   `domain/modules`, `application/modules/registry.py`, `GET /modules`;
   folder picker + recent projects; module selection screen.
3. **Conversation, no streaming (done).** `domain/conversations`,
   `application/conversations`, migration `0009_conversations.sql`,
   `infrastructure/ai/litellm_provider.py` (non-streaming), the
   `/conversations*` endpoints, and a Forge chat screen. Chat works,
   persisted (verified surviving a full reload), one response per
   message. Verification surfaced and fixed two bugs beyond the backend
   itself: the Project Picker was sending a project's filesystem path
   as `project_id` instead of the registered Project UUID (violating
   `conversations.project_id`'s foreign key), and the desktop shell's
   SQLite-by-default logic could be silently overridden by a
   development `.env` loaded into the process by `uv run` itself.
4. **Streaming (done).** `AIProviderPort.execute_stream()` (implemented,
   not yet called by anything -- Phase 5's job) and the separate
   `ConversationAIProviderPort.complete_stream()` (implemented and
   wired end-to-end, ADR-014's implementation note); SSE on
   `POST /conversations/{id}/messages`
   (`type: "user_message"|"delta"|"done"|"error"` events); the Forge
   chat screen renders the assistant reply incrementally with a
   "Pensando…" indicator before the first token. No cost estimate is
   computed for streamed replies (ADR-013's Phase 4 implementation
   note).
5. **Forge integrated with the real Task pipeline (done).** New
   `POST /conversations/{id}/escalate` (`ConversationEscalateRequest`)
   resolves the conversation's project, then calls the exact same
   `run_local_flow()` `POST /requests` itself uses -- no parallel
   authorization/policy path. `ConversationService.escalate_message()`
   only records `linked_task_id`/`linked_execution_id` on the
   triggering user message; it has no dependency on
   `application/orchestration` (the Task creation happens in the API
   route, mirroring how `create_request` itself is implemented). The
   Approval Card (`apps/desktop/frontend/src/screens/ApprovalCard.jsx`)
   renders in place of an ordinary chat bubble for any message with
   `linked_task_id`, fetches `GET /requests/{id}/flow`, and calls
   `POST /requests/{id}/approve` / `POST /suggestions/{id}/reject` --
   verified end-to-end live (escalate → card renders with the real
   suggestion/rationale → approve → card updates to show `PLANNED` and
   hides the actions) and surviving a reload.

   Verification surfaced, and this phase fixed, a pre-existing bug in
   the core Task/Suggestion pipeline (not introduced by this phase):
   `Orchestrator._resolve_task_stage()` generated a fresh `Suggestion`
   on every advance/approve call without marking the previous
   `PRESENTED` one as resolved, so `GET /requests/{id}/flow`'s
   top-level `suggestion`/`status` fields could keep reporting
   `PRESENTED`/`PENDING_SUGGESTION` after a stage was actually
   resolved. Fixed at the source in `SuggestionEngine.suggest_next()`
   (`application/suggestions/engine.py`), which now reuses an existing
   `PRESENTED` suggestion for the same `(role, action)` instead of
   duplicating it -- see ADR-011's "Amendment (OrchAI Desktop Phase 5)"
   and `tests/unit/application/test_suggestion_engine.py`.
   `ApprovalCard.jsx` reads `suggestion.status` directly again (an
   earlier `flow.task.state`-based workaround was removed once the fix
   landed).
6. **Studio skeleton (done).** `infrastructure/projects/media_workspace.py`
   (`MediaWorkspaceProjectAdapter`, media-type classification, binary
   files described rather than decoded), the `STUDIO` `ModuleDefinition`
   (`application/modules/registry.py`), a new
   `GET /projects/{project_id}/attachments` endpoint (independent of the
   project's registered `adapter_type`, touching nothing in
   `Orchestrator`/`ProjectAdapterRegistry`), and a `StudioHome.jsx`
   screen (chat, reusing the same `useConversationChat` hook
   `ForgeHome.jsx` now also uses, plus a read-only attachments panel).
   ADR-015 §5's Role/Action vocabulary decision was resolved for this
   phase by reusing the existing `TASK_PLANNER`/`PLAN` pair (see ADR-015's
   "Implementation Note (Phase 6)") rather than introducing a new role,
   so no vocabulary change was needed to ship the skeleton. Verified
   live: a demo folder with a text brief and image/audio placeholder
   files showed up in the attachments panel correctly classified by
   `media_type`, and Studio chat streamed a reply using Studio's own
   suggested model.
7. **Hardening (done).** Delivered as 7 independently-verified
   sub-phases, full suite green after each: (7.1) `AutomaticExecutionPolicy`
   became runtime-mutable via a new persisted `AutomaticPolicyRepository`,
   exposed through `GET`/`PUT /policies/automatic` and `orchai policies
   automatic show|set`; (7.2) execution cancellation wired end-to-end
   (`ExecutionEngine.cancel()`, `POST /executions/{id}/cancel`,
   `orchai executions cancel`); (7.3) metrics aggregation
   (`MetricsRepository.summarize()`, `GET /metrics/summary`,
   `orchai metrics summary`); (7.4) a metrics/audit `Dashboard.jsx`
   screen in the desktop UI (Chart.js, reachable from `ModuleSelect.jsx`,
   not a Module); (7.5) `orchestrator.py` decomposed from 1437 to 1016
   lines into five new sibling modules
   (`ports.py`/`results.py`/`events.py`/`connections.py`/`stages.py`/`gating.py`)
   with 25 new unit tests, the public constructor and 3 public method
   signatures verified byte-for-byte unchanged; (7.6) PyInstaller
   packaging (`apps/desktop/shell/packaging/orchai_desktop.spec`), which
   required turning `apps/desktop/shell/` into a real package for
   absolute imports and, discovered only by actually building and
   running the frozen executable, explicit data-file/hidden-import
   handling for `litellm`/`tiktoken`; (7.7) a `Dockerfile` for the
   separate headless/server deployment mode, requiring no source changes.
   See `docs/STATUS.md`'s Phase 7 entry for full detail.

## Relationship to the Existing API/CLI

The desktop shell is a third caller of the same application services
the CLI and any HTTP client already use --- it introduces no new
business logic of its own. `docs/architecture/API-UI-BOUNDARY.md`'s
existing invariant ("CLI and API share application behavior") extends
unchanged to "CLI, API, and Desktop share application behavior."

## Invariants

1. The desktop shell binds only to `127.0.0.1`; it is never exposed to
   the network.
2. `apps/desktop/` never becomes a dependency of `src/orchai/`.
3. "Recent projects" and other shell-local UI state live outside the
   backend's persistence layer.
4. The Approval Card (or an equivalent explicit-approval surface) is
   present for every module whose `task_pipeline_mode` can produce a
   pending suggestion or authorization --- it is never bypassed for UX
   convenience.
