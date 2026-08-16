# OrchAI --- Context Domain

## Purpose

`CONTEXT` defines information made available to an execution.

Context is a controlled resource, not an unrestricted collection of
project data.

## Lifecycle

``` text
REQUESTED
    ↓
AVAILABLE
    ↓
AUTHORIZED
    ↓
RESOLVED
    ↓
PROVIDED
```

## Sources

``` text
Task Definition
Project Documentation
Source Files
Configuration
Git History
Previous Executions
Execution Results
External References
```

## Context References

Tasks should normally reference context rather than duplicate complete
project content.

A reference may identify source, path, resource, version, scope, and
authorization requirements.

## Authorization

Availability does not imply authorization.

``` text
AVAILABLE ≠ AUTHORIZED
```

An execution receives only context authorized for that operation.

## Resolution

The Context Manager converts authorized references into concrete
execution input, potentially locating files, selecting sections,
collecting history, filtering sensitive data, enforcing scope, and
producing a bounded context package.

## Provider Boundary

Context should be resolved before crossing the AI Provider Adapter
boundary.

## Invariants

1.  Context access is controlled.
2.  Availability does not imply authorization.
3.  Provided context is traceable.
4.  Context resolution respects task scope.
5.  Sensitive context cannot cross trust boundaries without
    authorization.
