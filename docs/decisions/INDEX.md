# OrchAI Architecture Decision Index

## Purpose

This document provides navigation for Architecture Decision Records
(ADRs).

ADRs explain why important architectural choices were made.

## Current Decisions

-   [`ADR-001-INITIAL-TECHNOLOGY-STACK.md`](ADR-001-INITIAL-TECHNOLOGY-STACK.md)
    --- Accepted initial technology baseline.
-   [`ADR-002-PERSISTENCE-STRATEGY.md`](ADR-002-PERSISTENCE-STRATEGY.md)
    --- PostgreSQL primary persistence with SQLite local support.
-   [`ADR-003-IN-PROCESS-EVENT-DISPATCH.md`](ADR-003-IN-PROCESS-EVENT-DISPATCH.md)
    --- Initial event dispatch strategy.
-   [`ADR-004-API-FIRST-INTERFACE.md`](ADR-004-API-FIRST-INTERFACE.md)
    --- API-first interface boundary.
-   [`ADR-005-LOCAL-CLOUD-PROVIDER-BOUNDARY.md`](ADR-005-LOCAL-CLOUD-PROVIDER-BOUNDARY.md)
    --- Local/cloud AI provider isolation.
-   [`ADR-006-SUGGESTED-AS-DEFAULT-EXECUTION-MODE.md`](ADR-006-SUGGESTED-AS-DEFAULT-EXECUTION-MODE.md)
    --- Suggested as the default execution mode.
-   [`ADR-007-MODULAR-MONOLITH.md`](ADR-007-MODULAR-MONOLITH.md) ---
    Modular monolith architecture.
-   [`ADR-008-ASYNC-IN-PROCESS-EXECUTION.md`](ADR-008-ASYNC-IN-PROCESS-EXECUTION.md)
    --- Async-first in-process execution baseline.
-   [`ADR-009-PROJECT-CONTENT-OWNERSHIP.md`](ADR-009-PROJECT-CONTENT-OWNERSHIP.md)
    --- External ownership of connected project content.
-   [`ADR-010-PROJECT-READINESS-AND-SECURITY-GATES.md`](ADR-010-PROJECT-READINESS-AND-SECURITY-GATES.md)
    --- Readiness and security gates for operations on connected
    projects.

## ADR Status Model

``` text
Proposed
Accepted
Superseded
Deprecated
```

## ADR Rule

An accepted decision should not be silently rewritten when the
architectural choice changes materially.

Instead:

``` text
Existing ADR
    ↓
New Context
    ↓
New ADR
    ↓
Previous ADR → Superseded
```

## Relationship to Other Documentation

``` text
Architecture
    → describes the intended structure

ADR
    → explains why a significant choice was made

Status
    → describes the current state
```
