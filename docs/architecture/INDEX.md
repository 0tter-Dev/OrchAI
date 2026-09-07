# OrchAI Architecture Documentation Index

## Purpose

This document is the navigation entry point for architecture
implementation documentation.

These documents translate the conceptual architecture into technical
boundaries without becoming implementation code.

## Architecture Documents

-   [`../ARCHITECTURE.md`](../ARCHITECTURE.md) --- High-level
    architecture and implementation invariants.
-   [`COMPONENTS.md`](COMPONENTS.md) --- Logical component
    responsibilities and physical mapping.
-   [`TECHNOLOGY-STACK.md`](TECHNOLOGY-STACK.md) --- Accepted technology
    baseline.
-   [`APPLICATION-STRUCTURE.md`](APPLICATION-STRUCTURE.md) --- Physical
    source-tree organization.
-   [`DOMAIN-MODULE-STRUCTURE.md`](DOMAIN-MODULE-STRUCTURE.md) ---
    Domain module organization.
-   [`PERSISTENCE-STRATEGY.md`](PERSISTENCE-STRATEGY.md) --- Persistence
    boundaries and ownership.
-   [`EVENT-STRATEGY.md`](EVENT-STRATEGY.md) --- Event dispatch and
    future messaging strategy.
-   [`ADAPTER-CONTRACTS.md`](ADAPTER-CONTRACTS.md) --- AI and Project
    Adapter boundaries.
-   [`PROJECT-SECURITY-AND-READINESS.md`](PROJECT-SECURITY-AND-READINESS.md)
    --- Security profile, readiness levels, and operational gates for
    connected projects.
-   [`API-UI-BOUNDARY.md`](API-UI-BOUNDARY.md) --- API, CLI, and future
    UI boundaries.
-   [`CHAT-FIRST-REQUEST-MODEL.md`](CHAT-FIRST-REQUEST-MODEL.md) ---
    Chat-first `/requests` projection over the Task domain.
-   [`IDENTITY-AND-ACCESS-MODEL.md`](IDENTITY-AND-ACCESS-MODEL.md) ---
    Users, permissions, and JWT authentication for the CLI and API
    (implemented; see ADR-012). For the desktop client's single-user
    simplification, see ADR-016.
-   [`CONFIGURATION-ARCHITECTURE.md`](CONFIGURATION-ARCHITECTURE.md) ---
    Configuration loading and resolution.
-   [`TEST-STRATEGY.md`](TEST-STRATEGY.md) --- Testing layers and
    responsibilities.
-   [`DEPLOYMENT-MODEL.md`](DEPLOYMENT-MODEL.md) --- Initial and future
    deployment topology.
-   [`MODULES.md`](MODULES.md) --- The Module concept (Forge, Studio,
    and future modules) introduced by ADR-015.
-   [`DESKTOP-APPLICATION.md`](DESKTOP-APPLICATION.md) --- The OrchAI
    Desktop client shell introduced by ADR-017.

## Architectural Flow

``` text
INTERFACES
    ↓
APPLICATION
    ↓
DOMAIN

INFRASTRUCTURE
    ↓
DOMAIN / APPLICATION CONTRACTS

BOOTSTRAP
    ↓
COMPOSITION ROOT
```

## Current Architectural Focus

The architecture baseline is now sufficiently defined for initial
implementation.

Remaining work is implementation validation rather than conceptual stack
selection.

## Boundary Rule

Architecture documents explain **how the system is intended to be
built**.

They do not replace domain contracts or ADRs.
