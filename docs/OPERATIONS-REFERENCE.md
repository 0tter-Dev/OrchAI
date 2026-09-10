# OrchAI Operations Reference

## Purpose

This is the operational reference for configuring, running, and
troubleshooting OrchAI in real projects. For the narrative first-run
walkthrough, see [`USER-GUIDE.md`](USER-GUIDE.md) — read that first if
you have not run OrchAI before; come back here for configuration
detail, the policy/readiness mental model, the full API/CLI surface,
and troubleshooting.

## Recommended Operating Posture

```text
API-first
PostgreSQL as primary persistence
SQLite only for local tests and local smoke flows
Explicit provider configuration
Explicit project registration
Explicit policy/authorization visibility before high-impact operations
```

## Configuration Reference

The runtime configuration is environment-first, with an optional local
`.env` fallback.

| Variable | Purpose |
|---|---|
| `ORCHAI_DATABASE_URL` | Database connection; PostgreSQL is the default target, SQLite an explicit secondary option |
| `ORCHAI_AI_PROVIDER` | `litellm` for any real backend, or `stub` for the deterministic local provider |
| `ORCHAI_AI_BASE_URL` | Base URL for a local runtime (e.g. Ollama) |
| `ORCHAI_AI_API_KEY` | API key for a cloud provider |
| `ORCHAI_AI_ORGANIZATION` | Optional provider organization identifier |
| `ORCHAI_AI_PROJECT` | Optional provider project identifier |
| `ORCHAI_AI_MODEL` | `"<provider>/<model>"`, e.g. `ollama/qwen2.5-coder:latest` or `openai/gpt-5` — this, not `ORCHAI_AI_PROVIDER`, selects the real backend |
| `ORCHAI_AI_TIMEOUT_SECONDS` | Provider call timeout |
| `ORCHAI_API_HOST` / `ORCHAI_API_PORT` | HTTP API bind address |
| `ORCHAI_AUTH_ENFORCED` | `true` to require authentication on every route/command; `false` (default) keeps every endpoint unauthenticated |
| `ORCHAI_AUTH_SECRET_KEY` | JWT signing secret, required when auth is enforced |
| `ORCHAI_ADMIN_USERNAME` / `ORCHAI_ADMIN_PASSWORD` | Bootstrap superuser credentials |
| `ORCHAI_TOKEN` | Access token checked before the local credentials file, for non-interactive/CI use |

### Database

```powershell
$env:ORCHAI_DATABASE_URL = "postgresql://orchai:password@localhost:5432/orchai"
uv run orchai db sync
uv run orchai runtime check
```

```powershell
$env:ORCHAI_DATABASE_URL = "sqlite:///.orchai/orchai.db"
uv run orchai db sync
uv run orchai runtime check
```

`db sync` creates the target database when needed (PostgreSQL only)
and applies migrations in one step; for SQLite the create step is
skipped (informational, not an error) and migrations still run.

`runtime check` reports `operational_mode`:

- `shared-ready` — database and provider are reachable; suitable for
  shared operation
- `shared-degraded` — PostgreSQL is intended but a dependency is
  unhealthy
- `local-only` — valid for local usage, but not the recommended
  shared posture

### AI Provider

One `litellm` adapter covers every real backend (OpenAI, Anthropic,
Gemini, Ollama, and other OpenAI-compatible local runtimes); the
provider actually used is selected by `ORCHAI_AI_MODEL`'s
`"<provider>/<model>"` prefix.

```powershell
# stub — no network, deterministic, good for a first dry run
$env:ORCHAI_AI_PROVIDER = "stub"

# local Ollama model via LiteLLM
$env:ORCHAI_AI_PROVIDER = "litellm"
$env:ORCHAI_AI_BASE_URL = "http://localhost:11434"
$env:ORCHAI_AI_MODEL = "ollama/qwen2.5-coder:latest"

# cloud model via LiteLLM
$env:ORCHAI_AI_PROVIDER = "litellm"
$env:ORCHAI_AI_API_KEY = "your_api_key"
$env:ORCHAI_AI_MODEL = "openai/gpt-5"
```

```powershell
uv run orchai providers show
uv run orchai providers capabilities
uv run orchai providers health
uv run orchai runtime check
```

Related endpoints: `GET /`, `GET /settings/runtime`,
`GET /providers/settings`, `GET /providers/capabilities`,
`GET /providers/health`, `GET /runtime/check`.

### Authentication

Authentication is wired in but opt-in — every route/command carries a
permission requirement, enforced only once `ORCHAI_AUTH_ENFORCED` is
`true`. See `docs/context/identity-and-access.md` for the full model
and migration/rollout plan.

