# Project Adapter And Security

## Purpose

Defines the Project — an external development domain connected to
OrchAI through a Project Adapter — and the security, trust, and
readiness rules that govern what OrchAI may read, persist, share, or
modify about it.

## Objective

Let OrchAI connect to any project, including empty directories and
low-maturity legacy projects, while preventing unsafe, poorly
traceable, or conceptually invalid operations, and without ever
treating access to project information as ownership of it.

## Current Status

`implemented`

## Project Identity And Boundary

A project exposes stable identity, name, root location, adapter type,
configuration, capabilities, security profile, readiness level,
restricted areas, status, and supported workflows. It must not depend
on OrchAI internals:

```text
OrchAI Core
     ↓
Project Adapter Interface
     ↓
Project Adapter Implementation
     ↓
External Project
```

Project resources may include source code, documentation,
configuration, tests, a Git repository, build system, runtime
environment, and project metadata. Project state must not be confused
with task state: a project may contain many tasks with different
states while remaining operational, and project readiness state stays
distinct from task state. Project modifications should preserve
traceability across `PROJECT`, `TASK`, `EXECUTION`, `RESOURCE`,
`CHANGE`, and `VALIDATION`.

## Project Adapter (Component)

Provides the abstraction boundary between the Orchestrator and a
connected project. May expose capabilities such as file access,
documentation access, Git operations, test execution, build
operations, project-specific tools, and project configuration. Must
isolate project-specific implementation details and expose
standardized operations to the Orchestrator; must not contain global
Orchestrator workflow rules, redefine task semantics, or decide how
tasks should be executed.

The conceptual contract includes `discover`, `read`, `resolve_context`,
`write`, `run_tests`, `run_commands`, `git_status`, `validate`, and
`capabilities` — only supported capabilities should be exposed. The
current Project Adapter port validates the first concrete operational
subset: `capabilities()`, `discover(limit)`, `read_context(reference)`,
`resolve_context(references)`, `write(reference, content)`,
`write_documentation(reference, content)`, `run_tests(args)`,
`run_command(command)`, `git_status()`. The local filesystem adapter
discovers file resources as metadata, resolves authorized references
under the configured project root, runs protected operations behind
capabilities, and rejects path traversal outside that root. Discovery
and persisted context-resolution records do not copy complete project
files into OrchAI storage. Maps to `infrastructure/projects/`. Like the
AI Provider Adapter (see `Execution Engine`), a Project Adapter
preserves useful failure information while mapping provider-specific
failures into stable OrchAI error categories, and its types must never
leak into domain models.

## Project Manager (Component)

Manages projects known to the Orchestrator: register, configure,
select the active project, inspect capabilities, activate/deactivate
connections. Must not interpret project business rules, own project
source code, or replace the Project Adapter. Maps to
`application/projects/`.

## Capabilities Versus Authorization Versus Readiness

Projects may advertise `READ_PROJECT`, `READ_DOCUMENTATION`,
`WRITE_SOURCE`, `WRITE_DOCUMENTATION`, `RUN_TESTS`, `RUN_COMMANDS`,
`ACCESS_GIT` (see `Roles, Actions, And Models` for the shared
Capability concept). Capability availability is not authorization, and
it is also not readiness: a project may technically expose
`WRITE_SOURCE` and `ACCESS_GIT`, but OrchAI may still block code
change until the project is classified as ready for tracked
modification.

## Core Distinctions

The architecture distinguishes `CONNECTABLE ≠ READABLE ≠ MODIFIABLE ≠
AUTOMATABLE`, and `CAPABILITY ≠ ACCESS ≠ AUTHORIZATION ≠ READINESS`.

## Connectivity Rule

OrchAI may connect to an empty directory intended for a new project, a
project without Git, without documentation, without tests, or a
legacy project with low traceability. The lack of these elements must
not block connection itself — but these conditions may block specific
operations until the project reaches the required readiness level.

## Project Security Profile

Each connected project is governed by an explicit Project Security
Profile, defining at minimum `access_scope`, `persistence_scope`,
`provider_sharing_scope`, `change_scope`, `restricted_areas`, and
`readiness_level`. The current implementation persists both an
observed assessment derived from the adapter and an effective
persisted profile used as the runtime control source — this lets
OrchAI refresh what it can currently observe without silently
discarding operator-approved overrides.

## Project Readiness Levels

### LEVEL_0 — CONNECTABLE

Requirements: an accessible project root; the adapter can discover and
read allowed resources. Git, documentation, and tests are **not**
required.

