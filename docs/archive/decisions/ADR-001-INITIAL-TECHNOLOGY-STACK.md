# ADR-001 --- Initial Technology Stack

## Status

Accepted

## Context

OrchAI requires a stable implementation platform for asynchronous
orchestration, AI provider integration, project adapters, persistence,
API/CLI interfaces, and authorization-heavy domain logic.

The stack must support a modular monolith without coupling domain rules
to infrastructure technologies.

## Decision

The initial technology baseline is:

``` text
Python 3.14
uv
pyproject.toml
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

PostgreSQL is the primary persistence target. SQLite is supported for
lightweight/local operation.

## Rationale

Python provides a mature ecosystem for AI integrations, asynchronous
orchestration, HTTP clients, subprocess execution, validation, and
testing.

FastAPI aligns with the async-first API boundary and provides strong
typing and OpenAPI support without imposing application architecture.

Typer provides a CLI over the same application services.

Pydantic provides explicit data contracts at interface/application
boundaries.

SQLAlchemy provides a stable persistence abstraction while keeping
database implementation in infrastructure.

PostgreSQL provides relational integrity, transactions, strong
relationships, and JSON-capable fields suitable for OrchAI's operational
and historical data.

SQLite provides a low-friction backend for local operation and testing.

`uv` and `pyproject.toml` provide a single dependency and project
configuration baseline.

## Consequences

Positive:

-   clear separation between domain and infrastructure;
-   async-first runtime;
-   strong AI ecosystem;
-   relational persistence with flexible metadata support;
-   simple local development;
-   API/CLI reuse;
-   replaceable provider integrations.

Trade-offs:

-   Python is not optimal for every CPU-heavy workload;
-   SQLite is not the primary multi-instance database;
-   provider-specific capabilities require adapter extensions;
-   distributed execution infrastructure is intentionally deferred.

## Rejected / Deferred Alternatives

The following are not part of the initial baseline:

``` text
MongoDB
RabbitMQ
Redis
Celery
Kafka
Vector Database
Kubernetes
```

They may be introduced only when a concrete requirement justifies them.

## Invariants

1.  Domain code does not depend on selected technologies.
2.  API and CLI share application services.
3.  Provider SDKs remain infrastructure dependencies.
4.  Database technology remains behind repository boundaries.
5.  `asyncio` is the initial execution runtime.
