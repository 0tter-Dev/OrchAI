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

Event dispatch/messaging strategy, the AI and Project Adapter
contracts, project security/readiness, the API/UI boundary, the
chat-first request model, and identity/access have all moved to
`docs/context/` as part of the OrchFlow-inspired documentation
consolidation (see `docs/TO-DO.md`):
[`../context/events-and-state.md`](../context/events-and-state.md),
[`../context/execution-engine.md`](../context/execution-engine.md)
(AI Provider Adapter),
[`../context/project-adapter-and-security.md`](../context/project-adapter-and-security.md),
[`../context/chat-first-and-interfaces.md`](../context/chat-first-and-interfaces.md),
and
[`../context/identity-and-access.md`](../context/identity-and-access.md).

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
