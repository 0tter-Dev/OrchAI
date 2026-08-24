# OrchAI --- To-Do / Roadmap

## Purpose

This document is a prioritized backlog of planned work for OrchAI.

It is a task-planning document, not a project-state document. For
current implementation state, consult [`STATUS.md`](STATUS.md). For
architectural rules, consult
[`ARCHITECTURAL-CONTRACT.md`](ARCHITECTURAL-CONTRACT.md) and
[`IMPLEMENTATION-MAP.md`](IMPLEMENTATION-MAP.md). This document should
not duplicate the rationale already recorded there --- it links to it
instead.

Last reviewed against the codebase at `v0.1.8` (2026-08-23). See
"Audit basis" below for what was actually verified before writing this
backlog.

------------------------------------------------------------------------

## Audit basis

Before drafting this backlog, the following was verified directly
against the working copy, not assumed from documentation text alone:

- Full test suite executed clean: `124 passed` under
  `pytest -W error::DeprecationWarning`, matching the count
  `STATUS.md` claims.
- Every FastAPI route actually registered in
  `src/orchai/interfaces/api/main.py` (51 routes) was extracted and
  compared against `docs/API-ENDPOINTS-REPORT.md`. They match; the two
  extra entries in the report (`db create` / `db migrate`) are
  explicitly documented there as removed in v0.1.7, not live routes.
- Every Typer CLI command actually registered in
  `src/orchai/interfaces/cli/main.py` was extracted and compared
  against `STATUS.md`'s narrative of CLI coverage (audit show,
  suggestions show/generate/accept/reject, etc.). They match.
- `AutomaticExecutionPolicy`, execution cancellation, and metrics
  aggregation were grepped end-to-end to confirm the gaps `STATUS.md`
  already flags are real: no CLI/API surface configures the policy, no
  application code ever calls `AIProviderPort.cancel(...)`, and
  `MetricsRepository` only stores/lists individual records with no
  aggregation query.
- No authentication code (JWT, password hashing, user/session
  handling) exists anywhere in `src/`, confirming
  "Identity and Access Management: `DEFINED`" (design-only, per
  ADR-012) is accurate, not an oversight.
- The Ollama and OpenAI adapters
  (`src/orchai/infrastructure/ai/{ollama,openai_codex}.py`) are real,
  HTTP-backed, unit-tested, and wired into
  `orchai/bootstrap/runtime.py::provider_from_settings` via
  `ORCHAI_AI_PROVIDER` --- they are not stubs.

