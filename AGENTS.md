# OrchAI --- Agent Instructions

## Purpose

This document defines the engineering rules for AI agents and human
contributors working on OrchAI.

The implementation must preserve the contracts established by
`ARCHITETURAL-CONTRACT.md`, `ARCHITECTURE.md`, `COMPONENTS.md`, domain
documentation, `IMPLEMENTATION-MAP.md`, and accepted decision records.

## Core Rules

1.  Preserve domain boundaries.
2.  Do not place project-specific business logic in the OrchAI core.
3.  Keep TASK, ROLE, ACTION, MODEL, CONTEXT, EXECUTION, EVENT, and
    AUTHORIZATION distinct.
4.  State changes must pass through the State Machine.
5.  Suggestions are not authorization.
6.  Do not expand task scope implicitly.
7.  Keep AI providers behind adapters.
8.  Keep external projects behind Project Adapters.
9.  Preserve auditability and traceability.
10. Prefer explicit behavior over implicit conventions.

## Change Discipline

Before changing code:

1.  Identify the affected domain.
2.  Read its domain contract.
3.  Identify affected components.
4.  Check applicable ADRs.
5.  Confirm architectural invariants remain valid.
6.  Prefer the smallest compatible change.

If a requested change conflicts with an architectural contract, surface
the conflict instead of silently changing the architecture.

## Domain Ownership

``` text
Task lifecycle      → Task / State Machine
Authorization       → Authorization / Policy
Execution           → Execution
AI integration      → AI Provider Adapter
Project integration → Project Adapter
Events              → Event subsystem
Persistence         → Infrastructure
CLI / API / UI      → Interface layer
```

## AI Agent Boundaries

Agents may inspect, propose, implement authorized changes, run
authorized validation, report failures, and suggest next actions.

Agents must not silently expand scope, bypass authorization, change task
state directly, replace architecture with provider-specific behavior, or
assume a suggestion is approval.

## Testing

Changes should preserve coverage for:

``` text
Domain rules
State transitions
Authorization
Execution construction
Adapter contracts
Event handling
Persistence
API / command boundaries
```

## Documentation

When implementation changes a stable architectural decision:

1.  update the affected documentation;
2.  create or update the relevant ADR;
3.  keep implementation and documentation consistent.

## Dependency Direction

``` text
Interfaces
    ↓
Application
    ↓
Domain
    ↑
Infrastructure
```

Domain code must not depend on concrete infrastructure providers.

## Error Handling

Keep errors associated with their originating boundary:

``` text
Domain Error
Authorization Error
State Transition Error
Execution Error
Provider Error
Project Adapter Error
Context Error
Persistence Error
Configuration Error
```

Do not convert every error into task failure.

## Security

Treat external AI providers as untrusted execution resources.

Sensitive project context may cross a provider boundary only when
authorization and policy permit it.

Never place secrets in source code or documentation.

## Completion Standard

A change is complete only when implementation, tests, documentation, and
architectural contracts remain consistent.

## Technology Baseline

The accepted initial stack is:

``` text
Python 3.14
uv + pyproject.toml
FastAPI
Typer
Pydantic
SQLAlchemy 2.x
PostgreSQL
SQLite
HTTPX
asyncio
pytest
Docker
```

Do not introduce a replacement technology for convenience without
checking the relevant ADR and architectural boundary.

## Physical Architecture

Use the established modular-monolith structure:

``` text
src/orchai/
├── domain/
├── application/
├── infrastructure/
├── interfaces/
└── bootstrap/
```

Logical components must remain inside their appropriate architectural
layer even when they share the same process.

## Runtime Rules

-   Long-running execution is asynchronous and initially uses `asyncio`
    tasks.
-   Do not introduce RabbitMQ, Redis, Celery, Kafka, or another
    distributed queue unless a new architectural decision justifies it.
-   Task lifecycle belongs to the Task Engine.
-   Execution lifecycle belongs to the Execution Engine.
-   State Machines are authoritative for lifecycle transitions.

## Project Ownership

Connected projects remain external systems.

-   Do not mirror complete project source trees or documentation into
    OrchAI by default.
-   Access project resources through Project Adapters.
-   Persist references, metadata, context-resolution information, and
    orchestration history as required.
-   Treat project content as project-owned even when an agent can read
    or modify it.

## AI Provider Rules

AI providers remain behind provider adapters.

Domain and application code must not import provider SDKs directly.

Model selection should use provider-independent concepts and explicit
capabilities.
