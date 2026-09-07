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

## Immediate Priority --- Land Already-Completed Local Work

Everything described as "done" below (all of Priority 1 Phases 1--4,
Priority 2, Priority 3 items 1--4, and Priority 4 item 1) is
implemented and sitting in the local working tree, not yet committed
or pushed. Re-validated directly on 2026-09-06:
`uv run ruff check` clean, full suite `294 passed`,
`uv run orchai --help` smoke check passes, `uv lock --check`
consistent. Landing this work through the process now defined in
[`GIT-GITHUB-FLOW.md`](GIT-GITHUB-FLOW.md) --- not writing more of
it --- is the actual next action, ahead of anything else in this
document.

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

## OrchAI Desktop Initiative (ADR-013 through ADR-017)

The active strategic direction is turning OrchAI into a Windows desktop
chat application (`docs/VISION.md`), with a general layer (chat,
conversations, projects, a single local user, metrics/audit) and
specialized Modules (Forge, Studio) on top of the existing orchestration
core. Design work is recorded in ADR-013 (LiteLLM + streaming), ADR-014
(Conversation/Message domain), ADR-015 (Module concept), ADR-016
(single-user identity for desktop), and ADR-017 (the `pywebview` shell
itself); the phased implementation plan lives in
`docs/architecture/DESKTOP-APPLICATION.md` and is not duplicated here.
All 7 phases of that plan are now implemented (shell skeleton, Project
Picker + Forge module registration, persistent conversation, SSE
streaming end-to-end in the Forge chat screen, explicit message→Task
escalation with an Approval Card, a Studio skeleton --- a second module
with its own `media_workspace` project adapter, attachment discovery,
and streaming chat, reusing the `TASK_PLANNER`/`PLAN` pair per ADR-015's
"Implementation Note (Phase 6)" rather than resolving §5's
dedicated-vocabulary question --- and, closing the initiative, Phase 7
Hardening: runtime `AutomaticExecutionPolicy` configuration, execution
cancellation, metrics aggregation, a metrics/audit dashboard in the
desktop UI, the `orchestrator.py` decomposition, PyInstaller packaging,
and a headless-mode `Dockerfile`; see `docs/STATUS.md`'s Phase 7 entry
for the full breakdown). The OrchAI Desktop initiative itself is
complete; further work in this area is now incremental hardening, not
initiative phases.

This initiative reconciles and supersedes some of the priorities below,
noted inline at each affected item. New backlog items belong in
`docs/architecture/DESKTOP-APPLICATION.md`'s phase list, not as new
top-level priorities in this document, to avoid the same work being
tracked in two places.

------------------------------------------------------------------------

## Documentation & Delivery-Flow Refactor (in progress)

Step 1 is done (2026-09-06): [`GIT-GITHUB-FLOW.md`](GIT-GITHUB-FLOW.md)
established as the source of truth for branching, commit, PR,
versioning, and release discipline; `.github/workflows/ci.yml` renamed
to `OrchAI-FullValidation.yml` (job renamed to `Backend Quality`, its
`.pytest-tmp` creation bug fixed once exercised on a clean checkout for
the first time); the new manual `.github/workflows/OrchAI-Release.yml`
plus `scripts/release.py` (tag validation + git-log release notes);
`.github/pull_request_template.md` updated with Version Decision and
Documentation Checklist sections; `.github/dependabot.yml` removed
(the 8 stale Dependabot PRs it had opened were closed). Landed via
pull request #9.

Remaining steps, in order:

1.  Translate `docs/API-ENDPOINTS-REPORT.md` to English.
2.  Redesign `docs/STATUS.md` as a pure status snapshot (remap the
    current ~45-row table onto a 4-state vocabulary), archiving its
    historical narrative into a new `docs/HISTORY.md`; delete
    `docs/architecture/STATUS.md` and `docs/domains/STATUS.md`.
3.  Consolidate `docs/architecture/` (18 files) and `docs/domains/`
    (14 files) into a single `docs/context/` (16 files), as 2--3 pull
    requests grouped by cluster.
4.  Retire the ADR format: move all 17 ADRs to
    `docs/archive/decisions/`, folding still-relevant decisions into
    `ARCHITECTURAL-CONTRACT.md` or the matching `docs/context/*.md`
    file's "Key Rules" section.
5.  Consolidate root docs: new `docs/DEVELOPMENT-GUIDE.md`, trim
    `ARCHITECTURE.md`/`IMPLEMENTATION-MAP.md`, fold `docs/VISION.md`
    into `ARCHITECTURAL-CONTRACT.md`, retire `CONTRIBUTING.md` and
    `docs/engineering/DELIVERY-BASELINE.md` (both superseded by
    `GIT-GITHUB-FLOW.md` already).
