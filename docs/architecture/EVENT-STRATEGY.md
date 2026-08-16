# OrchAI --- Event Strategy

## Purpose

Events provide decoupled coordination between major OrchAI capabilities
while preserving historical traceability.

## Initial Strategy

Use an in-process event dispatcher in the first implementation.

Important historical events may be persisted durably through the
persistence layer.

``` text
Application Operation
        ↓
Domain Event
        ↓
In-Process Dispatcher
   ┌────┼────┬────┐
   ↓    ↓    ↓    ↓
Audit Metrics State Suggestions
```

No distributed broker is required initially.

## Event Contract

Events should preserve:

``` text
event_id
event_type
occurred_at
source
task_id
project_id
execution_id
correlation_id
causation_id
payload
```

## Event Semantics

Events represent facts that happened.

Commands represent requested operations.

Events must not be treated as unrestricted commands or implicit
authorization.

## State Changes

An event may participate in a lifecycle transition, but the State
Machine remains authoritative for whether the transition is valid.

``` text
EVENT
  ↓
STATE MACHINE
  ↓
VALIDATION
  ↓
STATE TRANSITION
```

## Idempotency

Consumers must be able to recognize duplicate delivery using event
identity or another deterministic mechanism.

## Ordering

Where workflow correctness requires ordering, use explicit sequence,
causation, correlation, or transactional metadata. Timestamps alone are
not sufficient as a universal ordering mechanism.

## Failure Handling

The initial in-process implementation must preserve the event and
failure information when a consumer fails.

Future durable delivery may introduce:

``` text
Retry
Dead-Letter Handling
Transactional Outbox
External Broker
```

## Future Messaging

RabbitMQ or another broker may be introduced when there is a concrete
need for:

-   multi-instance execution;
-   durable asynchronous delivery;
-   independent workers;
-   external event consumers;
-   materially higher throughput.

The event domain contract must remain independent from the transport
technology.

## Invariants

1.  Events represent facts.
2.  Events are immutable historical records.
3.  Events remain traceable.
4.  Consumers remain independently responsible for their own effects.
5.  Event transport does not leak into domain events.
6.  Initial dispatch is in-process and asynchronous where appropriate.
