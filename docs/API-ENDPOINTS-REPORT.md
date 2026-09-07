# OrchAI — API Endpoints Status Report (v0.1.11)

## How to read this report

This document is an objective x-ray of what the HTTP API (`src/orchai/interfaces/api/main.py`) actually does today, verified by direct code reading, the test suite (124 tests, unit and integration), and real calls run just now against the API to confirm the subtler points. It is not an architectural document (that already exists in `docs/architecture/API-UI-BOUNDARY.md`) — it is a checkpoint of "what is implemented and works" before moving on to real AI provider adapters.

> **v0.1.5 update:** section 9 described a "surprise" in `POST /requests` — the PLAN stage happened synchronously and without a policy gate, so the first suggestion the client saw was already `IMPLEMENT`. This wasn't an implementation nuance: it contradicted what `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` (section 3) and ADR-011's invariant #2 already specified. Fixed in this session.

> **v0.1.6 update:** `POST /requests/{id}/approve` now resolves the common `PENDING_SUGGESTION` case — when there is no pending authorization (the normal case in `SUGGESTED` mode after the PLAN gate), the endpoint internally delegates to the same gated mechanism used by `/advance` (`approve_stage: true`), instead of always responding `no_pending_authorization`. This is not a bypass: the delegated call still goes through the same policy evaluation. See section 9.

> **v0.1.7 update:** `POST /admin/db/create` and `POST /admin/db/migrate` (and the equivalent CLI commands `orchai db create`/`orchai db migrate`) were **removed** — `db sync` (`POST /admin/db/sync`, `orchai db sync`) is now the only standard database administration operation, covering both cases in a single step (creates the database if needed — PostgreSQL only, skipped without error on SQLite/local-flow — then applies migrations unconditionally). See section 2. This session also synchronized this report and the rest of the documentation with the real, complete state of the repository (the previous session had operated on a partial copy of the project, missing dozens of documents and 18 unit test files) — see `docs/STATUS.md` for the full account, including 8 pre-existing unit tests that only surfaced during this synchronization and were fixed to reflect the v0.1.5 PLAN gate.

> **v0.1.8 update:** `infrastructure/persistence/sqlite/` and `infrastructure/persistence/postgresql/` were unified into `infrastructure/persistence/db/` (migrations now live under `infrastructure/persistence/db/migrations/*.sql`, applied the same idempotent way described in section 2). No endpoint behavior changed. See `docs/STATUS.md` for the full account, including the isolated implementation of Identity and Access Control Phase 1 (`docs/TO-DO.md` Priority 1) — still with no route or command exposed.

> **v0.1.9 update:** Identity and Access Control Phase 2 implemented (`docs/TO-DO.md` Priority 1): JWT access-token issuance/validation (`JWTAccessTokenIssuer`) and SHA-256 refresh-token hashing (`Sha256RefreshTokenHasher`), plus `login()` / `refresh()` (single-use rotation) / `logout()` (idempotent) on `IdentityService`. No endpoint behavior changed — still no `/auth/*` route or CLI command exposed; that is Phase 3.

