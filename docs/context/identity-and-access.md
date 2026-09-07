# Identity And Access

## Purpose

Defines Identity and Access Management (IAM) for OrchAI: users, access
roles, permissions, JWT-based authentication, and the enforcement
points that consult them across the CLI and API.

## Objective

Give OrchAI a real, auditable notion of "who is calling" and "what may
they do," without redefining the existing domain model — `Authorization`,
`RoleName`, and `Execution` keep their current, unrelated meanings (see
the naming-collision note below), and this layer's `AccessRole` is a
distinct concept from `Authorization`'s `RoleName` for the same reason.

## Current Status

`implemented`

IAM shipped in four phases: Phase 1 (the identity data model and
`IdentityService`, isolated and unconsulted by anything else), Phase 2
(token lifecycle: login/refresh/logout), Phase 3 (enforcement:
`require_permission`/`require_cli_permission` wired into every
existing route/command behind `ORCHAI_AUTH_ENFORCED`), and Phase 4
(the user-configuration CRUD layer: admin-only management of
users/access roles/projects, and self-service `/me`). All four are
implemented and covered by the automated suite.

## Data Model

```text
User
  id                  UUID, primary key
  username            unique, not null
  email               unique, nullable
  password_hash       argon2id hash, not null
  is_superuser         bool, default false
  is_active           bool, default true
  created_at          timestamp
  updated_at          timestamp

AccessRole                            (named "AccessRole", not "Role" --
  id                  UUID, primary key    see the naming-collision note
  name                unique, not null   above: `RoleName` on
  description         text              `Authorization` is unrelated)

Permission
  id                  UUID, primary key
  key                 unique, not null   (e.g. "requests:create")
  description         text

RolePermission                     (many-to-many: AccessRole <-> Permission)
  role_id             -> AccessRole.id
  permission_id       -> Permission.id

UserRole                           (many-to-many: User <-> AccessRole)
  user_id             -> User.id
  role_id             -> AccessRole.id

UserPermission                        (direct grant, bypassing AccessRole)
  user_id             -> User.id
  permission_id       -> Permission.id

RefreshToken
  id                  UUID, primary key
  user_id             -> User.id
  token_hash          not null           (never store the raw token)
  issued_at           timestamp
  expires_at          timestamp
  revoked_at          timestamp, nullable

ProjectConnection                  (many-to-many: Project <-> User, see below)
  project_id          -> Project.id
  user_id             (no FK -- see the ProjectConnection section's note
                        on database placement)
  connected_at        timestamp
  primary key (project_id, user_id)
```

A user's **effective permission set** is the union of:

```text
permissions granted directly (UserPermission)
    +
permissions granted via every assigned AccessRole (UserRole -> RolePermission)
```

If `is_superuser = true`, the effective permission set is irrelevant —
every check short-circuits to allowed. This is also why superusers
need zero `AccessRole` assignments: there is no "no role" sentinel
value on `User` (no `-1`, no nullable scalar column) because the model
is N:N from the start — zero rows in `UserRole` for a user already
means "no role," unambiguously. Every *non*-superuser, however, is
required to have at least one `AccessRole` at all times — see the
mandatory-role rule below, which is what actually guarantees a
resolvable permission set for everyone not exempted by `is_superuser`.

This mirrors the shape of the existing persisted aggregates: plain
relational tables, no ORM-magic inheritance, migrated with the same
hand-rolled raw-SQL runner already used by
`SQLAlchemyDatabase.migrate()`. `Permission` rows are a fixed system
catalog, not admin-creatable through any endpoint: the full catalog
(below) is auto-seeded idempotently, synchronously, on every
`build_sqlalchemy_identity_runtime` call, immediately after
`database.migrate()` — see `bootstrap.runtime.PERMISSION_CATALOG` and
`SQLAlchemyPermissionRepository.seed_catalog`. Without this, a fresh
database's `permissions`/`access_roles` tables start empty and no
non-superuser could ever pass a permission check, since
`IdentityService.effective_permission_keys` can only return keys of
`Permission` rows that actually exist.

## Token Lifecycle

```text
POST /auth/login {username, password}
        │
        ▼
  verify password_hash (argon2id)
        │
        ▼
  issue access_token (JWT, ~15 min TTL)
    claims: sub=user_id, permissions=[...], is_superuser=bool, exp
  issue refresh_token (opaque random string, ~30 day TTL)
    persisted as RefreshToken.token_hash (hashed, e.g. SHA-256)
        │
        ▼
  return {access_token, refresh_token, expires_in}
```

