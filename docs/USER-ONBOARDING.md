# OrchAI User Onboarding Guide

## What OrchAI is today

For a deeper operational reference after the first setup, continue with
[`USER-OPERATIONS-GUIDE.md`](USER-OPERATIONS-GUIDE.md).

OrchAI is a generic orchestration layer for AI-assisted software
development workflows. In its current implementation, it already
supports:

- task lifecycle and state transitions;
- authorization and execution-mode enforcement;
- project readiness and security gates;
- protected project operations through a `Project Adapter`;
- event, audit, metrics, and suggestion history;
- a Typer CLI and an initial FastAPI interface.

It is still an executable foundation, not a complete end-user platform.

## Prerequisites and installation

- Python `3.14`
- `uv`

Install dependencies:

```powershell
uv sync
```

## Persistence model: PostgreSQL first, SQLite local

For real shared operation, OrchAI should be treated as a PostgreSQL-first
application. SQLite remains useful for local setup, smoke flows, and
tests, but should not be considered the target operational baseline for
team or service usage.

Recommended operational setup:

```powershell
$env:ORCHAI_DATABASE_URL = "postgresql://orchai:password@localhost:5432/orchai"
uv run orchai db sync
```

SQLite is still available for local-only usage:

```powershell
$env:ORCHAI_DATABASE_URL = "sqlite:///.orchai/orchai.db"
uv run orchai db sync
```

## First run with SQLite

SQLite is the default local backend.

```powershell
uv run orchai db sync
```

Optional explicit database URL:

```powershell
$env:ORCHAI_DATABASE_URL = "sqlite:///.orchai/orchai.db"
uv run orchai db sync
```

## API-first operation

The main external integration boundary should now be treated as the HTTP
API.

Why this matters:

- it keeps CLI, future web UI, mobile clients, desktop apps, and other
  services aligned on the same behavior;
- it exposes OrchAI as a reusable orchestration service instead of only
  a local tool;
- it preserves the architectural rule that interfaces do not own
  lifecycle or authorization logic.

Start the API:

```powershell
uv run orchai api serve
```

Inspect runtime settings through the API:

- `GET /`
- `GET /settings/runtime`
- `GET /providers/settings`
- `GET /runtime/check`
- `GET /providers/capabilities`

## Connecting a project and understanding readiness/security

For a more realistic persistent workflow, connect the project first so
it exists explicitly in OrchAI storage before you start orchestration
flows.

Persist the project connection:

```powershell
uv run orchai projects register .
```

Look up the persisted project later by root path:

```powershell
uv run orchai projects lookup .
```

Inspect a project directly through the filesystem adapter:

```powershell
uv run orchai projects discover .
uv run orchai projects readiness .
uv run orchai projects security .
```

Readiness levels:

- `LEVEL_0_CONNECTABLE`: readable project root
- `LEVEL_1_CHANGEABLE`: Git detected
- `LEVEL_2_VALIDATABLE`: Git plus minimum documentation
- `LEVEL_3_AUTOMATABLE`: Git, documentation, and tests/test strategy

High-impact operations are gated by these levels. Connecting a project
does not automatically authorize writing code, running validations, or
changing CI/CD.

## AI provider configuration

The runtime now supports explicit provider selection through
configuration.

Local stub provider:

```powershell
$env:ORCHAI_AI_PROVIDER = "stub"
```

Local Ollama provider:

```powershell
$env:ORCHAI_AI_PROVIDER = "ollama"
$env:ORCHAI_AI_BASE_URL = "http://localhost:11434"
$env:ORCHAI_AI_MODEL = "qwen2.5-coder:latest"
```

Cloud OpenAI/Codex-style provider:

```powershell
$env:ORCHAI_AI_PROVIDER = "openai"
$env:ORCHAI_AI_API_KEY = "your_api_key"
$env:ORCHAI_AI_MODEL = "gpt-5-codex"
```

Inspect the effective provider configuration safely:

```powershell
uv run orchai providers show
uv run orchai providers capabilities
uv run orchai providers health
uv run orchai runtime check
```

