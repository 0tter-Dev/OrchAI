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

## State

Project state must not be confused with task state.

A project may contain many tasks with different states while remaining
operational.

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
5.  Project changes remain traceable to executions where possible.