> **v0.1.10 update:** Identity and Access Control Phase 3 implemented — the phase that finally changes runtime behavior. Three new routes, `POST /auth/login` / `POST /auth/refresh` / `POST /auth/logout` (section 11), plus the `orchai auth login` / `orchai auth logout` / `orchai auth bootstrap-admin` commands. Every pre-existing route (50 of the application's 54 routes, excluding the 3 new `/auth/*` ones and the 4 docs/openapi routes) and every pre-existing CLI command (46 of 49 commands — only `auth login`, `auth bootstrap-admin`, and `api serve` are excluded, the first two because they are the bootstrap path itself, and `api serve` because it has no corresponding HTTP route) now goes through a declarative permission check — `require_permission(key)` (a FastAPI dependency) and `require_cli_permission(key)` (an explicit call at the start of the command body, not a decorator, so as not to break Typer/Click's signature introspection) — but this check is **inert by default**: `ORCHAI_AUTH_ENFORCED=false` is the rollout default (`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6), so no pre-existing endpoint/command behavior changed for anyone who doesn't flip the flag. With the flag on, a valid JWT bearer token becomes required (401 if missing/invalid), and each route/command's specific permission becomes required (403 if missing) — superusers (`is_superuser`) always pass. See section 11 for the full list of authentication routes and `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §4 for the full permission mapping. Suite now at **178 tests**.

> **v0.1.11 update:** Identity and Access Control Phase 4 implemented — the user-configuration CRUD layer the user explicitly requested as a prerequisite before moving on to the broader "user-based refactor." Seven new routes: `GET`/`POST /admin/users`, `PUT /admin/users/{id}/access-roles`, `GET`/`POST /admin/access-roles`, `PUT /admin/access-roles/{id}/permissions`, `GET /admin/projects` (section 12), plus `GET`/`PATCH /me` and `GET /me/projects` (also section 12). Equivalent CLI commands: `orchai users list|create|set-access-roles`, `orchai access-roles list|create|set-permissions`, `orchai projects list-all`, `orchai me show|update|projects`. The N:N `AccessRole` model (Phase 1) didn't change at all — instead, creating a non-superuser now requires supplying at least one `AccessRoleId` (replacing an earlier "system Default AccessRole" design the user asked to simplify away). A new, purely informational table, `project_connections` (migration `0008_project_connections.sql`), records which user connected which project — this is **not** an access-control boundary. `POST /projects` now automatically links the authenticated user when a valid token is present, a change made by capturing `require_permission`'s return value instead of discarding it — the only behavior change to a pre-existing route in this phase, and even so it doesn't change the permission check or response shape for anyone already using the route. This phase also fixed a latent gap: `permissions`/`access_roles` started empty in a fresh database, with no seeding anywhere in the code — today the full permission catalog is seeded automatically and idempotently on every identity-runtime build. See `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §8 for the full design. Suite now at **203 tests**.

> **Note (v0.2.0):** This report was last fully verified against `v0.1.11`, before the OrchAI Desktop initiative (ADR-013 through ADR-017) and its Phase 7 hardening landed. Two concrete examples of what's now stale: the execution-cancellation gap (section 7, "Known gaps" item 1) and the metrics-aggregation gap ("Known gaps" item 2) are both resolved as of `v0.2.0`, via `POST /executions/{id}/cancel` and `GET /metrics/summary`; the provider adapters this report still calls "the real Ollama/OpenAI/Anthropic adapters" (end of the usage example) were replaced by the single LiteLLM adapter back in ADR-013, before the Desktop initiative even started. The new `/modules`, `/conversations`, and `GET`/`PUT /policies/automatic` endpoints aren't documented here at all yet. See `docs/TO-DO.md`'s "Current Implementation Sequence" for what shipped since. The rest of this report is kept as a historical snapshot as of `v0.1.11` until a fuller re-audit lands as its own roadmap item.

Status legend:

- **✅ Complete** — works end to end as documented, covered by an integration test.
- **⚠️ Partial** — the endpoint responds and does something real, but doesn't cover all the behavior its name suggests (detailed in the actions column).
- **🚧 Not implemented** — no endpoint exists at all; mentioned here only to make the gap explicit.

The API is split into two surfaces (ADR-011): `/requests/*` is the **chat-first** surface, meant as the primary entry point for external clients (chat UIs, apps). The other groups (`/tasks`, `/authorizations`, `/executions`, etc.) are the **operational**, fine-grained-control surface — used both by operators/scripts and internally by the chat-first surface itself.

---

## 1. System and Providers

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `GET /` | ✅ | API index | Lists the main entry points and the recommended database dialect (postgresql). Doesn't touch the database. |
| `GET /health` | ✅ | Simple health check | Returns `{"status": "ok", "version": "0.1.11"}`. Doesn't validate the database or provider. |
| `GET /settings/runtime` | ✅ | Configuration diagnostics | Shows the effective resolved configuration (database, AI provider, API host/port) — useful for confirming which database/URL is actually in use before operating. |
| `GET /runtime/check` | ✅ | Consolidated diagnostics | Tests real database connectivity (`SELECT 1`) and the configured AI provider's healthcheck, returning `ready: true/false` and warnings when something isn't production-ready. |
| `GET /providers/settings` | ✅ | AI provider configuration | Shows which provider is configured (`stub` or `litellm`), model, timeout, whether the API key is present — without exposing the key itself. |
| `GET /providers/capabilities` | ✅ | Declared capabilities | Lists the capabilities the provider claims to support. Since ADR-013, the `litellm` provider is the only real implementation (covering OpenAI, Anthropic, Gemini, Ollama, and other OpenAI-API-compatible runtimes through a single adapter); `stub` remains available for local smoke tests. |
| `GET /providers/health` | ✅ | Provider healthcheck | Performs a real reachability check against the configured provider. |

## 2. Database Administration

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `POST /admin/db/sync` | ✅ | **Only database administration operation** | Since v0.1.7, this is the only database administration endpoint — `POST /admin/db/create` and `POST /admin/db/migrate` were removed. Creates the database if needed (only has a real effect on PostgreSQL, via `CREATE DATABASE`, checking beforehand whether it already exists) and then applies the versioned SQL migrations unconditionally (`infrastructure/persistence/db/migrations/*.sql`, idempotent, recording the version in `schema_migrations`). On SQLite/local-flow the creation step is simply skipped — `create_status: "skipped_non_postgresql"`, with an explicit message that the operation doesn't apply to the selected database/local-flow — **without error**; migrations are applied normally. Equivalent to the `orchai db sync` CLI command, which has the same informative behavior (no error/non-zero exit code for SQLite). |

## 3. Projects

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `GET /projects/discover` | ✅ | One-off exploration (not persisted) | Scans a local directory and lists classified resources (files), without writing anything to the database. Useful for "look before connecting." |
| `GET /projects/readiness` | ✅ | One-off assessment (not persisted) | Assesses a directory's readiness level (`LEVEL_0`..`LEVEL_3`, based on having `.git`, tests, CI) without persisting. |
| `GET /projects/security` | ✅ | One-off assessment (not persisted) | Derives the observed security profile (what can be read/persisted/shared with a provider) from disk, without persisting. |
| `POST /projects` | ✅ | **Connect a project** | This is the step that actually registers the project: assesses the directory's readiness/security and persists a `Project` record in the database, returning `project_id`. This is the real starting point of any flow. |
| `GET /projects` | ✅ | List connected projects | Lists projects already registered in the database. |
| `GET /projects/lookup` | ✅ | Find a project by path | Looks up an already-registered project by `project_root`, avoiding duplicate registration. |
| `GET /projects/{project_id}` | ✅ | Project detail | Returns the persisted record, including effective vs. observed readiness/security levels. |
| `PATCH /projects/{project_id}/security` | ✅ | Adjust security policy | Allows manually raising/restricting a project's effective security profile (e.g. allowing sharing with a cloud provider), independent of what was observed on disk. |

## 4. Tasks

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `POST /tasks` | ✅ | Create a task | Creates a `Task` linked to a project, in `CREATED` state, with the desired `execution_mode` (`MANUAL`/`SUGGESTED`/`AUTOMATIC`). |
| `GET /tasks` | ✅ | List tasks | With filtering by project and state. |
| `GET /tasks/{task_id}` | ✅ | Task detail | Current state + available transitions from there (state machine). |
| `GET /tasks/{task_id}/snapshot` | ✅ | Consolidated view | Combines a task's authorizations, executions, suggestions, events, audit, and metrics into a single response — this is the basis of `GET /requests/{id}/flow`. |
| `POST /tasks/{task_id}/transition` | ✅ | Manual state transition | Moves the task directly to another state machine state (operational/administrative use, doesn't go through suggestion or authorization). |
| `POST /tasks/{task_id}/advance` | ✅ | **Advance one workflow stage** | This is the real engine of the flow: PLAN → IMPLEMENT → REVIEW → VALIDATE → TEST → DOCUMENT. Each call automatically resolves the next stage (via `SuggestionEngine`), evaluates policy, and if `approve_stage: true`, requests+grants authorization and executes the step via the configured AI provider. |

## 5. Policies

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `POST /policies/evaluate` | ✅ | Simulate a policy decision | Evaluates whether an operation would be allowed (without executing anything), useful for debugging/dry-runs. **Important:** this is evaluation only — there is no endpoint to *configure* policy limits at runtime (see "Known gaps" below). |

## 6. Authorizations

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `POST /authorizations/request` | ✅ | Request authorization | Creates a pending authorization record (no decision) for a `role`+`action` on a task. |
| `POST /authorizations/{id}/decision` | ✅ | Decide an authorization | Records an explicit decision (`GRANTED`/`REJECTED`/`EXPIRED`/`REVOKED`). This is the only way for an authorization to stop being "pending." |
| `GET /authorizations` | ✅ | List/filter authorizations | Supports filtering by `task_id`, `status`, and `pending_only` (added in this session — previously only filtered by `task_id`). |
| `GET /authorizations/{id}` | ✅ | Authorization detail | State, most recent decision, requested context scope. |

## 7. Executions

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `POST /executions/request` | ✅ | Create an authorized execution | Links an execution to an already-granted authorization — doesn't run anything yet. |
| `POST /executions/{id}/run` | ✅ | **Run synchronously** | Runs the execution to completion (calls the AI provider, resolves the result) and only responds when it finishes. |
| `POST /executions/{id}/dispatch` | ✅ | **Run asynchronously** | Schedules the execution as a background asyncio task and responds immediately with `dispatched: true`; the client polls `GET /executions/{id}` afterward to see when it reaches `COMPLETED`. Validated with a polling test. |
| `POST /executions/{id}/transition` | ✅ | Manual state transition | Manually moves the execution between states (`PREPARING`, `STARTED`, `RUNNING`, etc.) — operational/debug use. |
| `POST /executions/{id}/complete` | ✅ | Manually record a result | Closes an execution with an explicit result/errors/resource usage, without going through the AI provider — used by external integrations or tests. |
| `POST /executions/{id}/resolve-context` | ✅ | Resolve authorized context | Materializes the content of authorized files (e.g. reads `README.md` from disk) and persists a resolution record. |
| `GET /executions/{id}/context` | ✅ | View already-resolved context | Lists an execution's context resolution records. |
| `GET /executions` / `GET /executions/{id}` | ✅ | List/detail executions | With filtering by task, project, and state. |
| — (cancellation) | 🚧 | — | **Doesn't actually exist.** There is a `cancel()` method declared on the interface (`ExecutionRepository` port) but no class implements it and no endpoint calls it. It's technically possible to force `POST /executions/{id}/transition` with `target_state: CANCELLED` (the state machine accepts that target), but that only changes the status in the database — it does **not** stop an execution already dispatched to run in the background. |

## 8. Observability (Audit, Metrics, Events, Suggestions)

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `GET /audit` | ✅ | Audit trail | Lists audit records (who did what, when, with what outcome), generated automatically on every relevant domain event. Now includes `correlation_id`/`causation_id`. |
| `GET /audit/{id}` | ✅ | Record detail | Added in this session. |
| `GET /events` | ✅ | Domain event history | Lists raw events (`TASK_CREATED`, `EXECUTION_COMPLETED`, etc.), filterable by type/task/execution/project. |
| `GET /metrics` | ⚠️ | Raw metric records | Lists individual records generated automatically per execution (e.g. `execution.success`, tokens, cost). **No aggregation** — no endpoint computes sums/averages/success rates over time; anyone wanting a dashboard has to aggregate the raw records client-side. |
| — (metrics aggregation) | 🚧 | — | **Doesn't exist.** `MetricsRepository` only has `add_many`/`list` — no aggregation method, neither in the domain nor the infrastructure. |
| `GET /suggestions` | ✅ | List suggestions | Filterable by task. |
| `GET /suggestions/{id}` | ✅ | Suggestion detail | Added in this session. |
| `POST /tasks/{task_id}/suggestions` | ✅ | Generate a suggestion on demand | Added in this session — previously only generated automatically inside `advance`/`local-flow`. |
| `POST /suggestions/{id}/accept` | ✅ | Accept a suggestion | Added in this session. Important: this only marks the record `ACCEPTED` — it does **not** by itself trigger authorization or execution (that still only happens inside `advance`, see the note in section 9). |
| `POST /suggestions/{id}/reject` | ✅ | Reject a suggestion | Added in this session. |

## 9. Chat-First Surface (`/requests/*`) — primary entry point

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `POST /requests` | ✅ | **Create a natural-language request** | Accepts `project_root` + `prompt` (+ optionally `role`/`action`/`model`). Registers the project (idempotent, by `root_location`), creates the task, and advances **exactly one gated stage** — PLAN, the first one. Fixed in this session: previously, the PLAN stage happened synchronously and without any gate, and the first suggestion the client saw was already `IMPLEMENT` (task already in `PLANNED`) — a real deviation from what the documentation specifies, not a nuance. Today the first suggestion is always `PLAN`/`TASK_PLANNER`, evaluated by the same policy as any other stage: in `SUGGESTED` mode (default) without `approve_suggestion: true`, the call stops at `PLANNING` with the suggestion `PRESENTED` and `blocked_reason: "suggested_mode_requires_approval"` — no authorization is created. With `approve_suggestion: true`, the PLAN stage actually runs (authorization granted + execution) and the task stops at `PLANNED`, ready for the next `advance`. Confirmed empirically (not just by reading code) by running the actual call. |
| `GET /requests/{id}/flow` | ✅ | **Observe the full state** | Unified view (task + authorizations + executions + suggestions + audit + metrics), with a derived `status` field (`PENDING_SUGGESTION`, `PENDING_AUTHORIZATION`, `RUNNING`, `COMPLETED`, etc.) — fixed in this session (see the note below). |
| `POST /requests/{id}/approve` | ✅ | **Approve and continue, covering both possible cases** | Re-evaluated and fixed in v0.1.6. Covers two cases: (1) a pending/undecided authorization already exists (e.g. created externally via a direct `POST /authorizations/request` against the task) — it's granted directly, as before; (2) the common case in `SUGGESTED` mode, where `run_task_workflow_stage` returns before creating any authorization when policy blocks, leaving only the `PRESENTED` suggestion — now, if there's no pending authorization but there is a `PRESENTED` suggestion, `/approve` internally delegates to the same gated mechanism as `/advance` (`approve_stage: true`). This isn't a bypass: the delegated call still goes through the same policy evaluation, and if it's refused (e.g. mode/config changed), the response comes back with `blocked_reason` populated and `approved: false`, exactly as `/advance` would report. As a result, `/approve` optionally accepts the same context fields as `/advance` (`context_paths`, `documentation_path`, `test_args`, `model`, `provider_target`) — only required when the current stage needs them (e.g. PLAN requires `context_paths`); they're ignored when case (1) applies. |
| `POST /requests/{id}/advance` | ✅ | **Advance to the next stage** | The chat-first equivalent of `POST /tasks/{task_id}/advance` — this is the endpoint, called with `approve_stage: true`, that actually makes the task progress (PLAN → IMPLEMENT → REVIEW → ...), granting authorization and executing via the configured provider. |

## 10. Legacy Flows (kept for compatibility)

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `POST /flows/local` | ✅ | Local demo flow | Precursor to `/requests` — uses exactly the same internal mechanism (`run_local_flow`), so it inherits the same fix: creates a project+task and advances only the first gated stage (PLAN), not jumping straight to a full execution. Kept for compatibility. |
| `POST /projects/operations` | ✅ | Protected project operation | Runs a specific operation on the Project Adapter (read, write, run a command/test) through policy+authorization, outside the PLAN→...→DOCUMENT cycle. The task created here still has to pass through `PLANNED` before the operation starts (a mechanical requirement of the state machine) — this hop was also fixed in this session to go through the same suggestion/policy gate (`TASK_PLANNER` role/`PLAN` action), instead of happening with no record at all. A single `approve_operation: true` covers both this bootstrap step and the operation itself. |

---

## 11. Authentication (ADR-012, Phase 3)

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `POST /auth/login` | ✅ | **Authenticate** | Exchanges `username`/`password` for an access/refresh token pair. `401` for invalid credentials or an inactive user. Doesn't require prior authentication — it's the entry point. CLI equivalent: `orchai auth login`, which persists the token pair to `~/.orchai/credentials.json` (permission `0600`). |
| `POST /auth/refresh` | ✅ | **Renew a session** | Exchanges a valid refresh token for a new access/refresh pair (single-use rotation — the used token is invalidated in the same step). `401` for a missing, expired, invalid, or already-used token. |
| `POST /auth/logout` | ✅ | **End a session** | Revokes a refresh token (idempotent — calling it again isn't an error). Requires authentication (any valid user), no specific permission. CLI equivalent: `orchai auth logout`, which also clears `~/.orchai/credentials.json`. |
| `orchai auth bootstrap-admin` | ✅ | **Create the first superuser** | No equivalent HTTP route (ADR-012 §8) — solves the chicken-and-egg problem: only works while the database has zero users, without requiring an already-authenticated caller. Username/password come from `--username`/`--password` or from `ORCHAI_ADMIN_USERNAME`/`ORCHAI_ADMIN_PASSWORD`. |

All other pre-existing routes and commands now declare a required permission (`require_permission(key)` / `require_cli_permission(key)`), but that check is only actually enforced when `ORCHAI_AUTH_ENFORCED=true` — the default is `false` (inert), preserving the behavior of every route/command documented in sections 1 through 10 above for anyone who hasn't turned the flag on. The full permission mapping per route/command is in `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §4, not duplicated here. A superuser token (`is_superuser`) always satisfies any permission.

User management gained its own surface in Phase 4 (section 12) — `admin:manage_users` is no longer a permission without a consumer.

---

## 12. User Configuration — Admin and Self-Service (ADR-012, Phase 4)

| Endpoint | Status | Role in the flow | What it actually does |
|---|---|---|---|
| `GET /admin/users` | ✅ | **List all users** | Returns every field of each user (username, email, is_superuser, is_active, timestamps, `access_roles` resolved by name, `connected_project_ids`) — except `password_hash`, never exposed. Requires `admin:manage_users`. |
| `POST /admin/users` | ✅ | **Create a new user** | Creates the user and immediately assigns their initial `AccessRole`s (`role_ids`). A non-superuser with no `role_id` at all is rejected with `400` (`UserRequiresAccessRoleError`) — replaces the discarded "system Default AccessRole" design with a simpler rule giving the same practical guarantee. Duplicate username → `409`. Requires `admin:manage_users`. |
| `PUT /admin/users/{id}/access-roles` | ✅ | **Replace a user's `AccessRole`s** | A *replace-all* operation, not incremental: the submitted list becomes the complete set. Emptying it to zero is rejected (`400`) unless the user is a superuser. Requires `admin:manage_users`. |
| `GET /admin/access-roles` | ✅ | **List all `AccessRole`s** | Each item comes with `permissions` and `users` fully resolved (not just ids). Requires `admin:manage_users`. |
| `POST /admin/access-roles` | ✅ | **Create an `AccessRole`** | Duplicate name → `409`. Reuses `IdentityService.create_access_role`, already tested since Phase 1. Requires `admin:manage_users`. |
| `PUT /admin/access-roles/{id}/permissions` | ✅ | **Replace an `AccessRole`'s permission bundle** | Also *replace-all*. `Permission` remains a fixed system catalog — there's no endpoint to create new permissions, only to (re)assign them to an `AccessRole`. Requires `admin:manage_users`. |
| `GET /admin/projects` | ✅ | **Administrative project directory** | Lists every project in the system with `capabilities`, readiness levels, and `connected_user_ids` — unlike `GET /projects` (`projects:read`), which lists projects without those administrative details. Requires the new `admin:manage_projects` permission. |
| `GET /me` | ✅ | **View your own profile** | Returns the same fields as `GET /admin/users` for the authenticated user, including `access_roles` and `connected_project_ids`. |
| `PATCH /me` | ✅ | **Update your own profile** | Only accepts `username`/`email` — there's no field for a user to change their own `AccessRole` or `is_superuser`. Duplicate username → `409`. |
| `GET /me/projects` | ✅ | **Projects connected by the logged-in user** | Reads from `project_connections` (see the note below). |

**Important about `/me`:** these three routes don't use `require_permission()` (which becomes a no-op when `ORCHAI_AUTH_ENFORCED=false`, leaving "who is the current user" undefined). They use their own dependency, `require_authenticated_user()` (`require_authenticated_cli_user()` on the CLI), which **always** requires a valid bearer token, regardless of the flag — there's no sensible "no-op" reading of "show my own profile."

**`project_connections` is not access control.** It's a purely informational reference — "this user connected this project to OrchAI" — that doesn't restrict reading, registering, or operating on any project, and a project can be connected by multiple users. `POST /projects` now automatically links the authenticated caller (when a valid token is present) to this record. It lives in the same database as `projects` (not the identity database, which stays fixed for security), since it's descriptive project metadata, not identity data.

---

## Known gaps (confirmed by reading code, not assumption)

1. **Execution cancellation** — doesn't actually exist. The port declares `cancel()`, nothing implements it. `target_state: CANCELLED` via manual transition only changes the status in the database, it doesn't stop anything running in the background.
2. **Metrics aggregation** — only per-execution raw record listing exists; no sum/average/rate over time or by project.
3. **Runtime configuration of `AutomaticExecutionPolicy`** — zero exposure in the CLI or API. The limits of `AUTOMATIC` mode (which `role`+`action` are allowed automatically, whether the model can be changed, whether context can be expanded) are today only the hardcoded default value in the code (`allowed_operations=((DEVELOPER, IMPLEMENT),)`); there's no way for a user to configure this without editing the source code. **This became more visible with the v0.1.5 PLAN gate fix:** since PLAN now also needs to be in `AutomaticExecutionPolicy`'s allowlist to skip approval, and `(TASK_PLANNER, PLAN)` isn't in the default allowlist, today **no** request in `AUTOMATIC` mode via CLI/API can get past the first stage without this configuration — `AUTOMATIC` mode only actually works through the internal Python API (`RunLocalFlowCommand`/`RunProjectOperationCommand` with a custom `automatic_policy`), not through the public CLI/API. This isn't a regression from the fix — it's the policy being correctly applied, revealing a gap that already existed (the config was never exposed); but before the fix it went unnoticed because PLAN itself wasn't evaluated.
4. **`ORCHAI_AUTH_ENFORCED` is still `false` by default** (section 11) — the permission check exists on every route/command, but is inert until this flag is deliberately turned on (an intentional rollout, `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6, not a bug). Without it on, the API/CLI remain open exactly as before Phase 3.

**Resolved** (kept here for traceability):

- ~~`/requests/{id}/approve` doesn't resolve the common `PENDING_SUGGESTION` case~~ (v0.1.6) — fixed: see section 9. `/approve` now delegates to the same gated mechanism as `/advance` when only a `PRESENTED` suggestion exists.
- ~~`POST /admin/db/create` raised a hard error in the CLI (`typer.BadParameter`) for a non-PostgreSQL database, but returned an informative 200 response in the API for the same case~~ (v0.1.7) — rather than aligning the two, `db create` and `db migrate` were **removed**; `db sync`/`POST /admin/db/sync` is now the only database administration operation, covering both cases in a single step — see section 2.
- ~~User management had no surface of its own~~ (v0.1.11) — resolved by Phase 4: see section 12. `orchai users *` / `orchai access-roles *` / `GET,POST /admin/users` / `GET,POST /admin/access-roles` now exist and consume `admin:manage_users`.

---

## Full API Usage Example

Scenario: connect a project, create a request, advance through to the **code review** stage. The entire sequence below was **actually run** against the API (via `TestClient`, not just inferred from code) to make sure the example reflects real behavior — already with the PLAN gate fix applied in this session (see the update note at the top of this document).

```bash
BASE=http://localhost:8000
DB="sqlite:///./demo.db"   # or omit it to use the PostgreSQL default

# 1. Connect (register) the project — optional as a standalone step, since
#    step 2's /requests already registers the project on its own (upsert by
#    path), but doing it here makes project_id available for filters later.
curl -s -X POST "$BASE/projects" -H 'Content-Type: application/json' -d '{
  "project_root": "/path/to/your/project",
  "database_url": "'"$DB"'"
}'
# → { "project_id": "…", "readiness_level": "LEVEL_2_VALIDATABLE", ... }

# 2. Create the natural-language request (chat-first)
curl -s -X POST "$BASE/requests" -H 'Content-Type: application/json' -d '{
  "project_root": "/path/to/your/project",
  "prompt": "Implement email validation on user sign-up",
  "context_paths": ["src/signup.py"],
  "database_url": "'"$DB"'"
}'
# → { "request_id": "…", "status": "PENDING_SUGGESTION",
#     "suggestion": { "suggested_role": "TASK_PLANNER", "suggested_action": "PLAN", ... } }
REQUEST_ID="…"   # copy the returned request_id
```

The first suggestion is now always `PLAN`/`TASK_PLANNER`, exactly as `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` (section 3) describes — "the next step after connecting" really is to plan, not implement. The task stays at `PLANNING`, awaiting approval like any other stage.

```bash
# 3. Advance to PLAN, explicitly approving — this stage now actually runs
#    (authorization + execution), like any other stage
curl -s -X POST "$BASE/requests/$REQUEST_ID/advance" -H 'Content-Type: application/json' -d '{
  "context_paths": ["src/signup.py"],
  "approve_stage": true,
  "database_url": "'"$DB"'"
}'
# → { "stage": "PLAN", "task_state": "PLANNED", "execution_state": "COMPLETED",
#     "output": "Stub provider processed 1 authorized context item(s)." }

# 4. Advance to IMPLEMENT
curl -s -X POST "$BASE/requests/$REQUEST_ID/advance" -H 'Content-Type: application/json' -d '{
  "context_paths": ["src/signup.py"],
  "approve_stage": true,
  "database_url": "'"$DB"'"
}'
# → { "stage": "IMPLEMENT", "task_state": "IMPLEMENTED", "execution_state": "COMPLETED",
#     "output": "Stub provider processed 1 authorized context item(s)." }

