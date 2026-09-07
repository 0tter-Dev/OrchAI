# OrchAI --- Chat-First Request Model

## Purpose

This document describes the Chat-First Request Model — the primary
interaction pattern for external clients that consume OrchAI as an AI
orchestration back-end through a conversational interface.

It does not replace the underlying domain model. It defines how that
model is projected toward an external user who thinks in terms of
project + model + role + prompt, not in terms of Tasks, Authorizations,
and Executions as separate resources.

---

## 1. Motivation

OrchAI's internal model is precise and explicit: a Task has a state
machine, an Execution has its own lifecycle, an Authorization is a
separate record with its own decision flow. This precision is correct
and must be preserved.

However, an external user operating through a chat-like interface does
not think in those terms. They think:

> I have a project. I want an AI to review this module. Use the local
> model. Do it.

The Chat-First Request Model bridges that gap. It is a thin projection
layer over the existing orchestration machinery.

---

## 2. Conceptual Request Flow

```text
External Client (chat UI, mobile app, desktop app)
        │
        │  POST /requests
        │  {
        │    "project_root": "/path/to/project",
        │    "prompt": "Review the authentication module for security issues",
        │    "role": "QUALITY_AGENT",
        │    "action": "REVIEW",
        │    "model": "qwen2.5-coder:latest",
        │    "execution_mode": "SUGGESTED",
        │    "provider_target": "LOCAL"
        │  }
        ▼
┌─────────────────────────────────────────────────────────┐
│                        OrchAI API                       │
│                                                         │
│  1. Register or look up project                         │
│  2. Create Task (title from prompt, description=prompt) │
│  3. Apply policy + authorization check                  │
│  4. Generate suggestion (if SUGGESTED mode)             │
│  5. Run execution (if AUTOMATIC or approved)            │
│  6. Return request_id + current status + suggestion     │
└─────────────────────────────────────────────────────────┘
        │
        │  Response:
        │  {
        │    "request_id": "tsk_abc123",
        │    "status": "PENDING_SUGGESTION",
        │    "suggestion": { ... },
        │    "flow_url": "/requests/tsk_abc123/flow"
        │  }
        ▼
External Client polls GET /requests/{request_id}/flow
or sends POST /requests/{request_id}/approve
```

---

## 3. Request Lifecycle

A Request is a Task observed through the chat-first lens. Its lifecycle
maps directly to the Task state machine:

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
    PLANNING
    IMPLEMENTING
    REVIEWING
    VALIDATING
    TESTING
    DOCUMENTING
        │
        ▼
    COMPLETED / FAILED / CANCELLED
```

Each stage transition is driven by `POST /requests/{id}/advance` — including
the very first one, PLAN. `POST /requests` never advances the task past a
stage on its own behalf: it creates the project and the task, then advances
through exactly one gated stage (PLAN), stopping there in SUGGESTED mode
unless `approve_suggestion: true` is supplied. There is no code path,
storage backend, or entry point (`/requests`, `/flows/local`,
`/projects/operations`, `/tasks/{id}/advance`) that skips this gate for any
stage. The only exception is `AUTOMATIC` execution mode, and even then only
for a `(role, action)` pair the operator has explicitly listed in
`AutomaticExecutionPolicy.allowed_operations` beforehand — AUTOMATIC mode
grants configured operations a "free" transition without waiting for a
human decision, it does not grant the request an unconditional pass through
every stage. Without that prior configuration, AUTOMATIC mode is blocked by
the exact same gate as SUGGESTED mode (`automatic_policy_denied` instead of
`suggested_mode_requires_approval`).

---

## 4. Observable Flow

`GET /requests/{request_id}/flow` returns the full orchestration trace
for a Request. This is the data source for the "live progress view" in
a chat interface.

The flow response includes:

```text
request_id         Stable identifier
status             Current status
task               Full task summary (state, metadata, timestamps)
orchestration      List of orchestration steps taken (from audit)
authorizations     Authorization records associated with this request
executions         Execution records (state, model, provider, outcome)
context            Resolved context metadata
suggestion         Current suggestion (if any, with approval_url)
events             Domain events in chronological order
audit              Audit records
metrics            Aggregated metrics (tokens, duration, cost estimate)
```

This single response allows a chat interface to render the complete
progress timeline without issuing multiple queries.

---

## 5. Configuration Selection in a Chat Context

In a chat-like interface, the user selects the following before
submitting a prompt:

```text
Project          Folder/path connected to OrchAI
Model            AI agent model:
                   LOCAL  → Ollama (e.g. qwen2.5-coder:latest)
                   CLOUD  → OpenAI/Codex or other configured adapter
