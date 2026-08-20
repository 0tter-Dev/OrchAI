# OrchAI --- Persistence Strategy

## Purpose

Persistence must provide durable operational state and historical
traceability without turning OrchAI into a storage system for connected
projects.

## Primary Strategy

``` text
SQLAlchemy 2.x
      ↓
PostgreSQL
```

SQLite is supported as a lightweight/local backend through the same
repository contracts.

## Current Implementation

The current implementation includes an initial SQLAlchemy persistence
layer with SQL migrations for local durable operation. SQLite is the
default local database, and the repository implementations use the same
application contracts intended for PostgreSQL.

The current persisted aggregates are:

``` text
Projects
Tasks
Authorization Requests
Authorization Decisions
Executions
Events
Audit Records
Context Resolution Metadata
Metric Records
Suggestions
```

This implementation is intentionally infrastructure-bound and uses the
same application repository contracts as the in-memory repositories.

The accepted target remains SQLAlchemy 2.x with PostgreSQL as the
primary database. The current migrations are validated against SQLite
and the configured local PostgreSQL database without changing domain
models or application use cases.

The CLI includes a local PostgreSQL setup helper for environments where
the PostgreSQL server is already running but the target database has not
yet been created:

``` text
orchai db create
```

## What OrchAI Persists

Operational state may include:

``` text
Projects
Project Adapter Configuration
Project References
Capabilities
Tasks
Executions
Current States
Authorization State
Configuration
```

Historical state may include:

``` text
Events
Execution Attempts
Authorization Decisions
Audit Records
Usage Records
User Decisions
Context Resolution Metadata
```

## What OrchAI Does Not Persist by Default

OrchAI does not mirror complete connected-project content merely to make
it available to AI agents.

The following remain owned by the external project:

``` text
Source Tree
Project Documentation
Repository Contents
Project Assets
Project-Owned Artifacts
```

The Project Adapter resolves these resources when required by an
authorized execution.

## Context Persistence

Context should normally be represented through references and resolution
metadata rather than permanent copies of complete project content.

``` text
Context Request
    ↓
Authorization
    ↓
Project Adapter
    ↓
Resolved Context
    ↓
Execution
```

If an execution requires a reproducible historical context snapshot, the
implementation may persist a bounded snapshot or artifact explicitly.
This is an execution-history decision, not a requirement to mirror the
project.

The current implementation persists resolved-context metadata such as
execution, project, source, resource, content hash, byte size, timestamp,
and adapter metadata. It does not persist the resolved file content.

## Metrics and Suggestions Persistence

The current implementation persists event-derived execution metrics and
task-state suggestions through the same repository contracts used by the
runtime. Metrics are derived from authoritative execution records and
events; suggestions remain non-authoritative and record their lifecycle
status separately from authorization decisions.

## Project Knowledge Persistence Policy

Persistence of project knowledge must remain narrower than project
readability.

Representative categories:

### Allowed by Default

- project identity;
- adapter metadata;
- resource references;
- capabilities;
- readiness metadata;
- context-resolution metadata;
- execution and audit history.

### Allowed Only with Explicit Authorization

- persisted architecture summaries;
- persisted naming-convention summaries;
- persisted functional summaries;
- persisted workflow summaries;
- explicit reproducible context snapshots.

### Not Persisted by Default

- complete project code;
- complete project documentation;
- full repository mirrors;
- secrets;
- credentials;
- personal data;
- sensitive proprietary artifacts.

Project readability must not be interpreted as permission to persist
project knowledge indefinitely.

## Repository Boundary

``` text
Domain / Application Contract
          ↓
Repository Interface
          ↓
SQLAlchemy Repository
          ↓
PostgreSQL / SQLite
```

Database-specific APIs must remain in infrastructure.

## Relational Model

PostgreSQL is preferred because OrchAI has strong relationships and
transactional lifecycle requirements among:

``` text
Projects
Tasks
Executions
Events
Authorization
Policies
Roles
Actions
Models
```

Flexible metadata may use PostgreSQL JSON-capable fields where
appropriate.

## MongoDB

MongoDB is not part of the initial persistence baseline.

A separate document store may be introduced later only when a concrete
workload demonstrates that relational storage plus JSON fields is
insufficient.

## Transactions

Critical consistency boundaries should be transactional where supported,
especially:

``` text
Authorization Decision + Audit
Task State Change + Historical Event
Execution Completion + Usage Record
```

## Concurrency

The model should support stable identifiers, explicit ownership, and
future optimistic concurrency controls without requiring parallel
execution in the first release.

## Invariants

1.  Domain models do not depend on database technology.
2.  Historical facts are not silently overwritten.
3.  Critical state changes use explicit transaction boundaries.
4.  Persistence failures remain distinguishable from domain failures.
5.  Project content remains external by default.
