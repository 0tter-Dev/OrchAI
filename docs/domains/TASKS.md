# OrchAI --- Tasks Domain

## 1. Purpose

A `TASK` represents a bounded unit of work requested by a user and
executed through the OrchAI.

Tasks are the primary domain entity around which planning, execution,
validation, authorization, state transitions, auditing, and
documentation are coordinated.

A task must remain explicit about its scope, intent, current state,
execution configuration, and authorization boundaries.

------------------------------------------------------------------------

## 2. Task Identity

Each task must have a stable unique identity.

A task should also expose human-readable metadata such as:

-   title;
-   description;
-   project;
-   creation information;
-   current state;
-   priority, when configured;
-   related tasks, when applicable.

Task identity must remain stable across its complete lifecycle.

------------------------------------------------------------------------

## 3. Task Scope

A task defines the intended scope of work.

The scope may include:

-   requested change;
-   affected functionality;
-   explicitly authorized contexts;
-   acceptance criteria;
-   constraints;
-   exclusions;
-   expected outputs.

The task scope must not be implicitly expanded by an agent.

Potentially necessary work outside the authorized scope must be surfaced
to the user according to the configured authorization policy.

------------------------------------------------------------------------

## 4. Task Configuration

A task may define or reference:

``` text
ROLE
ACTION
MODEL
CONTEXT
EXECUTION MODE
AUTHORIZATION POLICY
ACCEPTANCE CRITERIA
```

These values are independently represented.

The task may inherit defaults from project or global configuration, but
the effective configuration must remain observable.

------------------------------------------------------------------------

## 5. Task Lifecycle

A task progresses through explicit states.

The exact state set may evolve, but the lifecycle should support at
least the following conceptual phases:

``` text
CREATED
PLANNING
PLANNED
IMPLEMENTING
IMPLEMENTED
REVIEWING
VALIDATING
TESTING
VALIDATED
COMPLETED
BLOCKED
FAILED
CANCELLED
```

Not every task must pass through every state.

The State Machine determines which transitions are valid.

------------------------------------------------------------------------

## 6. Task State

Task state represents the current authoritative condition of the task.

State must not be inferred solely from:

-   agent output;
-   audit logs;
-   project documentation;
-   UI state.

The Orchestrator State Machine is the authoritative source for task
lifecycle state.

------------------------------------------------------------------------

## 7. Task Context

A task may reference project-specific context.

Context should normally be represented through references rather than
duplicating complete project documentation inside the task.

The task should preserve enough information to determine:

-   what context was requested;
-   what context was authorized;
-   what context was actually supplied to an execution.

------------------------------------------------------------------------

## 8. Acceptance Criteria

Acceptance criteria define what must be true for the requested work to
be considered successful.

They should be concise and testable where possible.

Acceptance criteria belong to the task rather than to a specific model
or role.

Different roles may use the same acceptance criteria for different
purposes.

------------------------------------------------------------------------

## 9. Related Executions

A task may have multiple executions.

For example:

``` text
TASK
 ├── PLAN
 ├── IMPLEMENT
 ├── REVIEW
 ├── VALIDATE
 └── TEST
```

Each execution represents an individual attempt to perform an action.

A task must therefore not assume that one execution equals task
completion.

------------------------------------------------------------------------

## 10. Rework and Iteration

A task may return to an earlier execution phase when an execution
identifies an issue.

For example:

``` text
IMPLEMENTED
    ↓
REVIEWING
    ↓
REVIEW_FAILED
    ↓
IMPLEMENTING
```

The workflow must preserve the history of previous executions rather
than overwriting them.

------------------------------------------------------------------------

## 11. Task Completion

A task should only enter a successful terminal state after the
configured completion conditions have been satisfied.

Depending on project configuration, completion may require:

-   successful implementation;
-   review;
-   validation;
-   tests;
-   documentation updates;
-   explicit user confirmation.

The exact completion policy is configurable.

------------------------------------------------------------------------

## 12. Task Cancellation

A task may be cancelled by an authorized user or policy.

Cancellation must preserve the task history and must not delete previous
executions or audit records.

------------------------------------------------------------------------

## 13. Task Immutability and History

Historical execution facts should be immutable.

Changes to task configuration, authorization, or state must be
represented as new events or records rather than silently rewriting
historical facts.

This is essential for auditability.

------------------------------------------------------------------------

## 14. Task Isolation

A task should be independently identifiable and auditable.

Future parallel execution must be able to distinguish:

``` text
TASK A
TASK B
TASK C
```

even when they belong to the same project.

Potential conflicts between tasks must be detectable before or during
execution according to future concurrency policies.

------------------------------------------------------------------------

## 15. Task Domain Invariants

The following rules are fundamental:

1.  A task has exactly one authoritative current state.
2.  State changes occur through valid State Machine transitions.
3.  An execution belongs to a task.
4.  An execution does not automatically imply task completion.
5.  Task scope must not be silently expanded.
6.  Historical execution information must remain traceable.
7.  Authorization must be distinguishable from configuration.
8.  Suggestions must not be treated as authorization.
9.  Project-specific information remains accessed through the project
    boundary.
10. Task lifecycle must remain independent from any specific AI
    provider.
