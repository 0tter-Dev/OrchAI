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

## Containerization

Docker is the preferred packaging mechanism for reproducible
environments.

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
