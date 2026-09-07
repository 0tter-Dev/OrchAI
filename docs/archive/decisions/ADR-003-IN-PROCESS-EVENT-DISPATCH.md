# ADR-003 --- Initial Event Dispatch Strategy

## Status

Accepted

## Context

OrchAI requires event-oriented coordination, but the first
implementation does not require a distributed broker.

## Decision

Use an in-process event dispatcher with durable event persistence for
historically significant events.

Introduce a transactional outbox before relying on external asynchronous
delivery.

## Rationale

This preserves event-oriented architecture without premature
infrastructure complexity.

## Consequences

Positive:

-   simple runtime;
-   low operational overhead;
-   easy local testing;
-   clear scaling path.

Trade-offs:

-   event processing initially shares the application runtime;
-   horizontal scaling requires additional infrastructure.

## Future Evolution

A broker may be introduced without changing the domain event contract.
