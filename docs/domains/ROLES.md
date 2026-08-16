# OrchAI --- Roles Domain

## Purpose

A `ROLE` defines the responsibility under which an execution operates.

Roles provide workflow responsibility without identifying a specific
model or provider.

## Role Identity

A role may define:

-   name;
-   description;
-   responsibility;
-   allowed actions;
-   model policy;
-   capability requirements;
-   workflow relationships;
-   execution constraints.

## Initial Roles

``` text
TASK PLANNER
DEVELOPER
QUALITY AGENT
```

These are conceptual roles, not mandatory provider implementations.

## Responsibilities

### TASK PLANNER

Understands task scope, decomposes work, identifies required actions and
context, and proposes execution plans.

The planner does not silently authorize implementation.

### DEVELOPER

Implements authorized changes, fixes implementation issues, and performs
in-scope refactoring.

### QUALITY AGENT

Reviews, validates, tests, and reports deviations from acceptance
criteria.

## Role and Action

``` text
ROLE + ACTION = EXECUTION RESPONSIBILITY
```

A role defines responsibility; an action defines the operation.

## Role and Model

``` text
ROLE
  ↓
MODEL POLICY
  ↓
SELECTED MODEL
```

A role must not be permanently bound to one model.

## Invariants

1.  A role represents responsibility, not a provider.
2.  A role does not identify a model.
3.  Role boundaries remain auditable.
4.  Cross-role progression respects authorization policy.
5.  Role definitions contain no project-specific business logic.
