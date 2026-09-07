# OrchAI --- Deployment Model

## Purpose

The initial deployment targets a single-node orchestration service while
preserving a path toward multi-process and multi-instance deployment.

## Initial Runtime

``` text
User
 │
 ├── CLI
 └── API
      │
      ▼
  OrchAI Process
      │
      ├── Domain
      ├── Application
      ├── Persistence
      ├── Event Dispatcher
      ├── AI Adapters
      └── Project Adapters
```

## Desktop Deployment

Per ADR-017, OrchAI Desktop packages the same backend process
(Domain/Application/Persistence/Event Dispatcher/AI Adapters/Project
Adapters, unmodified) behind a `pywebview` shell instead of a bare
`uvicorn` server reached over the network:

``` text
User
 │
 └── OrchAI Desktop (pywebview window)
      │
      ▼
  OrchAI Process (same as Initial Runtime above)
      │  bound to 127.0.0.1 only, never the network
      ├── Domain
      ├── Application
      ├── Persistence (SQLite, local)
      ├── Event Dispatcher
      ├── AI Adapters (LiteLLM, see ADR-013)
      └── Project Adapters
```

This is a second deployment shape alongside the existing headless
CLI/API deployment, not a replacement for it --- the same backend
supports both, per `docs/architecture/API-UI-BOUNDARY.md`'s "CLI and
API share application services" invariant, now extended to include the
desktop shell as a third caller. Desktop packaging (installer,
auto-update) is tracked as Phase 7 hardening in
`docs/architecture/DESKTOP-APPLICATION.md`, using PyInstaller or
briefcase rather than Docker, since the target is a native Windows
application, not a container.

## Containerization

Docker is the preferred packaging mechanism for reproducible
environments, for the headless CLI/API deployment shape.

The application remains runnable directly for local development and
testing.

## Local Development

Support:

``` text
Python Environment
SQLite
Local Test Project
Mock AI Adapter
Mock Project Adapter
```

## Production Evolution

The architecture should support later separation of:

``` text
API
Worker
Database
Event Transport
AI Providers
```

without changing domain contracts.

## Persistent Data

Persistent data must be separated from the application image.

Important data includes:

``` text
Database
Configuration
Audit
Events
Execution Records
Provider Metadata
```

Secrets use external secret configuration.

## Invariants

1.  Historical records do not depend on ephemeral process state.
2.  Persistent data survives application replacement.
3.  External providers remain replaceable.
4.  Deployment topology does not redefine domain behavior.
