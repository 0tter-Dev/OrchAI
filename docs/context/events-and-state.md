# Events And State

## Purpose

Defines the Event — a meaningful occurrence used to coordinate task
lifecycle, execution, authorization, state transitions, auditing,
metrics, and suggestions — and the in-process dispatch strategy that
delivers it.

## Objective

Keep the system modular and traceable by having independent components
react to the same facts without direct coupling to whichever component
produced them.

## Current Status

`implemented`

## Event Contract

An event preserves `event_id`, `event_type`, `occurred_at`, `source`,
`task_id`/`project_id`/`execution_id` when applicable, `correlation_id`,
`causation_id`, and a relevant payload. Events represent facts that
occurred; they must never be treated as unrestricted commands or
implicit authorization, and a command (a requested operation, e.g.
`RequestImplementation`) is conceptually distinct from an event
(something that happened, e.g. `IMPLEMENTATION_STARTED`).

Categories include Task Events (`TASK_CREATED`/`TASK_UPDATED`/
`TASK_CANCELLED`/`TASK_COMPLETED`), Planning Events, Execution Events
(`EXECUTION_REQUESTED`/`AUTHORIZED`/`STARTED`/`COMPLETED`/`FAILED`),
Review/Validation Events, Authorization Events, and Context Events;
the exact catalogue is implementation-specific and evolves.

## Events And The State Machine

An event may cause a state transition only when the State Machine
defines that transition as valid (`EVENT → STATE MACHINE → VALIDATION
→ STATE TRANSITION`); an event must never directly bypass the State
Machine to mutate task state.

## Dispatch Strategy

The initial and current implementation uses an in-process event
dispatcher; important historical events are persisted durably through
the persistence layer. No distributed broker is required initially:

```
Application Operation → Domain Event → In-Process Dispatcher →
    {Audit, Metrics, State, Suggestions}
```

A future broker (e.g. RabbitMQ) may be introduced when there is a
concrete need for multi-instance execution, durable asynchronous
delivery, independent workers, external consumers, or materially
higher throughput — the event domain contract stays independent of
transport technology regardless.

## Ordering, Idempotency, And Failure

Where correctness depends on ordering, events carry explicit sequence,
causation, correlation, or transactional metadata — timestamps alone
are not a sufficient universal ordering mechanism. Consumers must
recognize duplicate delivery (via event identity or another
deterministic mechanism) to avoid unintended duplicate effects. A
consumer failure must preserve the event and failure information
rather than silently discarding it; future durable delivery may add
retry, dead-letter handling, or a transactional outbox.

## Event Engine (Component)

Coordinates event-driven behavior: receives events, dispatches them,
triggers registered handlers, preserves ordering where required,
reports processing failures. Must not redefine business rules, bypass
the State Machine directly, or interpret an event as implicit user
authorization. Maps to `application/events/` (domain events in
`domain/events/`).

This document folds in the still-relevant decision from the former
ADR-003 (Initial Event Dispatch Strategy) — the in-process dispatcher
described above; full rationale remains in `docs/archive/decisions/`.

## Key Rules

- events represent facts and are immutable historical records; corrections are new events, never rewrites
- events never constitute authorization by themselves
- state changes occur only through the State Machine
- event consumers remain independently responsible for their own effects and must not silently redefine global workflow rules
- event processing must remain traceable, and duplicate delivery must not create unintended duplicate effects
- commands and events remain conceptually distinct

## Main Relationships

- coordinates `Tasks And Lifecycle`'s state transitions
- notifies `Observability` (audit, metrics) of every relevant occurrence
- notifies the suggestion engine (see `Observability`) so it can react to task/execution outcomes
- has no external transport dependency today; dispatch is internal to the application layer
