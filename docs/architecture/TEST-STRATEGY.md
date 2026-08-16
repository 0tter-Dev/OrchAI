# OrchAI --- Test Strategy

## Purpose

Testing verifies domain rules and complete orchestration flows.

## Layers

``` text
UNIT
  ↓
CONTRACT
  ↓
INTEGRATION
  ↓
END-TO-END
```

## Unit Tests

Cover:

``` text
State Machine
Authorization Rules
Domain Invariants
Execution Construction
Context Resolution
Suggestion Rules
Configuration Validation
```

These should avoid infrastructure dependencies.

## Contract Tests

Test:

``` text
AI Provider Adapter Contract
Project Adapter Contract
Repository Contract
Event Consumer Contract
```

## Integration Tests

Verify persistence, event dispatch, application services, API, CLI, and
adapter integration.

## End-to-End

At least one complete workflow should cover:

``` text
TASK
 → PLAN
 → AUTHORIZATION
 → IMPLEMENT
 → REVIEW
 → VALIDATION
 → COMPLETION
```

Failure and rework paths should also be covered.

## Security Tests

Important cases include:

``` text
Unauthorized execution
Unauthorized context
Cross-role progression
Cloud context restriction
Capability mismatch
Expired authorization
Revoked authorization
```

## Regression

A bug involving a domain invariant should normally produce a regression
test alongside the fix.

## Invariants

1.  Domain rules are independently testable.
2.  Adapter contracts are independently testable.
3.  Critical authorization paths are tested.
4.  Failure and recovery behavior is tested.
5.  Provider behavior is isolated unless intentionally tested.
