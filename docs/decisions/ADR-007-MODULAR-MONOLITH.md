# ADR-007 --- Modular Monolith Architecture

## Status

Accepted

## Context

OrchAI contains multiple strongly related domains and infrastructure
integrations but does not initially require independent deployment,
independent scaling, or distributed service ownership.

Premature service decomposition would increase operational and
consistency complexity before the core workflow is validated.

## Decision

Implement OrchAI as a modular monolith using Clean Architecture and
Hexagonal Architecture principles.

The physical structure is:

``` text
src/orchai/
├── domain/
├── application/
├── infrastructure/
├── interfaces/
└── bootstrap/
```

Logical modules remain independently bounded inside one deployable
application.

## Rationale

This provides:

-   strong internal boundaries;
-   low operational complexity;
-   straightforward local development;
-   simple transactions across related domains;
-   clear future extraction points if a component eventually requires
    independent deployment.

## Consequences

Positive:

-   one deployable unit;
-   no distributed transaction requirements;
-   easy debugging and testing;
-   domain boundaries remain explicit.

Trade-offs:

-   modules share one runtime;
-   future service extraction requires preserving the existing
    contracts;
-   horizontal scaling is initially application-level rather than
    per-module.

## Invariant

A logical module must not bypass another module's domain or application
contract merely because all modules currently share one process.
