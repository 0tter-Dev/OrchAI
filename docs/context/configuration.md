# Configuration

## Purpose

Defines how OrchAI behavior and boundaries are configured — layered,
deterministic, and observable — without embedding environment-specific
values in domain logic.

## Objective

Make the effective configuration for any given layer (global, OrchAI,
project, task, execution) always deterministic and inspectable, with
secrets kept out of ordinary configuration and invalid configuration
failing loudly rather than falling back to unsafe behavior.

## Current Status

`implemented`

## Layers And Categories

Configuration flows `GLOBAL → ORCHAI → PROJECT → TASK → EXECUTION`; a
lower layer may override a higher one only where the property
explicitly permits it — implicit precedence is avoided. Categories
include Runtime, Persistence, Events, Authorization, Execution Modes,
Models, Providers, Projects, Adapters, Logging, Metrics, Security, and
User Interface.

## Loading And Validation

```
Environment / Files / CLI → Configuration Loader → Validation →
    Normalized Configuration → Application Bootstrap
```

Validation reports property, expected form, received form (where
safe), source, and remediation guidance. The application exposes
normalized effective configuration to internal services instead of
repeatedly resolving raw layers. Secrets are provided through
environment variables (or a future secret manager) and must never be
serialized into ordinary task, audit, or configuration records.

## Current Implementation

A Pydantic-backed loader resolves database, AI provider, and API
settings:

```text
ORCHAI_DATABASE_URL
ORCHAI_AI_PROVIDER          ("stub" or "litellm", see ADR-013)
ORCHAI_AI_MODEL             ("<provider>/<model>", e.g. "ollama/qwen2.5-coder:latest")
ORCHAI_AI_BASE_URL
ORCHAI_AI_API_KEY
ORCHAI_AI_ORGANIZATION
ORCHAI_AI_PROJECT
ORCHAI_AI_TIMEOUT_SECONDS
ORCHAI_API_HOST
ORCHAI_API_PORT
ORCHAI_AUTH_ENFORCED        (default false, see Identity And Access)
```

`ORCHAI_DATABASE_URL` is read from the process environment, then a
local `.env` file, then falls back to `sqlite:///.orchai/orchai.db`;
process environment values always take precedence over `.env`. The
loader validates SQLite/PostgreSQL URLs and normalizes plain
PostgreSQL URLs to the SQLAlchemy `postgresql+psycopg` driver form.
The runtime can inspect effective configuration safely through the CLI
and API (`GET /settings/runtime`) without exposing provider secrets
directly.

## Key Rules

- effective configuration is deterministic and its precedence is explicit
- secrets remain outside source-controlled and persisted configuration
- invalid configuration fails clearly, never silently falling back to unsafe behavior
- configuration never silently expands authorization
- effective configuration can always be inspected safely

## Main Relationships

- read by every component at bootstrap (`bootstrap/runtime.py`)
- selects the active AI Provider Adapter (see `Execution Engine`) and database backend (see `Persistence`)
- inspectable through `Chat-First And Interfaces` (`GET /settings/runtime`, `GET /providers/settings`)
