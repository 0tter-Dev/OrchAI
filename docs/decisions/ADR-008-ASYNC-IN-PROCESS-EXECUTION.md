# ADR-008 --- Async In-Process Execution Baseline

## Status

Accepted

## Context

AI executions and project operations may be long-running. OrchAI should
remain responsive and avoid blocking the main application flow.

The initial implementation does not require parallel execution of
multiple workflows or a distributed worker fleet.

## Decision

Use Python `asyncio` tasks as the initial mechanism for long-running
asynchronous execution.

Do not require RabbitMQ, Redis, Celery, Kafka, or another distributed
queue for the first implementation.

Execution dispatch must remain behind a replaceable
application/infrastructure boundary.

## Rationale

This preserves asynchronous behavior with minimal infrastructure while
keeping the architecture ready for a future persistent worker model.

## Consequences

Positive:

-   simple deployment;
-   low operational overhead;
-   native fit with FastAPI and async provider clients;
-   straightforward local development.

Trade-offs:

-   in-process work depends on the OrchAI process remaining alive unless
    durable recovery is later introduced;
-   horizontal execution requires future worker/queue infrastructure;
-   cancellation and restart recovery must be explicitly handled by the
    application.

## Future Evolution

A durable job dispatcher and broker may be introduced when execution
durability across process restarts, independent workers, or
multi-instance deployment becomes a concrete requirement.

The Task and Execution domain model must remain unchanged by such an
evolution.
