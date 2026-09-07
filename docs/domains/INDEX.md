# OrchAI Domain Documentation Index

## Purpose

This document is the navigation entry point for the OrchAI domain model.

Each domain document defines one bounded conceptual responsibility.

## Core Workflow Domains

-   [`AUTHORIZATION.md`](AUTHORIZATION.md) --- Permission and
    authorization decisions.

Task identity/lifecycle, execution, roles/actions/models, and events
have moved to
[`../context/tasks-and-lifecycle.md`](../context/tasks-and-lifecycle.md),
[`../context/execution-engine.md`](../context/execution-engine.md),
[`../context/roles-actions-models.md`](../context/roles-actions-models.md),
and [`../context/events-and-state.md`](../context/events-and-state.md)
respectively, as part of the OrchFlow-inspired documentation
consolidation (see `docs/TO-DO.md`).

## Context and Project Domains

-   [`CONTEXT.md`](CONTEXT.md) --- Information available to an
    execution.
-   [`PROJECTS.md`](PROJECTS.md) --- External projects connected through
    adapters.

## Operational Domains

-   [`AUDIT.md`](AUDIT.md) --- Historical operational traceability.
-   [`METRICS.md`](METRICS.md) --- Measurable operational information.
-   [`SUGGESTIONS.md`](SUGGESTIONS.md) --- Non-authoritative
    recommendations.
-   [`CONFIGURATION.md`](CONFIGURATION.md) --- Domain-level
    configuration semantics.

## Domain Relationships

``` text
TASK
  │
  ├── ROLE
  ├── ACTION
  ├── CONTEXT
  └── AUTHORIZATION
          │
          ▼
      EXECUTION
          │
          ├── MODEL
          ├── CAPABILITIES
          └── PROJECT
                  │
                  ▼
                EVENTS
                  │
             ┌────┴────┐
             ▼         ▼
           AUDIT     METRICS
```

## Boundary Rule

Domain documents define **what the system means**.

Architecture documents define **how those concepts are implemented**.

Decision records define **why specific implementation choices were
accepted**.

## Reading Order

For a new contributor, the recommended order is:

1.  `../context/tasks-and-lifecycle.md`
2.  `../context/execution-engine.md`
3.  `AUTHORIZATION.md`
4.  `../context/events-and-state.md`
5.  `../context/roles-actions-models.md`
6.  `CONTEXT.md`
7.  `PROJECTS.md`
8.  `AUDIT.md`
9.  `METRICS.md`
10. `SUGGESTIONS.md`
11. `CONFIGURATION.md`
