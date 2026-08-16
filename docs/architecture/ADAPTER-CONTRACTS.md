# OrchAI --- Adapter Contracts

## Purpose

Adapters isolate OrchAI core behavior from external systems.

Primary families:

``` text
AI PROVIDER ADAPTER
PROJECT ADAPTER
```

## AI Provider Adapter

The conceptual contract is:

``` text
prepare()
validate()
execute()
cancel()
capabilities()
```

The exact interface may evolve.

## AI Execution Input

An adapter receives a bounded execution request containing:

``` text
Task
Role
Action
Model
Authorized Context
Execution Configuration
Applicable Capabilities
```

It must not receive unrestricted project access.

## AI Execution Result

The adapter should return:

``` text
Outcome
Provider Metadata
Model Metadata
Output
Warnings
Errors
Resource Usage
Artifacts
```

## Project Adapter

The conceptual contract includes:

``` text
discover
read
resolve_context
write
run_tests
run_commands
git_status
validate
capabilities
```

Only supported capabilities should be exposed.

## Capability Negotiation

``` text
Required Capability
        ↓
Adapter Capabilities
        ↓
Authorization
```

## Isolation

Provider-specific and project-specific types must not leak into domain
models.

## Failure Mapping

Adapters preserve useful failure information while mapping
provider-specific failures into stable OrchAI error categories.

## Invariants

1.  Adapters isolate external dependencies.
2.  Core code depends on contracts, not providers.
3.  Capabilities are explicit.
4.  External failures remain distinguishable.
5.  Adapters do not silently expand execution scope.
