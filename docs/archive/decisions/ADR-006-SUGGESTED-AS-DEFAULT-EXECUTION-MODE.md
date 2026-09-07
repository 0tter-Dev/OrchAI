# ADR-006 --- Suggested as Default Execution Mode

## Status

Accepted

## Context

OrchAI is intended to provide autonomous assistance while preserving
user control over workflow progression and authorization.

## Decision

`SUGGESTED` is the default execution mode.

The system may recommend:

``` text
Next Action
Alternative Model
Additional Context
Review
Validation
Testing
```

but recommendations do not authorize execution.

`MANUAL` and `AUTOMATIC` remain explicit alternatives.

## Rationale

This balances automation with user control and provides a safe default
while orchestration behavior matures.

## Consequences

Positive:

-   explicit user control;
-   reduced accidental progression;
-   useful autonomous assistance.

Trade-offs:

-   more user interaction than fully automatic execution;
-   automatic workflows require explicit configuration.

## Invariant

A suggestion can never silently become authorization.
