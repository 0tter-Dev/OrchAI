# OrchAI

OrchAI is a generic orchestration system for AI-assisted software
development workflows.

The project coordinates tasks, authorization, execution attempts,
context resolution, project adapters, events, audit, metrics, roles,
actions, and model/provider boundaries without embedding project-specific
business logic in the core.

## Current Status

Version: `v0.2.8`

The current implementation is an executable foundation, not a complete
product.

This section is intentionally a short summary, not the authoritative
status — it drifts if maintained as a second copy of the same facts.
For the current, detailed state of every area (what is `DEFINED`,
`DECIDED`, `PARTIAL`, or `IMPLEMENTED`), see
[docs/STATUS.md](docs/STATUS.md); for what remains as an explicitly
tracked gap, see the "Lacunas conhecidas" section of
[docs/API-ENDPOINTS-REPORT.md](docs/API-ENDPOINTS-REPORT.md).

At a high level, the operational foundation is implemented end to end:
task lifecycle, authorization, policy, execution, context resolution,
project adapters, events, audit, metrics, suggestions, and SQLAlchemy
persistence (SQLite for local/test use, PostgreSQL as the production
default) are all covered by the CLI and the HTTP API, with the
`/requests` chat-first surface (ADR-011) as the primary integration
point. Identity and access management (JWT authentication, persisted
users/permissions, a superuser role), documented in ADR-012 and
[docs/context/identity-and-access.md](docs/context/identity-and-access.md),
is now implemented end to end — `POST /auth/login` / `POST /auth/refresh`
/ `POST /auth/logout`, `orchai auth login` / `orchai auth logout` /
`orchai auth bootstrap-admin`, a permission check on every other
route/command, and an admin-facing CRUD layer for users/access-roles/
projects plus a self-service `/me` surface (`orchai users *` /
`orchai access-roles *` / `orchai me *`) — but enforcement is opt-in: set
`ORCHAI_AUTH_ENFORCED=true` to require it, since the default (`false`)
keeps every endpoint unauthenticated exactly as before, per the rollout
plan in that document.
Real AI provider adapters (beyond the deterministic `stub` provider),
deployment/container automation, and execution cancellation remain
pending.

## Requirements

- Python 3.14
- uv

## Setup

``` powershell
uv sync
```

If `uv` is not available in the current shell, use the project virtual
environment directly:

``` powershell
.venv\Scripts\python.exe -m pytest
```

## Configuration

The current configuration surface reads the process environment first
and then a local `.env` file.

``` powershell
$env:ORCHAI_DATABASE_URL = "postgresql://orchai:password@localhost:5432/orchai"
```

PostgreSQL is the explicit production default: it is what the runtime
assumes when `ORCHAI_DATABASE_URL` is not set at all. PostgreSQL URLs are
accepted and normalized to the SQLAlchemy `postgresql+psycopg` driver form.

SQLite remains fully supported, but only as a secondary option meant to
keep local development and automated tests fast and dependency-free. Set
it explicitly with a full URL or the `sqlite`/`local` shorthand:

``` powershell
$env:ORCHAI_DATABASE_URL = "sqlite:///.orchai/orchai.db"
# or, equivalently and shorter:
$env:ORCHAI_DATABASE_URL = "sqlite"
```

The runtime now also supports explicit AI provider and API settings.
Since the LiteLLM provider migration, one adapter covers every real
backend — which one runs is selected by `ORCHAI_AI_MODEL`'s
`"<provider>/<model>"` prefix, not by `ORCHAI_AI_PROVIDER` itself:

``` powershell
$env:ORCHAI_AI_PROVIDER = "litellm"
$env:ORCHAI_AI_BASE_URL = "http://localhost:11434"
$env:ORCHAI_AI_MODEL = "ollama/qwen2.5-coder:latest"
$env:ORCHAI_API_HOST = "127.0.0.1"
$env:ORCHAI_API_PORT = "8000"
```

For OpenAI-style cloud execution (via LiteLLM):

``` powershell
$env:ORCHAI_AI_PROVIDER = "litellm"
$env:ORCHAI_AI_API_KEY = "your_api_key"
$env:ORCHAI_AI_MODEL = "openai/gpt-5"
```

