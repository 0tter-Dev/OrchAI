# OrchAI --- Capabilities Domain

## Purpose

A `CAPABILITY` represents an operation that a component, role, model, or
adapter can technically perform.

Capabilities describe possibility, not permission.

## Initial Capability Set

``` text
READ_PROJECT
READ_DOCUMENTATION
WRITE_SOURCE
WRITE_DOCUMENTATION
RUN_TESTS
RUN_COMMANDS
USE_LOCAL_MODEL
USE_CLOUD_MODEL
ACCESS_GIT
```

## Capability vs Authorization

``` text
CAPABILITY = CAN PERFORM
AUTHORIZATION = MAY PERFORM
```

Technical support for an operation never grants permission to perform
it.

## Providers

Capabilities may be provided by:

``` text
Project Adapter
AI Provider Adapter
Execution Environment
Role Configuration
Infrastructure
```

## Evaluation

``` text
Required Capability
        ↓
Available Capability
        ↓
Authorization Policy
        ↓
Allowed Operation
```

## Scope

Capabilities may be scoped by project, task, role, action, environment,
resource, or execution mode.

## Invariants

1.  Capability availability never grants authorization.
2.  Capabilities remain explicit.
3.  Missing capabilities produce a distinct failure condition.
4.  Protected operations perform capability checks before execution.
