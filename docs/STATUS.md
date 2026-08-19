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
  API/UI Boundary                      `DECIDED`
  Execution Mode Baseline              `DECIDED`
  Application Implementation           `PARTIAL`
  Domain Implementation                `PARTIAL`
  Infrastructure Implementation        `PARTIAL`
  API Implementation                   `PENDING`
  CLI Implementation                   `PARTIAL`
  Automated Test Suite                 `PARTIAL`
  Deployment Implementation            `PENDING`

## Current Phase

**Phase: Executable Foundation In Progress**

The project has a consolidated architecture and domain foundation, an
accepted technology baseline, a defined physical code structure, and
ADRs for the major implementation decisions.

The implementation now has a minimal executable foundation covering task
lifecycle, authorization, execution, context resolution, project adapter
boundaries, a central application Orchestrator for the initial local
flow, an async Execution Engine with a replaceable AI Provider Adapter
boundary, filesystem Project Adapter discovery, context-resolution
metadata, event-derived audit and metrics records, task-state
suggestions with initial execution-mode enforcement, an initial policy
slice kept separate from authorization, and
SQLAlchemy-backed durable persistence for the initial operational and
historical aggregates.

The next implementation focus is orchestration expansion and interface
growth: richer policy configuration, provider configuration,
provider-specific validation, and public API surface.

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
