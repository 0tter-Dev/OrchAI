# ADR-009 --- External Project Content Ownership

## Status

Accepted

## Context

OrchAI coordinates work across external software projects but should not
become a second source of truth for project source code, documentation,
or project-owned artifacts.

Duplicating complete projects would increase storage, synchronization,
security, and consistency complexity.

## Decision

Connected projects remain the authoritative owners of their content.

OrchAI accesses project resources through `Project Adapter`
implementations.

OrchAI persists references, metadata, capabilities, task/execution
state, context-resolution metadata, and audit/history information, but
does not mirror complete project content by default.

## Context Model

``` text
Task
  ↓
Context Requirements
  ↓
Authorization
  ↓
Context Manager
  ↓
Project Adapter
  ↓
Resolved Context
  ↓
Execution
```

## Rationale

This keeps OrchAI focused on orchestration rather than storage and
synchronization.

It also ensures that project content remains current at the source and
that access is governed through explicit adapter and authorization
boundaries.

## Consequences

Positive:

-   no project-content synchronization problem;
-   lower persistence footprint;
-   clear ownership model;
-   project adapters can support different project types;
-   easier future integration with local and remote repositories.

Trade-offs:

-   executions depend on adapter availability when resolving context;
-   reproducibility may require explicit context snapshots or artifact
    persistence for selected executions.

## Invariant

Project-owned content must not be treated as OrchAI-owned state merely
because OrchAI can access it.
