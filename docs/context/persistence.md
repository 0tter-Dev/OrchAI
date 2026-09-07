# Persistence

## Purpose

Defines what OrchAI persists, why, and through which boundary —
durable operational state and historical traceability without turning
OrchAI into a storage system for connected projects.

## Objective

Give every operational and historical aggregate durable, transactional
storage behind a repository contract that domain and application code
never need to know is backed by SQLAlchemy, PostgreSQL, or SQLite
specifically.

## Current Status

`implemented`

## Strategy And Current Implementation

SQLAlchemy 2.x is the persistence toolkit, with PostgreSQL as the
explicit production default (`ORCHAI_DATABASE_URL` resolves to a local
PostgreSQL connection string when left unset) and SQLite as a
secondary, explicitly-opted-into option (`sqlite:///...` or the
`sqlite`/`local` alias) for fast, dependency-free local development
and tests. Both dialects share the same repository implementations,
application contracts, and SQL migrations. `orchai db sync` creates
the database if needed (a no-op for SQLite/local-flow) and then
applies migrations, in one step.

Currently persisted aggregates: Projects, Tasks, Authorization
Requests, Authorization Decisions, Executions, Events, Audit Records,
Context Resolution Metadata, Metric Records, Suggestions.

## What Is Persisted

**Operational state:** Projects, Project Adapter Configuration,
Project References, Capabilities, Tasks, Executions, Current States,
Authorization State, Configuration.

**Historical state:** Events, Execution Attempts, Authorization
Decisions, Audit Records, Usage Records, User Decisions, Context
Resolution Metadata.

## What Is Not Persisted By Default

OrchAI does not mirror complete connected-project content merely to
make it available to AI agents — Source Tree, Project Documentation,
Repository Contents, Project Assets, and Project-Owned Artifacts
remain owned by the external project; the Project Adapter resolves
them when required by an authorized execution. Context is normally
represented through references and resolution metadata (execution,
project, source, resource, content hash, byte size, timestamp, adapter
metadata) rather than permanent copies — the current implementation
does not persist resolved file content itself. A reproducible
historical context snapshot may be persisted explicitly as an
execution-history decision, never as a default requirement to mirror
the project. See `Project Adapter And Security`'s persistence policy
for the full allowed/authorized/never-persisted breakdown, which
applies here identically.

## Repository Boundary And Relational Model

```
Domain / Application Contract → Repository Interface →
    SQLAlchemy Repository → PostgreSQL / SQLite
```

Database-specific APIs stay in infrastructure; domain models never
depend on database technology. PostgreSQL is preferred for the strong
relational and transactional lifecycle requirements among Projects,
Tasks, Executions, Events, Authorization, Policies, Roles, Actions,
and Models, with JSON-capable fields for flexible metadata. MongoDB is
not part of the baseline and would only be introduced if a concrete
workload demonstrates relational storage plus JSON fields is
insufficient.

## Transactions And Concurrency

Critical consistency boundaries are transactional where supported,
especially Authorization Decision + Audit, Task State Change +
Historical Event, and Execution Completion + Usage Record. The model
supports stable identifiers and explicit ownership, leaving room for
future optimistic concurrency controls without requiring parallel
execution in the current release.

## Persistence (Component)

Provides durable storage for Orchestrator state and history —
Projects, Tasks, Task States, Events, Executions, Authorizations,
Suggestions, Audit Records, Metrics, Configuration. The concrete
implementation is intentionally unspecified at the domain level. Maps
to `infrastructure/persistence/`.

This document folds in the still-relevant decision from the former
ADR-002 (Persistence Strategy) — the SQLAlchemy/PostgreSQL/SQLite
strategy above; full rationale remains in `docs/archive/decisions/`.

## Key Rules

- domain models never depend on database technology
- historical facts are never silently overwritten
- critical state changes use explicit transaction boundaries
- persistence failures remain distinguishable from domain failures
- project content remains external by default; persistence of project knowledge stays narrower than project readability

## Main Relationships

- backs every aggregate created by `Tasks And Lifecycle`, `Execution Engine`, `Authorization Policy`, and `Observability`
- governed by `Project Adapter And Security`'s persistence policy for anything project-derived
- selected and configured through `Configuration`
