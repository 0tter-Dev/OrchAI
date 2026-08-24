# OrchAI Project Status

## Purpose

This document provides the high-level state of the OrchAI project.

It is a project-state document, not a task backlog and not a replacement
for architectural documentation.

## Status Vocabulary

  -----------------------------------------------------------------------
  Status                              Meaning
  ----------------------------------- -----------------------------------
  `DEFINED`                           The concept is documented
                                      sufficiently for the current phase.

  `DECIDED`                           An architectural or implementation
                                      decision has been explicitly
                                      accepted.

  `PARTIAL`                           The area is defined or implemented
                                      only in part.

  `IN_PROGRESS`                       Active implementation or refinement
                                      is underway.

  `IMPLEMENTED`                       The current intended scope is
                                      implemented and validated.

  `BLOCKED`                           Progress depends on an unresolved
                                      external or architectural issue.

  `PENDING`                           Intentionally deferred to a later
                                      phase.
  -----------------------------------------------------------------------

## Current State

Current version: `v0.1.11`

  Area                                 Status
  ------------------------------------ -----------
  Architectural Contract               `DEFINED`
  High-Level Architecture              `DEFINED`
  Component Boundaries                 `DEFINED`
  Implementation Map                   `DEFINED`
  Core Domain Model                    `IMPLEMENTED`
  Authorization                        `IMPLEMENTED`
  Task Lifecycle                       `IMPLEMENTED`
  Execution Model                      `IMPLEMENTED`
  Event Model                          `IMPLEMENTED`
  Roles and Actions                    `IMPLEMENTED`
  Models and Providers                 `IMPLEMENTED`
  Context Management                   `IMPLEMENTED`
  Project Integration                  `IMPLEMENTED`
  Capabilities                         `IMPLEMENTED`
  Audit and Metrics                    `IMPLEMENTED`
  Suggestions                          `IMPLEMENTED`
  Configuration                        `IMPLEMENTED`
  Modular Monolith Structure           `DECIDED`
  Physical Repository Structure        `DECIDED`
  Technology Stack                     `DECIDED`
  Persistence Strategy                 `IMPLEMENTED`
  Event Dispatch Strategy              `DECIDED`
  Async Execution Baseline             `DECIDED`
  AI Provider Boundary                 `DECIDED`
  Project Content Ownership Boundary   `DECIDED`
  Project Security / Readiness Gates   `IMPLEMENTED`
  API/UI Boundary                      `DECIDED`
  Chat-First Request Interface         `DECIDED`
  Identity and Access Management       `IMPLEMENTED`
  Execution Mode Baseline              `IMPLEMENTED`
  Application Implementation           `IN_PROGRESS`
  Domain Implementation                `IMPLEMENTED`
  Infrastructure Implementation        `IN_PROGRESS`
  API Implementation (operational)     `IMPLEMENTED`
  API Implementation (chat-first)      `IMPLEMENTED`
  CLI Implementation                   `IMPLEMENTED`
  Automated Test Suite                 `IMPLEMENTED`
  Deployment Implementation            `PENDING`

## Current Phase

**Phase: Chat-First Request Interface v0.1.11**

The project has a consolidated architecture and domain foundation, an
accepted technology baseline, a defined physical code structure, and
ADRs for the major implementation decisions.

The operational foundation is implemented: task lifecycle, authorization,
execution, context resolution, project adapter boundaries, a central
application Orchestrator for local flows and protected project operations,
an async Execution Engine with a replaceable AI Provider Adapter
boundary, filesystem Project Adapter discovery and protected operations,
context-resolution metadata, event-derived audit and metrics records,
state-aware suggestions, execution-mode enforcement for `MANUAL`,
`SUGGESTED`, and `AUTOMATIC`, an initial policy slice kept separate from
authorization, persisted effective-vs-observed project
readiness/security, and SQLAlchemy-backed durable persistence for the
initial operational and historical aggregates.

