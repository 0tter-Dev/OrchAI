# OrchAI --- Technology Stack

## Purpose

This document defines the accepted technology baseline for the first
implementation of OrchAI.

The stack is intentionally subordinate to the architectural boundaries.
No domain rule may depend on a selected framework, database engine,
provider SDK, or transport implementation.

## Baseline

  -----------------------------------------------------------------------
  Concern                             Baseline
  ----------------------------------- -----------------------------------
  Language                            Python 3.14

  Dependency / Environment Management `uv`

  Project Configuration               `pyproject.toml`

  API                                 FastAPI

  CLI                                 Typer

  Validation / Serialization          Pydantic

  Persistence Toolkit                 SQLAlchemy 2.x

  Primary Database                    PostgreSQL

  Lightweight Local Database          SQLite

  HTTP Client                         HTTPX

  Async Runtime                       `asyncio`

  Testing                             pytest

  API Schema                          OpenAPI through FastAPI

  Containerization                    Docker

  Logging / Observability             Structured application logging with
                                      an implementation-neutral boundary
  -----------------------------------------------------------------------

## Python Runtime

Python 3.14 is the target runtime for the initial implementation.

The project uses `uv` for environment and dependency management, with
`pyproject.toml` as the authoritative project configuration.

## API

FastAPI is the initial HTTP API framework.

It is selected for:

-   native asynchronous request handling;
-   strong type-driven request and response validation through Pydantic;
-   OpenAPI generation;
-   low ceremony for an API-first application;
-   compatibility with the async execution model.

FastAPI is restricted to the interface layer and must not leak into
domain logic.

## CLI

Typer is the initial CLI framework.

The CLI and API must invoke the same application services rather than
implementing independent business rules.

## Validation

Pydantic is used for interface-level schemas and application boundary
validation where structured data contracts are required.

Domain invariants remain domain responsibilities and must not be
delegated entirely to Pydantic models.

## Persistence

SQLAlchemy 2.x provides the persistence toolkit and repository
implementation boundary.

PostgreSQL is the primary database target because OrchAI has relational
operational state, lifecycle relationships, authorization records,
execution history, and transactional requirements. PostgreSQL also
provides JSON-capable storage for flexible metadata without requiring a
separate document database.

SQLite remains supported for lightweight/local deployments and testing
where appropriate. Domain models and repository contracts must not
depend on SQLite-specific behavior.

MongoDB is not part of the initial persistence baseline. It remains a
possible future specialized store if a concrete use case justifies it.

## Asynchronous Runtime

The initial runtime is async-first using Python `asyncio`.

Long-running Executions are represented as asynchronous work without
introducing distributed worker infrastructure during the first
implementation.

The architecture must keep execution dispatch behind an
application/infrastructure boundary so a future durable worker or broker
can be introduced without changing domain concepts.

## Messaging

No distributed message broker is required for the initial
implementation.

The initial event mechanism is an in-process dispatcher with durable
persistence for events that require historical traceability.

RabbitMQ or another broker may be introduced later when multi-instance
execution, durable external delivery, or throughput requirements justify
it.

## AI Integration

AI resources are provider-agnostic from the domain perspective.

``` text
Model Manager
      ↓
Model Provider Contract
      ↓
Provider Adapter
      ↓
Local / Cloud / External Agent
```

Provider SDKs remain infrastructure dependencies.

Model capabilities are explicit so Actions can express requirements
without depending on a specific provider or model family.

## Project Integration

Connected projects are external systems.

``` text
Application
    ↓
Project Adapter Contract
    ↓
Project Adapter Implementation
    ↓
External Project
```

OrchAI does not mirror complete project source trees or documentation by
default. It persists project identity, references, configuration,
capabilities, and orchestration metadata.

## Testing

pytest is the initial test framework.

Testing must cover domain invariants independently from infrastructure
and provide integration coverage for adapter contracts, persistence,
event handling, API/CLI boundaries, and end-to-end task/execution flows.

## Containerization

Docker is the initial containerization target for reproducible
development and deployment environments.

Containerization must not alter domain or application boundaries.

## Explicit Non-Goals for the Initial Stack

The initial implementation does not require:

``` text
RabbitMQ
Redis
Celery
Kafka
MongoDB
Vector Database
Object Storage
Kubernetes
```

These technologies may be evaluated later only when a concrete
architectural or operational requirement exists.

## Technology Invariants

1.  Domain code does not import FastAPI, Typer, SQLAlchemy, HTTPX,
    provider SDKs, or concrete infrastructure implementations.
2.  API and CLI share application services.
3.  Provider SDKs remain behind AI adapters.
4.  Project access remains behind Project Adapters.
5.  PostgreSQL is the primary persistent store.
6.  SQLite is an optional lightweight/local backend.
7.  `asyncio` is the initial execution runtime.
8.  Distributed messaging remains optional future infrastructure.
9.  Technology replacement must not require rewriting domain rules.
