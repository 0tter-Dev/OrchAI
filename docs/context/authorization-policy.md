# Authorization Policy

## Purpose

Defines Authorization — whether a requested operation may proceed —
and the three execution modes (`MANUAL`/`SUGGESTED`/`AUTOMATIC`) that
govern how that decision gets made.

## Objective

Keep policy, configuration, suggestion, authorization, and execution
as five distinct, non-interchangeable concepts, so that nothing short
of an explicit, traceable authorization decision ever permits a
protected operation.

## Current Status

`implemented`

## Fundamental Distinction

A policy may permit an operation. A configuration may define an
operation. A suggestion may recommend an operation. Only authorization
permits an operation when explicit authorization is required.
Execution means the operation actually occurred. These are never
interchangeable.

## Authorization Request And Decision

An authorization request identifies task, requested operation, role,
action, model (when relevant), context scope (when relevant), proposed
state transition, reason, execution mode, requester, and expiration
(when configured) — the user must be able to understand what they are
authorizing. A decision is `GRANTED`, `REJECTED`, `EXPIRED`, or
`REVOKED`, recorded and associated with the request.

## MANUAL Mode

The system follows explicit user instructions only: no unsolicited
workflow progression, suggestions may be disabled or limited, and
every action requiring authorization needs explicit approval. A prior
unrelated approval is never interpreted as authorization for a new
operation.

## SUGGESTED Mode (Default)

The system evaluates user configuration, current task state, relevant
project information, and (optionally) audit/metrics; identifies
possible improvements; presents the recommendation and rationale; and
waits for explicit user confirmation before doing anything. Examples:
using another model, requesting additional context, running
REVIEW/VALIDATION/TEST, continuing to the next action. A suggestion
never becomes authorization automatically.

## AUTOMATIC Mode

The system may execute configured operations without confirmation at
every step, but automatic execution stays bounded by task scope,
configured policies, authorized capabilities, execution mode, role
boundaries, and project restrictions. By default it may continue
between actions within the same role (e.g. `DEVELOPER →
IMPLEMENT/FIX/REFACTOR`) but must not silently cross role boundaries
(e.g. `DEVELOPER → QUALITY AGENT` still needs explicit authorization
unless cross-role automation was explicitly configured beforehand).

## Context Authorization

The system distinguishes Context Requested / Available / Authorized /
Resolved / Provided. An agent identifying additional potentially
useful context does not automatically gain access to it — the system
creates a new authorization request instead.

## Model Suggestions

The system may suggest an alternative model based on capabilities,
historical performance, availability, token limits, cost, local/cloud
usage, project configuration, and task requirements. In `SUGGESTED`
mode the user decides; in `MANUAL` mode the explicit selection remains
authoritative; in `AUTOMATIC` mode substitution may occur only within
the configured model-selection policy.

## Authorization Scope And Operational Gates

Authorization should be as specific as practical (one action, one
execution, one task phase, a predefined sequence, a role's configured
action set, or a specific context scope) — broad authorization only
when explicitly intended. Authorization alone may not be sufficient
for a protected project operation, which may also require sufficient
project readiness (see `Project Adapter And Security`), applicable
policy approval, and allowed persistence/provider-sharing behavior. If
the minimum readiness level is not satisfied, OrchAI blocks the
operation even when the user would otherwise authorize it — "user
authorizes code change" is not the same as "project is ready for code
change."

## Expiration, Revocation, And Audit

Authorization may expire when its lifetime ends, task scope changes,
relevant configuration changes, the authorized operation is no longer
valid, or the user revokes it — expired authorization is never reused.
Revocation (where technically applicable) must be auditable; an
already-completed execution cannot be undone merely by revoking its
authorization, though compensating actions may be initiated
separately. Authorization and state are related but independent (a
`GRANTED` authorization does not mean execution occurred). Every
authorization request and decision is traceable: who/what requested
it, what was requested, why, what configuration was active, what
decision was made, when, and what it enabled — and decisions generate
events (`AUTHORIZATION_REQUESTED`/`GRANTED`/`REJECTED`/`EXPIRED`/
`REVOKED`).

## Safety Boundary

The Orchestrator never treats the following as implicit authorization:
an agent recommendation, a previous task's authorization, a successful
previous execution, a model's own request, an available capability, a
configured default, or a metric-based recommendation. Authorization
must originate from an explicitly permitted authorization mechanism.

## Component Ownership

- **Authorization Manager** — creates authorization requests, records decisions, validates authorization, expires/invalidates where configured, associates authorization with a task and execution. Must distinguish Allowed-by-policy / Configured / Suggested / Authorized / Executed as separate concepts. Maps to `domain/authorization/` (application coordination in `application/`).
- **Policy Engine** — determines what operations are permitted per configured policy, evaluating execution mode, role/action permissions, project/context restrictions, cross-role automation rules, model restrictions, and user configuration. Must not convert a suggestion into authorization, override explicit user restrictions in `MANUAL` mode, or independently redefine project requirements. Maps to `domain/policies/` (application coordination in `application/policies/`).

## Key Rules

- authorization is distinct from policy, configuration, suggestion, and execution
- explicit user decisions remain authoritative where required
- `SUGGESTED` mode never silently executes suggestions; `MANUAL` mode never silently changes explicit execution parameters
- `AUTOMATIC` mode remains bounded by configured policies; cross-role automation requires explicit configuration or authorization
- context authorization must be independently traceable, and authorization decisions must be auditable
- expired or revoked authorization must not be reused
- authorization does not bypass minimum project readiness rules

## Main Relationships

- gates every `Execution Engine` attempt and every `Tasks And Lifecycle` stage transition
- constrained by `Project Adapter And Security`'s readiness gates for protected project operations
- consulted by `Identity And Access Management` once a request-scoped current user exists (the technical prerequisite for a future per-user authorization revisit — not yet started, see `docs/TO-DO.md`)
- reported through `Observability` (audit, events)
