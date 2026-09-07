# ADR-011 --- Chat-First Request Interface

## Status

Accepted

## Context

The initial API and CLI surfaces were designed as operational and
administrative interfaces — each step in the orchestration flow was
exposed as an explicit, fine-grained endpoint. Users had to compose
`POST /tasks`, `POST /authorizations/request`, `POST /executions/request`,
and related calls in sequence to produce one meaningful AI-assisted
operation.

This model works well for infrastructure operators and for automated
pipelines, but it assumes knowledge of OrchAI internals. It is not
suitable as a direct integration target for a conversational external
interface — a chat-like AI application where the user simply describes
what they want.

The product direction requires OrchAI to serve as the orchestration
back-end for external clients modeled after a standard AI chat interface,
where:

- the user connects a project folder;
- the user selects an AI agent (local via Ollama or cloud via an adapter);
- the user selects a ROLE and an ACTION;
- the user types a request in natural language (a prompt);
- OrchAI creates and manages the full orchestration flow transparently;
- the user observes the complete Orchestrator, Execution Engine, audit,
  and metrics flow from a single view.

This is called the **Chat-First Request Interface**.

## Decision

Introduce a `/requests` resource as the primary entry point for
external clients.

A Request maps one-to-one to a Task in the OrchAI domain model. It is
not a new domain concept — it is a user-facing projection of the
existing Task lifecycle, designed to be consumed without knowledge of
internal orchestration steps.

The new endpoints are:

```text
POST  /requests                          Create a new request (chat-like entry point)
GET   /requests/{request_id}/flow        Observe the full orchestration flow
POST  /requests/{request_id}/approve     Approve a pending suggestion and continue
POST  /requests/{request_id}/advance     Advance to the next workflow stage
```

`POST /requests` accepts:

```text
project_root      Path to the connected project
prompt            The user's request in natural language
role              ROLE to be applied (DEVELOPER, QUALITY_AGENT, …)
action            ACTION to be applied (IMPLEMENT, REVIEW, PLAN, …)
model             AI model identifier (optional; uses configured default)
execution_mode    MANUAL | SUGGESTED | AUTOMATIC (default: SUGGESTED)
provider_target   LOCAL | CLOUD (default: LOCAL)
context_paths     Optional list of additional context file paths
title             Optional task title (defaults to first line of prompt)
approve_suggestion  Shortcut to auto-approve the initial suggestion (default: false)
```

`POST /requests` returns:

```text
request_id        Stable identifier (same as task_id internally)
status            PENDING_SUGGESTION | PENDING_AUTHORIZATION | IN_PROGRESS |
                  RUNNING | COMPLETED | FAILED | CANCELLED
task              Task summary
suggestion        Present when mode=SUGGESTED and suggestion was not auto-approved
execution         Present when execution was started
flow_url          Link to GET /requests/{request_id}/flow
snapshot_url      Link to GET /tasks/{request_id}/snapshot
```

`GET /requests/{request_id}/flow` returns a fully observable view of the
orchestration flow: current task state, orchestration steps taken,
authorization records, execution records, resolved context metadata,
events, audit entries, and aggregated metrics — structured for a
conversational UI to render as a live progress view.

`POST /requests/{request_id}/approve` allows the user to approve a
pending suggestion and continue the flow — the primary interaction in
`SUGGESTED` mode.

`POST /requests/{request_id}/advance` drives the task through subsequent
workflow stages (PLAN → IMPLEMENT → REVIEW → VALIDATE → TEST →
DOCUMENT) using the same orchestration logic as the existing
`POST /tasks/{task_id}/advance`.

## Rationale

Introducing `/requests` as a separate resource layer achieves three
goals without disrupting the existing API surface:

1. **Simplicity for external clients.** A chat application can interact
   with OrchAI using a single `POST /requests` call and a polling loop
   on `GET /requests/{id}/flow`, without knowing about tasks,
   authorizations, or executions as separate resources.

2. **Architectural continuity.** The new endpoints are thin projections
   over the existing application services and domain model. No new
   domain concepts are introduced; no invariants are relaxed. The
   existing fine-grained endpoints remain fully operational for
   operators and automated pipelines.

3. **Future interface compatibility.** The `/requests` contract becomes
   the stable surface for future web, mobile, and desktop clients. The
   internal endpoint structure can evolve without changing the external
   contract.

## Consequences

Positive:

- external clients no longer need to know OrchAI's internal step
  structure to create and observe an orchestration flow;
- the observable flow response makes audit, metrics, and Orchestrator
  state visible from a single endpoint;
- the existing fine-grained endpoints remain unchanged and operational;
- the authorization, policy, execution mode, and suggestion invariants
  are preserved — the `/requests` layer adds a projection, not a bypass.

Trade-offs:

- two entry points now exist for the same underlying flow (`/flows/local`
  and `/requests`); `POST /requests` supersedes `POST /flows/local` as
  the recommended external entry point, but `/flows/local` is retained
  for backward compatibility;
- the `flow` response shape must be maintained as a stable contract once
  external clients consume it.

## Invariants

1. `/requests` is a projection of the Task domain; it does not introduce
   independent lifecycle rules.
