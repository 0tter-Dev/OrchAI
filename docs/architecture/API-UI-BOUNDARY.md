# OrchAI --- API and UI Boundary

## Purpose

The interface layer exposes OrchAI capabilities without exposing
internal implementation details.

## Interface Model

The first implementation is API-first with a CLI using the same
application services.

``` text
CLI ───────┐
           ├── Application Services
API ───────┘
```

Future VS Code, desktop, or web clients can consume the API without
changing domain logic.

## Core Operations

``` text
TASK MANAGEMENT
TASK STATE
PLANNING
AUTHORIZATION
EXECUTION
SUGGESTIONS
PROJECTS
AUDIT
METRICS
CONFIGURATION
```

## Current CLI Implementation

The current CLI surface includes a minimal local flow command and a
database migration command. These commands use application services and
infrastructure configuration to exercise:

``` text
PROJECT
TASK
AUTHORIZATION
EXECUTION
CONTEXT
```

The command is intentionally a thin interface over application services.
It does not own lifecycle rules, authorization decisions, context
resolution, or project-resource access.

The current commands are:

``` text
orchai db create
orchai db migrate
orchai local-flow
```

## Commands and Queries

``` text
COMMAND
    → requests a change

QUERY
    → reads information
```

Commands pass through application services.

## Authorization UI

Authorization requests should expose:

``` text
Task
Role
Action
Model
Context
Project
Scope
Reason
Execution Mode
Expiration
```

## Execution Visibility

Users should be able to inspect:

``` text
Current State
Current Execution
Execution History
Model
Provider
Context Scope
Outcome
Errors
Resource Usage
```

## Invariants

1.  UI state is not authoritative task state.
2.  UI actions do not bypass authorization.
3.  Suggestions remain suggestions until accepted.
4.  API and CLI share application behavior.
