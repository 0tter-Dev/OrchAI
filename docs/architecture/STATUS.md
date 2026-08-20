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
  Project Security / Readiness Boundary          `IMPLEMENTED`
  Execution Mode Enforcement                     `IMPLEMENTED`
  API/UI Boundary                                `DECIDED`
  Configuration Architecture                     `DEFINED`
  Test Strategy                                  `DEFINED`
  Deployment Model                               `DEFINED`

## Implementation Validation

The following are intentionally pending until their implementation
exists:

-   performance and concurrency validation.

The following have initial implementation validation:

-   task, authorization, execution, context, and project-adapter
    boundaries;
-   central application Orchestrator composition for the initial flow;
-   initial policy boundary kept separate from authorization decisions;
-   async Execution Engine dispatch through a provider-independent
    `AIProviderPort`;
-   stub AI provider adapter and local Ollama adapter boundary;
-   provider-result contract validation and boundary-classified failure
    mapping;
-   filesystem Project Adapter discovery and authorized context reads;
-   protected Project Adapter operations for bounded writes,
    documentation writes, test runs, limited commands, and Git status;
-   persisted effective-vs-observed project readiness/security with
    runtime policy enforcement;
-   execution-mode enforcement where `MANUAL` follows explicit commands
    without proactive suggestions, `SUGGESTED` requires explicit
    approval, and `AUTOMATIC` remains bounded by configured policy;
-   context-resolution metadata persistence without copying project
    content;
-   durable in-process event dispatch with audit consumption;
-   idempotent metric derivation from authoritative execution events;
-   SQLAlchemy-backed SQLite and PostgreSQL migration execution for
    operational state, event history, audit records, and
    context-resolution metadata;
-   Typer CLI local orchestration, migration, event, audit, and project
    discovery/operation commands;
-   dependency-rule enforcement tests and runtime failure/recovery
    validation;
-   unit and integration tests for the implemented foundation.

## Current Phase

**Phase: Executable Operational Foundation v0.1.1**

The project has a consolidated architectural, domain, technology,
repository-structure, and decision-record foundation.

The implementation now includes the first executable operational slices,
durable history for events and audit records, resolved-context metadata,
a filesystem Project Adapter boundary with protected operations, runtime
readiness/security enforcement, and a replaceable AI provider boundary
for execution.

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
