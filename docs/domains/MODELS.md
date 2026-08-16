# OrchAI --- Models Domain

## Purpose

A `MODEL` identifies an AI execution resource.

Models are replaceable resources and must not become workflow logic.

## Model Identity

A model should expose:

-   stable identifier;
-   provider;
-   execution class;
-   local/cloud classification;
-   capabilities;
-   context limits, when known;
-   cost metadata, when available;
-   availability state.

## Model Classes

``` text
LOCAL
CLOUD
EXTERNAL AGENT
FUTURE PROVIDER
```

## Selection

Model selection may consider:

-   task requirements;
-   role;
-   action;
-   capabilities;
-   project policy;
-   local availability;
-   cloud availability;
-   context limits;
-   cost;
-   historical performance.

The effective model must remain observable in execution records.

## Replacement

Changing a model must not require changing:

``` text
TASK
ROLE
ACTION
PROJECT
AUTHORIZATION
```

Provider-specific behavior belongs behind adapters.

## Local and Cloud

The system must distinguish local and cloud execution because context
handling, cost, availability, and security policies may differ.

Sensitive project context must not be sent to cloud resources without
authorization.

## Failure

A model failure may result in:

``` text
RETRY
CHANGE MODEL
REPLAN
BLOCK
REQUEST USER DECISION
```

according to policy.

## Invariants

1.  A model is an execution resource.
2.  A model is not a role.
3.  A model is not an authorization authority.
4.  Provider details remain behind adapters.
5.  Effective model selection is auditable.
