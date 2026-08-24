# ADR-012 --- Authentication and Access Control for the CLI and API

## Status

Accepted --- Implemented (v0.1.11). All four phases described below are
built and tested: the identity data model, the JWT token lifecycle, the
permission-enforcement wiring across the API and CLI, and the
admin/self-service CRUD layer for users, access roles, and projects. See
`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` for the maintained,
detailed account of the implementation, and `docs/STATUS.md` for the
project-wide status. This ADR is retained as the historical design record
of the decision; it is not updated to mirror every implementation detail.

## Context

OrchAI's API and CLI currently have no notion of identity. Confirmed by
direct inspection of `src/orchai/interfaces/api/main.py`: there is no
`CORSMiddleware`, no `APIKeyHeader`/`HTTPBearer` dependency, no
`Depends(...)` guarding any route. Every endpoint — connecting a project,
creating a request, granting an authorization, running an execution — is
reachable by any caller who can reach the process. The CLI has the
equivalent property: any local invocation acts with full privilege. This
was flagged as a known gap in `docs/API-ENDPOINTS-REPORT.md` and is already
anticipated by `docs/architecture/CHAT-FIRST-REQUEST-MODEL.md` section 9
("Authentication: the request boundary is the natural place to introduce
per-user or per-client API keys when multi-tenant operation is needed").

As OrchAI moves toward real AI provider adapters and toward being used by
more than one person or automated client against the same deployment, this
gap stops being acceptable. The project needs:

- a way to identify who (or what) is making a call, across both the API
  and the CLI;
- a way to grant or restrict what an identity can do;
- a built-in superuser/admin identity that can operate without
  restriction and administer other identities' permissions;
- everything persisted in the database, not in configuration files or
  environment variables, so it survives restarts and can be managed at
  runtime.

**Naming collision to resolve up front.** OrchAI's domain already defines
an `Authorization` aggregate (`domain/authorization`) — a request-scoped
grant for a specific `(role, action)` pair against a task, decided via
`POST /authorizations/{id}/decision`. That concept answers "is the
Orchestrator allowed to run this AI action on this task right now?" It has
nothing to do with "is this HTTP caller who they claim to be, and are they
allowed to call this endpoint at all?" — the question this ADR addresses.
Reusing the word "authorization" for both would make every future
conversation about either one ambiguous. This ADR therefore introduces a
separate vocabulary — **Identity and Access Management (IAM)**, with
**Users**, **Permissions**, and **Access Tokens** — and deliberately avoids
calling any part of it "authorization." `RoleName` (`DEVELOPER`,
`QUALITY_AGENT`, ...) is likewise a distinct, pre-existing concept — the
orchestration role an AI action plays — and is not reused or overloaded
here either.

This ADR originally documented the design only, with implementation to
follow once the design was settled. Implementation is now complete — see
the Status section above and `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`
for what was actually built.

## Decision

Introduce an Identity and Access Management (IAM) layer, orthogonal to the
existing Task/Authorization/Execution domain, covering both the API and
the CLI:

1. **Users** are persisted entities with a hashed credential, an
   `is_superuser` flag, and an `is_active` flag.
2. **Permissions** are coarse, string-named capabilities (for example
   `requests:create`, `requests:advance`, `authorizations:decide`,
   `projects:connect`, `admin:manage_users`), each mapped to one or more
   endpoints/CLI commands. A user's effective permissions are the union of
   permissions granted directly and permissions granted through any
   **Role** (a named, reusable bundle of permissions) assigned to them.
3. A user with `is_superuser = true` bypasses all permission checks
   unconditionally — this is the "unlimited use" superuser the product
   needs, and it is also the only identity that can create users and
   grant/revoke permissions and roles for others.
4. **Authentication** is JWT-based:
   - `POST /auth/login` exchanges a username/password for a short-lived
     **access token** (JWT, signed with a server-held secret, carrying the
     user id and effective permissions as claims) and a longer-lived
     **refresh token** (opaque, stored hashed in the database so it can be
     individually revoked).
   - `POST /auth/refresh` exchanges a valid refresh token for a new access
     token.
   - `POST /auth/logout` revokes a refresh token.
   - The CLI performs the same exchange (`orchai auth login`) and persists
     the resulting tokens in a local, user-only-readable credentials file,
     resolved automatically by every subsequent CLI command exactly like
     `ORCHAI_DATABASE_URL` is resolved today.
5. Every API route except `GET /health`, `GET /`, `POST /auth/login`,
   `POST /auth/refresh`, and the OpenAPI/docs routes requires a valid
   access token. Every CLI command except `auth login` requires a resolved
   token (from the credentials file, `ORCHAI_TOKEN`, or an explicit
   `--token`).
6. Enforcement is declarative per route/command: each one declares the
   permission it requires (or none, if only authentication — not a
   specific permission — is needed), checked by a single shared dependency
   (API) / decorator (CLI), not scattered ad hoc checks.
7. Everything is persisted relationally, in new tables introduced by a new
   migration (`0007_identity_and_access.sql`, following the existing
   hand-rolled raw-SQL migration convention in
   `infrastructure/persistence/db/migrations/` — one shared, dialect-portable
   SQL file applied identically to SQLite and PostgreSQL, there is no
   separate PostgreSQL migration path) — no in-memory-only user store,
   consistent with how every other aggregate in the system is already
   persisted.
8. A bootstrap path creates the first superuser without requiring an
   already-authenticated caller (a chicken-and-egg problem otherwise):
   either a one-time `orchai auth bootstrap-admin` CLI command that only
   succeeds when zero users exist yet, or `ORCHAI_ADMIN_USERNAME` /
   `ORCHAI_ADMIN_PASSWORD` environment variables consumed on first startup
   with no users present. Exact mechanism to be settled during
   implementation design; both are compatible with this ADR.

See `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` for the detailed data
model, endpoint/command inventory, token lifecycle, and the mapping from
existing endpoints to required permissions.

## Rationale

- **Persisted, not config-based**: permissions and users must be
  manageable at runtime by the superuser, without redeploying or editing
  files on disk — matching how every other piece of OrchAI state already
  works.
- **JWT for the access token**: stateless verification for the common
  case (every request does not need a database round-trip just to check
  who is calling), while the refresh token stays server-side and
  revocable, avoiding the classic "JWT can't be revoked" problem for the
  token that matters most for session termination.
- **Coarse permissions over per-field ACLs**: OrchAI's endpoints are
  already organized into a small number of coherent capability groups
  (requests, tasks, authorizations, executions, projects, admin). Modeling
  permissions at that grain keeps the system's mental model simple for a
  first version, while `Role` gives room to compose bundles without
  needing per-user permission lists to grow unbounded. Finer-grained
  scoping (for example, per-project access) is a natural extension once
  the coarse model is in place and is called out as future work rather
  than blocking this decision.
- **Superuser as an explicit, first-class flag** (not "a role named
  admin with every permission"): a role-based "all permissions" user would
  break the moment a new permission is added and someone forgets to add it
  to that role. An explicit bypass flag cannot silently drift out of sync.
- **Same model for CLI and API**: the CLI already talks to the same
  application services as the API (both go through
  `build_sqlalchemy_runtime`/`build_local_flow_dependencies_from_settings`).
  A user identity enforced only at the API boundary while the CLI remains
  unrestricted would leave a wide-open bypass; both must authenticate
  against the same persisted identity store.

## Consequences

Positive:

- callers are identifiable and their access is auditable (a natural
  extension: the existing `audit_repository` records can carry a
  `decided_by`/`requester` value that is now a real, verified user
  identity instead of a free-text string supplied by the caller, e.g. the
  `requester="cli"` / `decided_by="cli"` literals currently hardcoded
  throughout `run_local_flow`/`run_project_operation`/`run_task_workflow_stage`);
- a genuine multi-user, multi-client deployment becomes possible without
  everyone sharing full access;
- the superuser gives a clear, explicit escape hatch for operators and
  automated pipelines that need unrestricted access, without requiring a
  permission list.

Trade-offs / follow-up work required:

- every existing endpoint and CLI command needs a permission assignment
  decision before enforcement is turned on — this is nontrivial audit work
  covered in the companion architecture document;
- a new dependency for password hashing (argon2id, via a maintained
  library such as `argon2-cffi`) and one for JWT handling are required;
  per `AGENTS.md`, the signing secret must come from configuration/
  environment (`ORCHAI_JWT_SECRET`), never hardcoded or committed, and
  must be rotatable;
  concrete version pins should be re-verified against current advisories
  at implementation time rather than assumed from this ADR;
- existing tests that call the API/CLI directly (`TestClient`,
  `CliRunner`) will need a fixture that provisions/authenticates a test
  user (or a superuser) before this is enforced, or the test suite breaks
  wholesale the day enforcement is turned on;
- this introduces the first real "secret" the project has to manage in
  production (the JWT signing key, and stored password hashes) — the
  security posture of the persistence layer for these tables specifically
  deserves its own review pass during implementation, separate from the
  general database security already in place.

## Non-Goals (this ADR)

- OAuth2/OIDC federation with an external identity provider — a superuser
  and password-based users cover the immediate need; federation is a
  plausible future ADR, not this one.
- Per-project or per-resource fine-grained ACLs beyond the coarse
  permission groups described here.
- Rate limiting / abuse protection — a related but separate concern.
- OAuth2/OIDC federation and per-project fine-grained ACLs remain out of
  scope for the implemented system as well as the original design; the
  implementation matches the target design described in this ADR and its
  companion architecture document, `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`.

## Supersedes

None. Extends ADR-004 (API-First Interface Boundary) and ADR-011
(Chat-First Request Interface) by adding an access-control layer in front
of both, without changing either's request/response contracts beyond the
new authentication requirement.
