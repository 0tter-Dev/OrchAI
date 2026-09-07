# Context Management

## Purpose

Defines Context — the information made available to an execution — as
a controlled resource, not an unrestricted collection of project data.

## Objective

Keep availability, authorization, persistability, and provider
shareability as independently tracked properties of context, so that
an agent noticing useful information never implies it may see, keep,
or externalize that information.

## Current Status

`implemented`

## Lifecycle

```text
REQUESTED → AVAILABLE → AUTHORIZED → RESOLVED → PROVIDED
```

Where applicable, the architecture also distinguishes `PERSISTABLE`
and `PROVIDER-SHAREABLE` as separate properties of resolved context.

## Sources

Context may originate from the task definition, project documentation,
source files, configuration, Git history, previous executions,
execution results, or external references. Tasks should normally
reference context rather than duplicate complete project content — a
reference identifies source, path, resource, version, scope, and
authorization requirements.

## Authorization

Availability does not imply authorization (`AVAILABLE ≠ AUTHORIZED`).
An execution receives only context authorized for that operation, and
authorized context is not automatically persistable, shareable with a
cloud provider, or shareable with any provider outside the project
trust boundary.

## Resolution

The Context Manager converts authorized references into concrete
execution input: locating files, selecting sections, collecting
history, filtering sensitive data, enforcing scope, and producing a
bounded context package. Context should be resolved before crossing
the AI Provider Adapter boundary.

## Context Manager (Component)

Resolves, validates, prepares, and packages context for AI execution.
May resolve requested context, locate project documentation, validate
context authorization, build focused context packages, identify
potentially missing context, and report context requirements. Must
not silently expand explicitly restricted context, modify project
documentation without authorization, or determine the business scope
of a task. Maps to `application/context/` (domain contract in
`domain/context/`).

## Key Rules

- context access is controlled; availability never implies authorization
- provided context is traceable
- context resolution respects task scope
- sensitive context cannot cross trust boundaries without authorization
- authorized context is distinct from both persistable context and provider-shareable context

## Main Relationships

- feeds every `Execution Engine` attempt with resolved, authorized context
- constrained by `Authorization Policy`'s context-authorization mechanics
- sourced from `Project Adapter And Security`, respecting its persistence and provider-sharing policy
- resolved context metadata is reported through `Observability`
