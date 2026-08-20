# OrchAI Documentation Index

## Purpose

This document is the top-level navigation map for the OrchAI
documentation.

It does not replace the documents it references. Its purpose is to
provide a stable entry point for humans and AI agents.

## Documentation Map

### Architectural Foundation

-   [`ARCHITETURAL-CONTRACT.md`](ARCHITETURAL-CONTRACT.md) ---
    Architectural invariants and non-negotiable principles.
-   [`ARCHITECTURE.md`](ARCHITECTURE.md) --- High-level system
    architecture and relationships.
-   [`COMPONENTS.md`](COMPONENTS.md) --- Major component
    responsibilities and boundaries.
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
