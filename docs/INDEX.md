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
-   [`DEVELOPMENT-GUIDE.md`](DEVELOPMENT-GUIDE.md) --- Day-to-day
    engineering discipline: architectural rules, code quality, scope
    control, documentation/naming rules, testing and CI/CD direction,
    and the selected technology baseline.
-   [`IMPLEMENTATION-MAP.md`](IMPLEMENTATION-MAP.md) --- Roadmap from
    architecture to implementation.

### Context Documentation

`docs/context/` is the consolidation of the former `docs/architecture/`
and `docs/domains/` directories into one file per bounded concept (see
`docs/TO-DO.md`'s "Next Implementation Roadmap"):

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
-   [`context/observability.md`](context/observability.md) --- Audit,
    Metrics, and Suggestions.
-   [`context/configuration.md`](context/configuration.md) --- The
    layered configuration contract and current environment variables.
-   [`context/persistence.md`](context/persistence.md) --- What OrchAI
    persists, the repository boundary, and the relational model.
-   [`context/modules-and-domain-structure.md`](context/modules-and-domain-structure.md)
    --- Physical source-tree organization, domain purity, and the
    Module concept (Forge, Studio).
-   [`context/technology-and-test-strategy.md`](context/technology-and-test-strategy.md)
    --- The accepted technology baseline and testing layers.
-   [`context/deployment-and-desktop.md`](context/deployment-and-desktop.md)
    --- Headless and desktop deployment shapes.

### Archived Decisions

The ADR format is retired as the active decision-record mechanism.
Still-relevant decisions now live in
[`ARCHITECTURAL-CONTRACT.md`](ARCHITECTURAL-CONTRACT.md) §6
(cross-cutting) or the matching `docs/context/*.md` file's "Key Rules"
section (single-domain) above.

-   [`archive/decisions/INDEX.md`](archive/decisions/INDEX.md) --- All
    17 ADRs, preserved verbatim for historical record.

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
-   [`context/configuration.md`](context/configuration.md) --- Effective
    configuration model, precedence, and runtime surface.

## Documentation Layers

``` text
ARCHITECTURAL CONTRACT
        ↓
ARCHITECTURE
        ↓
CONTEXT DOCUMENTATION
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
