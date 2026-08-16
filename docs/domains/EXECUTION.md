# OrchAI --- Execution Domain

## 1. Purpose

An `EXECUTION` represents an actual attempt to perform an `ACTION` for a
`TASK` using a specific `ROLE` and `MODEL`.

Execution is the bridge between orchestration and an external AI agent
or model.

------------------------------------------------------------------------

## 2. Execution Identity

Each execution must have a unique identity.

An execution should preserve references to:

``` text
TASK
ROLE
ACTION
MODEL
PROJECT
CONTEXT
AUTHORIZATION
```

It should also contain execution timestamps and outcome information.

------------------------------------------------------------------------

## 3. Execution Lifecycle

A conceptual execution lifecycle is:

``` text
REQUESTED
    ↓
AUTHORIZED
    ↓
PREPARING
    ↓
STARTED
    ↓
RUNNING
    ↓
COMPLETED
```

Failure paths may include:

``` text
REJECTED
BLOCKED
FAILED
CANCELLED
TIMEOUT
```

The exact lifecycle is controlled by the execution and state domains.

------------------------------------------------------------------------

## 4. Execution Inputs

An execution may require:

-   task definition;
-   role definition;
-   action definition;
-   selected model;
-   authorized context;
-   project capabilities;
-   acceptance criteria;
-   execution mode;
-   applicable policies;
-   authorization.

The Execution Engine must construct a bounded execution request from
these inputs.

------------------------------------------------------------------------

## 5. Role

The role establishes the responsibility under which the execution
occurs.

Examples:

``` text
TASK PLANNER
DEVELOPER
QUALITY AGENT
```

The role does not identify the specific model.

------------------------------------------------------------------------

## 6. Action

The action establishes what the execution should perform.

Examples:

``` text
PLAN
IMPLEMENT
REVIEW
VALIDATE
TEST
DOCUMENT
```

The action does not identify the model.

------------------------------------------------------------------------

## 7. Model

The model identifies the AI resource used by the execution.

A model may be:

-   local;
-   cloud-hosted;
-   accessed through an external development agent;
-   provided by a future AI provider.

The model is an execution resource and must remain replaceable.

------------------------------------------------------------------------

## 8. Context

Context defines the information made available to the model.

The execution must preserve the distinction between:

``` text
Requested Context
Authorized Context
Resolved Context
Provided Context
```

This distinction is important for auditability and security.

------------------------------------------------------------------------

## 9. Execution Preparation

Before invoking the model, the system may perform:

-   parameter validation;
-   policy validation;
-   authorization validation;
-   context resolution;
-   model availability checks;
-   project capability checks;
-   execution package preparation.

Preparation must not silently change user-authorized scope.

------------------------------------------------------------------------

## 10. Execution Result

An execution result should preserve:

-   success or failure;
-   model output;
-   execution metadata;
-   relevant generated artifacts;
-   errors;
-   warnings;
-   resource usage;
-   timing information.

The result may generate subsequent events.

------------------------------------------------------------------------

## 11. Resource Usage

Where available, the execution should record:

-   input tokens;
-   output tokens;
-   total tokens;
-   execution duration;
-   estimated cost;
-   provider usage;
-   local/cloud classification;
-   model-specific resource information.

This information feeds the Audit and Metrics domains.

------------------------------------------------------------------------

## 12. Execution Failure

Execution failure must not automatically imply task failure.

A failed execution may lead to:

``` text
RETRY
REPLAN
BLOCKED
USER REVIEW
TASK FAILED
```

depending on the configured workflow.

------------------------------------------------------------------------

## 13. Execution Retry

Retries must create traceable execution attempts.

The system should not overwrite the failed execution with the successful
retry.

Example:

``` text
TASK
 ├── EXECUTION #1 → FAILED
 └── EXECUTION #2 → COMPLETED
```

This preserves operational history and enables accurate metrics.

------------------------------------------------------------------------

## 14. Cross-Role Execution

A role transition is a significant workflow boundary.

For example:

``` text
DEVELOPER → QUALITY AGENT
```

must be distinguishable from:

``` text
DEVELOPER → another DEVELOPER action
```

Automatic execution may continue within a role according to policy, but
cross-role progression must follow the configured authorization
boundary.

------------------------------------------------------------------------

## 15. Execution and Project Changes

An execution may modify project resources when the selected action
permits it.

Examples include:

-   source code;
-   tests;
-   documentation;
-   configuration.

The Orchestrator must preserve enough information to identify which
execution caused the operation.

Project-specific persistence remains the responsibility of the Project
Adapter and the project itself.

------------------------------------------------------------------------

## 16. Execution Isolation

An execution must be associated with exactly one task.

It may reference shared resources, but its identity and result must
remain independently auditable.

------------------------------------------------------------------------

## 17. Execution Domain Invariants

1.  Every execution belongs to a task.
2.  Every execution has one role, one action, and one effective model.
3.  Authorization must be validated before execution where required.
4.  Execution results must be traceable.
5.  Failed executions must not be overwritten.
6.  Context supplied to execution must be auditable.
7.  Model/provider details must remain behind adapters.
8.  Execution must not silently expand task scope.
9.  Cross-role transitions must respect authorization policy.
10. Resource usage should be captured whenever technically available.
