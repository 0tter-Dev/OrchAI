# OrchAI --- API and UI Boundary

## Purpose

The interface layer exposes OrchAI capabilities without exposing
internal implementation details.

## Interface Model

The implementation is API-first with a CLI using the same application
services.

``` text
CLI ───────┐
           ├── Application Services
API ───────┘
```

Future chat interfaces, web applications, mobile clients, and desktop
applications consume the API without changing domain logic.

The API exposes two distinct surfaces for different consumer profiles:

```text
/requests/*    Chat-First surface — primary entry point for external
               clients (chat UIs, mobile apps, web apps). Accepts a
               project + model + role + action + prompt and orchestrates
               the complete flow transparently.

Fine-grained   Operational surface — explicit step-by-step control for
endpoints      operators, automated pipelines, and direct integration.
               (/tasks/*, /authorizations/*, /executions/*, /flows/*)
```

## Chat-First Request Interface (Primary External Entry Point)

See `CHAT-FIRST-REQUEST-MODEL.md` for the full description.

The primary flow for external clients:

``` text
POST  /requests                          Create request (project + model + role + prompt)
GET   /requests/{request_id}/flow        Observe full orchestration flow
POST  /requests/{request_id}/approve     Approve pending suggestion
POST  /requests/{request_id}/advance     Advance to next workflow stage
```

A Request maps one-to-one to a Task internally. The `/requests` layer
is a projection, not a new domain concept.

## Core Operations

``` text
TASK MANAGEMENT
TASK STATE
PLANNING
AUTHORIZATION
EXECUTION
SUGGESTIONS
PROJECTS
AUDIT
METRICS
CONFIGURATION
```

## Current Interface Implementation

The current implementation includes a Typer CLI and a FastAPI surface.
Both are thin interfaces over application services and infrastructure
configuration.

The interfaces are intentionally thin. They do not own lifecycle rules,
authorization decisions, context resolution, or project-resource
access.

### CLI Commands

``` text
orchai db sync
orchai local-flow
orchai request                     (chat-first: project + role + action + prompt)
orchai projects register
orchai tasks list
orchai tasks create
orchai tasks show
orchai tasks snapshot
orchai tasks advance
orchai tasks transition
orchai authorizations list           (--status, --pending-only filters)
orchai authorizations show
orchai authorizations request
orchai authorizations decide
orchai policies evaluate
orchai executions list
orchai executions request
orchai executions dispatch
orchai executions run
orchai executions show
orchai executions transition
orchai executions complete           (--metadata, --resource-metadata JSON)
orchai executions resolve-context
orchai executions context
orchai audit list
orchai audit show
orchai events list
orchai metrics list
orchai suggestions list
orchai suggestions show
orchai suggestions generate
orchai suggestions accept
orchai suggestions reject
orchai projects discover
orchai projects readiness
orchai projects security
orchai projects operate
orchai projects list
orchai projects lookup
orchai projects show
orchai projects update-security
orchai providers show
orchai providers capabilities
orchai providers health
orchai runtime check
orchai api serve
```

### HTTP Endpoints

#### Chat-First Surface (primary external integration)

``` text
POST  /requests
GET   /requests/{request_id}/flow
POST  /requests/{request_id}/approve
POST  /requests/{request_id}/advance
```

#### System and Providers

``` text
GET   /health
GET   /
GET   /settings/runtime
GET   /providers/settings
GET   /providers/capabilities
GET   /providers/health
GET   /runtime/check
```

#### Projects

``` text
POST  /projects
GET   /projects
GET   /projects/lookup
GET   /projects/{project_id}
PATCH /projects/{project_id}/security
GET   /projects/discover
GET   /projects/readiness
GET   /projects/security
```

#### Tasks

``` text
POST  /tasks
GET   /tasks
GET   /tasks/{task_id}
GET   /tasks/{task_id}/snapshot
POST  /tasks/{task_id}/advance
POST  /tasks/{task_id}/transition
```

#### Authorizations and Policies

``` text
GET   /authorizations                (?task_id&status&pending_only&limit)
GET   /authorizations/{authorization_id}
POST  /authorizations/request
POST  /authorizations/{authorization_id}/decision
POST  /policies/evaluate
```

#### Executions

``` text
POST  /executions/request
POST  /executions/{execution_id}/dispatch
POST  /executions/{execution_id}/run
GET   /executions
GET   /executions/{execution_id}
POST  /executions/{execution_id}/transition
POST  /executions/{execution_id}/complete
POST  /executions/{execution_id}/resolve-context
GET   /executions/{execution_id}/context
```

#### Observability

``` text
GET   /events
GET   /audit
GET   /audit/{audit_id}
GET   /metrics
GET   /suggestions
GET   /suggestions/{suggestion_id}
POST  /tasks/{task_id}/suggestions          (generate a suggestion for a task)
POST  /suggestions/{suggestion_id}/accept
POST  /suggestions/{suggestion_id}/reject
```

#### Legacy Flows

``` text
POST  /flows/local                  (retained for backward compatibility)
POST  /projects/operations
```

#### Admin

``` text
POST  /admin/db/sync
```

## Commands and Queries

``` text
COMMAND
    → requests a change

QUERY
    → reads information
```

Commands pass through application services.

Operational list queries support bounded filtering:

``` text
GET /tasks?project_id=<id>&state=PLANNING&limit=20
GET /executions?task_id=<id>&project_id=<id>&state=COMPLETED&limit=20
GET /tasks/{task_id}/snapshot
GET /requests/{request_id}/flow
```

## Authorization UI

Authorization requests should expose:

``` text
Task / Request
Role
Action
Model
Context
Project
Scope
Reason
Execution Mode
Expiration
```

## Execution Visibility

Users should be able to inspect:

``` text
Current State
Available Transitions
Current Execution
Execution History
Authorization History
Model
Provider
Context Scope
Resolved Context Metadata
Outcome
Errors
Resource Usage
```

Through the chat-first surface this is surfaced by
`GET /requests/{request_id}/flow` as a unified response.

## Invariants

1.  UI state is not authoritative task state.
2.  UI actions do not bypass authorization.
3.  Suggestions remain suggestions until accepted.
4.  API and CLI share application behavior.
5.  `/requests` is a projection over Task — it introduces no independent
    lifecycle rules.
6.  `POST /requests/{id}/approve` records an explicit authorization
    decision; it does not bypass the authorization boundary.
7.  "Pending" is derived from the absence of a decision
    (`Authorization.status is None`) or from `SuggestionStatus.PRESENTED`,
    never from a literal `"PENDING"` string — neither
    `AuthorizationDecisionStatus` nor `SuggestionStatus` has such a member.
8.  Code that needs "the most recent" record from a repository `list()`
    result must select explicitly by timestamp
    (e.g. `max(records, key=lambda r: r.created_at)`), never by list
    position (`[-1]`, `reversed()[0]`). Repository implementations do not
    share an ordering guarantee: in-memory repositories preserve
    insertion order, while SQLAlchemy repositories order `list()` results
    newest-first.
