# OrchAI Domain Documentation Index

## Purpose

This document is the navigation entry point for the OrchAI domain model.

Each domain document defines one bounded conceptual responsibility.

## Core Workflow Domains

-   [`TASKS.md`](TASKS.md) --- Task identity, scope, lifecycle, and
    state.
-   [`EXECUTION.md`](EXECUTION.md) --- Concrete execution attempts and
    outcomes.
-   [`AUTHORIZATION.md`](AUTHORIZATION.md) --- Permission and
    authorization decisions.
-   [`EVENTS.md`](EVENTS.md) --- Domain events and event semantics.

## Agent and Operation Domains

-   [`ROLES.md`](ROLES.md) --- Agent responsibilities.
-   [`ACTIONS.md`](ACTIONS.md) --- Operations an execution may perform.
-   [`MODELS.md`](MODELS.md) --- AI execution resources.
-   [`CAPABILITIES.md`](CAPABILITIES.md) --- Technically available
    capabilities.

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

1.  `TASKS.md`
2.  `EXECUTION.md`
3.  `AUTHORIZATION.md`
4.  `EVENTS.md`
5.  `ROLES.md`
6.  `ACTIONS.md`
7.  `MODELS.md`
8.  `CONTEXT.md`
9.  `PROJECTS.md`
10. `CAPABILITIES.md`
11. `AUDIT.md`
12. `METRICS.md`
13. `SUGGESTIONS.md`
14. `CONFIGURATION.md`
