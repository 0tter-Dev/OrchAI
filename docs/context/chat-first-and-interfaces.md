# Chat-First And Interfaces

## Purpose

Defines the Chat-First Request Model — the `/requests` projection of
the Task domain that is the primary entry point for external clients
— and the CLI/API/future-UI boundary rules that apply to every
interface OrchAI exposes.

## Objective

Let an external user who thinks in terms of "project + model + role +
prompt" drive the same precise Task/Authorization/Execution machinery
operators use through the fine-grained surface, without introducing a
second, competing set of lifecycle rules.

## Current Status

`implemented`

## Interface Model

The implementation is API-first with a CLI using the same application
services:

```text
CLI ───────┐
           ├── Application Services
API ───────┘
```

Future chat interfaces, web applications, mobile clients, and desktop
applications consume the API without changing domain logic. Both
interfaces are intentionally thin: they do not own lifecycle rules,
authorization decisions, context resolution, or project-resource
access.

## Client / UI (Component)

Provides the user-facing interface for interacting with the
Orchestrator. May create tasks, select projects, configure execution
parameters, review task state and execution results, approve or
reject authorization requests, review suggestions, and inspect audit
information and metrics. Must not contain core orchestration rules,
directly modify task state, bypass authorization, or directly invoke
project operations outside the Orchestrator.

## Two Surfaces

```text
/requests/*    Chat-First surface — primary entry point for external
               clients (chat UIs, mobile apps, web apps). Accepts a
               project + model + role + action + prompt and
               orchestrates the complete flow transparently.

Fine-grained   Operational surface — explicit step-by-step control for
endpoints      operators, automated pipelines, and direct integration
               (/tasks/*, /authorizations/*, /executions/*, /flows/*).
```

A Request maps one-to-one to a Task internally — the `/requests` layer
is a projection, not a new domain concept, and introduces no
independent lifecycle rules.

## Request Lifecycle

```text
POST /requests
        │
        ▼
    CREATED
        │
        ├─── SUGGESTED mode ───► PENDING_SUGGESTION
        │                               │
        │                        POST /requests/{id}/approve
        │                               │
        │                               ▼
        ├─── MANUAL / AUTOMATIC ──► RUNNING
        │
        ▼
    PLANNING → IMPLEMENTING → REVIEWING → VALIDATING → TESTING → DOCUMENTING
        │
        ▼
    COMPLETED / FAILED / CANCELLED
```

Each stage transition is driven by `POST /requests/{id}/advance` —
including the very first one, PLAN. `POST /requests` never advances
the task past a stage on its own behalf: it creates the project and
the task, then advances through exactly one gated stage (PLAN),
stopping there in `SUGGESTED` mode unless `approve_suggestion: true`
is supplied. No code path, storage backend, or entry point (`/requests`,
`/flows/local`, `/projects/operations`, `/tasks/{id}/advance`) skips
this gate for any stage. The only exception is `AUTOMATIC` execution
mode, and even then only for a `(role, action)` pair the operator has
explicitly listed in `AutomaticExecutionPolicy.allowed_operations`
beforehand — without that prior configuration, `AUTOMATIC` mode is
blocked by the same gate as `SUGGESTED` mode
(`automatic_policy_denied` instead of
`suggested_mode_requires_approval`).

## Observable Flow

`GET /requests/{request_id}/flow` returns the full orchestration trace
for a request — request_id, status, task summary, orchestration steps
(from audit), authorizations, executions, resolved context metadata,
current suggestion (with an approval URL), events, audit records, and
aggregated metrics — in one response, so a chat interface can render a
complete progress timeline without issuing multiple queries.

## Configuration Selection In A Chat Context

The user selects Project, Model (local via Ollama or cloud via another
configured provider), Role (`DEVELOPER`/`PLANNER`/`QUALITY_AGENT`/
`VALIDATOR`/`TESTER`/`DOCUMENTER`), Action (`PLAN`/`IMPLEMENT`/`REVIEW`/
`VALIDATE`/`TEST`/`DOCUMENT`), and Execution Mode
(`MANUAL`/`SUGGESTED`/`AUTOMATIC`). Everything else — authorization,
context resolution, readiness gates, policy enforcement, audit,
metrics — is handled transparently by OrchAI.

## Approval And Advancing

When `execution_mode=SUGGESTED` and `approve_suggestion=false`, the API
returns immediately after generating a suggestion; the client shows it
to the user and waits for explicit approval via
`POST /requests/{request_id}/approve`. This records an explicit
authorization decision and does not bypass OrchAI's authorization
machinery — it is equivalent to
`POST /authorizations/{id}/decision` with `status=GRANTED`.

For multi-stage tasks, the client sends one
`POST /requests/{request_id}/advance` per stage, mapping to the
existing `POST /tasks/{task_id}/advance` and driving the Task through
the Orchestrator's staged workflow.

