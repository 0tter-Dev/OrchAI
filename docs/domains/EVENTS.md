# OrchAI --- Events Domain

## 1. Purpose

An `EVENT` represents a meaningful occurrence within the OrchAI.

Events provide the coordination mechanism between task lifecycle,
execution, authorization, state transitions, auditing, metrics, and
other components.

The event model enables the system to remain modular while maintaining
traceability.

------------------------------------------------------------------------

## 2. Event Characteristics

An event should contain enough information to identify:

-   event type;
-   unique event identity;
-   timestamp;
-   source;
-   task, when applicable;
-   project, when applicable;
-   related execution, when applicable;
-   relevant payload;
-   correlation information.

Events represent facts that occurred.

They must not be used as unrestricted commands disguised as historical
facts.

------------------------------------------------------------------------

## 3. Event Categories

Events may be categorized conceptually as:

### Task Events

``` text
TASK_CREATED
TASK_UPDATED
TASK_CANCELLED
TASK_COMPLETED
```

### Planning Events

``` text
PLANNING_STARTED
PLANNING_COMPLETED
PLANNING_BLOCKED
```

### Execution Events

``` text
EXECUTION_REQUESTED
EXECUTION_AUTHORIZED
EXECUTION_STARTED
EXECUTION_COMPLETED
EXECUTION_FAILED
```

### Review and Validation Events

``` text
REVIEW_STARTED
REVIEW_PASSED
REVIEW_FAILED
VALIDATION_STARTED
VALIDATION_PASSED
VALIDATION_FAILED
TEST_STARTED
TEST_PASSED
TEST_FAILED
```

### Authorization Events

``` text
AUTHORIZATION_REQUESTED
AUTHORIZATION_GRANTED
AUTHORIZATION_REJECTED
AUTHORIZATION_EXPIRED
```

### Context Events

``` text
CONTEXT_REQUESTED
CONTEXT_AUTHORIZED
CONTEXT_RESOLVED
CONTEXT_REJECTED
```

The exact event catalogue is implementation-specific and may evolve.

------------------------------------------------------------------------

## 4. Events and State

Events may cause state transitions when the State Machine defines the
corresponding transition as valid.

Conceptually:

``` text
EVENT
  ↓
STATE MACHINE
  ↓
VALIDATION
  ↓
STATE TRANSITION
```

An event must not directly bypass the State Machine to mutate task
state.

------------------------------------------------------------------------

## 5. Event Ordering

Where workflow correctness depends on ordering, events must provide
sufficient information to establish the required order.

The implementation may use:

-   sequence numbers;
-   timestamps;
-   causation identifiers;
-   correlation identifiers;
-   transactional ordering.

The concrete mechanism is implementation-specific.

------------------------------------------------------------------------

## 6. Causation and Correlation

Events should support tracing relationships between actions.

For example:

``` text
TASK_CREATED
    ↓
PLANNING_STARTED
    ↓
PLANNING_COMPLETED
    ↓
AUTHORIZATION_REQUESTED
    ↓
AUTHORIZATION_GRANTED
    ↓
IMPLEMENTATION_STARTED
```

The system should be able to determine why an event occurred and which
previous event or operation caused it.

------------------------------------------------------------------------

## 7. Event Consumers

Different components may consume the same event for different purposes.

For example:

``` text
EXECUTION_COMPLETED
        │
        ├── State Machine
        ├── Audit Manager
        ├── Metrics
        └── Suggestion Engine
```

Consumers must remain independently responsible for their own
processing.

------------------------------------------------------------------------

## 8. Event Failure

Failure to process an event must not silently destroy the event itself.

The system should support appropriate failure handling such as:

-   retry;
-   dead-letter handling;
-   error recording;
-   operator intervention.

The specific mechanism belongs to the implementation architecture.

------------------------------------------------------------------------

## 9. Event Idempotency

Event consumers should be designed to avoid unintended duplicate effects
when the same event is delivered more than once.

Where required, consumers should use event identity or another
deterministic mechanism to recognize already-processed events.

------------------------------------------------------------------------

## 10. Event Immutability

Once an event represents a historical fact, its core meaning must not be
modified.

Corrections should be represented through additional events rather than
rewriting historical events.

------------------------------------------------------------------------

## 11. Commands vs Events

The architecture must distinguish commands from events.

A command represents a requested operation.

An event represents something that happened.

For example:

``` text
COMMAND:
RequestImplementation

EVENT:
IMPLEMENTATION_STARTED
```

A user request may generate a command, which after authorization and
successful processing may produce one or more events.

------------------------------------------------------------------------

## 12. Event Domain Invariants

1.  Events represent meaningful occurrences.
2.  Historical events are immutable.
3.  Events do not automatically constitute authorization.
4.  State changes occur through the State Machine.
5.  Event consumers must not silently redefine global workflow rules.
6.  Event processing must remain traceable.
7.  Duplicate delivery must not create unintended duplicate effects.
8.  Commands and events must remain conceptually distinct.