```text
POST /auth/refresh {refresh_token}
        │
        ▼
  look up RefreshToken by hash(refresh_token)
  reject if missing / revoked / expired
        │
        ▼
  issue a new access_token (same claims, refreshed exp)
  rotate the refresh token too (single-use rotation)
```

```text
POST /auth/logout {refresh_token}
        │
        ▼
  mark the matching RefreshToken revoked_at = now()
```

The **access token** is verified statelessly (signature + `exp` check,
no database round-trip) by a single shared dependency on every
protected route. The **refresh token** is the only thing that can be
revoked server-side — a deliberate trade-off.

The CLI stores `{access_token, refresh_token, expires_at}` in a local
file (`~/.orchai/credentials.json`, permissions `0600`), refreshing
transparently when the access token is close to expiry.

## Enforcement Points

### API

A single FastAPI dependency, e.g. `require_permission("requests:create")`,
attached per route. It:

1. Extracts and verifies the bearer JWT (`HTTPBearer`).
2. Rejects with `401` if missing/invalid/expired.
3. Rejects with `403` if the user lacks the permission (and is not a superuser).
4. Makes the resolved user available to the route handler.

Unauthenticated routes are an explicit, short allowlist: `GET /`,
`GET /health`, `POST /auth/login`, `POST /auth/refresh`,
`GET /openapi.json`, `GET /docs`, `GET /redoc`.

### CLI

A shared Typer callback resolves the token before any command body
runs, exactly like `database_url` resolution is threaded through every
command. `orchai auth login` is the only command that runs without a
pre-existing token.

## Permission Inventory

The mapping from endpoint/command groups to permission keys — coarse
by design. This is the implemented catalog, auto-seeded via
`bootstrap.runtime.PERMISSION_CATALOG`; adding a new key still means
editing that constant, not something dynamic.

```text
requests:create        POST /requests, POST /flows/local, `orchai request`,
                        `orchai local-flow`
requests:advance        POST /requests/{id}/advance, POST /tasks/{id}/advance,
                        `orchai tasks advance`
requests:approve        POST /requests/{id}/approve
projects:connect        POST /projects, POST /projects/operations,
                        `orchai projects operate`
projects:read           GET /projects*, GET /tasks*, GET /executions*,
                        GET /authorizations*, GET /audit*, GET /events*,
                        GET /metrics*, GET /suggestions*
authorizations:decide   POST /authorizations/request,
                        POST /authorizations/{id}/decision
executions:manage       POST /executions/*, `orchai executions *`
suggestions:manage      POST /suggestions/{id}/accept|reject,
                        POST /tasks/{id}/suggestions
policies:evaluate       POST /policies/evaluate
policies:manage         GET/PUT /policies/automatic,
                        `orchai policies automatic show|set`
admin:manage_users      GET/POST /admin/users, PUT /admin/users/{id}/access-roles,
                        GET/POST /admin/access-roles,
                        PUT /admin/access-roles/{id}/permissions,
                        `orchai users *`, `orchai access-roles *`.
                        Superuser-only in practice, but modeled as a
                        normal permission so it can in principle be
                        delegated
admin:db                POST /admin/db/sync, `orchai db sync`
admin:manage_projects   GET /admin/projects, `orchai projects list-all`
                        (Phase 4 -- the admin project directory,
                        distinct from `projects:read`)
```

`GET /projects/discover`, `GET /projects/readiness`, `GET /projects/security`
are read-only, non-persisting filesystem inspections with no project
identity yet to scope by — they still require authentication (any
valid user), but need no specific permission beyond that.

`GET /me`, `PATCH /me`, and `GET /me/projects` (`orchai me
show|update|projects`) require no specific permission key either, but
unlike the routes above they do not go through `require_permission()`
at all — they use a distinct dependency, `require_authenticated_user()`
(`require_authenticated_cli_user()` on the CLI side), that always
demands a valid token regardless of `ORCHAI_AUTH_ENFORCED`. See the
self-service section below for why.

## Interaction With The Chat-First Surface