2. Authorization, policy evaluation, execution mode enforcement, and
   suggestion boundaries apply identically through `/requests` as
   through any other interface path — including the very first stage,
   PLAN. `POST /requests` creates the project and the task and then
   advances through exactly one gated stage; it never silently completes a
   stage on the caller's behalf. The only exception is `AUTOMATIC`
   execution mode with the corresponding `(role, action)` explicitly
   present in `AutomaticExecutionPolicy.allowed_operations` — configured
   in advance, never as a side effect of calling `/requests`.
3. `approve` does not bypass authorization — it records an explicit user
   decision.
4. `/requests/{id}/flow` is read-only; it never mutates state.

## Amendment (2026-08-23)

An earlier implementation of `POST /requests` (via `run_local_flow`)
violated invariant #2: it transitioned the task `CREATED → PLANNING →
PLANNED` unconditionally, before any suggestion or policy evaluation ran,
regardless of execution mode. The first suggestion a caller ever saw was
therefore `IMPLEMENT` (the task was already `PLANNED`), never `PLAN` — a
real deviation from this document and from
`docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` section 3, not merely an
underspecified detail. `POST /projects/operations` (`run_project_operation`)
had the identical shape for its own internal `PLANNED` bootstrap hop.

Both were fixed to route through the same gated, single-stage-advance
mechanism used by `POST /tasks/{id}/advance` and `POST
/requests/{id}/advance` (`run_task_workflow_stage`), so a single code path
enforces the gate for every entry point and storage backend. See the
amendment note in `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` sections
3 and 8 for the corrected behavior.

## Amendment (v0.1.6)

A direct consequence of the amendment above surfaced immediately: after
the PLAN-stage gate fix, the common `SUGGESTED`-mode outcome for a
blocked stage leaves only a suggestion in `PRESENTED` status, with no
Authorization ever created (`run_task_workflow_stage` returns before
calling `request_authorization` whenever policy denies). `POST
/requests/{id}/approve`, which only ever looked for a pending
Authorization, could not resolve this case and always reported
`no_pending_authorization` — a violation of invariant #3 in practice,
since the primary `SUGGESTED`-mode interaction path was unusable. It now
covers both cases: a standalone pending Authorization is still granted
directly; otherwise, if a `PRESENTED` suggestion exists, `/approve`
delegates internally to the same gated single-stage-advance mechanism
used by `/advance` (`approve_stage=true`), still evaluated by policy,
not a bypass. Because of this, `/approve` also accepts the same
passthrough fields as `/advance` (`context_paths`, `documentation_path`,
`test_args`, `model`, `provider_target`), needed only when the currently
blocked stage itself requires them (e.g. PLAN requires `context_paths`).

## Amendment (OrchAI Desktop Phase 5)

Verifying Forge's Approval Card (`docs/decisions/ADR-014-CONVERSATION-DOMAIN-MODEL.md`,
`docs/architecture/DESKTOP-APPLICATION.md` Phase 5) end-to-end surfaced a
bug in the mechanism the previous amendment (v0.1.6) relies on:
`Orchestrator._resolve_task_stage()` (`application/orchestration/orchestrator.py`)
called `SuggestionEngine.suggest_next()` unconditionally on every
`/advance`/`/approve` call that did not pass an explicit `stage` --
exactly what `/approve`'s internal delegation to `run_task_workflow_stage`
does. Each call generated a brand-new `Suggestion` record for the task's
current state without marking the *previous* `PRESENTED` one as
resolved, so multiple suggestion records could exist for the same
task/stage: one left permanently `PRESENTED` (the original), and a
newer one actually carried through to `ACCEPTED`. Since
`_serialize_request_flow`'s `pending_suggestion` selection
(`max(... key=generated_at)`) only filters by `status is PRESENTED`, the
stale original could still win that selection after the newer one was
already accepted and the stage completed -- so `GET /requests/{id}/flow`
could keep reporting `suggestion.status: "PRESENTED"` and
`status: "PENDING_SUGGESTION"` indefinitely after a stage the user had
already approved and that had already executed.

This was invisible before Phase 5 because no prior caller kept
persistently re-rendering "is this still awaiting approval?" from
these fields across multiple fetches -- CLI/API consumers read a single
response and moved on. Fixed in `SuggestionEngine.suggest_next()`
(`application/suggestions/engine.py`): it now checks for an existing
`PRESENTED` suggestion matching the *same* `(suggested_role,
suggested_action)` the current task state would produce, and reuses it
instead of creating a duplicate; a stale `PRESENTED` suggestion left
over for a *different* stage (e.g. one bypassed via a direct
`POST /tasks/{id}/transition`) is correctly ignored and a fresh one is
generated instead. This keeps invariant #3 (`approve` records an
explicit decision, never bypasses authorization) intact and requires no
change to `SuggestionStatus`, `_serialize_request_flow`, or any call
site -- the fix is confined to `SuggestionEngine`, which every caller
already routes through. See `tests/unit/application/test_suggestion_engine.py`
for the regression coverage.

## Supersedes

None. Extends ADR-004 (API-First Interface Boundary) without superseding
it.
