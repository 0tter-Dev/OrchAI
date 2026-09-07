# OrchAI User Operations Guide

## Purpose

This guide is the operational reference for teams using OrchAI in real
projects.

Use it after reading [`USER-ONBOARDING.md`](USER-ONBOARDING.md).

The onboarding guide explains how to get started quickly.

This guide explains how to operate OrchAI safely, how to configure it,
how to interpret its boundaries, and how to troubleshoot common usage
patterns.

## Recommended operating posture

The recommended posture today is:

```text
API-first
PostgreSQL as primary persistence
SQLite only for local tests and local smoke flows
Explicit provider configuration
Explicit project registration
Explicit policy/authorization visibility
```

That means:

- external clients should prefer the HTTP API as the main integration surface;
- PostgreSQL should be treated as the shared or central operational database;
- SQLite should be treated as a local-only option;
- provider selection should be explicit;
- project readiness and project security should be inspected before high-impact operations.

## Configuration reference

The current runtime configuration is environment-first with optional
local `.env` fallback.

Supported variables:

```text
ORCHAI_DATABASE_URL
ORCHAI_AI_PROVIDER
ORCHAI_AI_BASE_URL
ORCHAI_AI_API_KEY
ORCHAI_AI_ORGANIZATION
ORCHAI_AI_PROJECT
ORCHAI_AI_MODEL
ORCHAI_AI_TIMEOUT_SECONDS
ORCHAI_API_HOST
ORCHAI_API_PORT
```

### Database

Recommended shared setup:

```powershell
$env:ORCHAI_DATABASE_URL = "postgresql://orchai:password@localhost:5432/orchai"
uv run orchai db sync
uv run orchai runtime check
```

Local-only setup:

```powershell
$env:ORCHAI_DATABASE_URL = "sqlite:///.orchai/orchai.db"
uv run orchai db sync
uv run orchai runtime check
```

Interpretation:

- `operational_mode=shared-ready` means database and provider are reachable and the runtime is suitable for shared operation;
- `operational_mode=shared-degraded` means PostgreSQL is intended but some operational dependency is unhealthy;
- `operational_mode=local-only` means the runtime is valid for local usage, but not in the recommended shared posture.

### AI provider

Since ADR-013, the single `litellm` provider covers every real backend
(OpenAI, Anthropic, Gemini, Ollama, and other OpenAI-compatible local
runtimes) -- which one is actually used is selected by
`ORCHAI_AI_MODEL`'s `"<provider>/<model>"` prefix, not by
`ORCHAI_AI_PROVIDER` itself.

Local stub:

```powershell
$env:ORCHAI_AI_PROVIDER = "stub"
```

Local Ollama model:

```powershell
$env:ORCHAI_AI_PROVIDER = "litellm"
$env:ORCHAI_AI_BASE_URL = "http://localhost:11434"
$env:ORCHAI_AI_MODEL = "ollama/qwen2.5-coder:latest"
```

Cloud model, e.g. OpenAI:

```powershell
$env:ORCHAI_AI_PROVIDER = "litellm"
$env:ORCHAI_AI_API_KEY = "your_api_key"
$env:ORCHAI_AI_MODEL = "openai/gpt-5"
```

Operational checks:

```powershell
uv run orchai providers show
uv run orchai providers capabilities
uv run orchai providers health
uv run orchai runtime check
```

Related API endpoints:

- `GET /`
- `GET /settings/runtime`
- `GET /providers/settings`
- `GET /runtime/check`
- `GET /providers/capabilities`
- `GET /providers/health`

## Execution modes

OrchAI distinguishes three execution modes:

### `MANUAL`

- follows the user's explicit command;
- does not proactively continue a workflow;
- still respects readiness, security, and authorization rules.

### `SUGGESTED`

- is the default mode;
- may propose a next action;
- never treats a suggestion as approval.

### `AUTOMATIC`

- may continue inside already allowed policy boundaries;
- remains bounded by role, action, readiness, security, and configuration;
- is not unrestricted autonomy.

## Policy, authorization, suggestion, execution

These concepts are intentionally separate:

```text
POLICY
CONFIGURATION
SUGGESTION
AUTHORIZATION
EXECUTION
```

Practical meaning:

- policy answers whether an operation is allowed under current rules;
- configuration defines the current runtime posture and defaults;
- suggestion recommends a next step but does not approve it;
- authorization records an explicit approval when required;
- execution is the actual attempt to perform work.

