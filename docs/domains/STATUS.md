# OrchAI Domain Status

## Purpose

This document tracks the definition and implementation state of the
domain model.

It intentionally remains concise. Detailed rules belong to the
individual domain documents.

## Domain Status

  Domain          Status      Primary Document
  --------------- ----------- ----------------------------------------
  Tasks           `PARTIAL`   [`TASKS.md`](TASKS.md)
  Execution       `PARTIAL`   [`EXECUTION.md`](EXECUTION.md)
  Authorization   `PARTIAL`   [`AUTHORIZATION.md`](AUTHORIZATION.md)
  Events          `PARTIAL`   [`EVENTS.md`](EVENTS.md)
  Roles           `PARTIAL`   [`ROLES.md`](ROLES.md)
  Actions         `PARTIAL`   [`ACTIONS.md`](ACTIONS.md)
  Models          `PARTIAL`   [`MODELS.md`](MODELS.md)
  Context         `PARTIAL`   [`CONTEXT.md`](CONTEXT.md)
  Projects        `PARTIAL`   [`PROJECTS.md`](PROJECTS.md)
  Capabilities    `PARTIAL`   [`CAPABILITIES.md`](CAPABILITIES.md)
  Audit           `DEFINED`   [`AUDIT.md`](AUDIT.md)
  Metrics         `DEFINED`   [`METRICS.md`](METRICS.md)
  Suggestions     `DEFINED`   [`SUGGESTIONS.md`](SUGGESTIONS.md)
  Configuration   `PARTIAL`   [`CONFIGURATION.md`](CONFIGURATION.md)

## Implementation State

``` text
Domain Contracts
    -> DEFINED

Domain Code
    -> PARTIAL

Domain Unit Tests
    -> PARTIAL

Domain Integration
    -> PARTIAL
```

Implemented domain slices currently include task state transitions,
authorization requests and decisions, execution lifecycle,
role/action/model/capability vocabularies, context references/packages,
and external project metadata.

Audit, metrics, suggestions, policy, and provider adapter domains remain
definition-first and are not yet implemented as validated code.

## Open Conceptual Areas

The following concepts affect multiple domains and should be finalized
before implementation:

-   Agent as a domain concept versus a composition of role, policy,
    model, and capabilities.
-   Workflow responsibility versus State Machine responsibility.
-   Task Engine versus Application Orchestration.
-   Execution Engine versus Execution domain.
-   Model Manager versus model/provider contracts.
-   Context Manager versus Context domain.
-   Project Adapter boundary versus Project domain.

These are tracked here as architectural follow-up topics rather than
domain implementation tasks.

## Rule

A domain may be marked `IMPLEMENTED` only when its contract,
implementation, and relevant tests are aligned.