Role             Orchestration role:
                   DEVELOPER, PLANNER, QUALITY_AGENT, VALIDATOR,
                   TESTER, DOCUMENTER
Action           Operation to perform:
                   PLAN, IMPLEMENT, REVIEW, VALIDATE, TEST, DOCUMENT
Execution Mode   MANUAL | SUGGESTED | AUTOMATIC
```

Everything else (authorization, context resolution, readiness gates,
policy enforcement, audit, metrics) is handled transparently by OrchAI.

---

## 6. Approval in SUGGESTED Mode

When `execution_mode=SUGGESTED` and `approve_suggestion=false`, the API
returns immediately after generating a suggestion. The client shows the
suggestion to the user and waits for explicit approval:

```text
POST /requests/{request_id}/approve
{
  "reason": "User confirmed in chat UI"
}
```

This records an explicit authorization decision and continues the flow.
It does not bypass OrchAI's authorization machinery — it is equivalent
to `POST /authorizations/{id}/decision` with `status=GRANTED`.

---

## 7. Advancing Through Stages

For multi-stage tasks (e.g. PLAN → IMPLEMENT → REVIEW), the client
sends one request per stage:

```text
POST /requests/{request_id}/advance
{
  "stage": "REVIEW",
  "approve_stage": true,
  "context_paths": ["src/auth.py"]
}
```

This maps to the existing `POST /tasks/{task_id}/advance` and drives
the Task through the Orchestrator's staged workflow.

---

## 8. Relationship to Existing Endpoints

The `/requests` surface is additive — it does not replace any existing
endpoint.

```text
/requests/*           Chat-first projection for external clients
/flows/local          Legacy local flow (retained for compatibility)
/tasks/*              Fine-grained task management for operators
/authorizations/*     Direct authorization management
/executions/*         Direct execution management
/audit, /events,
/metrics, /suggestions  Observability endpoints (also surfaced in /flow)
```

External clients targeting a chat-like integration should use
`/requests/*`. Internal tools, operators, and automated pipelines
continue to use the existing fine-grained endpoints.

`POST /projects/operations` is an operator-only endpoint that runs a single
protected `ProjectOperation` (read, write, run a command, run tests) outside
the PLAN → ... → DOCUMENT cycle. The task it creates internally must still
reach `PLANNED` before that operation can start, because the task state
machine only allows `IMPLEMENTING`/`REVIEWING`/`VALIDATING`/`TESTING`
directly from `PLANNED`. That bootstrap hop is gated by the same
suggestion/policy mechanism described above (role `TASK_PLANNER`, action
`PLAN`) — it is authorized and audited like any other stage, and a single
`approve_operation: true` covers both the bootstrap and the operation
itself. It does not run an AI execution of its own; only an authorization
record is created for it, since the operation being requested is the actual
unit of work.

---

## 9. Future Considerations

- **Streaming:** resolved by ADR-013 --- `AIProviderPort` gains
  `execute_stream()`, and the new `/conversations/{id}/messages`
  endpoint (ADR-014) streams via SSE. `GET /requests/{id}/flow` itself
  remains a read-only, non-streaming snapshot.
- **Session continuity:** resolved by ADR-014 --- rather than a
  `session_id` parameter on `/requests`, a new, independent
  `Conversation`/`Message` bounded context groups multi-turn chat, with
  explicit-only escalation of a message to a `/requests` call. See
  `docs/decisions/ADR-014-CONVERSATION-DOMAIN-MODEL.md`.
- **Model discovery:** still open. `GET /providers/models` (or an
  equivalent) to let a client populate the model selector dynamically
  remains unimplemented; ADR-013's adoption of LiteLLM makes this more
  valuable, since the set of usable models grows with LiteLLM's own
  provider coverage.
- **Authentication:** resolved differently than anticipated here ---
  ADR-012 implemented persisted users/permissions/JWT for the CLI and
  API generally, and ADR-016 defines how OrchAI Desktop specifically
  uses that layer (attribution only, no enforcement, single local
  user) rather than per-user API keys at the request boundary.
