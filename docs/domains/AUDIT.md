# OrchAI --- Audit Domain

## Purpose

`AUDIT` preserves the operational history required to understand what
OrchAI did, why it did it, and under which authorization and execution
conditions.

## Scope

Audit should cover:

``` text
TASK
STATE TRANSITION
AUTHORIZATION
CONTEXT
EXECUTION
MODEL
EVENT
USER DECISION
SUGGESTION
ERROR
RETRY
RESOURCE USAGE
PROJECT CHANGE
```

It should also cover, where applicable:

``` text
PROJECT READINESS
PROJECT SECURITY PROFILE
PERSISTENCE SCOPE CHANGE
PROVIDER-SHARING DECISION
GIT INITIALIZATION
CI/CD ENABLEMENT
```

## Record

An audit record should contain, where applicable:

-   unique identity;
-   timestamp;
-   actor;
-   operation;
-   task;
-   project;
-   execution;
-   authorization;
-   correlation information;
-   outcome;
-   relevant metadata.

## Historical Integrity

Audit records are append-oriented.

Corrections should be represented by additional records or events rather
than silently rewriting history.

## Events and Metrics

Events describe occurrences.

Audit provides operational history.

Metrics derive from authoritative execution and audit information.

## Invariants

1.  Significant protected operations are auditable.
2.  Authorization decisions are auditable.
3.  Execution attempts remain traceable.
4.  Historical records preserve their meaning.
5.  Audit failures must not silently erase the operation that should
    have been recorded.
6.  Readiness-gated and security-sensitive project operations are
    auditable.