Useful mental model:

```text
suggested
    ≠
authorized

authorized
    ≠
ready

ready
    ≠
executed
```

## Project readiness and security

Readiness is about how safe and automatable the connected project is.

Current practical thresholds:

- `LEVEL_0_CONNECTABLE`: root is readable;
- `LEVEL_1_CHANGEABLE`: repository can be changed safely enough for bounded write operations;
- `LEVEL_2_VALIDATABLE`: repository is ready for validation-oriented flows;
- `LEVEL_3_AUTOMATABLE`: repository is mature enough for broader automated workflows such as CI/CD-related changes.

Practical guidance:

- code write operations should assume at least `LEVEL_1_CHANGEABLE`;
- test and validation operations should assume at least `LEVEL_2_VALIDATABLE`;
- CI/CD and stronger automation should assume `LEVEL_3_AUTOMATABLE`.

Security profile rules can still block an operation even when readiness
is high.

Example:

- a project can be changeable enough for writes;
- but cloud provider sharing may still be disabled;
- so a cloud-targeted operation can still be blocked.

## Recommended API-first workflow

For a service-like external integration:

1. Configure PostgreSQL and provider settings.
2. Run `uv run orchai runtime check`.
3. Start the API with `uv run orchai api serve`.
4. Register the external project with `POST /projects`.
5. Use `GET /projects/lookup` when the caller only knows the root path.
6. Inspect `GET /projects/readiness` and `GET /projects/security`.
7. Use `POST /policies/evaluate` before high-impact work when the client wants a dry decision.
8. Use `POST /flows/local` for the initial orchestration path or `POST /projects/operations` for bounded project work.
9. Inspect persisted state through `GET /tasks`, `GET /tasks/{task_id}/snapshot`, `POST /tasks/{task_id}/advance`, `GET /authorizations`, `GET /executions`, `GET /events`, `GET /audit`, `GET /metrics`, and `GET /suggestions`.

## Useful command sequences

### First shared setup

```powershell
$env:ORCHAI_DATABASE_URL = "postgresql://orchai:password@localhost:5432/orchai"
$env:ORCHAI_AI_PROVIDER = "litellm"
$env:ORCHAI_AI_BASE_URL = "http://localhost:11434"
$env:ORCHAI_AI_MODEL = "ollama/qwen2.5-coder:latest"
uv run orchai db sync
uv run orchai runtime check
uv run orchai api serve
```

### Register and inspect a project

```powershell
uv run orchai projects register .
uv run orchai projects lookup .
uv run orchai projects readiness .
uv run orchai projects security .
uv run orchai projects show <project-id>
```

### Run the first orchestration flow

```powershell
uv run orchai local-flow . docs/INDEX.md --approve-suggestion
```

### Drive lifecycle explicitly

```powershell
uv run orchai tasks create --title "Direct task" --description "Lifecycle test" --requested-change "Implement feature" --execution-mode SUGGESTED
uv run orchai authorizations request <task-id> --role DEVELOPER --action IMPLEMENT --reason "Need execution authorization" --requester "operator" --execution-mode SUGGESTED --model-id local-demo --context-scope "README.md"
uv run orchai authorizations decide <authorization-id> --status GRANTED --decided-by "manager" --reason "Approved"
uv run orchai executions request --task-id <task-id> --role DEVELOPER --action IMPLEMENT --model-id local-demo --authorization-id <authorization-id> --requested-context "README.md" --authorized-context "README.md"
uv run orchai executions dispatch <execution-id>
uv run orchai executions run <execution-id>
uv run orchai executions context <execution-id>
```

### Advance one task through staged orchestration

```powershell
uv run orchai tasks advance <task-id> --context-path docs/INDEX.md --approve-stage
uv run orchai tasks advance <task-id> --stage TEST --approve-stage
uv run orchai tasks advance <task-id> --stage DOCUMENT --context-path docs/INDEX.md --documentation-path docs/RESULT.md --approve-stage
```

This higher-level flow is useful when you want OrchAI to coordinate the
next task step instead of manually issuing separate task transition,
authorization, execution, and documentation commands.

## Operational queries

OrchAI now supports bounded operational queries instead of only broad
history listing.

CLI examples:

