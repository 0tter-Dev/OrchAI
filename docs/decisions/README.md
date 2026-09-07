# OrchAI --- Architecture Decision Records

## Purpose

Decision records document implementation choices that materially affect
the architecture.

They complement:

``` text
ARCHITECTURAL-CONTRACT
ARCHITECTURE
IMPLEMENTATION-MAP
DOMAIN DOCUMENTATION
```

## Decision Rules

Create an ADR when a choice:

-   constrains architecture;
-   affects replaceability;
-   introduces infrastructure dependency;
-   changes trust boundaries;
-   changes persistence or event behavior;
-   materially affects implementation strategy.

## Status Values

``` text
Proposed
Accepted
Superseded
Deprecated
```

Do not silently rewrite an accepted decision when the architectural
choice changes. Create a new ADR when a decision is superseded.

## Current Baseline

``` text
ADR-001  Initial Technology Stack
ADR-002  Initial Persistence Strategy
ADR-003  Initial Event Dispatch
ADR-004  API-First Interface Boundary
ADR-005  Local/Cloud Provider Boundary
ADR-006  Suggested Default Execution Mode
ADR-007  Modular Monolith Architecture
ADR-008  Async In-Process Execution Baseline
ADR-009  External Project Content Ownership
ADR-010  Project Readiness and Security Gates
ADR-011  Chat-First Request Interface
ADR-012  Authentication and Access Control for the CLI and API
ADR-013  LiteLLM Provider Adapter and Streaming Execution
ADR-014  Conversation and Message Domain Model
ADR-015  Module Concept (Forge, Studio, and Future Modules)
ADR-016  Single Local User Identity for OrchAI Desktop
ADR-017  Desktop Application Shell
```
