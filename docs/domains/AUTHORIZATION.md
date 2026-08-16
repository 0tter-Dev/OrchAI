# OrchAI --- Authorization Domain

## 1. Purpose

Authorization defines whether a requested operation may proceed.

It is one of the primary control mechanisms of the OrchAI and
establishes the boundary between system capability and user-approved
execution.

------------------------------------------------------------------------

## 2. Fundamental Distinction

The system must distinguish:

``` text
POLICY
CONFIGURATION
SUGGESTION
AUTHORIZATION
EXECUTION
```

These concepts are not interchangeable.

A policy may permit an operation.

A configuration may define an operation.

A suggestion may recommend an operation.

Only authorization permits an operation when explicit authorization is
required.

Execution means the operation actually occurred.

------------------------------------------------------------------------

## 3. Authorization Request

An authorization request should identify:

-   task;
-   requested operation;
-   role;
-   action;
-   model, when relevant;
-   context scope, when relevant;
-   proposed state transition;
-   reason for authorization;
-   execution mode;
-   requester;
-   expiration, when configured.

The user must be able to understand what they are authorizing.

------------------------------------------------------------------------

## 4. Authorization Decision

A decision may be:

``` text
GRANTED
REJECTED
EXPIRED
REVOKED
```

The decision must be recorded and associated with the request.

------------------------------------------------------------------------

## 5. MANUAL Mode

In `MANUAL` mode:

-   the system follows explicit user instructions;
-   no unsolicited workflow progression is performed;
-   suggestions may be disabled or limited;
-   actions requiring authorization must receive explicit approval.

The system must not interpret a prior unrelated approval as
authorization for a new operation.

------------------------------------------------------------------------

## 6. SUGGESTED Mode

`SUGGESTED` is the default execution mode.

The system:

1.  evaluates the user-defined configuration;
2.  evaluates the current task state;
3.  evaluates relevant project information;
4.  may evaluate audit and metrics;
5.  identifies possible improvements;
6.  presents the recommendation and rationale;
7.  waits for explicit user confirmation.

Examples of suggestions include:

``` text
Use another model
Request additional context
Run REVIEW
Run VALIDATION
Run TEST
Continue to the next action
```

A suggestion never becomes authorization automatically.

------------------------------------------------------------------------

## 7. AUTOMATIC Mode

In `AUTOMATIC` mode, the system may execute configured operations
without asking for confirmation at every step.

However, automatic execution remains bounded by:

-   task scope;
-   configured policies;
-   authorized capabilities;
-   execution mode;
-   role boundaries;
-   project restrictions.

By default, automatic execution may continue between actions within the
same role but must not silently cross role boundaries.

Example:

``` text
DEVELOPER
  ├── IMPLEMENT
  ├── FIX
  └── REFACTOR
```

may be automatically continued when configured.

But:

``` text
DEVELOPER
      ↓
QUALITY AGENT
```

requires explicit authorization unless cross-role automation has been
explicitly configured beforehand.

------------------------------------------------------------------------

## 8. Context Authorization

Context access may require explicit authorization.

The system must distinguish:

``` text
Context Requested
Context Available
Context Authorized
Context Resolved
Context Provided
```

An agent identifying additional potentially useful context does not
automatically gain access to it.

The system may create a new authorization request.

------------------------------------------------------------------------

## 9. Model Suggestions

The system may suggest an alternative model based on:

-   model capabilities;
-   historical performance;
-   current availability;
-   token limits;
-   cost;
-   local/cloud resource usage;
-   project configuration;
-   task requirements.

In `SUGGESTED` mode, the user decides whether to accept the suggestion.

In `MANUAL` mode, the explicit model selection remains authoritative.

In `AUTOMATIC` mode, model substitution may occur only within the
configured model-selection policy.

------------------------------------------------------------------------

## 10. Workflow Progression Authorization

After an execution completes, the system may identify a possible next
action.

Example:

``` text
IMPLEMENTED
    ↓
Suggestion: REVIEW
```

In `SUGGESTED` mode:

``` text
Suggestion
    ↓
User Confirmation
    ↓
REVIEW
```

In `AUTOMATIC` mode, the system may continue if the transition is
already authorized by policy.

------------------------------------------------------------------------

## 11. Authorization Scope

Authorization should be as specific as practical.

An authorization may apply to:

-   one action;
-   one execution;
-   one task phase;
-   a predefined sequence;
-   a role's configured action set;
-   a specific context scope.

Broad authorization should only be used when explicitly intended.

------------------------------------------------------------------------

## 12. Authorization Expiration

Authorization may expire when:

-   its configured lifetime ends;
-   task scope changes;
-   relevant configuration changes;
-   the authorized operation is no longer valid;
-   the user revokes it.

Expired authorization must not be reused.

------------------------------------------------------------------------

## 13. Authorization Revocation

Where technically applicable, authorization may be revoked before
execution.

Revocation must be auditable.

An already completed execution cannot be undone merely by revoking its
authorization, although compensating actions may be initiated
separately.

------------------------------------------------------------------------

## 14. Authorization and State

Authorization and state are related but independent.

For example:

``` text
TASK STATE:
PLANNED

AUTHORIZATION:
GRANTED

EXECUTION:
NOT STARTED
```

Authorization does not mean that execution occurred.

Similarly:

``` text
TASK STATE:
IMPLEMENTED

AUTHORIZATION:
GRANTED FOR REVIEW

REVIEW:
NOT STARTED
```

------------------------------------------------------------------------

## 15. Authorization and Events

Authorization decisions should generate events such as:

``` text
AUTHORIZATION_REQUESTED
AUTHORIZATION_GRANTED
AUTHORIZATION_REJECTED
AUTHORIZATION_EXPIRED
AUTHORIZATION_REVOKED
```

These events provide auditability and may participate in state
transitions.

------------------------------------------------------------------------

## 16. Authorization and Audit

Every authorization request and decision must be traceable.

The audit record should preserve:

-   who or what requested authorization;
-   what was requested;
-   why it was requested;
-   what configuration was active;
-   what decision was made;
-   when it was made;
-   what execution or transition it enabled.

------------------------------------------------------------------------

## 17. Safety Boundary

The Orchestrator must never treat the following as implicit
authorization:

-   an agent recommendation;
-   a previous task's authorization;
-   a successful previous execution;
-   a model's own request;
-   an available capability;
-   a configured default;
-   a metric-based recommendation.

Authorization must originate from an explicitly permitted authorization
mechanism.

------------------------------------------------------------------------

## 18. Authorization Domain Invariants

1.  Authorization is distinct from policy.
2.  Authorization is distinct from configuration.
3.  Authorization is distinct from suggestion.
4.  Authorization is distinct from execution.
5.  Explicit user decisions remain authoritative where required.
6.  `SUGGESTED` mode never silently executes suggestions.
7.  `MANUAL` mode never silently changes explicit execution parameters.
8.  `AUTOMATIC` mode remains bounded by configured policies.
9.  Cross-role automation requires explicit configuration or
    authorization.
10. Context authorization must be independently traceable.
11. Authorization decisions must be auditable.
12. Expired or revoked authorization must not be reused.
