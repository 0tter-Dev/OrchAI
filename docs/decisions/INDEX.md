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
-   [`ADR-011-CHAT-FIRST-REQUEST-INTERFACE.md`](ADR-011-CHAT-FIRST-REQUEST-INTERFACE.md)
    --- Chat-first `/requests` interface for external clients.
-   [`ADR-012-AUTHENTICATION-AND-AUTHORIZATION.md`](ADR-012-AUTHENTICATION-AND-AUTHORIZATION.md)
    --- Identity and access control (JWT authentication, persisted
    users/permissions, superuser) for the CLI and API. Accepted ---
    implemented (v0.1.11).
-   [`ADR-013-LITELLM-AND-STREAMING-PROVIDER.md`](ADR-013-LITELLM-AND-STREAMING-PROVIDER.md)
    --- LiteLLM as the AI provider adapter, plus a streaming extension
    to `AIProviderPort`. Design only; implementation is follow-up work.
-   [`ADR-014-CONVERSATION-DOMAIN-MODEL.md`](ADR-014-CONVERSATION-DOMAIN-MODEL.md)
    --- `Conversation`/`Message` as a new bounded context, with
    explicit-only escalation to a real Task. Design only; implementation
    is follow-up work.
-   [`ADR-015-MODULE-CONCEPT.md`](ADR-015-MODULE-CONCEPT.md) --- The
    `ModuleDefinition` registry (Forge, Studio, and future modules).
    Design only; implementation is follow-up work.
-   [`ADR-016-DESKTOP-SINGLE-USER-IDENTITY-SIMPLIFICATION.md`](ADR-016-DESKTOP-SINGLE-USER-IDENTITY-SIMPLIFICATION.md)
    --- Single local user identity, attribution-only, for OrchAI
    Desktop. Design only; implementation is follow-up work.
-   [`ADR-017-DESKTOP-APPLICATION-SHELL.md`](ADR-017-DESKTOP-APPLICATION-SHELL.md)
    --- `pywebview` desktop shell with an in-process backend. Design
    only; implementation is follow-up work.

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
