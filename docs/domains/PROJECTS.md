# OrchAI --- Projects Domain

## Purpose

A `PROJECT` represents an external development domain connected to
OrchAI through a Project Adapter.

OrchAI coordinates projects but does not own their internal business
logic.

## Identity

A project should expose:

-   stable identity;
-   name;
-   root location;
-   adapter type;
-   configuration;
-   capabilities;
-   security profile;
-   readiness level;
-   restricted areas;
-   status;
-   supported workflows.

## Boundary

``` text
OrchAI Core
     ↓
Project Adapter Interface
     ↓
Project Adapter Implementation
     ↓
External Project
```

The project must not depend on OrchAI internals.

## Resources

``` text
Source Code
Documentation
Configuration
Tests
Git Repository
Build System
Runtime Environment
Project Metadata
```

## Capabilities

Projects may advertise:

``` text
READ_PROJECT
READ_DOCUMENTATION
WRITE_SOURCE
WRITE_DOCUMENTATION
RUN_TESTS
RUN_COMMANDS
ACCESS_GIT
```

Capability availability is not authorization.

Capability availability is also not readiness.

For example, a project may technically expose `WRITE_SOURCE` and
`ACCESS_GIT`, but OrchAI may still block code change until the project
is classified as ready for tracked modification.

## Security Profile

A project should define, explicitly or implicitly through configuration,
its security profile:

-   what OrchAI may access;
-   what OrchAI may persist;
-   what OrchAI may share with providers;
-   which areas are restricted;
-   which operations require explicit authorization;
-   which operations require a minimum readiness level.

## Readiness Level

Projects may be connected at different readiness levels.

Representative levels include:

``` text
LEVEL_0  CONNECTABLE
LEVEL_1  CHANGEABLE
LEVEL_2  VALIDATABLE
LEVEL_3  AUTOMATABLE
```

Examples:

-   project connection may be allowed at `LEVEL_0`;
-   code change may require `LEVEL_1`;
-   test and validation flow may require `LEVEL_2`;
-   CI/CD flow may require `LEVEL_3`.

Projects without Git, documentation, or tests remain connectable, but
those missing prerequisites may block higher-impact operations.

## State

Project state must not be confused with task state.

A project may contain many tasks with different states while remaining
operational.

Project readiness state must also remain distinct from task state.

## Traceability

Project modifications should preserve:

``` text
PROJECT
TASK
EXECUTION
RESOURCE
CHANGE
VALIDATION
```

## Invariants

1.  Projects remain external domains.
2.  Project-specific rules stay outside OrchAI core.
3.  Project access occurs through adapters.
4.  Capability availability is distinct from authorization.
5.  Capability availability is distinct from readiness.
6.  Project changes remain traceable to executions where possible.
7.  Any project may be connected, even if it is not yet ready for
    tracked modification or automation.