```powershell
$env:ORCHAI_AUTH_ENFORCED = "true"
$env:ORCHAI_AUTH_SECRET_KEY = "a-real-secret-change-me"
$env:ORCHAI_ADMIN_USERNAME = "admin"
$env:ORCHAI_ADMIN_PASSWORD = "change-me"

uv run orchai auth bootstrap-admin
uv run orchai auth login --username admin --password change-me
uv run orchai auth logout
```

## Execution Modes

- **`MANUAL`** — follows the explicit command; no proactive workflow
  progression; still respects readiness, security, and authorization
- **`SUGGESTED`** (default) — may propose a next action; a suggestion
  is never treated as approval
- **`AUTOMATIC`** — may continue only inside already-configured policy
  boundaries; still bounded by role, action, readiness, security, and
  configuration; not unrestricted autonomy

```powershell
uv run orchai local-flow . docs/INDEX.md --execution-mode MANUAL
uv run orchai local-flow . docs/INDEX.md --execution-mode SUGGESTED
uv run orchai local-flow . docs/INDEX.md --execution-mode AUTOMATIC
```

## Policy, Authorization, Suggestion, Execution

These concepts are intentionally separate and never conflated:

```text
POLICY         — whether an operation is allowed under current rules
CONFIGURATION  — current runtime posture and defaults
SUGGESTION     — a recommended next step; never an approval
AUTHORIZATION  — an explicit, recorded approval when one is required
EXECUTION      — the actual attempt to perform work
```

```text
suggested ≠ authorized
authorized ≠ ready
ready ≠ executed
```

Typical block reasons: `suggested_mode_requires_approval`, readiness
too low for the requested operation, cloud provider sharing not
allowed, cross-role automation not permitted by policy, missing
adapter capability, or an authorization scoped to a different
execution than the one requested. The correct response is to inspect
project readiness, project security profile, the requested
role/action/model/context, execution mode, provider target, and any
explicit authorization decision — never to bypass the rule.

## Project Readiness And Security

Readiness measures how safe and automatable a connected project is:

| Level | Meaning |
|---|---|
| `LEVEL_0_CONNECTABLE` | root is readable |
| `LEVEL_1_CHANGEABLE` | Git detected; safe enough for bounded writes |
| `LEVEL_2_VALIDATABLE` | Git plus minimum documentation; ready for validation flows |
| `LEVEL_3_AUTOMATABLE` | Git, documentation, and tests/test strategy; ready for CI/CD-oriented automation |

Practical guidance: code writes assume at least `LEVEL_1_CHANGEABLE`;
test/validation flows assume at least `LEVEL_2_VALIDATABLE`; CI/CD
work assumes `LEVEL_3_AUTOMATABLE`. A project's security profile can
still block an operation even when readiness is high — for example, a
project can be changeable enough for writes while cloud provider
sharing remains disabled, blocking a cloud-targeted operation.

```powershell
uv run orchai projects register .
uv run orchai projects lookup .
uv run orchai projects discover .
uv run orchai projects readiness .
uv run orchai projects security .
uv run orchai projects update-security <project-id> --readiness-level LEVEL_3_AUTOMATABLE
```

## API Reference

The API mirrors CLI operations and reuses the same application
services and orchestration flow.

**System / runtime**: `GET /`, `GET /health`, `GET /settings/runtime`,
`GET /runtime/check`, `GET /providers/settings`,
`GET /providers/capabilities`, `GET /providers/health`.

**Chat-first (primary integration point)**: `/requests`.

**Projects**: `POST /projects`, `GET /projects/lookup`,
`GET /projects/discover`, `GET /projects/readiness`,
`GET /projects/security`, `GET /projects`,
`GET /projects/{project_id}`, `PATCH /projects/{project_id}/security`,
`POST /projects/operations`.

**Tasks**: `POST /tasks`, `GET /tasks`, `GET /tasks/{task_id}`,
`GET /tasks/{task_id}/snapshot`, `POST /tasks/{task_id}/transition`,
`POST /tasks/{task_id}/advance`.

**Authorizations**: `GET /authorizations`,
`GET /authorizations/{authorization_id}`,
`POST /authorizations/request`,
`POST /authorizations/{authorization_id}/decision`.

**Policies**: `POST /policies/evaluate`.

**Executions**: `POST /executions/request`,
`POST /executions/{execution_id}/dispatch`,
`POST /executions/{execution_id}/run`,
`POST /executions/{execution_id}/run-stream`, `GET /executions`,
`GET /executions/{execution_id}`,
`POST /executions/{execution_id}/transition`,
`POST /executions/{execution_id}/complete`,
`POST /executions/{execution_id}/resolve-context`,
`GET /executions/{execution_id}/context`.