A Chat-First Request Interface has been introduced (ADR-011) as the
primary API surface for external clients modeled after a conversational
AI interface. The `/requests` resource projects the Task domain toward
a user who provides a project, model, role, action, and prompt — without
requiring knowledge of the internal orchestration steps.

PostgreSQL is now the explicit production default throughout
configuration, the CLI, and the API: `ORCHAI_DATABASE_URL` resolves to a
local PostgreSQL connection string when left unset entirely. SQLite
remains fully supported, but strictly as a secondary option for fast,
dependency-free local development and automated tests, opted into with a
`sqlite:///...` URL or the shorter `sqlite`/`local` alias.

The CLI and API surfaces have been expanded to correctly cover every
already-implemented application capability across tasks, executions,
authorization, suggestions, audit, and metrics, while keeping the
`/requests` chat-first surface as the primary usage concept:

- `orchai audit show` / `GET /audit/{audit_id}` retrieve a single audit
  record, and correlation/causation identifiers are now surfaced in both
  `audit list` output and the audit serialization;
- `orchai suggestions show|generate|accept|reject` and their
  `GET /suggestions/{id}`, `POST /tasks/{task_id}/suggestions`,
  `POST /suggestions/{id}/accept`, `POST /suggestions/{id}/reject`
  API counterparts round out suggestion lifecycle management, which was
  previously read-only through the interfaces;
- `orchai executions complete` gained `--metadata` /
  `--resource-metadata` JSON options so execution outcomes can carry the
  same metadata the domain model already supports;
- authorization listing (`orchai authorizations list`,
  `GET /authorizations`) now supports filtering by decision `status` and
  by `pending_only`, pushed down to the repository layer instead of
  requiring callers to filter client-side.

Two correctness bugs were found and fixed while doing this work, both in
the primary chat-first flow:

- `POST /requests/{id}/approve` compared authorization/suggestion status
  against a literal `"PENDING"` string that neither
  `AuthorizationDecisionStatus` nor `SuggestionStatus` defines, so the
  endpoint could never find a pending authorization to approve. It now
  checks `status is None` (authorization) and
  `status is SuggestionStatus.PRESENTED` (suggestion), matching the
  actual domain semantics of "pending".
- Selection of "the most recent" authorization, suggestion, or execution
  in `_serialize_request_flow` and in the approve handler relied on list
  position (`[-1]`, `reversed()`), which silently picks the wrong record
  under the SQLAlchemy repositories (which order `list()` results
  newest-first) versus the in-memory repositories (which preserve
  insertion order). Selection is now explicit by timestamp
  (`max(..., key=lambda r: r.created_at)`), independent of repository
  ordering.

A third, more consequential correctness bug was found and fixed in v0.1.5,
in the same chat-first flow: `POST /requests` (and its `POST /flows/local`
and `POST /projects/operations` siblings, which share the same
`run_local_flow`/`run_project_operation` orchestration code) transitioned a
freshly created task `CREATED -> PLANNING -> PLANNED` unconditionally and
without any suggestion/policy evaluation, regardless of execution mode.
This was a genuine deviation from
`docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` (section 3) and ADR-011
invariant #2, not merely an implementation nuance: the first suggestion a
caller ever saw was `IMPLEMENT` (the task was already `PLANNED`), never
`PLAN`, and the PLAN stage carried no authorization, execution, or audit
trail of its own. Both entry points now delegate to the same gated,
single-stage-advance mechanism already used by `POST /tasks/{id}/advance`
(`run_task_workflow_stage`), so no code path — regardless of storage
backend — can silently complete a stage. `AUTOMATIC` execution mode is the
only way to skip the approval step for a given stage, and only for a
`(role, action)` pair explicitly present in
`AutomaticExecutionPolicy.allowed_operations`, configured in advance. See
the ADR-011 amendment note and `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md`
sections 3 and 8 for the corrected behavior, and
`docs/API-ENDPOINTS-REPORT.md` for the updated worked example.