Allowed: register project; discover resources; read authorized
resources; start a new project from an empty directory when explicitly
requested; produce suggestions; propose Git, documentation, tests, or
project structure.

Blocked by default: code modification; test workflow execution; CI/CD
setup; large architectural restructuring; Git-dependent operational
flows.

### LEVEL_1 — CHANGEABLE

Minimum requirement: Git initialized and operational.

Allowed with explicit authorization: modify source code; modify
project configuration; create or update basic documentation; perform
localized refactors.

Rule: `CODE CHANGE requires at least LEVEL_1`.

### LEVEL_2 — VALIDATABLE

Minimum requirements: Git initialized and operational; minimal
documentation exists, defining at least enough to identify the
project's objective, scope, relevant technical/business rules, and
known boundaries or constraints.

Allowed with explicit authorization: structure a test workflow; create
or update tests with traceable rationale; execute validation flows
with documented meaning; make architecture or quality recommendations
with supporting context.

Rule: `TEST / VALIDATION FLOW requires at least LEVEL_2`.

### LEVEL_3 — AUTOMATABLE

Minimum requirements: Git initialized and operational; minimal
documentation exists; tests exist or a documented testing strategy
exists; relevant project commands or workflows are identifiable.

Allowed with explicit authorization: define CI/CD workflows; define
validation pipelines; define branch policies; define automated quality
gates.

Rule: `CI/CD FLOW requires at least LEVEL_3`.

### Readiness Gates By Operation

```text
Connect project                          -> LEVEL_0
Read authorized project context          -> LEVEL_0
Change code                              -> LEVEL_1
Run or structure meaningful test flows   -> LEVEL_2
Create or change CI/CD                   -> LEVEL_3
```

## Persistence Policy

**Allowed by default:** project identity; adapter type; capabilities;
references to project resources; context-resolution metadata; hashes
and byte counts; execution and audit history; readiness level;
security profile metadata.

**Allowed only with explicit authorization:** persisted summaries of
project architecture, naming conventions, project workflows, or
functional structure; explicit reproducible context snapshots.

**Not persisted by default:** full source trees; full project
documentation; complete repository mirrors; secrets; credentials;
personal data; sensitive regulated content; raw proprietary project
dumps.

## Provider Sharing Policy

Project information is classified at least as `LOCAL_ONLY`,
`CLOUD_ALLOWED_WITH_AUTHORIZATION`, or `NEVER_EXTERNALIZED`. Personal
and sensitive data are restricted by default; proprietary project
information does not cross a cloud-provider boundary without explicit
authorization; provider sharing must respect both task authorization
and the project security profile; context that is readable is not
automatically shareable with a provider.

## Sensitive Operations

The following always require explicit authorization, even when the
minimum readiness level is satisfied: initialize Git; create or
formalize project documentation; restructure project architecture;
define or alter project conventions; create or alter Git workflow or
CI/CD; expand persistence scope; allow cloud-provider sharing for
restricted content; expand access to restricted project areas.

## LGPD And Confidentiality

OrchAI must not treat access to project information as ownership of
that information. The architecture explicitly supports data
minimization, purpose limitation, explicit authorization for sensitive
processing, traceability of what left the project boundary, and clear
separation between orchestration history and project-owned
intellectual property.

This document folds in the still-relevant decision from the former
ADR-010 (Project Readiness and Security Gates) — the LEVEL_0-3 model
above; full rationale remains in `docs/archive/decisions/`.

## Key Rules

- any project may be connected, even if not yet ready for tracked modification or automation
- connection does not imply modification rights
- code change requires Git readiness (LEVEL_1); test/validation flow requires Git plus minimum documentation (LEVEL_2); CI/CD requires Git, documentation, and tests or a documented testing strategy (LEVEL_3)
- capability availability is distinct from both authorization and readiness
- readability does not imply persistability or provider shareability
- project-owned content remains project-owned
- sensitive project operations remain explicitly authorized
- readiness gates must be auditable and enforceable
- project-specific rules stay outside the OrchAI core; project access occurs only through adapters

## Main Relationships

- gated by `Authorization Policy`'s operational-gate mechanism (readiness is necessary but not sufficient on its own)
- provides the capabilities consulted by `Roles, Actions, And Models`
- referenced descriptively (never as an access boundary) by `Identity And Access Management`'s `project_connections`
- exposed through `Chat-First And Interfaces` (`/projects`) and consumed by `Context Management` for context resolution