# 5. Advance to REVIEW — the code review stage you asked for
curl -s -X POST "$BASE/requests/$REQUEST_ID/advance" -H 'Content-Type: application/json' -d '{
  "context_paths": ["src/signup.py"],
  "approve_stage": true,
  "database_url": "'"$DB"'"
}'
# → { "stage": "REVIEW", "task_state": "REVIEWING", "execution_state": "COMPLETED",
#     "output": "Stub provider processed 1 authorized context item(s)." }

# 6. At any point, see the full state of the request
curl -s "$BASE/requests/$REQUEST_ID/flow?database_url=$DB"
# → task (state=REVIEWING), authorizations, executions, suggestions, audit, and
#   metrics, all together. A new suggestion (for VALIDATE) already appears here,
#   marked PRESENTED, because the next stage also requires approval.
```

Notes about the example:

- Each call to `/advance` resolves the next stage on its own (via the `SuggestionEngine`) — there's no need to pass `stage` explicitly, unless you want to force a specific out-of-order step.
- `approve_stage: true` is what actually authorizes and executes the stage, **for any stage, including PLAN**. Without it, the call stops in state `blocked_reason: "suggested_mode_requires_approval"`, without creating any authorization (the task stays at `PLANNING`, never even reaching `PLANNED`). As of v0.1.6, `POST /requests/{id}/approve` also resolves this case — calling it (passing `context_paths` when the blocked stage requires context, like PLAN) has the same effect as repeating `/advance` with `approve_stage: true`.
- If you try to advance once more after step 5 (toward `VALIDATE`), the call tends to block with `blocked_reason: "validation_requires_level_2"` unless the connected project already has recognized test structure on disk (readiness level `LEVEL_2_VALIDATABLE`) — that's the project's readiness policy, not a bug, but worth knowing before building a fully automated end-to-end flow.
- The `"output": "Stub provider processed …"` reflects that execution currently runs against the `stub` provider (deterministic, no cost, no real AI) — this is exactly the point the real Ollama/OpenAI/Anthropic adapters were meant to replace.
