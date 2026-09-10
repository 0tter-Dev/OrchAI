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

The current concrete adapter is `LiteLLMProvider`
(`infrastructure/ai/litellm_provider.py`), covering OpenAI, Anthropic,
Gemini, Ollama, and other OpenAI-compatible local runtimes behind one
calling convention (see `Technology And Test Strategy`); it replaced
two earlier hand-rolled, single-provider adapters.

`execute_stream()` extends the same port with an `AsyncIterator` of
`AIProviderStreamChunk` (`delta`, `finished`, `provider_name`,
`finish_reason`, and token counts, arriving across chunks rather than
only on the final one) for incremental output — additive, not a
replacement: `execute()` remains what `AUTOMATIC`-mode,
non-interactive, and CLI callers use when only the final result
matters, and `Execution`'s state machine still records exactly one
atomic terminal result regardless of whether it was produced by a
streamed or non-streamed call. Transport to external clients is
Server-Sent Events, not a WebSocket, since the flow is strictly
server-to-client. Cost estimation is skipped for streamed replies
(`resource_usage.estimated_cost` is always `None`), since computing it
accurately would require reassembling the full response from every
chunk first. `execute_stream()` is implemented and unit-tested, and
`ExecutionEngine.run_stream()` is its Task-bounded caller: it drives
`execute_stream()`, yields each chunk onward, and reassembles the
accumulated deltas and token counts into the same
`AIProviderExecutionResult` shape `ExecutionEngine.run()` produces, so
completion/event/audit recording needs no branching by
streamed-vs-not. `run_stream()` is now externally reachable through
`POST /executions/{execution_id}/run-stream` (SSE) — a dedicated
fine-grained operational endpoint alongside the existing non-streaming
`POST /executions/{execution_id}/run`, not a change to `/requests`'s
own advance flow (see `Chat-First And Interfaces`'s Request Lifecycle:
`/requests/{id}/advance` still drives the multi-stage orchestrator
through the non-streaming `execute()`/`run()` path end to end). Each
SSE chunk event carries `type: "delta"`; once the stream ends, a final
`type: "done"` event carries the fully serialized terminal `Execution`
(state, result, resource usage), the same delta-then-done shape used
by conversation streaming. The one-shot CLI process has no persistent
connection to stream over, so `orchai executions run` intentionally
stays on the non-streaming path — mirroring how conversation streaming
has no CLI command either. The Desktop Approval Card consuming this
endpoint is tracked as the next step in `docs/TO-DO.md`. This is now
the same externally-reachable shape as the streaming already used by
non-escalated conversation messages
(`ConversationAIProviderPort.complete_stream()`, see `Chat-First And
Interfaces`'s Conversations section) — both are SSE-reachable, just
through different endpoints for their different bounded contexts.

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
- long-running execution is asynchronous (`asyncio`), without distributed worker infrastructure, and execution dispatch stays behind an application/infrastructure boundary so a future durable worker or broker can be introduced without changing domain concepts

This document folds in the still-relevant decisions from the former
ADR-008 (Async In-Process Execution Baseline) and ADR-013 (LiteLLM
Provider Adapter and Streaming Execution — the AI Provider Adapter
Boundary section above); full rationale for each remains in
`docs/archive/decisions/`.

## Main Relationships

- belongs to `Tasks And Lifecycle`
- depends on `AI Provider Adapter` for the actual model call
- depends on `Roles, Actions, And Models` for what it is executing and with what
- depends on `Context Management` for what the adapter may see
- emits records to `Observability`
- is invoked through `Chat-First And Interfaces` (`/requests/{id}/advance`) and the operational surface (`/executions`)
