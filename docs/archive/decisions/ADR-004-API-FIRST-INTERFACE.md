# ADR-004 --- API-First Interface Boundary

## Status

Accepted

## Context

OrchAI is expected to support CLI, desktop, editor integrations, and
future web interfaces.

## Decision

Use an API-first application boundary.

Initial interfaces:

``` text
FastAPI
Typer CLI
```

Both call shared application services.

## Rationale

This avoids duplicating orchestration behavior and leaves room for VS
Code, desktop, and web clients.

## Consequences

Positive:

-   consistent behavior;
-   reusable application services;
-   future UI flexibility.

Trade-offs:

-   stronger application-layer discipline is required.

## Invariant

No interface may implement independent task lifecycle or authorization
rules.