```powershell
uv run orchai tasks list --project-id <project-id> --state PLANNING --limit 20
uv run orchai tasks snapshot <task-id> --history-limit 50
uv run orchai executions list --task-id <task-id> --project-id <project-id> --state COMPLETED --limit 20
uv run orchai events list --execution-id <execution-id> --event-type EXECUTION_COMPLETED --limit 20
uv run orchai audit list --execution-id <execution-id> --authorization-id <authorization-id> --limit 20
uv run orchai metrics list --execution-id <execution-id> --name execution.success --limit 20
```

API examples:

```text
GET /tasks?project_id=<id>&state=PLANNING&limit=20
GET /tasks/{task_id}/snapshot
GET /executions?task_id=<id>&project_id=<id>&state=COMPLETED&limit=20
GET /events?execution_id=<id>&event_type=EXECUTION_COMPLETED&limit=20
GET /audit?execution_id=<id>&authorization_id=<id>&limit=20
GET /metrics?execution_id=<id>&name=execution.success&limit=20
```

Lifecycle-aware clients can also use the `available_transitions` field
returned by task and execution payloads to drive UI actions without
reimplementing the OrchAI state machines outside the service.

When an external client wants one consolidated view per task instead of
several separate list calls, `GET /tasks/{task_id}/snapshot` is the
best current operational read model.

When the client wants OrchAI itself to progress the task, the current
task-centric write model is `POST /tasks/{task_id}/advance`.

## Common block reasons

Typical reasons a flow or operation may stop:

- `suggested_mode_requires_approval`
- readiness too low for the intended operation
- cloud provider sharing not allowed
- requested role/action not allowed by current policy
- missing project adapter capability
- authorization exists for a different scope than the requested execution

The correct response is usually not to bypass the rule, but to inspect:

- project readiness;
- project security profile;
- requested role/action/model/context;
- execution mode;
- provider target;
- explicit authorization decision.

## Async execution dispatch

The architecture already treats long-running execution as asynchronous.

Current practical guidance:

- prefer `POST /executions/{execution_id}/dispatch` when OrchAI is
  running as an API service;
- follow the persisted execution state with `GET /executions/{id}`;
- use `GET /events`, `GET /audit`, and `GET /metrics` for operational
  visibility after dispatch.

The CLI also exposes `orchai executions dispatch`, but because the CLI
is a one-shot process, it currently uses a synchronous fallback so the
command can complete reliably. The API remains the primary async
surface.

## Troubleshooting

### `runtime check` warns about local-only mode

This usually means the runtime is using SQLite.

Use PostgreSQL if this is meant to be a shared service instance.

### Provider health is unreachable

Check:

- `ORCHAI_AI_PROVIDER`
- `ORCHAI_AI_BASE_URL`
- `ORCHAI_AI_API_KEY`
- selected model
- local Ollama process or cloud network reachability

### Policy says allowed but operation still does not run

Policy approval does not override:

- project readiness;
- project security profile;
- missing authorization when one is still required;
- adapter capability boundaries.

### Tests fail on Windows temp directories

The root `conftest.py` now defaults `--basetemp` to `.cache/pytest-tmp`
automatically (a fresh, project-local directory), specifically because
the system-wide default (`%TEMP%/pytest-of-<user>`) has a broken ACL in
some Windows checkouts of this project -- created under a different
Windows account/session, denying access to every account tested since.
Plain `pytest` / `uv run pytest` should work with no flags needed.

If you still want a different location (e.g. to inspect fixture output
after a run, or because `.cache/pytest-tmp` itself is inaccessible in
your environment for the same reason), pass `--basetemp` explicitly to
override the default:

```powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$base = Join-Path ([System.IO.Path]::GetTempPath()) "orchai-pytest-$timestamp"
.venv\Scripts\python.exe -m pytest --basetemp $base
```

## Current boundaries and limits

OrchAI is already a usable executable foundation, but some limits still
matter:

- the API and CLI cover the current foundation, not the full future product vision;
- policy configuration is still a local/runtime-first slice, not a full policy engine;
- provider integration currently covers `stub` and the multi-provider
  `litellm` adapter (OpenAI, Anthropic, Gemini, Ollama, and other
  OpenAI-compatible runtimes, ADR-013);
- the local filesystem adapter remains the primary project adapter;
- the current staged task-centric flow is implemented, but richer
  multi-user orchestration and broader automation patterns are still
  evolving.