`POST /projects/operations` is an operator-only endpoint that runs a
single protected `ProjectOperation` (read, write, run a command, run
tests) outside the PLAN → ... → DOCUMENT cycle. The task it creates
internally must still reach `PLANNED` before that operation can start
(the state machine only allows `IMPLEMENTING`/`REVIEWING`/
`VALIDATING`/`TESTING` directly from `PLANNED`); that bootstrap hop is
gated by the same suggestion/policy mechanism (role `TASK_PLANNER`,
action `PLAN`), authorized and audited like any other stage, and a
single `approve_operation: true` covers both the bootstrap and the
operation itself.

## Relationship To Existing Endpoints

`/requests/*` is additive — it does not replace `/flows/local` (legacy,
retained for compatibility), `/tasks/*`/`/authorizations/*`/
`/executions/*` (fine-grained management for operators), or the
observability endpoints (also surfaced in `/flow`). External clients
targeting a chat-like integration use `/requests/*`; internal tools,
operators, and automated pipelines continue to use the fine-grained
endpoints.

## Endpoint And Command Inventory

The full HTTP endpoint set is grouped by resource: System/Providers
(`/`, `/health`, `/settings/runtime`, `/providers/*`, `/runtime/check`),
Projects, Tasks, Authorizations/Policies, Executions, Observability
(`/events`, `/audit*`, `/metrics`, `/suggestions*`), Legacy Flows
(`/flows/local`, `/projects/operations`), Admin (`/admin/db/sync`,
plus the identity admin surface in `Identity And Access`), and the
Chat-First surface above. See `docs/API-ENDPOINTS-REPORT.md` for the
authoritative, continuously-verified per-endpoint status. The CLI
(`orchai`) mirrors this same surface command-for-command (`orchai
request`, `orchai tasks *`, `orchai projects *`, `orchai executions *`,
`orchai policies *`, `orchai audit/events/metrics/suggestions *`,
`orchai api serve`, etc.) — both are thin interfaces over the same
application services and never own lifecycle rules directly.

Operational list queries support bounded filtering, e.g. `GET
/tasks?project_id=<id>&state=PLANNING&limit=20`.

## Conversations

A `Conversation` (with `Message` records) is a second, independent
bounded context alongside `/requests` — multi-turn and long-lived,
where most messages are ordinary back-and-forth that never need a
`Task`/`Authorization`/`Execution` behind them. `Conversation` carries
`id`, `module_id`, an optional `project_id`, and a title; `Message`
carries `role` (`USER`/`ASSISTANT`/`SYSTEM`), `content`, `provider_name`,
an optional `model_id`, and optional `linked_task_id`/
`linked_execution_id`. A message's lifecycle is a plain enum
(`PENDING → STREAMING → COMPLETE | FAILED`), not a `StateMachine`-governed
aggregate like Task or Execution.

**Escalation to a real Task is always explicit, never inferred.** A
message becomes a `Task` only through a deliberate user action (an
"Execute as Task" control, or a slash-command like `/plan`,
`/implement`, `/review` mapping to a known `(role, action)` pair) — at
that point OrchAI calls the exact same `/requests` machinery described
above, with no parallel authorization path, and records the resulting
`task_id`/`execution_id` on the triggering message. There is no
automatic intent classifier; if automatic classification is ever
proposed, it must itself surface only as a suggestion (see
`Observability`), never as direct, silent Task creation.

Non-escalated messages are answered through a separate, narrower
`ConversationAIProviderPort.complete()`/`complete_stream()` (no
Task/Role/Action concept at all) rather than the Task-bounded
`AIProviderPort.execute()` used by `/requests` (see `Execution
Engine`) — `LiteLLMProvider` implements both ports. Endpoints:
`POST`/`GET /conversations`, `GET /conversations/{id}`, `POST`/`GET
/conversations/{id}/messages` (message send may stream, see `Execution
Engine`'s streaming note); message escalation is `POST
/conversations/{id}/escalate`.

## Key Rules

- UI state is never authoritative task state; UI actions never bypass authorization
- suggestions remain suggestions until explicitly accepted
- API and CLI share application behavior — neither owns lifecycle rules independently
- `/requests` is a projection over Task and introduces no independent lifecycle rules
- `POST /requests/{id}/approve` records an explicit authorization decision; it never bypasses the authorization boundary
- "pending" is derived from the absence of a decision (`Authorization.status is None`) or `SuggestionStatus.PRESENTED`, never a literal `"PENDING"` string
- selecting "the most recent" record from a repository `list()` result must use an explicit timestamp comparison, never list position — repositories do not share an ordering guarantee
- `Conversation`/`Message` persistence is independent of `Task`; a `Message` escalates only through an explicit user action mapping to a known `(role, action)` pair, never inferred intent, and escalation reuses the `/requests` authorization/policy/suggestion path unmodified

This document folds in the still-relevant decisions from the former
ADR-004 (API-First Interface Boundary — superseded in spirit by the
chat-first layer above), ADR-011 (Chat-First Request Interface — the
Request Lifecycle mechanics above), and ADR-014 (Conversation/Message
domain model — the Conversations section above); full rationale for
each remains in `docs/archive/decisions/`.

## Main Relationships

- projects `Tasks And Lifecycle` toward external clients
- delegates every stage transition to `Authorization Policy` and `Execution Engine`
- reports through `Observability` via `GET /requests/{id}/flow`
- depends on `Identity And Access` for the bearer-token authentication layer in front of it