One practical consequence surfaced by this fix: since `AutomaticExecutionPolicy`
still has zero runtime configuration exposure in the CLI or API (a
previously known gap), `AUTOMATIC` mode can no longer complete *any* stage
through the public CLI/API surface out of the box — the default policy only
allows `(DEVELOPER, IMPLEMENT)`, and PLAN is now correctly gated too. It
still works when driven through the Python API with a custom
`AutomaticExecutionPolicy`, which is how the new regression tests validate
it.

The `alembic` dependency was removed from `pyproject.toml` in v0.1.5: it
was declared but never imported anywhere in `src/` (the project uses a
hand-rolled raw-SQL migration runner, `SQLAlchemyDatabase.migrate()`, not
Alembic). `uv.lock` was regenerated accordingly.

Two follow-up findings were investigated and closed out after v0.1.5:

- A suspected incompatibility between `pydantic==2.13.4` and Python 3.14
  (`TypeError: _eval_type() got an unexpected keyword argument
  'prefer_fwd_module'`) turned out **not** to be a real project issue: it
  only reproduced against Python `3.14.0rc2`, a stale pre-release build
  that this sandbox's local `uv` Python index happened to offer. Against
  the actual final release, `3.14.7`, the full test suite passes cleanly
  with the project's exact pinned dependencies unchanged. No code or
  dependency change was needed; this is recorded here so it is not
  re-investigated as a live bug in a future session.
- The `StarletteDeprecationWarning: Using httpx with starlette.testclient
  is deprecated; install httpx2 instead` warning seen in test runs was
  real and is now fixed: `httpx2` (a separate package from `httpx`, not a
  version of it) is added to the `dev` dependency group in
  `pyproject.toml`, since it is only needed by `starlette.testclient`
  in tests — the runtime `httpx` dependency used by the Ollama/OpenAI
  provider adapters is untouched. Verified with
  `pytest -W error::DeprecationWarning`: zero warnings remain.

Two more gaps, both already known and flagged as candidates in
`docs/API-ENDPOINTS-REPORT.md`, were reassessed and closed in v0.1.6:

- `POST /requests/{id}/approve` could not resolve the common SUGGESTED-mode
  case: `run_task_workflow_stage` returns before ever creating an
  Authorization when policy blocks (the normal outcome right after the
  v0.1.5 PLAN-gate fix), leaving only a suggestion in `PRESENTED` status —
  so `/approve`, which only ever looked for a pending Authorization, always
  reported `no_pending_authorization` in that case. It now covers both
  cases: a standalone pending Authorization (e.g. one created directly via
  `POST /authorizations/request`) is still granted directly; otherwise, if
  a `PRESENTED` suggestion exists, `/approve` delegates internally to the
  same gated single-stage-advance mechanism used by `/advance`
  (`approve_stage=true`) — still evaluated by policy, not a bypass. Because
  of this, `/approve` now optionally accepts the same passthrough fields as
  `/advance` (`context_paths`, `documentation_path`, `test_args`, `model`,
  `provider_target`), needed only when the currently blocked stage itself
  requires them (e.g. PLAN requires `context_paths`).
- `POST /admin/db/create` returned a soft, informative response for a
  non-PostgreSQL target, but the CLI's `orchai db create` raised a hard
  error (`typer.BadParameter`) for the exact same case. Both now behave the
  same way: they validate, then simply inform the user that the operation
  does not apply to the currently selected local-flow/SQLite database, with
  no error. A new `db sync` operation (`POST /admin/db/sync`,
  `orchai db sync`) was also added, combining `create` and `migrate` into
  the single step operators actually want when bringing a database up to
  date: create it if needed (skipped, not an error, for a non-PostgreSQL
  target) and then apply migrations unconditionally.