6.  Merge `docs/USER-ONBOARDING.md` + `docs/USER-OPERATIONS-GUIDE.md`
    into `docs/USER-GUIDE.md` + `docs/OPERATIONS-REFERENCE.md`.
7.  Rewrite `docs/INDEX.md` as the single navigation hub.
8.  Restructure `AGENTS.md` (explicit Source-of-Truth order,
    `docs/context/` authorization gate, agent identity and PR
    delivery workflow).

This runs in parallel with the backlog below; it does not block it.

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

ADR-016 (`docs/decisions/ADR-016-DESKTOP-SINGLE-USER-IDENTITY-SIMPLIFICATION.md`)
confirms this remains untouched by the OrchAI Desktop initiative: the
desktop shell reuses the existing IAM implementation only for
attribution (a single local user), never enables
`ORCHAI_AUTH_ENFORCED`, and does not start this multi-user revisit.

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

## Priority 2 --- AI Provider Adapter: LiteLLM Migration (ADR-013)

Superseded by ADR-013. The previously planned manual Anthropic adapter
is no longer needed --- LiteLLM already speaks to Anthropic's API, along
with every other provider this item would have added one at a time.

1.  ~~**Anthropic (Claude) adapter.**~~ Obsolete. LiteLLM covers
    Anthropic (and Gemini, and other providers) without a
    provider-specific hand-rolled adapter.
2.  **Streaming support.** Resolved by ADR-013:
    `AIProviderPort.execute_stream()` plus `infrastructure/ai/litellm_provider.py`.
    See `docs/architecture/DESKTOP-APPLICATION.md` Phase 4 for the
    implementation phase.
3.  **Retry/backoff policy.** Resolved by ADR-013: LiteLLM provides
    retry/backoff natively, removing the need for a bespoke policy at
    the adapter or `ExecutionEngine` level.
4.  **Migration (done, OrchAI Desktop Phase 3).**
    `infrastructure/ai/litellm_provider.py` implements `AIProviderPort`
    (`execute()`, non-streaming; `execute_stream()` is Phase 4);
    `ollama.py` and `openai_codex.py` and their tests are deleted;
    `AIProviderSettings.provider` is now `Literal["stub", "litellm"]`,
    and `provider_from_settings()` (`bootstrap/runtime.py`) constructs
    `LiteLLMProvider` for every non-stub case. Provider routing moved
    entirely into `ORCHAI_AI_MODEL`'s `"<provider>/<model>"` prefix
    (e.g. `ollama/qwen2.5-coder:latest`, `openai/gpt-5`).

------------------------------------------------------------------------

## Priority 3 --- Close Known Runtime Gaps

These were already named as gaps in `docs/STATUS.md`; items 1--3 are
now closed (OrchAI Desktop Phase 7.1--7.3).

1.  **`AutomaticExecutionPolicy` runtime configuration (done, OrchAI
    Desktop Phase 7.1).** A new singleton-row `AutomaticPolicyRepository`
    (migration `0010_automatic_policy.sql`) makes the policy
    runtime-mutable: `LocalPolicyService.evaluate()` re-reads it from
    the repository on every call instead of freezing it at
    construction. `GET`/`PUT /policies/automatic` (new
    `policies:manage` permission for the write) and `orchai policies
    automatic show|set` expose it -- `AUTOMATIC` mode is now
    configurable for any `(role, action)` pair through the public
    CLI/API surface, not just the hardcoded default
    `(DEVELOPER, IMPLEMENT)` via direct Python construction.
2.  **Execution cancellation (done, OrchAI Desktop Phase 7.2).**
    `ExecutionEngine.cancel()` cancels the tracked `asyncio.Task`
    (populated by `.dispatch()`), treats the provider's own `.cancel()`
    as a secondary best-effort signal, and always finishes by
    transitioning the execution to `CANCELLED` directly (publishing the
    new `EventType.EXECUTION_CANCELLED`) since `asyncio.CancelledError`
    bypasses `run()`'s own exception handling. `LiteLLMProvider.cancel()`
    is now a documented no-op rather than raising.
    `POST /executions/{id}/cancel` and `orchai executions cancel`
    expose it.
