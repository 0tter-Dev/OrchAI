# OrchAI --- Configuration Domain

## Purpose

Configuration defines OrchAI behavior and boundaries without embedding
environment-specific values in domain logic.

## Layers

``` text
GLOBAL
   ↓
ORCHAI
   ↓
PROJECT
   ↓
TASK
   ↓
EXECUTION
```

The effective value must be deterministic and observable.

## Categories

``` text
Runtime
Persistence
Events
Authorization
Execution Modes
Models
Providers
Projects
Adapters
Logging
Metrics
Security
User Interface
```

## Overrides

Lower-level configuration may override higher-level defaults only where
the property explicitly permits overriding.

Implicit precedence must be avoided.

## Secrets

Secrets must not be stored directly in ordinary configuration documents.

Configuration should reference environment or secret-management
mechanisms.

## Validation

Configuration must be validated before normal operation.

Invalid configuration should fail clearly rather than silently falling
back to unsafe behavior.

## Invariants

1.  Effective configuration is deterministic.
2.  Configuration precedence is explicit.
3.  Secrets remain outside source-controlled configuration.
4.  Invalid configuration fails predictably.
5.  Configuration does not silently expand authorization.
