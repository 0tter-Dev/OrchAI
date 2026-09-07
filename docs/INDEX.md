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
-   [`architecture/STATUS.md`](architecture/STATUS.md) --- Current
    architecture-definition status.
-   [`architecture/PROJECT-SECURITY-AND-READINESS.md`](architecture/PROJECT-SECURITY-AND-READINESS.md)
    --- Security, trust, and readiness rules for connected projects.

### Domains

-   [`domains/INDEX.md`](domains/INDEX.md) --- Domain documentation
    navigation.
-   [`domains/STATUS.md`](domains/STATUS.md) --- Current
    domain-definition and implementation status.

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
-   [`domains/AUTHORIZATION.md`](domains/AUTHORIZATION.md) --- Detailed
    explanation of policy, authorization, and execution boundaries.
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

The root [`STATUS.md`](STATUS.md) describes the overall project state.

Section-specific status documents describe only their own scope.
