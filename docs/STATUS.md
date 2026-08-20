# OrchAI Project Status

## Purpose

This document provides the high-level state of the OrchAI project.

It is a project-state document, not a task backlog and not a replacement
for architectural documentation.

## Status Vocabulary

  -----------------------------------------------------------------------
  Status                              Meaning
  ----------------------------------- -----------------------------------
  `DEFINED`                           The concept is documented
                                      sufficiently for the current phase.

  `DECIDED`                           An architectural or implementation
                                      decision has been explicitly
                                      accepted.

  `PARTIAL`                           The area is defined or implemented
                                      only in part.

  `IN_PROGRESS`                       Active implementation or refinement
                                      is underway.

  `IMPLEMENTED`                       The current intended scope is
                                      implemented and validated.

  `BLOCKED`                           Progress depends on an unresolved
                                      external or architectural issue.

  `PENDING`                           Intentionally deferred to a later
                                      phase.
  -----------------------------------------------------------------------

## Current State

Current version: `v0.1.1`

  Area                                 Status
  ------------------------------------ -----------
  Architectural Contract               `DEFINED`
  High-Level Architecture              `DEFINED`
  Component Boundaries                 `DEFINED`
  Implementation Map                   `DEFINED`
  Core Domain Model                    `DEFINED`
  Authorization                        `DEFINED`
  Task Lifecycle                       `DEFINED`
  Execution Model                      `DEFINED`
  Event Model                          `DEFINED`
  Roles and Actions                    `DEFINED`
  Models and Providers                 `DEFINED`
  Context Management                   `DEFINED`
  Project Integration                  `DEFINED`
  Capabilities                         `DEFINED`
  Audit and Metrics                    `DEFINED`
  Suggestions                          `DEFINED`
  Configuration                        `DEFINED`
  Modular Monolith Structure           `DECIDED`
  Physical Repository Structure        `DECIDED`
  Technology Stack                     `DECIDED`
  Persistence Strategy                 `DECIDED`
  Event Dispatch Strategy              `DECIDED`
  Async Execution Baseline             `DECIDED`
  AI Provider Boundary                 `DECIDED`
  Project Content Ownership Boundary   `DECIDED`
  Project Security / Readiness Gates   `IMPLEMENTED`
  API/UI Boundary                      `DECIDED`
  Execution Mode Baseline              `IMPLEMENTED`
  Application Implementation           `IN_PROGRESS`
  Domain Implementation                `IN_PROGRESS`
  Infrastructure Implementation        `IN_PROGRESS`
  API Implementation                   `PENDING`
  CLI Implementation                   `IN_PROGRESS`
  Automated Test Suite                 `IN_PROGRESS`
  Deployment Implementation            `PENDING`

## Current Phase

**Phase: Executable Operational Foundation v0.1.1**

The project has a consolidated architecture and domain foundation, an
accepted technology baseline, a defined physical code structure, and
ADRs for the major implementation decisions.

The implementation now has an executable operational foundation covering
task lifecycle, authorization, execution, context resolution, project
adapter boundaries, a central application Orchestrator for local flows
and protected project operations, an async Execution Engine with a
replaceable AI Provider Adapter boundary, filesystem Project Adapter
discovery and protected operations, context-resolution metadata,
event-derived audit and metrics records, state-aware suggestions,
execution-mode enforcement for `MANUAL`, `SUGGESTED`, and `AUTOMATIC`,
an initial policy slice kept separate from authorization, persisted
effective-vs-observed project
readiness/security, and SQLAlchemy-backed durable persistence for the
initial operational and historical aggregates.

The next implementation focus is orchestration expansion and interface
growth: richer policy configuration, additional provider
implementations, broader project-adapter operations, deeper
state-driven orchestration beyond the current demo flow, and a public
API surface.

## Source of Truth

This document tracks project state.

It does not redefine architectural rules.

For architectural rules, consult:

-   `ARCHITETURAL-CONTRACT.md`
-   `ARCHITECTURE.md`
-   `COMPONENTS.md`
-   relevant domain documentation
-   relevant ADRs
-   `IMPLEMENTATION-MAP.md`

## Important Distinction

``` text
DEFINED
    ≠
IMPLEMENTED

DECIDED
    ≠
IMPLEMENTED

DOCUMENTED
    ≠
VALIDATED
```