The `/requests/*` surface (see `Chat-First And Interfaces`) stays the
primary integration point for external clients; IAM sits in front of
it, not inside it. A chat client authenticates once
(`POST /auth/login`), then uses the resulting access token on every
`/requests/*` call exactly as it uses `database_url` today — an
`Authorization: Bearer <token>` header, not a new request field,
keeping the `ChatRequest` payload shape itself unchanged.

## Migration And Rollout

All of the following is done:

1. The identity tables shipped via `0007_identity_and_access.sql`;
   `project_connections` followed in `0008_project_connections.sql`.
2. The bootstrap-admin path and the `/auth/*` endpoints / `orchai auth *`
   commands shipped first, without enforcement — every other route
   stayed open until the next step, so the login/token flow could be
   validated end-to-end before anything could break existing callers.
3. The permission dependency (`require_permission`/`require_cli_permission`)
   was added to every route/command per the inventory above, gated by
   `ORCHAI_AUTH_ENFORCED` (default `false`).
4. The test suite covers both modes: unenforced (existing calls keep
   working with no token) and enforced (a fixture provisions a
   superuser, or a scoped user for a test that specifically wants a
   `403`, and injects the resulting token into `TestClient`/`CliRunner`
   calls).
5. The Phase 4 user-configuration CRUD layer shipped additively, with
   the permission catalog auto-seeded on every identity-runtime build
   so `ORCHAI_AUTH_ENFORCED=true` is actually usable in a fresh
   database.

Flipping `ORCHAI_AUTH_ENFORCED` to `true` **by default** (rather than
per-deployment opt-in, which already works today) remains a
deliberate, separate operational decision the user has not made — see
`docs/TO-DO.md`'s Cross-Cutting Rules.

## Resolved And Open Questions

Resolved during implementation:

- Refresh tokens rotate on every use (`IdentityService.refresh` always
  revokes the presented token, whether or not rotation succeeds past
  that point).
- Argon2id (password hashing) and a signed JWT (access tokens, via
  `JWTAccessTokenIssuer`) were the library choices made at
  implementation time; refresh tokens are hashed with SHA-256
  (`Sha256RefreshTokenHasher`), a deliberately cheaper scheme than
  Argon2id since refresh tokens are high-entropy random strings, not
  low-entropy human-chosen secrets.
- `admin:manage_users` is modeled as a normal permission (not
  code-level-gated beyond that), consistent with `admin:db` and
  `admin:manage_projects` — all three are superuser-only *in practice*
  only because nothing else grants them by default.

Still open:

- Whether `ORCHAI_AUTH_ENFORCED` should ever flip to `true` by default
  is a deployment decision, not an implementation one.
- Whether `Permission` should ever become admin-creatable (currently a
  fixed system catalog by deliberate choice) if a future permission
  key needs to exist before the code that checks it ships.

## User-Configuration CRUD Layer (Phase 4)

Phase 4 adds admin-facing management of the identity data above, plus
a self-service surface, without changing any pre-existing
route/command's behavior or the underlying `AccessRole` N:N model. It
is purely additive.

### Admin-Only Surface (`admin:manage_users` / `admin:manage_projects`)

```text
GET  /admin/users                          orchai users list
POST /admin/users                          orchai users create
PUT  /admin/users/{id}/access-roles        orchai users set-access-roles
GET  /admin/access-roles                   orchai access-roles list
POST /admin/access-roles                   orchai access-roles create
PUT  /admin/access-roles/{id}/permissions  orchai access-roles set-permissions
GET  /admin/projects                       orchai projects list-all
```

`GET /admin/users` and `GET /admin/access-roles` return every field
except `password_hash` (never exposed), each resolved to full nested
detail rather than bare ids: a user's `access_roles` list names, and
an access role's `users`/`permissions` lists are fully resolved
records, not id arrays. `GET /admin/projects` is the admin project
directory: every project with its `capabilities`, readiness levels,
and `connected_user_ids` — distinct from `GET /projects`
(`projects:read`), which lists projects but not those extra admin
details.

### The Mandatory-Role Rule (Replacing A "Default AccessRole")

An earlier design considered a single "Default AccessRole" that a new
user without an explicit role would fall back to (the first
`AccessRole` ever created, transferable to another). It was dropped in
favor of a simpler rule with the same practical guarantee: **creating
a non-superuser requires specifying at least one `AccessRoleId` up
front** (`POST /admin/users`, `PUT /admin/users/{id}/access-roles` —
see `UserRequiresAccessRoleError`). Superusers are exempt, since
`is_superuser=True` already bypasses every permission check. This
means every non-superuser always resolves at least one permission set,
without any new "default" concept, extra table, or sentinel value to
maintain — the N:N model already made a sentinel like `-1` unnecessary
once "zero rows" was recognized as an unambiguous "no role."

