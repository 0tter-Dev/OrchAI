# OrchAI Domain Status

## Purpose

This document tracks the definition and implementation state of the
domain model.

It intentionally remains concise. Detailed rules belong to the
individual domain documents.

> **Reconciliation note (2026-08-23, v0.1.7):** this document previously
> marked every domain `PARTIAL` while `docs/STATUS.md` and
> `docs/architecture/STATUS.md` already marked the corresponding areas
> `IMPLEMENTED`. That was documentation drift, not a real
> disagreement: this file had not been updated since 2026-08-20, before
> several domains reached their current implemented-and-tested state
> (confirmed directly against the code and a clean `124 passed` test
> run during this reconciliation). The table below now matches
> `docs/STATUS.md`. See `docs/TO-DO.md` for what remains open at the
> application/infrastructure level (IAM, `AutomaticExecutionPolicy`
> runtime configuration, execution cancellation, metrics aggregation,
> an Anthropic provider adapter) --- none of that is a domain-layer gap,
> which is what this document tracks.

## Domain Status

  Domain          Status         Primary Document
  --------------- -------------- ----------------------------------------
  Tasks           `IMPLEMENTED`  [`TASKS.md`](TASKS.md)
  Execution       `IMPLEMENTED`  [`EXECUTION.md`](EXECUTION.md)
  Authorization   `IMPLEMENTED`  [`AUTHORIZATION.md`](AUTHORIZATION.md)
  Events          `IMPLEMENTED`  [`EVENTS.md`](EVENTS.md)
  Roles           `IMPLEMENTED`  [`ROLES.md`](ROLES.md)
  Actions         `IMPLEMENTED`  [`ACTIONS.md`](ACTIONS.md)
  Models          `IMPLEMENTED`  [`MODELS.md`](MODELS.md)
  Context         `IMPLEMENTED`  [`CONTEXT.md`](CONTEXT.md)
  Projects        `IMPLEMENTED`  [`PROJECTS.md`](PROJECTS.md)
  Capabilities    `IMPLEMENTED`  [`CAPABILITIES.md`](CAPABILITIES.md)
  Audit           `IMPLEMENTED`  [`AUDIT.md`](AUDIT.md)
  Metrics         `PARTIAL`      [`METRICS.md`](METRICS.md)
  Suggestions     `IMPLEMENTED`  [`SUGGESTIONS.md`](SUGGESTIONS.md)
  Configuration   `IMPLEMENTED`  [`CONFIGURATION.md`](CONFIGURATION.md)

Metrics is the one domain kept at `PARTIAL` rather than matched to
`docs/STATUS.md`'s combined "Audit and Metrics: `IMPLEMENTED`" row: its
current contract (deriving per-execution `MetricRecord`s from
authoritative events) is implemented and tested, but the domain
document's own aggregation-oriented invariants have no aggregation
query anywhere in the codebase yet (`MetricsRepository` only supports
`add_many()` and a filtered `list()` of individual records). See
`docs/TO-DO.md` Priority 3.

## Implementation State

``` text
Domain Contracts
    -> DEFINED

Domain Code
    -> IMPLEMENTED

Domain Unit Tests
    -> IMPLEMENTED

Domain Integration
    -> IMPLEMENTED (for the current operational scope)
```

Implemented domain slices currently include task state transitions,
authorization requests and decisions, execution lifecycle,
role/action/model/capability vocabularies, context references/packages,
context-resolution metadata, external project metadata, filesystem
Project Adapter discovery and protected operations, domain events,
initial audit records, event-derived execution metrics, task-state
suggestions, execution-mode enforcement, an initial policy slice at the
application boundary, and the provider-independent execution adapter
boundary.

Metrics and suggestions are implemented only for the first operational
slice: metrics as per-execution derivation without aggregation (see
above), suggestions as single-next-step recommendations from current
task state without a broader recommendation engine. Policy is
runtime-enforced for the local flow and protected project operations,
but is not yet a fully configurable engine --- there is no CLI/API
surface to configure `AutomaticExecutionPolicy` at runtime (tracked in
`docs/TO-DO.md`). Audit is implemented for the initial event-derived
history path. Project integration is limited to the filesystem
adapter, and provider integration currently covers the
provider-independent `AIProviderPort` plus three concrete adapters:
`stub` (in-process, deterministic, for tests), `ollama` (real
HTTP-backed local inference), and `openai` (real HTTP-backed cloud
inference via the Responses API, covering OpenAI and Codex-capable
models). An Anthropic/Claude adapter does not exist yet (also tracked
in `docs/TO-DO.md`). Project security profiles and readiness gates are
now implemented as a runtime-enforced domain/application slice with
persisted effective and observed project state.

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
