# Technology And Test Strategy

## Purpose

Defines the accepted technology baseline for OrchAI's implementation
and the testing layers that verify it — both intentionally subordinate
to the architectural boundaries, never the other way around.

## Objective

Let any technology in this baseline be replaced without rewriting a
single domain rule, and let every domain rule, adapter contract, and
critical authorization path be verified independently of the others.

## Current Status

`implemented`

## Technology Baseline

| Concern | Baseline |
|---|---|
| Language | Python 3.14 |
| Dependency / Environment Management | `uv` |
| Project Configuration | `pyproject.toml` |
| API | FastAPI |
| CLI | Typer |
| Validation / Serialization | Pydantic |
| Persistence Toolkit | SQLAlchemy 2.x |
| Primary Database | PostgreSQL |
| Lightweight Local Database | SQLite |
| HTTP Client | HTTPX |
| Async Runtime | `asyncio` |
| Testing | pytest |
| Linting / Formatting | `ruff` (pinned `==0.15.11`) |
| API Schema | OpenAPI through FastAPI |
| AI Provider Access | LiteLLM (ADR-013) |
| Streaming Transport | Server-Sent Events (ADR-013) |
| Desktop Shell | `pywebview` on Windows WebView2 (ADR-017) |
| Desktop Frontend (build-time only) | Vite + React, built to static assets |
| Containerization | Docker |
| Logging / Observability | Structured application logging, implementation-neutral boundary |

FastAPI and Typer are restricted to the interface layer and must
invoke the same application services rather than implementing
independent business rules. Pydantic is used for interface-level
schemas and boundary validation — domain invariants remain domain
responsibilities, never delegated entirely to Pydantic models. `ruff`
is pinned exactly (not a lower-bound range) because its default rule
set has changed across minor releases (0.16.4 flags import-sorting
issues on files 0.15.11 reports clean); always invoke it through the
project environment (`uv run ruff check`), never as an ephemeral tool
(`uv tool run`/`uvx`), so the pinned version is what actually runs.

## Async Runtime And Messaging

The runtime is async-first using `asyncio`; long-running Executions
are asynchronous work without distributed worker infrastructure in the
current implementation. Execution dispatch stays behind an
application/infrastructure boundary so a future durable worker or
broker can be introduced without changing domain concepts. No
distributed message broker is required today — the event mechanism is
an in-process dispatcher with durable persistence for events needing
historical traceability (see `Events And State`); RabbitMQ or another
broker may be introduced later only when multi-instance execution,
durable external delivery, or throughput requirements justify it.

## AI Integration

AI resources are provider-agnostic from the domain's perspective
(`Model Manager → Model Provider Contract → Provider Adapter →
Local/Cloud/External Agent`); provider SDKs remain infrastructure
dependencies. Per ADR-013, the single Provider Adapter implementation
is LiteLLM (`infrastructure/ai/litellm_provider.py`), covering OpenAI,
Anthropic, Gemini, Ollama, and other OpenAI-compatible local runtimes
behind one calling convention, plus streaming and retry/backoff —
LiteLLM itself never appears above `infrastructure/ai/`.

## Explicit Non-Goals For The Current Stack

RabbitMQ, Redis, Celery, Kafka, MongoDB, a vector database, object
storage, and Kubernetes are not required by the current
implementation — these may be evaluated later only when a concrete
architectural or operational requirement exists.

## Test Layers

```text
UNIT → CONTRACT → INTEGRATION → END-TO-END
```

- **Unit** — State Machine, authorization rules, domain invariants, execution construction, context resolution, suggestion rules, configuration validation; avoid infrastructure dependencies.
- **Contract** — AI Provider Adapter contract, Project Adapter contract, repository contract, event consumer contract.
- **Integration** — persistence, event dispatch, application services, API, CLI, adapter integration.
- **End-to-end** — at least one complete workflow (`TASK → PLAN → AUTHORIZATION → IMPLEMENT → REVIEW → VALIDATION → COMPLETION`), including failure and rework paths.
- **Security** — unauthorized execution, unauthorized context, cross-role progression, cloud context restriction, capability mismatch, expired/revoked authorization.

A bug involving a domain invariant normally produces a regression test
alongside its fix.

This document folds in the still-relevant decision from the former
ADR-001 (Initial Technology Stack) — the baseline above and the
explicit non-goals it originally set, most of which still hold; full
rationale remains in `docs/archive/decisions/`.

## Key Rules

- domain code never imports FastAPI, Typer, SQLAlchemy, HTTPX, provider SDKs, or concrete infrastructure
- API and CLI share application services; provider SDKs and project access stay behind adapters
- PostgreSQL is the primary persistent store, SQLite an optional lightweight/local backend
- technology replacement must never require rewriting domain rules
- domain rules, adapter contracts, and critical authorization paths are all independently testable

## Main Relationships

- constrains every context file's component-ownership boundaries (domain never imports infrastructure)
- the async runtime backs `Execution Engine`; the in-process dispatcher backs `Events And State`
- the AI provider baseline is what `Execution Engine`'s adapter boundary formalizes
