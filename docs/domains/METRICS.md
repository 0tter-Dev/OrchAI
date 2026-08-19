# OrchAI --- Metrics Domain

## Purpose

`METRICS` provides measurable operational information about
orchestration, execution, models, projects, and workflow behavior.

## Core Metrics

``` text
Token Usage
Execution Duration
Model Usage
Local vs Cloud Usage
Estimated Cost
Success Rate
Failure Rate
Retry Rate
Task Completion Time
Suggestion Acceptance Rate
```

## Sources

Metrics derive from authoritative records:

``` text
Execution
Audit
Events
Task Lifecycle
Authorization
```

The UI is never the source of truth.

## Current Implementation

The initial implementation includes an event subscriber that derives
execution metrics from persisted execution records after
`EXECUTION_COMPLETED` and `EXECUTION_FAILED` events. It currently records
duration, success/failure counters, token usage, and estimated cost when
the provider result includes those values.

## Dimensions

Metrics may be grouped by:

``` text
Task
Project
Role
Action
Model
Provider
Execution Mode
Time Period
Outcome
```

## Cost

``` text
ESTIMATED COST ≠ INVOICED COST
```

Estimated values must remain identifiable as estimates.

## Local vs Cloud

Track whether execution occurred through local or cloud resources.

## Accuracy

Do not silently count suggestions as executions, rejected authorizations
as executions, failed event deliveries as completed operations, or
retries as replacements for previous attempts.

## Invariants

1.  Metrics derive from authoritative information.
2.  Retries remain individually measurable.
3.  Estimated values are identified as estimates.
4.  Metrics do not change task state.