**Observability**: `GET /events`, `GET /audit`, `GET /metrics`,
`GET /suggestions`.

**Identity and admin**: `POST /auth/login`, `POST /auth/refresh`,
`POST /auth/logout`, `GET /me`, `GET /admin/users`,
`GET /admin/access-roles`, `GET /admin/projects`.

**Flows**: `POST /flows/local`.

List endpoints support operational filtering, e.g.
`GET /tasks?project_id=<id>&state=PLANNING&limit=20` and
`GET /executions?task_id=<id>&project_id=<id>&state=COMPLETED&limit=20`.
Lifecycle-aware clients can drive UI actions from the
`available_transitions` field on task and execution payloads instead
of reimplementing the state machines externally.

For service-like operation, `POST /executions/{execution_id}/dispatch`
is the async-friendly option: it schedules the execution in-process
and lets the client follow persisted state through
`GET /executions/{id}`, `GET /events`, `GET /audit`, and
`GET /metrics`. `POST /executions/{execution_id}/run` is the direct,
synchronous bridge to the configured provider when the caller wants to
wait for the result inline. `POST /executions/{execution_id}/run-stream`
is the incremental variant of that same direct call: it requires the
execution to already be `AUTHORIZED` (`404`/`409` otherwise) and
returns a `text/event-stream` response — one `type: "delta"` event per
provider chunk, then a final `type: "done"` event carrying the fully
serialized terminal execution, mirroring
`POST /conversations/{id}/messages`'s streaming shape. On the
chat-first surface, `POST /requests/{request_id}/approve-stream` is
the streaming counterpart of `POST /requests/{request_id}/approve`:
same decision logic (grant a pending authorization directly, or
delegate to the gated advance mechanism), but an AI-driven stage's
execution streams the same `delta`/`done` shape, with the `done`
payload matching what the non-streaming endpoint already returns. This
is what the OrchAI Desktop Approval Card calls when the user approves
an escalated message's Task.

## CLI Reference

### Direct lifecycle operations

For clients that need to drive the state model explicitly instead of
using `local-flow` or a staged `tasks advance`:

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

### Explicit authorization flow

```powershell
uv run orchai authorizations request <task-id> --role QUALITY_AGENT --action REVIEW --reason "Need explicit review authorization" --requester "operator" --execution-mode SUGGESTED --context-scope "docs/INDEX.md" --proposed-state REVIEWING
uv run orchai authorizations decide <authorization-id> --status GRANTED --decided-by "review-manager" --reason "Approved"
```

### Policy pre-check

Ask OrchAI to evaluate a policy decision before executing a flow or
protected operation — useful for previewing likely blockers, surfacing
readiness/provider-boundary issues in a UI, or validating approval
state in an external orchestration layer:

```powershell
uv run orchai policies evaluate --execution-mode MANUAL --role DEVELOPER --action IMPLEMENT --requested-model local-demo --effective-model local-demo --current-task-state PLANNED --project-operation WRITE_SOURCE --project-root . --explicit-user-command
```

### Operational queries

```powershell
uv run orchai tasks list --project-id <project-id> --state PLANNING --limit 20
uv run orchai tasks snapshot <task-id> --history-limit 50
uv run orchai executions list --task-id <task-id> --project-id <project-id> --state COMPLETED --limit 20
uv run orchai events list --execution-id <execution-id> --event-type EXECUTION_COMPLETED --limit 20
uv run orchai audit list --execution-id <execution-id> --authorization-id <authorization-id> --limit 20
uv run orchai metrics list --execution-id <execution-id> --name execution.success --limit 20
```

## Async Execution Dispatch

Long-running execution is treated as asynchronous by design. Prefer
`POST /executions/{execution_id}/dispatch` when running as an API
service, and follow persisted state through `GET /executions/{id}`,
`GET /events`, `GET /audit`, and `GET /metrics`. The CLI also exposes
`orchai executions dispatch`, but because the CLI is a one-shot
process it uses a synchronous fallback so the command completes
reliably — the API remains the primary async surface. The same
one-shot constraint applies to streaming: `orchai executions run` has
no streaming counterpart, and `POST /executions/{execution_id}/run-stream`
is API-only, mirroring how conversation streaming also has no CLI
command.

## Windows Local Setup And Control

