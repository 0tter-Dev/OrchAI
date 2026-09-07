# Roles, Actions, And Models

## Purpose

Defines three independently recombinable dimensions of an execution —
the Role (responsibility), the Action (operation), and the Model (AI
resource) — plus the Capability concept that gates what each can
technically do.

## Objective

Keep "who is responsible," "what is being done," and "which AI
resource performs it" as three separate, freely recombinable concepts,
so that changing one never requires changing the others.

## Current Status

`implemented`

## Roles

A Role defines the responsibility under which an execution operates,
without identifying a specific model or provider. Initial roles: `TASK
PLANNER` (understands scope, decomposes work, proposes plans — never
silently authorizes implementation), `DEVELOPER` (implements authorized
changes), `QUALITY AGENT` (reviews, validates, tests). `ROLE + ACTION =
EXECUTION RESPONSIBILITY`; a role is never permanently bound to one
model (`ROLE → MODEL POLICY → SELECTED MODEL`).

## Actions

An Action defines what an execution is intended to perform, independent
of role and model. Initial vocabulary: `PLAN`, `IMPLEMENT`, `FIX`,
`REFACTOR`, `REVIEW`, `VALIDATE`, `TEST`, `DOCUMENT`. An action must
remain inside task scope; out-of-scope work follows `REPORT → SUGGEST →
REQUEST AUTHORIZATION`. Action completion does not imply task
completion.

## Models

A Model identifies an AI execution resource — local, cloud-hosted, an
external development agent, or a future provider — and must never
become workflow logic. Selection may consider task requirements, role,
action, capabilities, project policy, availability, context limits,
cost, and historical performance, but the effective model must remain
observable in execution records. Changing a model must never require
changing the task, role, action, project, or authorization. The system
must distinguish local and cloud execution, since context handling,
cost, availability, and security policy differ, and sensitive project
context must never reach a cloud resource without authorization.

## Capabilities

A Capability represents an operation a component, role, model, or
adapter can technically perform — possibility, not permission
(`CAPABILITY = CAN PERFORM`, `AUTHORIZATION = MAY PERFORM`). Initial
set: `READ_PROJECT`, `READ_DOCUMENTATION`, `WRITE_SOURCE`,
`WRITE_DOCUMENTATION`, `RUN_TESTS`, `RUN_COMMANDS`, `USE_LOCAL_MODEL`,
`USE_CLOUD_MODEL`, `ACCESS_GIT`. Capabilities may be provided by the
Project Adapter, AI Provider Adapter, execution environment, role
configuration, or infrastructure, and are evaluated as `Required
Capability → Available Capability → Authorization Policy → Allowed
Operation`.

## Component Ownership

- **Role Manager** — registers roles, retrieves definitions, validates capabilities, resolves allowed actions. Must not identify the AI model itself, replace action definitions, or execute models. Maps to `domain/roles/`.
- **Action Manager** — registers actions, retrieves definitions, validates whether a role may execute an action, resolves requirements. Must not select models, authorize execution, or directly execute a model. Maps to `domain/actions/`.
- **Model Manager** — tracks provider, model, execution environment, capabilities, availability, limits, usage, cost, and performance. Must not silently replace user configuration in `MANUAL` mode, treat metrics as authorization, or directly implement provider-specific communication. Maps to `domain/models/` (application coordination in `application/models/`).

## Key Rules

- a role represents responsibility, never a provider or a model
- an action represents an operation and never identifies a model or bypasses authorization
- a model is an execution resource, never a role or an authorization authority
- capability availability never grants authorization by itself
- provider-specific behavior stays behind adapters
- role, action, and model boundaries remain independently auditable
- cross-role progression respects the authorization policy
- missing capabilities produce a distinct, explicit failure condition

## Main Relationships

- configures every `Execution Engine` attempt
- constrained by `Authorization Policy`
- resolved through `AI Provider Adapter` for models, `Project Adapter And Security` for project-provided capabilities
- surfaced by `Tasks And Lifecycle` as part of task configuration
