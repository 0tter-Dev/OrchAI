# OrchAI --- Architecture Decision Records

## Purpose

Decision records document implementation choices that materially affect
the architecture.

They complement:

``` text
ARCHITETURAL-CONTRACT
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
```