`orchai runtime check` is the fastest way to confirm whether the
configured database is reachable, whether the selected provider is
reachable, and whether the current runtime posture is `local-only`,
`shared-ready`, or `shared-degraded`.

## Running `local-flow`

The initial orchestration flow exercises project registration, task
creation, suggestion generation, explicit authorization, execution, and
context resolution.

```powershell
uv run orchai local-flow . docs/INDEX.md --title "Local flow" --approve-suggestion
```

Important output fields:

- `project_id`: persisted connected project
- `task_id`: orchestration task
- `authorization_id`: explicit authorization record
- `execution_id`: execution attempt
- `task_state`: resulting task lifecycle state
- `execution_state`: resulting execution lifecycle state
- `suggestion_status`: whether a suggestion stayed presented or was accepted
- `events` / `audit_records`: persisted observability count

## Protected project operations

Run protected operations through orchestration rather than directly:

```powershell
uv run orchai projects operate . WRITE_SOURCE --resource src/app.py --content "print('hello')" --approve-operation
uv run orchai projects operate . RUN_TESTS --test-args "-q" --approve-operation
uv run orchai projects operate . GIT_STATUS --approve-operation
```

These operations still pass through readiness, policy, authorization,
and adapter capability checks.

## `MANUAL`, `SUGGESTED`, and `AUTOMATIC`

- `MANUAL`: executes the explicit operation without proactive suggestion.
- `SUGGESTED`: default mode; OrchAI may suggest the next step, but waits
  for explicit approval.
- `AUTOMATIC`: proceeds only inside configured policy boundaries; it is
  not unrestricted autonomy.

Examples:

```powershell
uv run orchai local-flow . docs/INDEX.md --execution-mode MANUAL
uv run orchai local-flow . docs/INDEX.md --execution-mode SUGGESTED
uv run orchai local-flow . docs/INDEX.md --execution-mode AUTOMATIC
```

## API entry points

The initial HTTP API mirrors mature CLI operations.

- `GET /health`
- `POST /flows/local`
- `POST /projects`
- `GET /projects/lookup`
- `POST /projects/operations`
- `GET /projects/discover`
- `GET /projects/readiness`
- `GET /projects/security`
- `GET /projects`
- `GET /projects/{project_id}`
- `PATCH /projects/{project_id}/security`
- `GET /events`
- `GET /audit`
- `GET /metrics`
- `GET /suggestions`

The API is intentionally thin and reuses the same application services
and orchestration flow used by the CLI.

Additional operational endpoints:

