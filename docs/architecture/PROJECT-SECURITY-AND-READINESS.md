# OrchAI --- Project Security and Readiness

## Purpose

This document defines the explicit security, trust, and operational
readiness rules for projects connected to OrchAI.

It clarifies:

- what OrchAI may connect to;
- what OrchAI may read;
- what OrchAI may persist;
- what OrchAI may send to AI providers;
- what OrchAI may modify;
- which operations require a minimum project readiness level.

The goal is to allow OrchAI to connect to any project, including empty
directories and low-maturity legacy projects, while preventing unsafe,
poorly traceable, or conceptually invalid operations.

## Core Distinctions

The architecture must distinguish:

``` text
CONNECTABLE
    ≠
READABLE
    ≠
MODIFIABLE
    ≠
AUTOMATABLE
```

It must also distinguish:

``` text
CAPABILITY
    ≠
ACCESS
    ≠
AUTHORIZATION
    ≠
READINESS
```

## Connectivity Rule

OrchAI may connect to:

- an empty directory intended for a new project;
- a project without Git;
- a project without documentation;
- a project without tests;
- a legacy project with low traceability.

The lack of these elements must not block connection itself.

However, these conditions may block specific operations until the
project reaches the required readiness level.

## Project Security Profile

Each connected project should be governed by an explicit
`Project Security Profile`.

At minimum, the profile should define:

- `access_scope`
- `persistence_scope`
- `provider_sharing_scope`
- `change_scope`
- `restricted_areas`
- `readiness_level`

The current implementation persists both:

- an observed assessment derived from the adapter;
- an effective persisted profile used as the runtime control source.

This allows OrchAI to refresh what it can currently observe about the
project without silently discarding operator-approved overrides.

## Project Readiness Levels

### LEVEL_0 --- CONNECTABLE

Requirements:

- accessible project root;
- adapter can discover and read allowed resources.

Git, documentation, and tests are not required.

Allowed operations:

- register project;
- discover resources;
- read authorized resources;
- start a new project from an empty directory when explicitly requested;
- produce suggestions;
- propose Git, documentation, tests, or project structure.

Blocked by default:

- code modification;
- test workflow execution;
- CI/CD setup;
- large architectural restructuring;
- Git-dependent operational flows.

### LEVEL_1 --- CHANGEABLE

Minimum requirement:

- Git initialized and operational for the project.

Allowed operations with explicit authorization:

- modify source code;
- modify project configuration;
- create or update basic documentation;
- perform localized refactors.

Rule:

``` text
CODE CHANGE
    requires at least
LEVEL_1
```

### LEVEL_2 --- VALIDATABLE

Minimum requirements:

- Git initialized and operational;
- minimal documentation exists;
- the documentation defines at least enough to identify:
  - project objective;
  - scope;
  - relevant technical or business rules;
  - known boundaries or constraints.

Allowed operations with explicit authorization:

- structure a test workflow;
- create or update tests with traceable rationale;
- execute validation flows with documented meaning;
- make architecture or quality recommendations with supporting context.

Rule:

``` text
TEST / VALIDATION FLOW
    requires at least
LEVEL_2
```

### LEVEL_3 --- AUTOMATABLE

Minimum requirements:

- Git initialized and operational;
- minimal documentation exists;
- tests exist or a documented testing strategy exists;
- relevant project commands or workflows are identifiable.

Allowed operations with explicit authorization:

- define CI/CD workflows;
- define validation pipelines;
- define branch policies;
- define automated quality gates.

Rule:

``` text
CI/CD FLOW
    requires at least
LEVEL_3
```

## Readiness Gates by Operation

``` text
Connect project
    -> LEVEL_0

Read authorized project context
    -> LEVEL_0

Change code
    -> LEVEL_1

Run or structure meaningful test flows
    -> LEVEL_2

Create or change CI/CD
    -> LEVEL_3
```

## Persistence Policy

### Allowed by Default

- project identity;
- adapter type;
- capabilities;
- references to project resources;
- context-resolution metadata;
- hashes and byte counts;
- execution and audit history;
- readiness level;
- security profile metadata.

### Allowed Only with Explicit Authorization

- persisted summaries of project architecture;
- persisted summaries of naming conventions;
- persisted summaries of project workflows;
- persisted summaries of functional structure;
- explicit reproducible context snapshots.

### Not Persisted by Default

- full source trees;
- full project documentation;
- complete repository mirrors;
- secrets;
- credentials;
- personal data;
- sensitive regulated content;
- raw proprietary project dumps.

## Provider Sharing Policy

Project information should be classified at least as:

- `LOCAL_ONLY`
- `CLOUD_ALLOWED_WITH_AUTHORIZATION`
- `NEVER_EXTERNALIZED`

Rules:

- personal data and sensitive data are restricted by default;
- proprietary project information does not cross a cloud-provider
  boundary without explicit authorization;
- provider sharing must respect both task authorization and project
  security profile;
- context that is readable is not automatically shareable with a
  provider.

## Sensitive Operations

The following operations always require explicit authorization, even
when the minimum readiness level is satisfied:

- initialize Git;
- create or formalize project documentation;
- restructure project architecture;
- define or alter project conventions;
- create or alter Git workflow;
- create or alter CI/CD;
- expand persistence scope;
- allow cloud-provider sharing for restricted content;
- expand access to restricted project areas.

## LGPD and Confidentiality

OrchAI must not treat access to project information as ownership of that
information.

The architecture must explicitly support:

- data minimization;
- purpose limitation;
- explicit authorization for sensitive processing;
- traceability of what left the project boundary;
- clear separation between orchestration history and project-owned
  intellectual property.

## Invariants

1.  Any project may be connected.
2.  Connection does not imply modification rights.
3.  Code change requires Git readiness.
4.  Test workflow requires Git and minimum documentation.
5.  CI/CD requires Git, documentation, and tests or documented testing
    strategy.
6.  Readability does not imply persistability.
7.  Readability does not imply provider shareability.
8.  Project-owned content remains project-owned.
9.  Sensitive project operations remain explicitly authorized.
10. Readiness gates must be auditable and enforceable.
