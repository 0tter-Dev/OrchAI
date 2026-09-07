# Tasks And Lifecycle

## Purpose

Defines the Task entity — the bounded unit of work requested by a user
and executed through OrchAI — and the state machine that governs its
lifecycle.

## Objective

Provide a single authoritative representation of task identity, scope,
configuration, and state so that planning, execution, authorization,
and auditing all coordinate around the same task record.

## Current Status

`implemented`

## Task Identity And Scope

- a task has a stable, unique identity that does not change across its lifecycle
- a task carries human-readable metadata (title, description, project, creation info, current state, priority when configured)
- a task defines its intended scope (requested change, authorized contexts, acceptance criteria, constraints, exclusions, expected outputs)
- scope must not be implicitly expanded by an agent; potentially necessary out-of-scope work must be surfaced through the configured authorization policy

## Task Configuration

A task defines or references `ROLE`, `ACTION`, `MODEL`, `CONTEXT`,
`EXECUTION MODE`, `AUTHORIZATION POLICY`, and `ACCEPTANCE CRITERIA` as
independently represented values. A task may inherit defaults from
project or global configuration, but its effective configuration must
remain observable.

## Lifecycle States

Conceptual states: `CREATED`, `PLANNING`, `PLANNED`, `IMPLEMENTING`,
`IMPLEMENTED`, `REVIEWING`, `VALIDATING`, `TESTING`, `VALIDATED`,
`COMPLETED`, `BLOCKED`, `FAILED`, `CANCELLED`. Not every task passes
through every state; the Task Engine and State Machine (below) jointly
determine which transitions are valid and applied.

A task may have multiple executions (one per stage: PLAN, IMPLEMENT,
REVIEW, VALIDATE, TEST) and may return to an earlier phase when an
execution identifies an issue (e.g. `IMPLEMENTED → REVIEWING →
REVIEW_FAILED → IMPLEMENTING`) without overwriting the history of
prior executions.

## Task Engine

Owns the administrative lifecycle of tasks: create, load, update
metadata, associate with a project, retrieve, archive. Consumes
project information, task configuration, and user commands; produces
task lifecycle events. Must not execute AI models, directly modify
project code, independently authorize execution, or determine the
next role autonomously. Maps to `application/tasks/`.

## State Machine

Controls valid task state transitions: evaluates whether a transition
is valid, applies valid transitions, rejects invalid ones, exposes
current state, emits state-transition events. Consumes task events,
task state, workflow rules, and execution results. Must not
independently choose AI models, independently authorize
user-controlled transitions, execute AI agents, or bypass defined
transition rules. State is authoritative here — never inferred from
agent output, audit logs, project documentation, or UI state. Maps to
`domain/tasks/`.

## Completion And Cancellation

A task enters a successful terminal state only after configured
completion conditions are satisfied (which may require implementation,
review, validation, tests, documentation updates, or explicit user
confirmation, depending on project configuration). A task may be
cancelled by an authorized user or policy; cancellation preserves task
history and never deletes prior executions or audit records.
Historical execution facts are immutable — changes to configuration,
authorization, or state are new events or records, never silent
rewrites.

## Key Rules

- a task has exactly one authoritative current state, held by the State Machine
- an execution belongs to a task and does not by itself imply task completion
- task scope must not be silently expanded
- historical execution information must remain traceable
- authorization must be distinguishable from configuration, and suggestions must never be treated as authorization
- project-specific information stays behind the project boundary
- task lifecycle must remain independent from any specific AI provider
- a task must be independently identifiable and auditable, distinguishable from other tasks in the same project (a prerequisite for future concurrent execution)

## Main Relationships

- depends on `Execution Engine` for running each stage
- depends on `Authorization Policy` for gating stage transitions
- depends on `Roles, Actions, And Models` for stage configuration
- depends on `Context Management` for what an execution may see
- emits records to `Observability` (audit and metrics)
- is exposed through `Chat-First And Interfaces` (`/requests`, `/tasks`)
