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

The current implementation validates the first concrete operational
application port:

``` text
AIProviderPort.capabilities()
AIProviderPort.validate_request(AIProviderExecutionRequest)
AIProviderPort.execute(AIProviderExecutionRequest)
    -> AIProviderExecutionResult
AIProviderPort.cancel(execution_id)
```

The request contains execution identity, task identity, role, action,
model, project reference, and only the resolved authorized context
items. Provider-specific SDK or HTTP types remain in infrastructure
adapters.

The `prepare` operation remains a conceptual future extension. Request
validation, cancellation surface, and provider capabilities are already
formalized in the application port.

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

The current Project Adapter port validates the first concrete
operational subset:

``` text
capabilities()
discover(limit)
read_context(reference)
resolve_context(references)
write(reference, content)
write_documentation(reference, content)
run_tests(args)
run_command(command)
git_status()
```

The local filesystem adapter discovers file resources as metadata,
resolves authorized references under the configured project root, runs
protected operations behind capabilities, and rejects path traversal
outside that root. Discovery and persisted context-resolution records do
not copy complete project files into OrchAI storage.

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
