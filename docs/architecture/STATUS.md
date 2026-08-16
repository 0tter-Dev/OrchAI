# OrchAI Architecture Status

## Purpose

This document tracks the state of the technical architecture and
distinguishes architectural decisions from implementation progress.

## Architecture Status

  Area                                           Status
  ---------------------------------------------- -----------
  High-Level Architecture                        `DEFINED`
  Component Boundaries                           `DEFINED`
  Modular Monolith Boundary                      `DECIDED`
  Domain/Application/Infrastructure Separation   `DECIDED`
  Physical Source Structure                      `DECIDED`
  Technology Stack                               `DECIDED`
  Persistence Strategy                           `DECIDED`
  Event Strategy                                 `DECIDED`
  Async Runtime Baseline                         `DECIDED`
  AI Provider Boundary                           `DECIDED`
  Project Adapter Boundary                       `DECIDED`
  Context Ownership Model                        `DECIDED`
  API/UI Boundary                                `DECIDED`
  Configuration Architecture                     `DEFINED`
  Test Strategy                                  `DEFINED`
  Deployment Model                               `DEFINED`

## Implementation Validation

The following are intentionally pending until their implementation
exists:

-   dependency-rule enforcement;
-   PostgreSQL migration validation;
-   provider adapter contract validation;
-   runtime failure/recovery validation;
-   performance and concurrency validation.

The following have initial implementation validation:

-   task, authorization, execution, context, and project-adapter
    boundaries;
-   in-process event dispatch;
-   SQLAlchemy-backed SQLite migration execution for the initial local
    schema;
-   Typer CLI local orchestration and migration commands;
-   unit and integration tests for the implemented foundation.

## Current Phase

**Phase: Executable Foundation In Progress**

The project has a consolidated architectural, domain, technology,
repository-structure, and decision-record foundation.

The implementation now includes the first executable slices and is moving
toward durable configuration and persistence.

## Status Rule

``` text
DECIDED
    ≠
IMPLEMENTED

DEFINED
    ≠
VALIDATED
```

A decision is an architectural commitment. It becomes
implementation-validated only after the corresponding code and tests
exist.