`orchai.bat` (repository root) is the recommended entrypoint for
first-time Windows setup or day-to-day local startup: `[1]`/`[2]` run
checks then start (headless API / Desktop), `[3]` opens the API docs
in a browser, `[4]`/`[5]` open the Setup/Control menus, `[0]` exits.
It delegates to two auxiliary launchers under `tools\windows\`, both
adapted from the sibling project OrchFlow's own launcher model
(`orchflow-setup.bat`/`orchflow-control.bat`), extended for OrchAI's
headless-API-vs-Desktop choice (OrchFlow only has one deployment
mode).

`tools\windows\orchai-setup.bat` is the environment/dependency check.
Run it with no arguments for an interactive menu (`[1]` check for
headless API use, `[2]` check for Desktop use, `[0]` exit), or drive
it non-interactively:

```bat
tools\windows\orchai-setup.bat check
tools\windows\orchai-setup.bat check desktop
```

The check flow verifies Python 3.14+ and `uv` are on `PATH` (plus
Node.js when the target mode is `desktop`), creates `.env` from the
committed `.env.example` only when `.env` does not already exist
(never overwriting one that does), runs `uv sync --dev`, builds
`apps/desktop/frontend` with `npm install`/`npm run build` only in
`desktop` mode (headless-API-only setup never requires Node.js), runs
`uv run orchai db sync`, and validates the CLI with
`uv run orchai --help`. A missing prerequisite is reported with a
short, actionable install pointer instead of a raw tool error, and the
script never installs global software on its own — only project-local
dependencies (`uv sync`, `npm install`).

`tools\windows\orchai-control.bat` is routine local lifecycle control,
wrapping `scripts\orchai-local-process-control.ps1`. Run it with no
arguments for an interactive menu (`[1]` status, `[2]` start headless
API, `[3]` start Desktop, `[4]` stop, `[5]` restart in the
previously-started mode, `[0]` exit), or drive it non-interactively:

```bat
tools\windows\orchai-control.bat status
tools\windows\orchai-control.bat start api
tools\windows\orchai-control.bat start desktop
tools\windows\orchai-control.bat stop
tools\windows\orchai-control.bat restart
tools\windows\orchai-control.bat restart api
```

Unlike OrchFlow (which always tracks a fixed API+Web pair), OrchAI
tracks exactly one local process at a time -- either the headless API
(`uv run orchai api serve`, readiness detected by polling
`ORCHAI_API_HOST`/`ORCHAI_API_PORT` for a listening socket, same as
OrchFlow's own API/Web tracking) or the Desktop shell
(`uv run --extra desktop python -m apps.desktop.shell.main`, tracked
by pid directly, since `server_runner.py` binds a free port at runtime
with nothing fixed to poll for). `start`/`restart` without an explicit
mode either requires one (`start`) or reuses the mode recorded from
the last tracked start (`restart`). State (a PID file, JSON process
metadata, a generated service command, and a startup log) lives under
`ORCHAI_RUNTIME_DIR` (default `runtime\`, gitignored, resolved
relative to the repository root); `stop`/`restart` only ever act on a
process this control script itself started and can still verify by
pid + start time + process name, refusing to touch an unmanaged
process holding the configured API port.

## Troubleshooting

### `runtime check` warns about local-only mode

The runtime is using SQLite; switch to PostgreSQL if this is meant to
be a shared service instance.

### Provider health is unreachable

Check `ORCHAI_AI_PROVIDER`, `ORCHAI_AI_BASE_URL`, `ORCHAI_AI_API_KEY`,
the selected model, and local process/network reachability.

### Policy says allowed but the operation still does not run

Policy approval does not override project readiness, the project
security profile, a still-required missing authorization, or adapter
capability boundaries.

### Tests fail on Windows temp directories

The root `conftest.py` defaults `--basetemp` to `.cache/pytest-tmp`
automatically (a fresh, project-local directory), because the
system-wide default (`%TEMP%/pytest-of-<user>`) has a broken ACL in
some Windows checkouts of this project. Plain `pytest` /
`uv run pytest` should work with no flags needed. If a different
location is needed:

```powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$base = Join-Path ([System.IO.Path]::GetTempPath()) "orchai-pytest-$timestamp"
.venv\Scripts\python.exe -m pytest --basetemp $base
```

Avoid reusing the same `--basetemp` directory across repeated Windows
runs, since `pytest` may fail while recreating it.

## Current Boundaries And Limits

- the API and CLI cover the current implementation baseline, not the
  full product vision (see `docs/ARCHITECTURAL-CONTRACT.md` §7)
- policy configuration is still a local/runtime-first slice, not a
  full policy engine
- provider integration covers the `stub` provider and the
  multi-provider `litellm` adapter (OpenAI, Anthropic, Gemini, Ollama,
  and other OpenAI-compatible runtimes)
- the local filesystem adapter remains the primary Project Adapter;
  a media-workspace adapter backs the Studio module
- the staged task-centric workflow is implemented, but broader
  multi-user orchestration patterns are still evolving — see
  `docs/context/identity-and-access.md`'s Migration And Rollout
  section
