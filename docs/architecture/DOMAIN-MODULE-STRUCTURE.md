# OrchAI --- Domain Module Structure

## Purpose

This document maps core domain concepts to physical domain modules.

## Modules

``` text
domain/
├── tasks/
├── executions/
├── authorization/
├── policies/
├── roles/
├── actions/
├── models/
├── context/
├── projects/
├── capabilities/
└── events/
```

## Responsibilities

Each module may contain:

``` text
Entities
Value Objects
Domain Services
Domain Errors
Invariants
Domain Contracts
State / Transition Rules
```

A module owns the rules of its concept. Application orchestration must
not duplicate domain invariants.

## Task and Execution State Machines

Task and Execution State Machines live with their respective lifecycle
domains:

``` text
domain/tasks/
domain/executions/
```

They are deterministic, independently testable, and authoritative for
valid state transitions.

A completed Task cannot be transitioned to an earlier in-process state
unless the Task State Machine explicitly defines such a transition. A
rejected or terminal Execution cannot become completed unless a new
Execution represents the subsequent attempt.

## Cross-Domain References

Prefer stable identifiers and explicit contracts over cyclic object
graphs.

Example:

``` text
Execution
  → TaskId
  → RoleId
  → ActionId
  → ModelId
  → ProjectId
  → AuthorizationId
```

## Domain Purity

Domain modules must not import:

``` text
FastAPI
Typer
SQLAlchemy
HTTPX
Provider SDKs
Filesystem implementations
Database drivers
```

## Project Ownership Rule

The domain represents the concept of a Project and references to project
resources. It does not own the project's source tree, documentation, or
external artifacts.

## Context Rule

The domain represents context requirements, authorization scope,
references, and resolved context metadata. Complete project content is
not a required domain persistence concern.

## Invariants

1.  One domain module owns each domain rule.
2.  Infrastructure is not imported by the domain.
3.  Cross-domain behavior uses explicit contracts.
4.  State transitions are controlled by State Machines.
5.  Domain logic remains independently testable.
6.  Project content remains external to the OrchAI domain.
