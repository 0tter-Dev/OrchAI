# Execution Engine

## Purpose

Defines an Execution — a bounded attempt to perform an Action for a
Task using a specific Role and Model — and the engine that constructs,
runs, and records it.

## Objective

Provide the single mechanism by which an authorized task stage is
actually carried out against an AI provider, with results, resource
usage, and failures captured in a traceable, replaceable way.

## Current Status

`implemented`

## Execution Identity And Lifecycle

An execution has a unique identity and preserves references to its
`TASK`, `ROLE`, `ACTION`, `MODEL`, `PROJECT`, `CONTEXT`, and
`AUTHORIZATION`, plus timestamps and outcome information.

Conceptual lifecycle: `REQUESTED → AUTHORIZED → PREPARING → STARTED →
RUNNING → COMPLETED`, with failure paths `REJECTED`/`BLOCKED`/
`FAILED`/`CANCELLED`/`TIMEOUT`.

## Execution Construction

The Execution Engine builds a bounded execution request from: task
definition, role definition, action definition, selected model,
authorized context, project capabilities, acceptance criteria,
execution mode, applicable policies, and authorization. Before
invoking the model it may perform parameter/policy/authorization
validation, context resolution, model availability checks, and
project capability checks — none of which may silently change
user-authorized scope.

## Execution Result And Resource Usage

A result preserves success/failure, model output, execution metadata,
generated artifacts, errors, warnings, resource usage, and timing.
Where available, resource usage records input/output/total tokens,
duration, estimated cost, provider usage, and local/cloud
classification, feeding the Observability domain.

Execution failure never implies task failure by itself; a failed
execution may lead to retry, replan, block, user review, or task
failure depending on configured workflow. Retries create new,
traceable execution attempts rather than overwriting the failed one
(`EXECUTION #1 → FAILED`, `EXECUTION #2 → COMPLETED`).

## Execution Engine (Component)

Coordinates the actual execution of an authorized task action. May
validate execution parameters, prepare an execution request, invoke
the selected model adapter, capture output and metadata, and report
results. Must not silently change the user's selected model, expand
context authorization, change role, cross role boundaries
independently, or interpret a suggestion as authorization. Maps to
`application/executions/`; individual Execution attempts are owned
here, and failed or interrupted attempts remain historical records,
never overwritten by later attempts.

## AI Provider Adapter Boundary

The conceptual adapter contract is `prepare()` / `validate()` /
`execute()` / `cancel()` / `capabilities()`. The current implementation
formalizes `AIProviderPort.capabilities()`, `validate_request()`,
`execute()` (returning an `AIProviderExecutionResult`), and
`cancel(execution_id)`; `prepare()` remains a conceptual future
extension.

The request an adapter receives is bounded: `Task`, `Role`, `Action`,
`Model`, `Authorized Context`, `Execution Configuration`, `Applicable
Capabilities` — never unrestricted project access. The result an
adapter returns: `Outcome`, `Provider Metadata`, `Model Metadata`,
`Output`, `Warnings`, `Errors`, `Resource Usage`, `Artifacts`.
Provider-specific SDK/HTTP types stay inside infrastructure adapters
and never leak into domain models. Adapters preserve useful failure
information while mapping provider-specific failures into stable
OrchAI error categories, and capability negotiation follows the same
`Required Capability → Available Capability → Authorization Policy →
Allowed Operation` sequence described in `Roles, Actions, And Models`.

## Key Rules

- every execution belongs to exactly one task
- every execution has one role, one action, and one effective model
- authorization must be validated before execution where required
- execution results must be traceable and failed executions must never be overwritten
- context supplied to an execution must be auditable, distinguishing Requested/Authorized/Resolved/Provided context
- model and provider details stay behind adapters
- execution must not silently expand task scope
- cross-role transitions must respect authorization policy
- resource usage should be captured whenever technically available

## Main Relationships

- belongs to `Tasks And Lifecycle`
- depends on `AI Provider Adapter` for the actual model call
- depends on `Roles, Actions, And Models` for what it is executing and with what
- depends on `Context Management` for what the adapter may see
- emits records to `Observability`
- is invoked through `Chat-First And Interfaces` (`/requests/{id}/advance`) and the operational surface (`/executions`)