- `GET /`
- `GET /settings/runtime`
- `GET /providers/settings`
- `GET /runtime/check`
- `GET /providers/capabilities`
- `GET /providers/health`
- `POST /tasks`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/snapshot`
- `POST /tasks/{task_id}/transition`
- `POST /tasks/{task_id}/advance`
- `GET /authorizations`
- `GET /authorizations/{authorization_id}`
- `POST /authorizations/request`
- `POST /authorizations/{authorization_id}/decision`
- `POST /policies/evaluate`
- `POST /executions/request`
- `POST /executions/{execution_id}/dispatch`
- `POST /executions/{execution_id}/run`
- `GET /executions`
- `GET /executions/{execution_id}`
- `POST /executions/{execution_id}/transition`
- `POST /executions/{execution_id}/complete`
- `POST /executions/{execution_id}/resolve-context`
- `GET /executions/{execution_id}/context`

The list endpoints support operational filtering for persisted state:

- `GET /tasks?project_id=<id>&state=PLANNING&limit=20`
- `GET /executions?task_id=<id>&project_id=<id>&state=COMPLETED&limit=20`

## Inspecting persisted tasks and executions

After running a flow or protected operation, inspect the persisted state
directly:

```powershell
uv run orchai tasks list
uv run orchai tasks show <task-id>
uv run orchai tasks snapshot <task-id> --history-limit 50
uv run orchai authorizations list --task-id <task-id>
uv run orchai authorizations show <authorization-id>
uv run orchai executions list
uv run orchai executions show <execution-id>
uv run orchai executions context <execution-id>
uv run orchai tasks list --project-id <project-id> --state PLANNING --limit 10
uv run orchai executions list --task-id <task-id> --project-id <project-id> --state COMPLETED --limit 10
```

This is useful for checking lifecycle state, execution mode, authorized
context, explicit authorization decisions, timestamps, execution
result metadata, and the currently available lifecycle transitions for
each task or execution. For a single task-centric operational read, use
`orchai tasks snapshot <task-id>` or `GET /tasks/{task_id}/snapshot`.

## Advancing a task through the staged workflow

For a more realistic task-centric flow, OrchAI can now advance one
persisted task through its next recommended stage while keeping
authorization, execution, events, audit, and task state in sync.

CLI examples:

```powershell
uv run orchai tasks advance <task-id> --context-path docs/INDEX.md --approve-stage
uv run orchai tasks advance <task-id> --stage TEST --approve-stage
uv run orchai tasks advance <task-id> --stage DOCUMENT --context-path docs/INDEX.md --documentation-path docs/RESULT.md --approve-stage
```

API example:

- `POST /tasks/{task_id}/advance`

Practical behavior:

- when no explicit `stage` is provided, OrchAI advances to the next
  suggested stage for the current task state;
- AI-backed stages reuse the configured provider adapter and persist
  authorization plus execution history;
- the `TEST` stage runs through the Project Adapter and requires
  readiness compatible with test execution;
- the `DOCUMENT` stage writes the generated output to the provided
  documentation path and completes the task when successful.

## Explicit authorization flow

When you need to model approval as a first-class workflow, OrchAI now
supports direct authorization request and decision operations in
addition to the orchestration flows.

CLI examples:

```powershell
uv run orchai authorizations request <task-id> --role QUALITY_AGENT --action REVIEW --reason "Need explicit review authorization" --requester "operator" --execution-mode SUGGESTED --context-scope "docs/INDEX.md" --proposed-state REVIEWING
uv run orchai authorizations decide <authorization-id> --status GRANTED --decided-by "review-manager" --reason "Approved"
```

API examples:

- `POST /authorizations/request`
- `POST /authorizations/{authorization_id}/decision`

This is useful when an external service or UI needs to separate:

- requesting approval;
- waiting for a human decision;
- continuing execution only after the recorded result.

## Policy pre-check

Before executing a flow or protected operation, an external client can
now ask OrchAI to evaluate the policy decision directly.

CLI example:

```powershell
uv run orchai policies evaluate --execution-mode MANUAL --role DEVELOPER --action IMPLEMENT --requested-model local-demo --effective-model local-demo --current-task-state PLANNED --project-operation WRITE_SOURCE --project-root . --explicit-user-command
```

API example:

- `POST /policies/evaluate`

This is useful for:

- previewing likely blockers before execution;
- surfacing readiness and provider-boundary issues in UI flows;
- validating approval state in external orchestration layers.

## Direct lifecycle operations

OrchAI now also exposes direct low-level lifecycle operations for
clients that need to drive the state model explicitly instead of using
only `local-flow` or protected project operations.

CLI examples:

```powershell
uv run orchai tasks create --title "Direct task" --description "Lifecycle test" --requested-change "Implement feature" --execution-mode SUGGESTED
uv run orchai tasks transition <task-id> --target-state PLANNING
uv run orchai executions request --task-id <task-id> --role DEVELOPER --action IMPLEMENT --model-id local-demo --authorization-id <authorization-id>
uv run orchai executions dispatch <execution-id>
uv run orchai executions run <execution-id>
uv run orchai executions transition <execution-id> --target-state RUNNING
uv run orchai executions complete <execution-id> --output "Done" --success
uv run orchai executions resolve-context <execution-id> --source SOURCE_FILE
```

API examples:

- `POST /tasks`
- `POST /tasks/{task_id}/transition`
- `POST /executions/request`
- `POST /executions/{execution_id}/run`
- `POST /executions/{execution_id}/transition`
- `POST /executions/{execution_id}/complete`
- `POST /executions/{execution_id}/resolve-context`

Use this layer when you are building a richer external client or when
you want to orchestrate lifecycle steps explicitly. Prefer the higher
level flows when you want OrchAI to coordinate the steps for you.

When you do want the real AI provider adapter to run, `executions run`
and `POST /executions/{execution_id}/run` are the direct bridge from the
persisted orchestration state to the configured local or cloud provider.

For service-like API usage, `POST /executions/{execution_id}/dispatch`
is the async-friendly option. It schedules the execution in-process and
lets the client follow persisted state through `GET /executions/{id}`,
`GET /events`, `GET /audit`, and `GET /metrics`.

## Recommended API-first sequence

For service-like operation with PostgreSQL as the main persistence
target, the most coherent sequence today is:

1. Configure `ORCHAI_DATABASE_URL` to PostgreSQL and start the API with `uv run orchai api serve`.
2. Register the external project with `POST /projects`.
3. Re-find the persisted project with `GET /projects/lookup` when an external component only has the root path.
4. Inspect `GET /projects/readiness` and `GET /projects/security` for the target root.
5. Pre-check the intended action with `POST /policies/evaluate` when a client needs to predict blockers before execution.
6. Run `POST /flows/local` or `POST /projects/operations` depending on the use case.
7. If needed, request or decide explicit approvals through `POST /authorizations/request` and `POST /authorizations/{authorization_id}/decision`.
8. Inspect `GET /tasks`, `GET /tasks/{task_id}/snapshot`, `POST /tasks/{task_id}/advance`, `GET /authorizations`, `GET /executions`, `GET /executions/{execution_id}/context`, `GET /events`, `GET /audit`, and `GET /metrics`.

## Policies, rules, and why an operation may be blocked

OrchAI intentionally separates:

- `policy`;
- `configuration`;
- `suggestion`;
- `authorization`;
- `execution`.

Practical interpretation:

- policy decides whether an operation is allowed to proceed in the
  current mode and boundary conditions;
- configuration defines runtime/provider/database/API behavior;
- suggestion recommends a next action but does not authorize it;
- authorization records explicit approval when required;
- execution is the actual attempt and result.

Typical block reasons include:

- `suggested_mode_requires_approval`
- readiness too low for the requested operation
- provider sharing not allowed for cloud execution
- cross-role automation not allowed by policy
- missing adapter capability

## Detailed policy and security interpretation

The most important rules for users are:

- code change requires at least `LEVEL_1_CHANGEABLE`;
- validation/test-oriented flows require at least `LEVEL_2_VALIDATABLE`;
- CI/CD-oriented work should be treated as `LEVEL_3_AUTOMATABLE`;
- cloud execution requires project security rules that allow provider
  sharing for the authorized context;
- an approved operation can still be blocked if readiness or security
  gates are not satisfied.

This is why:

```text
authorized
    ≠