In v0.1.7, `db create` and `db migrate` were reassessed again and this
time **fully removed** rather than aligned: `POST /admin/db/create`,
`POST /admin/db/migrate`, `orchai db create`, and `orchai db migrate` no
longer exist as endpoints or commands anywhere in the project.
`db sync`/`POST /admin/db/sync` is now the single, sole database
administration operation, covering both cases (create-if-needed, then
migrate) in one step; its informational messaging for non-PostgreSQL
targets (added in v0.1.6) is preserved. Every mention of the removed
`create`/`migrate` operations was swept from the CLI, the API, the test
suite, and the documentation (`README.md`,
`docs/API-ENDPOINTS-REPORT.md`, `docs/USER-ONBOARDING.md`,
`docs/USER-OPERATIONS-GUIDE.md`,
`docs/architecture/API-UI-BOUNDARY.md`,
`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`,
`docs/architecture/PERSISTENCE-STRATEGY.md`).

This same v0.1.7 pass also found and fixed a data-integrity problem in
the working copy this project was being developed against: it was
missing 38 documentation files and 18 unit test files that exist in the
authoritative, git-tracked repository (no application source code was
missing — the handful of genuinely empty `src/` directories were
confirmed empty in the authoritative repository too). Once the missing
unit tests were restored, 8 of them failed immediately, all as a direct
and previously invisible consequence of the v0.1.5 PLAN-stage gate fix
described above (`run_task_workflow_stage` now stops a `CREATED` task at
`PLANNING`/`BLOCKED` instead of silently completing PLAN, and
`run_local_flow` now correctly transitions a failed execution to
`BLOCKED` instead of leaving it stuck in `IMPLEMENTING`). These 8 tests
were updated to assert the corrected, already-intended behavior; no
production code changed as a result. The full suite — now 124 tests
after also deduplicating overlapping `db sync` coverage — passes
cleanly, including under `pytest -W error::DeprecationWarning`.

In v0.1.8, `docs/domains/STATUS.md` — found stale during the v0.1.7 audit
(it still marked every domain `PARTIAL` from a 2026-08-20 snapshot, while
this document and the individual domain documents already reflected their
current implemented-and-tested state) — was reconciled: 13 of its 14
domains now read `IMPLEMENTED`, matching this document; Metrics stays
`PARTIAL` (see that file for why). This closes the one documentation
defect the v0.1.7 audit found.

Also in v0.1.8, `infrastructure/persistence/sqlite/` and
`infrastructure/persistence/postgresql/` were merged into a single
`infrastructure/persistence/db/` (`db/admin.py` + `db/migrations/`), and
`PostgreSQLDatabaseAdmin`/`PostgreSQLDatabaseTarget`/
`parse_postgresql_target` were renamed to the generic `DatabaseAdmin`/
`DatabaseTarget`/`parse_database_target`: the project's persistence model
already applies the same dialect-portable SQL migrations to SQLite and
PostgreSQL alike (see `docs/architecture/PERSISTENCE-STRATEGY.md`), so a
two-folder, engine-named split did not reflect that abstraction. Every
reference across `src/`, `tests/`, and docs was updated accordingly.

Identity and Access Management moved from `DEFINED` to `PARTIAL` in
v0.1.8 with the first implementation slice, Phase 1 of the plan in
`docs/TO-DO.md`: an isolated `domain/identity` (`User`, `AccessRole`,
`Permission`, `RefreshToken`), `application/identity` (`IdentityService`
and its ports), an Argon2id password-hashing adapter, in-memory and
SQLAlchemy repositories, and migration `0007_identity_and_access.sql`.
Deliberately isolated, per the user's own explicit instruction: nothing
here is called from any FastAPI route or CLI command yet, and no
existing execution/action/role/model permission check consults it — it
is a self-contained vertical slice exercised only by its own tests. The
full suite is now **143 tests** (124 + 19 new), still clean under
`pytest -W error::DeprecationWarning`.