Authentication is wired in but opt-in (ADR-012, Phase 3): every route and
command carries a permission requirement, but it is only enforced once
`ORCHAI_AUTH_ENFORCED` is set to `true`.

``` powershell
$env:ORCHAI_AUTH_ENFORCED = "true"
$env:ORCHAI_AUTH_SECRET_KEY = "a-real-secret-change-me"
$env:ORCHAI_ADMIN_USERNAME = "admin"
$env:ORCHAI_ADMIN_PASSWORD = "change-me"
```

Bootstrap the first superuser (only works while zero users exist yet),
then log in — the CLI persists the resulting token pair to
`~/.orchai/credentials.json` and reuses it for later commands:

``` powershell
uv run orchai auth bootstrap-admin
uv run orchai auth login --username admin --password change-me
uv run orchai auth logout
```

An `ORCHAI_TOKEN` environment variable is checked before the local
credentials file, for non-interactive/CI use. HTTP clients send the
access token from `POST /auth/login` (or `POST /auth/refresh`) as
`Authorization: Bearer <token>` on every subsequent request.

Run a consolidated operational check before serving the API or using a
shared database:

``` powershell
uv run orchai runtime check
```

For API-first consumers, the HTTP surface now exposes a root index and
provider settings entry points in addition to the runtime checks:

```text
GET /
GET /settings/runtime
GET /providers/settings
GET /providers/capabilities
GET /providers/health
```

## Guides

- [User guide](docs/USER-GUIDE.md)
- [Operations reference](docs/OPERATIONS-REFERENCE.md)
- [Git and GitHub delivery flow](docs/GIT-GITHUB-FLOW.md)
- [Documentation index](docs/INDEX.md)

## CLI

The CLI remains important for operations and local administration, but
the intended main integration boundary is now the HTTP API.

`db sync` is the single, standard database administration command: it
creates the target database when needed (PostgreSQL only) and then
applies migrations, in one step.

``` powershell
$env:ORCHAI_DATABASE_URL = "postgresql://postgres:password@localhost:5432/orchai"
uv run orchai db sync
```

For a fast local/test run with no PostgreSQL server at all, use the
secondary SQLite option instead — the create step is skipped
(informational, not an error), and migrations still run:

``` powershell
$env:ORCHAI_DATABASE_URL = "sqlite"
uv run orchai db sync
```

Inspect effective provider settings:

``` powershell
uv run orchai providers show
uv run orchai providers capabilities
uv run orchai runtime check
```

Serve the API with the configured host and port:

``` powershell
uv run orchai api serve
```

Run the minimal local orchestration flow:

``` powershell
uv run orchai local-flow . docs/INDEX.md --title "Local flow" --approve-suggestion
```

The local flow registers a project, creates a task, records explicit
authorization, creates an execution, resolves only authorized context,
and completes the execution. Persisted project configuration now reuses
the effective readiness/security profile for the same project root while
refreshing the latest observed assessment from the adapter. Without
`--approve-suggestion`, the default `SUGGESTED` mode presents the
generated suggestion and stops before authorization/execution. `MANUAL`
mode runs the explicit operation without generating a proactive
suggestion, while `AUTOMATIC` mode proceeds only when the configured
policy allows the role/action pair.

Run the same initial operation through bounded automatic mode:

``` powershell
uv run orchai local-flow . docs/INDEX.md --execution-mode AUTOMATIC
```

Run the same flow with a configured cloud provider target:

``` powershell
uv run orchai local-flow . docs/INDEX.md --provider-target CLOUD --approve-suggestion
```

Discover project resources through the filesystem Project Adapter:

``` powershell
uv run orchai projects register .
uv run orchai projects discover . --limit 20
```

Inspect observed vs effective persisted project configuration:

``` powershell
uv run orchai projects list
uv run orchai projects lookup .
uv run orchai projects show <project-id>
uv run orchai projects update-security <project-id> --readiness-level LEVEL_3_AUTOMATABLE
```

Run a protected project operation through orchestration:

``` powershell
uv run orchai projects operate . WRITE_SOURCE --resource src/app.py --content "print('hello')" --approve-operation
uv run orchai projects operate . RUN_TESTS --test-args "-q" --approve-operation
uv run orchai projects operate . GIT_STATUS --approve-operation
```

Inspect persisted history:

``` powershell
uv run orchai events list --limit 10
uv run orchai audit list --limit 10
uv run orchai metrics list --limit 10
uv run orchai suggestions list --limit 10
uv run orchai tasks list --limit 10
uv run orchai tasks create --title "Direct task" --description "Lifecycle test" --requested-change "Implement feature" --execution-mode SUGGESTED
uv run orchai tasks transition <task-id> --target-state PLANNING
uv run orchai tasks snapshot <task-id> --history-limit 50
uv run orchai tasks advance <task-id> --context-path docs/INDEX.md --approve-stage
uv run orchai tasks advance <task-id> --stage TEST --approve-stage
uv run orchai tasks advance <task-id> --stage DOCUMENT --context-path docs/INDEX.md --documentation-path docs/RESULT.md --approve-stage
uv run orchai tasks list --project-id <project-id> --state PLANNING --limit 10
uv run orchai authorizations list
uv run orchai authorizations request <task-id> --role QUALITY_AGENT --action REVIEW --reason "Need explicit review authorization" --requester "operator" --execution-mode SUGGESTED
uv run orchai authorizations decide <authorization-id> --status GRANTED --decided-by "review-manager" --reason "Approved"
uv run orchai policies evaluate --execution-mode MANUAL --role DEVELOPER --action IMPLEMENT --requested-model local-demo --effective-model local-demo --current-task-state PLANNED --project-operation WRITE_SOURCE --project-root . --explicit-user-command
uv run orchai executions list --limit 10
uv run orchai executions request --task-id <task-id> --role DEVELOPER --action IMPLEMENT --model-id local-demo --authorization-id <authorization-id>
uv run orchai executions run <execution-id>
uv run orchai executions dispatch <execution-id>
uv run orchai executions transition <execution-id> --target-state RUNNING
uv run orchai executions complete <execution-id> --output "Done" --success
uv run orchai executions resolve-context <execution-id> --source SOURCE_FILE
uv run orchai executions list --task-id <task-id> --project-id <project-id> --state COMPLETED --limit 10
uv run orchai events list --project-id <project-id> --limit 10
uv run orchai audit list --project-id <project-id> --limit 10
uv run orchai metrics list --project-id <project-id> --limit 10
```

For API-first clients that need one consolidated operational read per
task, use:

```text
GET /tasks/{task_id}/snapshot
POST /tasks/{task_id}/advance
```

## Tests

``` powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
uv run pytest --basetemp ".pytest-tmp/run-$timestamp"
```

The current suite covers unit and integration behavior, including CLI
and API execution, SQLite restart-surviving persistence, policy
enforcement, recovery paths for provider/context failures,
architectural dependency checks, protected project operations, and the
async execution engine with fake providers, including API-first async
dispatch and persisted-state follow-up.

In restricted Windows environments, prefer a workspace-local
`--basetemp` with a unique suffix per run when the workspace allows it.
Reusing the same directory may fail on repeated executions, so prefer:

``` powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
uv run pytest --basetemp ".pytest-tmp/run-$timestamp"
```

If the workspace temp directory is blocked, run against a writable
system temp path instead:

``` powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$base = Join-Path ([System.IO.Path]::GetTempPath()) "orchai-pytest-$timestamp"
.venv\Scripts\python.exe -m pytest --basetemp $base
```

## Architecture

Start with [docs/INDEX.md](docs/INDEX.md) for the documentation map.
Important architectural boundaries are captured in:

- [docs/ARCHITECTURAL-CONTRACT.md](docs/ARCHITECTURAL-CONTRACT.md)
- [docs/context/modules-and-domain-structure.md](docs/context/modules-and-domain-structure.md)
- [docs/context/persistence.md](docs/context/persistence.md)
- [docs/IMPLEMENTATION-MAP.md](docs/IMPLEMENTATION-MAP.md)

## License

MIT. See [LICENSE](LICENSE).
