# OrchAI Domain Documentation Index

## Purpose

This document is the navigation entry point for the OrchAI domain model.

Each domain document defines one bounded conceptual responsibility.

## Core Workflow Domains

Task identity/lifecycle, execution, roles/actions/models, events,
authorization, identity/access, project adapter/security, and context
management have all moved to `docs/context/` as part of the
OrchFlow-inspired documentation consolidation (see `docs/TO-DO.md`):
[`../context/tasks-and-lifecycle.md`](../context/tasks-and-lifecycle.md),
[`../context/execution-engine.md`](../context/execution-engine.md),
[`../context/roles-actions-models.md`](../context/roles-actions-models.md),
[`../context/events-and-state.md`](../context/events-and-state.md),
[`../context/authorization-policy.md`](../context/authorization-policy.md),
[`../context/identity-and-access.md`](../context/identity-and-access.md),
[`../context/project-adapter-and-security.md`](../context/project-adapter-and-security.md),
and
[`../context/context-management.md`](../context/context-management.md).

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
3.  `../context/authorization-policy.md`
4.  `../context/events-and-state.md`
5.  `../context/roles-actions-models.md`
6.  `../context/context-management.md`
7.  `../context/project-adapter-and-security.md`
8.  `../context/identity-and-access.md`
9.  `AUDIT.md`
10. `METRICS.md`
11. `SUGGESTIONS.md`
12. `CONFIGURATION.md`