Identity and Access Management stays `PARTIAL` in v0.1.9 with Phase 2 of
the same plan: JWT access-token issuance/validation
(`JWTAccessTokenIssuer`, PyJWT, HS256, ~15 minute TTL) and SHA-256
refresh-token hashing (`Sha256RefreshTokenHasher` — deliberately distinct
from the Argon2id `PasswordHasher`, since refresh tokens are high-entropy
random strings rather than user-chosen secrets), plus `login()` /
`refresh()` / `logout()` on `IdentityService` (single-use refresh-token
rotation, idempotent logout). Still deliberately isolated: nothing here
is called from any FastAPI route or CLI command, and there is still no
`/auth/*` surface or `ORCHAI_AUTH_ENFORCED` flag — that remains Phase 3.
The full suite is now **160 tests** (143 + 17 new), still clean under
`pytest -W error::DeprecationWarning`.

Identity and Access Management moved from `PARTIAL` to `IMPLEMENTED` in
v0.1.10 with Phase 3 of the same plan — the phase that actually changes
runtime behavior, closing out `docs/TO-DO.md` Priority 1: a shared FastAPI
dependency (`require_permission(key)` in `interfaces/api/main.py`) and its
CLI counterpart (`require_cli_permission(key)`, called explicitly as the
first statement of each command body rather than as a decorator, so
Typer/Click's signature-introspection-based argument parser is never at
risk); `POST /auth/login` / `POST /auth/refresh` / `POST /auth/logout` and
`orchai auth login` / `orchai auth logout` / `orchai auth bootstrap-admin`;
declarative per-route/per-command permission requirements wired into every
pre-existing route (50 of 54 app routes) and command (46 of 49 commands —
`auth login`, `auth bootstrap-admin`, and `api serve` are the exceptions,
the first two being the bootstrap path itself and the third having no HTTP
route counterpart to mirror); and the bootstrap-superuser path (ADR-012
§8, via `orchai auth bootstrap-admin` or `ORCHAI_ADMIN_USERNAME`/
`ORCHAI_ADMIN_PASSWORD`). All of this is gated behind `ORCHAI_AUTH_ENFORCED`,
default `false` per the rollout plan in
`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6 — so no existing
caller's behavior changed by landing this code; enforcement is wired in
but inert until deliberately turned on. User management
(`admin:manage_users`, a `/users` HTTP surface, `orchai users *`) is
deliberately out of scope for this phase, per the permission inventory in
`IDENTITY-AND-ACCESS-MODEL.md` §4. The full suite is now **178 tests**
(160 + 18 new: unit coverage for `AuthSettings` loading/validation, plus
integration coverage for the `/auth/*` routes and enforced/unenforced
behavior on both the API and CLI, including the superuser-bypass and
missing-permission-403/exit-1 cases), still clean under
`pytest -W error::DeprecationWarning`.

Identity and Access Management gained a fourth, purely additive phase in
v0.1.11: a user-configuration CRUD layer, requested by the user as an
explicit prerequisite to the broader per-user authorization refactor
("primeiro deixar o cadastro/configuração de usuários mais robusto").
Admin-only management of users and access roles
(`GET/POST /admin/users`, `PUT /admin/users/{id}/access-roles`,
`GET/POST /admin/access-roles`, `PUT /admin/access-roles/{id}/permissions`;
`orchai users list|create|set-access-roles`,
`orchai access-roles list|create|set-permissions`), gated by
`admin:manage_users`; an admin project directory
(`GET /admin/projects`, `orchai projects list-all`) gated by a new
`admin:manage_projects` permission, listing every project's capabilities,
readiness, and connected users; and a self-service surface (`GET`/`PATCH
/me`, `GET /me/projects`, `orchai me show|update|projects`) that always
requires a real authenticated caller via a new
`require_authenticated_user()` / `require_authenticated_cli_user()`
dependency — deliberately distinct from `require_permission`'s
inert-when-`ORCHAI_AUTH_ENFORCED=false` behavior, since "show my own
profile" has no meaningful no-op reading.

The existing N:N `AccessRole` model (Phase 1) was kept entirely
unchanged — no schema migration, no single-scalar-role-per-user column,
no `-1` sentinel. An earlier "Default AccessRole" design (a system-wide
fallback role for a user created without one) was proposed and then
dropped by the user in favor of a simpler rule with the same practical
guarantee: creating a non-superuser now requires specifying at least one
`AccessRoleId` up front (`UserRequiresAccessRoleError` otherwise).
Superusers remain exempt, since `is_superuser=True` already bypasses
every permission check. `PUT .../access-roles` and `PUT .../permissions`
are both replace-all operations.

A new, purely informational `project_connections` table
(`0008_project_connections.sql`) records which users connected which
project to OrchAI — explicitly not an access-control boundary, and
living in the same database as `projects` (not the pinned identity
database), since it is descriptive project metadata, not a security
concern. `POST /projects` now auto-links the caller when authenticated,
by capturing `require_permission`'s claims as a parameter instead of
discarding them via the `dependencies=[...]` list form — the one change
to a pre-existing route's code in this phase, and it does not alter that
route's permission check or response shape for any existing caller.

This phase also closed a latent correctness gap that predates it:
`permissions` and `access_roles` started completely empty in a fresh
database, with no seeding anywhere in the codebase, which meant no
non-superuser could ever pass a permission check even with
`ORCHAI_AUTH_ENFORCED=true`. The full permission-key catalog (the eleven
keys from `IDENTITY-AND-ACCESS-MODEL.md` §4 plus the new
`admin:manage_projects`) is now auto-seeded idempotently — via a
synchronous SQLAlchemy Core helper, not the async `PermissionRepository`
port, since the identity-runtime builders are plain sync functions called
from both async FastAPI startup and sync CLI entry points — on every
`build_sqlalchemy_identity_runtime` call, immediately after
`database.migrate()`. See `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`
§8 for the full design. The full suite is now **203 tests** (178 + 25
new), still clean under `pytest -W error::DeprecationWarning`.

The next implementation focus is:

- an Anthropic (Claude) provider adapter — Ollama and OpenAI are already
  real, HTTP-backed, tested, and wired via `ORCHAI_AI_PROVIDER`;
- the broader per-user action/role/model authorization and multi-user
  Project Adapter binding change the user has described (the "refatoração
  para usuários"), now that its explicit prerequisite (this
  user-configuration CRUD layer) is in place. Its one hard technical
  dependency — a request-scoped "current logged-in user" to check
  permissions against — has been resolved since Phase 3, but starting it
  is still an explicit decision the user has not yet made (per the user's
  own standing instruction, changes to the project's established
  foundation require explicit authorization before implementation, not
  just before-the-fact reporting) — see `docs/TO-DO.md` Priority 1's
  "Scope note" for the full framing;
- flipping `ORCHAI_AUTH_ENFORCED` to `true` by default, once a decision
  is made on whether/when to do so — also not yet authorized;
- richer policy configuration, including `AUTOMATIC` execution policy
  runtime configuration (now a sharper gap given the PLAN-stage fix above);
- execution cancellation and metrics aggregation as first-class
  application capabilities;
- deployment and container automation.

## Source of Truth

This document tracks project state.

It does not redefine architectural rules.

For architectural rules, consult:

-   `ARCHITECTURAL-CONTRACT.md`
-   `ARCHITECTURE.md`
-   `architecture/COMPONENTS.md`
-   relevant domain documentation
-   relevant ADRs
-   `IMPLEMENTATION-MAP.md`

## Important Distinction

``` text
DEFINED
    ≠
IMPLEMENTED

DECIDED
    ≠
IMPLEMENTED

DOCUMENTED
    ≠
VALIDATED
```
