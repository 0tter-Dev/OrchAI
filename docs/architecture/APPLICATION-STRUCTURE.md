# OrchAI --- Application Structure

## Purpose

This document defines the physical source-tree baseline for the OrchAI
modular monolith.

The structure applies Clean Architecture and Hexagonal Architecture
principles without requiring every logical component to become an
independent package or service.

## Repository Layout

``` text
src/
└── orchai/
    ├── domain/
    │   ├── tasks/
    │   ├── executions/
    │   ├── authorization/
    │   ├── policies/
    │   ├── roles/
    │   ├── actions/
    │   ├── models/
    │   ├── context/
    │   ├── projects/
    │   ├── capabilities/
    │   └── events/
    │
    ├── application/
    │   ├── tasks/
    │   ├── executions/
    │   ├── orchestration/
    │   ├── agents/
    │   ├── models/
    │   ├── context/
    │   ├── projects/
    │   └── events/
    │
    ├── infrastructure/
    │   ├── persistence/
    │   ├── messaging/
    │   ├── ai/
    │   ├── projects/
    │   ├── filesystem/
    │   ├── configuration/
    │   └── observability/
    │
    ├── interfaces/
    │   ├── api/
    │   └── cli/
    │
    └── bootstrap/
```

Empty modules should not be created merely to match the diagram. A
directory becomes implementation-relevant when a concrete responsibility
exists.

## Domain Layer

Contains stable business concepts and invariants.

Examples:

``` text
Task
Execution
Role
Action
Model
Authorization
Policy
Context
Project
Capability
Event
```

Task and Execution lifecycle state machines belong to their respective
domain modules.

## Application Layer

Coordinates use cases and workflows.

The initial application responsibilities are:

``` text
Task Engine
Execution Engine
Orchestration
Agent Coordination
Model Resolution
Context Resolution
Project Coordination
Event Dispatch Coordination
```

Application services may depend on domain contracts and
repository/provider ports but not concrete infrastructure
implementations.

## Infrastructure Layer

Contains concrete adapters and technical implementations:

``` text
Persistence
AI Providers
Project Adapters
Event / Messaging Transport
Configuration Sources
Filesystem / External Resources
Observability
```

Infrastructure implements contracts required by the core.

## Interfaces Layer

Translates external requests into application commands/queries.

``` text
API
CLI
Future Desktop / Editor / Web Interfaces
```

Interfaces do not own task lifecycle, authorization, or state transition
rules.

## Bootstrap Layer

The composition root is responsible for:

-   loading configuration;
-   constructing dependencies;
-   selecting implementations;
-   initializing infrastructure;
-   starting the application runtime.

## Dependency Direction

``` text
Interfaces
    ↓
Application
    ↓
Domain

Infrastructure
    ↓
Domain / Application Contracts

Bootstrap
    ↓
Everything required to compose the runtime
```

Domain code must never import infrastructure implementations.

## Modular Monolith Rule

The modules are logical boundaries inside one deployable application.

They are not independent processes and must not be treated as
microservices unless a future architectural decision explicitly
introduces service decomposition.