One documentation defect was found by this audit and has since been
fixed (2026-08-23, v0.1.8; see `docs/STATUS.md`'s changelog narrative):
`docs/domains/STATUS.md` was last touched 2026-08-20 and still marked
every domain `PARTIAL`, while `docs/STATUS.md`,
`docs/architecture/STATUS.md`, and the individual domain documents
themselves (`docs/domains/AUTHORIZATION.md`, `docs/domains/TASKS.md`)
already said `IMPLEMENTED` for the corresponding areas. The "next
implementation focus" bullet in `docs/STATUS.md` naming AI provider
adapters was also reworded at the same time to reflect that Ollama and
OpenAI are already implemented and only Anthropic is missing.

------------------------------------------------------------------------

## How to use this backlog

- Priorities are ordered by a mix of risk, effort, and how much they
  unblock other work --- not strictly by architectural layer.
- Each item names the concrete files most likely to change. This is a
  starting point for whoever picks up the item, not a constraint.
- Before implementing an item, re-read the referenced architecture
  document or ADR. This document intentionally does not restate
  design decisions already made elsewhere.
- When an item is completed, remove it from here and record it in
  `STATUS.md`'s changelog narrative, per the existing convention in
  that document.

------------------------------------------------------------------------

## Priority 1 --- Identity and Access Management (ADR-012)

Phases 1--4 below are done: every HTTP endpoint and CLI command carries a
declarative permission requirement, enforced by a shared FastAPI
dependency / CLI check, and an admin-facing CRUD layer plus self-service
`/me` surface exist for managing users/access-roles/projects. It remains
opt-in, though --- nothing is actually rejected until
`ORCHAI_AUTH_ENFORCED` is explicitly set to `true` (default `false`, per
the rollout plan in `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6)
--- so every endpoint in `src/orchai/interfaces/api/main.py`, including
`/requests`, `/projects/operations`, and `/admin/db/sync`, is still
reachable with no authentication at all until that flag is turned on.
Whether/when to flip it, and whether to proceed with the broader per-user
authorization refactor described in "Scope note" below, are open
decisions --- not yet authorized by the user.

> **Corrections found while grounding the design docs against the actual
> codebase, before writing the implementation plan below:**
>
> 1. The data model sketch in `IDENTITY-AND-ACCESS-MODEL.md` §1 names an
>    entity `Role`. `src/orchai/domain/identifiers.py` already reserves
>    a `RoleId` identifier (currently unused, but reserved), and
>    `src/orchai/domain/roles/names.py` already defines an unrelated
>    `RoleName` enum consumed by the existing `Authorization` aggregate
>    (`DEVELOPER`, `REVIEWER`, etc. --- a *task* role, not an *access*
>    role). To avoid a second, incompatible meaning for "Role" in the
>    codebase, this new concept is named `AccessRole` /
>    `AccessRoleId` throughout code and docs, never bare `Role`/`RoleId`.
> 2. ADR-012 §7 describes the new migration as `0007_identity_and_access.sql`
>    "(SQLite) and its PostgreSQL counterpart" --- implying two migration
>    paths. There is only one: every existing migration under
>    `infrastructure/persistence/db/migrations/` is plain, dialect-portable
>    SQL applied identically to whichever engine is configured (see
>    `SQLAlchemyDatabase.migrate()` / `_migration_files()`). `0007_...`
>    follows the same convention --- a single file, no PostgreSQL-specific
>    variant.
> 3. `IDENTITY-AND-ACCESS-MODEL.md` §3 describes CLI token resolution as
>    working "exactly like `database_url` resolution is threaded through
>    every command today." That is not how the CLI works today: there is
>    no shared Typer callback/`ctx.obj` --- `settings = load_settings()`
>    is copy-pasted independently at the top of ~40 command functions in
>    `interfaces/cli/main.py`, and `main.py` has zero FastAPI `Depends(...)`
>    usages; every route rebuilds its own settings/dependencies. Phase 3
>    below has to *introduce* the first shared enforcement hook on both
>    sides, not reuse an existing one.

**Preparatory step:** done, 2026-08-23 --- `infrastructure/persistence/sqlite/`
+ `infrastructure/persistence/postgresql/` consolidated into
`infrastructure/persistence/db/`. See `docs/STATUS.md`'s v0.1.8 changelog
entry for full detail; not repeated here per this document's own
completed-item convention (see "How to use this backlog" above).

### Scope note on the broader authorization change

Once enforced end-to-end, this layer changes the system's general
behavior: every execution will need to check not just "is this
`(role, action)` pair allowed by policy" (today's `AutomaticExecutionPolicy`)
but "is *this logged-in user* allowed to request this action, invoke this
role, and use this AI model," and a connected `Project Adapter` will be
bindable to one or more users (today only one operator has access to
whatever projects they connect; going forward, more than one user may
link the same project). An `Admin` user retains access to everything.
That is a near-total revisit of how requests flow through the system ---
intentionally **not** part of Phase 1, Phase 2, or Phase 3.

Its one hard technical dependency --- a request-scoped "current logged-in
user" to check permissions against --- is now resolved: Phase 3 (below)
provides exactly that, via `AccessTokenClaims` resolved by
`require_permission`/`require_cli_permission`. This revisit can now
*start* without being blocked on missing infrastructure. Whether it
*should* start now, later, or with adjustments first is still an open
decision the user has not made --- per the user's own standing
instruction, this is a change to the project's established foundation
(business rules for who may do what) and requires the user's explicit
authorization before implementation begins, not merely a note in this
backlog. Do not start it without that explicit go-ahead, and do not fold
it into any other item's scope.

### Phase 1 --- Identity domain, in isolation (done, 2026-08-23)

Isolated `domain/identity` + `application/identity` + `infrastructure/identity`
slice (users, access roles, permissions, refresh tokens; Argon2id password
hashing; in-memory and SQLAlchemy persistence; migration
`0007_identity_and_access.sql`), exercised only by its own tests --- nothing
called from `main.py` or `interfaces/cli/main.py`. `143 passed`. See
`docs/STATUS.md`'s v0.1.8 changelog entry for full detail; not repeated
here per this document's own completed-item convention.

### Phase 2 --- JWT issuance and token lifecycle (done, 2026-08-23)

JWT access-token issuance/validation (`JWTAccessTokenIssuer`, PyJWT), SHA-256
refresh-token hashing (`Sha256RefreshTokenHasher`), and `login()` /
`refresh()` (single-use rotation) / `logout()` (idempotent) on
`IdentityService` --- still nothing called from `main.py` or
`interfaces/cli/main.py`; still no `/auth/*` route, `orchai auth` command,
or `ORCHAI_AUTH_ENFORCED` flag --- that is Phase 3. `160 passed`. See
`docs/STATUS.md`'s v0.1.9 changelog entry for full detail; not repeated
here per this document's own completed-item convention.

### Phase 3 --- Enforcement wiring (done, 2026-08-23)

The first phase that changes runtime behavior: `require_permission(key)`
(FastAPI dependency) and `require_cli_permission(key)` (a plain function
called explicitly as each CLI command's first statement, not a decorator
--- see `docs/STATUS.md`'s v0.1.10 changelog entry for why); `POST
/auth/login` / `POST /auth/refresh` / `POST /auth/logout` and `orchai
auth login` / `orchai auth logout` / `orchai auth bootstrap-admin`;
declarative per-route/per-command permission requirements wired into
every pre-existing route and command, gated behind `ORCHAI_AUTH_ENFORCED`
(default off, per the rollout plan in `IDENTITY-AND-ACCESS-MODEL.md` §6);
and the bootstrap-superuser path (ADR-012 §8). `178 passed`. See
`docs/STATUS.md`'s v0.1.10 changelog entry for full detail; not repeated
here per this document's own completed-item convention.

### Phase 4 --- User-configuration CRUD layer (done, 2026-08-23)

Admin-only management of the identity data (`GET/POST /admin/users`,
`PUT /admin/users/{id}/access-roles`, `GET/POST /admin/access-roles`,
`PUT /admin/access-roles/{id}/permissions`, `GET /admin/projects`;
`orchai users *`, `orchai access-roles *`, `orchai projects list-all`),
gated by two permission keys (`admin:manage_users`, and the new
`admin:manage_projects`); a self-service `/me` / `orchai me *` surface
that always requires a real authenticated caller regardless of
`ORCHAI_AUTH_ENFORCED` (`require_authenticated_user()` /
`require_authenticated_cli_user()`, distinct from `require_permission`'s
inert-when-disabled behavior); a purely informational `project_connections`
reference table recording which users connected which project (not an
access boundary, migration `0008_project_connections.sql`); and
auto-seeding of the full permission catalog on every identity-runtime
build, fixing a latent gap where `permissions`/`access_roles` started
empty in a fresh database and no non-superuser could ever pass a
permission check. See `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`
§8 for the full design, including the "mandatory `AccessRole` at
creation" rule that replaced an earlier "Default AccessRole" design
(dropped per the user's own simplification --- see that section). `203
passed`. See `docs/STATUS.md`'s v0.1.11 changelog entry for full detail;
not repeated here per this document's own completed-item convention.

This closes out Priority 1 as originally scoped (Phases 1--4). The
broader behavioral revisit described in "Scope note" above --- per-user
action/role/model authorization and multi-user `Project Adapter` binding
(the "refatoração para usuários") --- remains deliberately out of scope
here and needs the user's explicit authorization before it starts (see
"Scope note" above); Phase 4 was an explicit prerequisite the user asked
for first, not the start of that refactor.

------------------------------------------------------------------------

## Priority 2 --- Complete the AI Provider Adapter Set

1.  **Anthropic (Claude) adapter.** Add
    `src/orchai/infrastructure/ai/anthropic.py` implementing
    `AIProviderPort`, following the existing pattern in `ollama.py` /
    `openai_codex.py` (HTTPX-backed, `capabilities()`,
    `validate_request()`, `healthcheck()`, `execute()`, `cancel()`).
    Wire it into `AIProviderSettings.provider` (currently
    `Literal["stub", "ollama", "openai"]`) and
    `provider_from_settings()` in `bootstrap/runtime.py`. Add
    `tests/unit/infrastructure/test_anthropic_adapter.py` mirroring the
    existing adapter tests.
2.  **Streaming support.** Both existing adapters make a single
    blocking HTTP call and return the full result. If interactive
    or long-running executions become a priority, revisit
    `AIProviderPort.execute()` and the adapters for a streaming
    variant --- this is a bigger architectural change and should get
    its own ADR before implementation, per
    `docs/architecture/ADAPTER-CONTRACTS.md`'s note that "the exact
    interface may evolve."
3.  **Retry/backoff policy.** Neither adapter retries on transient
    HTTP failures today; they raise `AIProviderError` immediately. If
    real usage surfaces this as a problem, add a bounded retry policy
    at the adapter or `ExecutionEngine` level rather than duplicating
    retry logic per adapter.

------------------------------------------------------------------------

## Priority 3 --- Close Known Runtime Gaps

These are already named as gaps in `docs/STATUS.md`; they are
restated here as concrete, scoped work items.

1.  **`AutomaticExecutionPolicy` runtime configuration.** Today the
    policy is only configurable by constructing
    `AutomaticExecutionPolicy(...)` in Python
    (`src/orchai/application/policies/service.py`); there is no CLI or
    API surface. Add a persisted policy configuration (likely a new
    small table/repository, or an extension of existing project/global
    configuration) plus `orchai policies automatic show|set` CLI
    commands and a corresponding `GET`/`PUT /policies/automatic`
    API pair, so an operator can configure allowed `(role, action)`
    pairs without redeploying code. Until this exists, `AUTOMATIC`
    mode is only reachable through the Python API, not the public
    CLI/API surface, for any pair beyond the hardcoded default
    `(DEVELOPER, IMPLEMENT)`.
2.  **Execution cancellation.** `AIProviderPort.cancel(execution_id)`
    exists on the port
    (`src/orchai/application/executions/ports.py`), but nothing in
    `ExecutionEngine` or `ExecutionService` ever calls it, and both
    concrete adapters (`ollama.py`, `openai_codex.py`) simply raise
    "does not support cancellation." Add a `cancel()` path through
    `ExecutionService` → `ExecutionEngine` → provider, an
    `EXECUTION_CANCELLED` domain event/state per the existing
    `domain/executions/state_machine.py`, and expose
    `POST /executions/{id}/cancel` + `orchai executions cancel`.
3.  **Metrics aggregation.** `MetricsRepository` currently only
    supports `add_many()` and a filtered `list()` of raw
    `MetricRecord`s (`src/orchai/application/metrics/ports.py`). Add
    aggregation queries (count/sum/avg over a time window, grouped by
    role/action/model/project) and expose them via a new
    `GET /metrics/summary` endpoint and `orchai metrics summary`
    command, per the metric categories already named in
    `docs/IMPLEMENTATION-MAP.md` §4.11 (token usage, success rate,
    failure rate, etc.) but never aggregated today.

------------------------------------------------------------------------

## Priority 4 --- Deployment and Operational Readiness

`docs/STATUS.md` correctly marks "Deployment Implementation" as
`PENDING`; there is no `Dockerfile` or deployment automation in the
repository today, even though `IMPLEMENTATION-MAP.md` §22 lists Docker
in the technology baseline.

1.  Add a `Dockerfile` (and a `docker-compose.yml` for local
    PostgreSQL + the API) so the documented technology baseline
    actually has a runnable container path.
2.  Extend `docs/engineering/DELIVERY-BASELINE.md`'s CI workflow
    (`.github/workflows/ci.yml`) toward the items it already lists as
    deferred: release automation, package publishing, deployment
    workflows, environment promotion, and secret-scanning/dependency
    security gates. Treat that document's "what is intentionally not
    implemented yet" section as the authoritative list --- work
    through it top to bottom rather than reinventing the sequencing.

------------------------------------------------------------------------

## Priority 5 --- Longer-Horizon / Architectural Follow-ups

These are open conceptual questions already tracked in
`docs/domains/STATUS.md` under "Open Conceptual Areas." They do not
block current implementation but should be resolved with an ADR before
more code accretes around an ambiguous boundary:

-   Agent as an explicit domain concept versus a composition of role,
    policy, model, and capabilities.
-   Workflow responsibility versus State Machine responsibility.
-   Task Engine versus Application Orchestration (the current
    `Orchestrator` in
    `src/orchai/application/orchestration/orchestrator.py` has grown
    to ~56 KB / over a thousand lines --- worth revisiting whether it
    should be decomposed before it grows further).
-   Execution Engine versus Execution domain.
-   Model Manager versus model/provider contracts.
-   Context Manager versus Context domain.
-   Project Adapter boundary versus Project domain.

Also tracked here rather than as near-term work: concurrency /
parallel-task execution readiness
(`docs/IMPLEMENTATION-MAP.md` §16). No implementation is needed now,
but new features should keep task/execution identity, scope, and
modifications explicit so this remains possible later without a
domain-model rewrite.

------------------------------------------------------------------------

## Explicitly out of scope for this backlog

Per `docs/ARCHITECTURAL-CONTRACT.md` §3 (Architectural Non-Goals),
the following should not appear as backlog items without a prior ADR
explicitly revisiting the contract: replacing the developer,
autonomous unrestricted workflow decisions, permanent coupling to one
AI provider or to VS Code, and forcing a single development workflow
on every connected project.