ready
```

and also:

```text
suggested
    ≠
authorized
```

## Current limits

Current gaps to keep in mind:

- public API is still an initial slice;
- policy configuration is still a local/runtime-first slice, not a full
  policy engine;
- provider integration currently covers the adapter boundary plus
  `stub`, `Ollama`, and an initial OpenAI/Codex-style cloud adapter;
- project integration is currently centered on the local filesystem
  adapter;
- the staged task-centric workflow is implemented, but broader multi-user
  orchestration patterns are still evolving.

## Windows / pytest / temp/cache issues

In restricted Windows environments, the default global temp directory
may fail during `pytest` setup. Also avoid reusing the same `basetemp`
directory across repeated runs on Windows, because `pytest` may try to
create it again and abort early. Prefer a workspace-local directory
with a unique suffix when the workspace allows it:

```powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
uv run pytest --basetemp ".pytest-tmp/run-$timestamp"
```

If the workspace temp folder itself is blocked by local permissions,
prefer a writable system temp location:

```powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$base = Join-Path ([System.IO.Path]::GetTempPath()) "orchai-pytest-$timestamp"
.venv\Scripts\python.exe -m pytest --basetemp $base
```

## When OrchAI is a good fit today

Use OrchAI now when you want:

- explicit orchestration history;
- readiness-gated project operations;
- controlled experimentation with local project automation;
- a foundation for future API/UI growth.

Wait before relying on it as a full platform when you need:

- mature multi-user workflows;
- production-ready deployment automation;
- broad provider ecosystem support;
- a complete DevSecOps automation surface.