`PUT /admin/users/{id}/access-roles` and
`PUT /admin/access-roles/{id}/permissions` are both **replace-all**
operations, not incremental add/remove: the given id list becomes the
complete set (`IdentityService.set_access_roles_for_user`/
`set_permissions_for_role`).

`Permission` rows themselves stay a fixed system catalog — only
*assignment* (role↔permission, user↔role) is admin-editable through
this layer. `AccessRole` creation, by contrast, is exposed
(`POST /admin/access-roles`), since a new named bundle of existing
permissions is low-risk and reuses the already-tested
`IdentityService.create_access_role`.

### `ProjectConnection`: A Reference, Not An Access Boundary

`project_connections` records *which users have connected which
projects to OrchAI* — "this user has touched this project" — for
`GET /admin/projects`'s `connected_user_ids`, `GET /admin/users`'s
`connected_project_ids`, and the self-service `GET /me/projects`. It
is explicitly **not** an access-control boundary: it does not restrict
who can read, register, or operate on a project, and a project may be
connected by any number of users. `POST /projects` auto-links the
caller when a claims-bearing token is present (i.e. under
enforcement), via the same `require_permission` dependency the route
already used, now captured as a parameter instead of a discarded
`dependencies=[...]` entry.

It lives in the *same database as `projects`* (the request's
resolvable/overridable `database_url`), not the identity database:
identity is deliberately pinned to the primary database only (a
security decision, so identity/auth checks can never be redirected via
a per-request override), while "who connected this project" is
descriptive project metadata, like `tasks`/`executions`/
`audit_records`. Consequently it carries no foreign key on `user_id`
— the project database and identity database are not guaranteed to be
the same database under a per-request `database_url` override.
Admin/self routes that need it without a natural per-request database
(`GET /admin/users`, `GET /me`, `GET /me/projects`) resolve it against
the default primary database, matching every other unscoped admin
lookup.

### Self-Service Surface (`/me`, Always Authenticated)

```text
GET   /me            orchai me show
PATCH /me            orchai me update
GET   /me/projects   orchai me projects
```

These require no specific permission key, but they cannot simply be
`require_permission()` with `permission_key=None` either: that
dependency intentionally no-ops (returns `None`, no caller resolved)
when `ORCHAI_AUTH_ENFORCED=false`, which is fine for existing
"authenticated only" routes but leaves "who is the current user"
undefined — and `/me` has no meaningful reading of "show my own
profile" without one. Instead, `/me` uses a distinct dependency,
`require_authenticated_user()` (`require_authenticated_cli_user()` on
the CLI), that always resolves and returns real claims regardless of
the enforcement flag. Introducing this did not change
`require_permission`'s behavior anywhere it is already used — `/me` is
a brand-new surface with zero pre-existing callers.

`PATCH /me` (`UpdateUserProfileCommand`) can change only `username` and
`email`; it has no `access_roles`/`is_superuser`/`id` field, so a user
can never elevate or reassign their own access through self-service.

## Key Rules

- `Authorization`, `RoleName`, and `Execution` keep their pre-existing, unrelated meanings — `AccessRole`/`AccessRoleId` is used throughout, never bare `Role`/`RoleId`
- `Permission` is a fixed system catalog; only role↔permission and user↔role assignment is admin-editable
- a non-superuser always has at least one `AccessRole`; a superuser needs none, since `is_superuser=True` bypasses every check
- the identity database is pinned to the primary database and never redirected by a per-request override
- `/me` always resolves a real caller regardless of `ORCHAI_AUTH_ENFORCED`; every other route's permission check is inert when the flag is off
- `project_connections` is descriptive metadata, never an access-control boundary
- flipping `ORCHAI_AUTH_ENFORCED` to `true` by default is a deployment decision that has not been made

## Main Relationships

- gates every route and command through `Authorization Policy`'s enforcement points
- referenced by `Chat-First And Interfaces` for the `/requests/*` bearer-token flow
- referenced by `Project Adapter And Security` through `project_connections` (descriptive only)
- is the resolved "current logged-in user" that any future per-user authorization revisit would consult (not yet started, see `docs/TO-DO.md`)