3.  **Metrics aggregation (done, OrchAI Desktop Phase 7.3).** A new
    `MetricsRepository.summarize()` (backed by the pure,
    repository-independent `application/metrics/aggregation.py`)
    computes count/sum/avg per metric name, grouped by any combination
    of `project_id`/`role`/`action`/`model_id`/`outcome`, over an
    optional time window. `GET /metrics/summary` and `orchai metrics
    summary` expose it. Deliberately scoped to what's already emitted
    today (success/failure/duration/tokens/cost) -- retry rate and
    suggestion acceptance rate from `docs/IMPLEMENTATION-MAP.md` §4.11
    would need cross-referencing suggestions/audit and remain
    unaggregated.
4.  **Stale `PRESENTED` suggestions after a task advances (found during
    OrchAI Desktop Phase 5, fixed).** `Orchestrator._resolve_task_stage()`
    called `SuggestionEngine.suggest_next()` on every advance/approve
    call that doesn't pass an explicit stage -- exactly what
    `POST /requests/{id}/approve` does internally -- generating a new
    `Suggestion` record each time without ever marking the *previous*
    `PRESENTED` one for the same task as resolved, so a stale suggestion
    from an already-resolved stage could win
    `_serialize_request_flow`'s "most recent PRESENTED" selection and
    make `GET /requests/{id}/flow` report
    `PENDING_SUGGESTION`/`PRESENTED` indefinitely after the stage
    actually completed. Fixed in `SuggestionEngine.suggest_next()`
    (`application/suggestions/engine.py`): it now reuses an existing
    `PRESENTED` suggestion matching the task's current
    `(suggested_role, suggested_action)` instead of duplicating it, and
    correctly ignores a stale `PRESENTED` suggestion left over for a
    *different*, already-superseded stage. See ADR-011's "Amendment
    (OrchAI Desktop Phase 5)" section and
    `tests/unit/application/test_suggestion_engine.py`.
    `apps/desktop/frontend/src/screens/ApprovalCard.jsx` no longer needs
    its earlier `flow.task.state`-based workaround and reads
    `suggestion.status` directly again.

------------------------------------------------------------------------

## Priority 4 --- Deployment and Operational Readiness

1.  **Add a `Dockerfile` (done, OrchAI Desktop Phase 7.7).** A
    root-level `Dockerfile` (multi-stage, `uv sync --locked --no-dev`
    without the `desktop` extra, non-root user, `HEALTHCHECK` against
    `GET /health`) and `.dockerignore` now give the headless CLI/API
    deployment shape a runnable container path, per
    `docs/architecture/DEPLOYMENT-MODEL.md`. No source change was
    needed: `create_app()` already produces the correct headless
    behavior (the desktop UI's static mount is conditional on
    `ORCHAI_DESKTOP_STATIC_DIR`, which nothing sets outside the desktop
    shell). A `docker-compose.yml` for local PostgreSQL + the API was
    not added -- still a reasonable, low-effort follow-up if wanted, but
    not required for the container path itself to work.
2.  Extend `.github/workflows/OrchAI-FullValidation.yml` and
    [`GIT-GITHUB-FLOW.md`](GIT-GITHUB-FLOW.md) (which superseded
    `docs/engineering/DELIVERY-BASELINE.md`, see "Documentation &
    Delivery-Flow Refactor" above) toward what remains genuinely
    deferred: package publishing, deployment workflows beyond the
    existing untested `Dockerfile` (add a CI step that builds and runs
    it), environment promotion strategy, and dependency security gates
    (deliberately *not* Dependabot --- that was dropped in favor of
    this leaner model; a lighter-weight vulnerability scan, if any, is
    still an open choice). Release-tag validation and git-log-based
    release notes are no longer deferred: they exist via the manual
    `OrchAI - Release Validation` workflow and `scripts/release.py`.

------------------------------------------------------------------------

## Priority 5 --- Longer-Horizon / Architectural Follow-ups

These are open conceptual questions already tracked in
`docs/domains/STATUS.md` under "Open Conceptual Areas." They do not
block current implementation but should be resolved with an ADR before
more code accretes around an ambiguous boundary:

-   Agent as an explicit domain concept versus a composition of role,
    policy, model, and capabilities.
-   Workflow responsibility versus State Machine responsibility.
-   Task Engine versus Application Orchestration: the conceptual
    question (whether these should be distinct concepts) remains open,
    but the file-size pressure that made it urgent is resolved --
    `orchestrator.py` was decomposed (OrchAI Desktop Phase 7.5) from
    1437 lines into `orchestrator.py` (1016 lines, its 3 public methods
    and 12-collaborator constructor unchanged) plus five sibling
    modules (`ports.py`, `results.py`, `events.py`, `connections.py`,
    `stages.py`, `gating.py`) in `application/orchestration/`, each
    with its own new unit tests (the file had none before). See
    `docs/STATUS.md`'s Phase 7 entry for the breakdown.
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
