# OrchAI --- Configuration Architecture

## Purpose

Defines how configuration is loaded, validated, merged, and exposed.

## Flow

``` text
Environment / Files / CLI
          ↓
Configuration Loader
          ↓
Validation
          ↓
Normalized Configuration
          ↓
Application Bootstrap
```

## Layering

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

Each layer has explicit override rules.

## Format

The initial implementation should support a human-readable structured
configuration format, with environment variables for deployment-specific
overrides and secrets.

The serialization format remains behind the configuration boundary.

## Validation

Validation should report property, expected form, received form where
safe, source, and remediation guidance.

## Secrets

Secrets are provided through environment variables or a future secret
manager.

They must not be serialized into ordinary task or audit records.

## Effective Configuration

The application should expose normalized effective configuration to
internal services instead of repeatedly resolving raw layers.

## Current Implementation

The current implementation includes a minimal Pydantic-backed
configuration loader for database settings.

``` text
ORCHAI_DATABASE_URL
```

The loader reads `ORCHAI_DATABASE_URL` from the process environment and
then from a local `.env` file when the process environment does not
define it. Process environment values take precedence over `.env`
values. When neither is provided, the default local value is:

``` text
sqlite:///.orchai/orchai.db
```

The loader validates SQLite and PostgreSQL database URLs and normalizes
plain PostgreSQL URLs to the SQLAlchemy `postgresql+psycopg` driver form.

This is sufficient for the current SQLAlchemy persistence foundation.
The configuration layer still needs expanded layered overrides, safe
inspection, and future secret-management integration.

## Invariants

1.  Configuration resolution is deterministic.
2.  Secrets remain outside normal persisted configuration.
3.  Invalid configuration fails clearly.
4.  Effective configuration can be inspected safely.
