# ADR-002 --- Persistence Strategy

## Status

Accepted

## Context

OrchAI needs durable operational state and historical traceability while
connected projects remain external systems whose source content is not
owned by OrchAI.

The system also contains strong relationships and transactional
lifecycle state among Tasks, Executions, Events, Authorization,
Projects, Roles, Actions, and Models.

## Decision

Use:

``` text
SQLAlchemy 2.x
      ↓
PostgreSQL
```

as the primary persistence baseline.

Support SQLite through the same repository contracts for
lightweight/local operation and testing.

Do not introduce MongoDB as the primary store.

## Rationale

PostgreSQL provides:

-   relational integrity;
-   transactions;
-   foreign-key relationships;
-   predictable lifecycle queries;
-   strong indexing;
-   JSON-capable fields for flexible metadata;
-   mature Python support;
-   broad deployment compatibility.

This matches OrchAI's operational model better than making the system
primarily document-oriented.

The need for flexible structures does not by itself justify a second
database because PostgreSQL can represent bounded metadata using
JSON-capable fields.

## Project Content Boundary

OrchAI does not mirror complete project source trees or documentation by
default.

The database stores:

``` text
Project identity
Adapter configuration
References
Capabilities
Tasks
Executions
Authorization
Events
Audit
Metrics / usage metadata
Context-resolution metadata
```

The Project Adapter resolves project-owned content when required.

## Consequences

Positive:

-   strong consistency for lifecycle state;
-   straightforward audit/history queries;
-   flexible metadata without a second primary database;
-   simple local SQLite path;
-   clear future scaling path.

Trade-offs:

-   relational schema design requires discipline;
-   PostgreSQL is operationally heavier than SQLite;
-   specialized document workloads may eventually justify an additional
    store.

## Future Evolution

A specialized document, object, vector, or cache store may be introduced
only for a demonstrated workload and must remain outside the core domain
model.
