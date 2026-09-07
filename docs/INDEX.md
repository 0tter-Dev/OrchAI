# OrchAI Documentation Index

## Purpose

This document is the top-level navigation map for the OrchAI
documentation.

It does not replace the documents it references. Its purpose is to
provide a stable entry point for humans and AI agents.

## Documentation Map

### Architectural Foundation

-   [`VISION.md`](VISION.md) --- Product-level narrative: what OrchAI is
    for, the desktop client, and the general layer / Module structure
    (Forge, Studio).
-   [`ARCHITECTURAL-CONTRACT.md`](ARCHITECTURAL-CONTRACT.md) ---
    Architectural invariants and non-negotiable principles.
-   [`ARCHITECTURE.md`](ARCHITECTURE.md) --- High-level system
    architecture and relationships.
-   [`architecture/COMPONENTS.md`](architecture/COMPONENTS.md) --- Major
    component responsibilities and boundaries.
-   [`IMPLEMENTATION-MAP.md`](IMPLEMENTATION-MAP.md) --- Roadmap from
    architecture to implementation.

### Architecture Implementation

-   [`architecture/INDEX.md`](architecture/INDEX.md) --- Architecture
    documentation navigation.

### Domains

-   [`domains/INDEX.md`](domains/INDEX.md) --- Domain documentation
    navigation.

### Context Documentation (in progress)

`docs/context/` is the target consolidation of `docs/architecture/`
and `docs/domains/` into one file per bounded concept (see
`docs/TO-DO.md`'s "Next Implementation Roadmap"). So far:

-   [`context/tasks-and-lifecycle.md`](context/tasks-and-lifecycle.md)
    --- Task identity, scope, lifecycle, and the state machine.
-   [`context/execution-engine.md`](context/execution-engine.md) ---
    Execution construction, results, and the AI Provider Adapter
    boundary.
-   [`context/roles-actions-models.md`](context/roles-actions-models.md)
    --- Roles, Actions, Models, and Capabilities.
-   [`context/events-and-state.md`](context/events-and-state.md) ---
    Event contract, dispatch strategy, and the State Machine
    relationship.
-   [`context/authorization-policy.md`](context/authorization-policy.md)
    --- Authorization concepts and the MANUAL/SUGGESTED/AUTOMATIC
    execution modes.
-   [`context/identity-and-access.md`](context/identity-and-access.md)
    --- Users, access roles, permissions, and JWT authentication.
-   [`context/project-adapter-and-security.md`](context/project-adapter-and-security.md)
    --- Project Adapter boundary, security profile, and the LEVEL_0-3
    readiness gates.
-   [`context/context-management.md`](context/context-management.md)
    --- Context lifecycle and authorization for AI execution.
-   [`context/chat-first-and-interfaces.md`](context/chat-first-and-interfaces.md)
    --- The `/requests` chat-first projection and the CLI/API/UI
    boundary.

### Architecture Decisions

-   [`decisions/INDEX.md`](decisions/INDEX.md) --- Architecture Decision
    Record navigation.

### Repository Guidance

-   [`../AGENTS.md`](../AGENTS.md) --- Rules and constraints for human
    and AI contributors.
-   [`../CONTRIBUTING.md`](../CONTRIBUTING.md) --- Practical branch,
    validation, and pull request baseline for contributors.
-   [`USER-ONBOARDING.md`](USER-ONBOARDING.md) --- Product-oriented
    onboarding guide for users adopting OrchAI in real projects.
-   [`USER-OPERATIONS-GUIDE.md`](USER-OPERATIONS-GUIDE.md) --- Detailed
    operational guide for configuration, policies, providers, runtime
    posture, and real-project usage.
-   [`engineering/DELIVERY-BASELINE.md`](engineering/DELIVERY-BASELINE.md)
    --- Initial Git/GitHub/CI baseline for safe incremental delivery.
-   [`context/authorization-policy.md`](context/authorization-policy.md)
    --- Detailed explanation of policy, authorization, and execution
    boundaries.
-   [`architecture/CONFIGURATION-ARCHITECTURE.md`](architecture/CONFIGURATION-ARCHITECTURE.md)
    --- Effective configuration model, precedence, and runtime surface.

## Documentation Layers

``` text
ARCHITECTURAL CONTRACT
        ↓
ARCHITECTURE
        ↓
COMPONENTS
        ↓
DOMAINS
        ↓
ARCHITECTURE IMPLEMENTATION
        ↓
DECISIONS
        ↓
IMPLEMENTATION MAP
        ↓
CODE
```

## Navigation Rule

When investigating a topic:

1.  Start here to locate the authoritative document.
2.  Follow the most specific document available.
3.  Do not duplicate authoritative information in an index.
4.  If implementation and documentation disagree, consult `STATUS.md`
    and the relevant architectural contract before changing either.

## Status Authority

The root [`STATUS.md`](STATUS.md) is the single, sole status document
for the project — it describes overall project state as a pure
snapshot. No other document tracks status; there is nothing left to
diverge from it.

For how the project reached its current state, see
[`HISTORY.md`](HISTORY.md), a one-time, frozen archive that is never
extended. Going forward, what changed release-over-release is covered
by generated release notes (`scripts/release.py`), not a document like
this one.
