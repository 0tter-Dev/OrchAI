# Deployment And Desktop

## Purpose

Defines the two runtime deployment shapes OrchAI supports on the same
backend — a headless CLI/API service and a Windows desktop application
— and how the desktop shell is structured, started, and phased.

## Objective

Let the identical Domain/Application/Persistence/Event/AI-Adapter/
Project-Adapter backend run either as a networked service or as a
local single-user desktop process, with no source change required to
switch between them.

## Current Status

`implemented`

## Headless Deployment

```text
User → CLI / API → OrchAI Process
                     ├── Domain
                     ├── Application
                     ├── Persistence
                     ├── Event Dispatcher
                     ├── AI Adapters
                     └── Project Adapters
```

Docker is the preferred packaging mechanism for reproducible
environments in this shape; a root `Dockerfile` (multi-stage, `uv sync
--locked --no-dev` without the `desktop` extra, non-root user,
`HEALTHCHECK` against `GET /health`) gives it a runnable container
path, requiring zero source changes since `create_app()` already
produces the correct headless behavior (the desktop UI's static mount
is conditional on `ORCHAI_DESKTOP_STATIC_DIR`, which nothing sets
outside the desktop shell). The application remains directly runnable
for local development and testing (Python environment, SQLite, a
local test project, mock AI/Project adapters).

## Desktop Deployment (ADR-017)

```text
User → OrchAI Desktop (pywebview window) → OrchAI Process (same as headless)
         bound to 127.0.0.1 only, never the network
         Persistence: SQLite, local
         AI Adapters: LiteLLM (ADR-013)
```

A second deployment shape alongside the headless one, not a
replacement — the same backend supports both, extending "CLI and API
share application behavior" to "CLI, API, and Desktop share
application behavior." Desktop packaging uses PyInstaller (or
briefcase), not Docker, since the target is a native Windows
application, not a container.

### Repository Layout

```text
apps/desktop/
  shell/       main.py (entrypoint), server_runner.py, native_bridge.py, packaging/
  frontend/    Vite + React, build-time only; dist/ mounted as FastAPI StaticFiles
```

`apps/desktop/` is a sibling of `src/orchai/`; the dependency direction
is one-way — the desktop shell depends on the existing FastAPI app and
application services, and `src/orchai/` never imports anything from
`apps/desktop/`.

### Startup Sequence

Pick a free `127.0.0.1` port → build the runtime via
`bootstrap/runtime.py` (same composition root as CLI/API) →
`create_app()` with the frontend `dist/` mounted as `StaticFiles`
under `/app` (never `/`, which the API's own JSON index owns) → start
`uvicorn.Server` in a background thread → `webview.create_window(...)`
→ `webview.start()`. Never binds to `0.0.0.0` — one process, one HTTP
origin, no CORS configuration required.

### Identity (ADR-016)

No login screen. On first launch, `server_runner.py` silently
provisions exactly one local superuser if none exists; every
desktop-originated request resolves through `require_desktop_local_user()`
rather than `require_permission()`/`require_authenticated_user()`.
`ORCHAI_AUTH_ENFORCED` is never set to `true` by the desktop shell
(see `Identity And Access`).

### Screens

Project Picker (folder picker + recent projects, cross-referenced with
readiness/security badges) → Module Selection (`GET /modules`) → Chat
(conversation sidebar, streaming composer/transcript, and the
**Approval Card** — a distinct card, never an ordinary chat bubble,
shown whenever a message's linked Task reaches `PENDING_SUGGESTION` or
has a pending Authorization, with Approve/Reject actions and a link to
the full orchestration trace). The Approval Card is the visible
surface of Human Authority and Suggested-by-Default
(`ARCHITECTURAL-CONTRACT.md` §2.1/§2.2) and must never be visually
demoted to look optional or skippable.

### Implementation History

All 7 phases of the OrchAI Desktop initiative are complete: shell
skeleton; Project Picker + Module registry (Forge); persistent
conversation; SSE streaming; Forge integrated with the real Task
pipeline (message escalation via the Approval Card); a Studio module
skeleton; and Phase 7 hardening (runtime-configurable
`AutomaticExecutionPolicy`, execution cancellation, metrics
aggregation, a metrics/audit dashboard, an `orchestrator.py`
decomposition, PyInstaller packaging, and the headless `Dockerfile`).
See `docs/HISTORY.md` for the full phase-by-phase account.

## Production Evolution

The architecture should support later separation of API/Worker/
Database/Event Transport/AI Providers without changing domain
contracts. Persistent data (database, configuration, audit, events,
execution records, provider metadata) must be separated from the
application image, and secrets use external secret configuration.

## Key Rules

- the desktop shell binds only to `127.0.0.1`; it is never exposed to the network
- `apps/desktop/` never becomes a dependency of `src/orchai/`
- "recent projects" and other shell-local UI state live outside the backend's persistence layer
- the Approval Card (or an equivalent explicit-approval surface) is present for every module whose `task_pipeline_mode` can produce a pending suggestion or authorization
- historical records never depend on ephemeral process state; deployment topology never redefines domain behavior

## Main Relationships

- runs the same `Tasks And Lifecycle`/`Execution Engine`/`Authorization Policy` core in both deployment shapes
- the desktop shell is a third caller alongside `Chat-First And Interfaces`'s CLI and API
- desktop identity defers to `Identity And Access`'s single-user simplification (ADR-016)
- module selection surfaces `Modules And Domain Structure`'s Module concept
