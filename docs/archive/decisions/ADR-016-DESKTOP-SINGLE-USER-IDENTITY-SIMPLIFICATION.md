# ADR-016 --- Single Local User Identity for OrchAI Desktop

## Status

Accepted --- Design only; implementation is follow-up work (OrchAI
Desktop Phase 1, see `docs/architecture/DESKTOP-APPLICATION.md`).

## Context

ADR-012 designed, and v0.1.8--v0.1.11 fully implemented, a JWT-based
multi-user Identity and Access Management (IAM) layer: persisted
`User`/`AccessRole`/`Permission` records, Argon2id password hashing,
access/refresh token issuance, and declarative per-route/per-command
permission enforcement (`docs/architecture/IDENTITY-AND-ACCESS-MODEL.md`).
It ships gated behind `ORCHAI_AUTH_ENFORCED`, default `false` --- every
endpoint is reachable with no authentication until that flag is
explicitly turned on.

`docs/TO-DO.md`'s Priority 1 "Scope note" separately identifies a much
larger, deliberately un-started body of work: making `Project Adapter`
bindable to more than one user and checking, per execution, whether
*this specific logged-in user* may invoke a given role/action/model ---
a near-total revisit of how requests flow through the system. That note
is explicit that starting it requires the user's own explicit
authorization, not an incidental decision folded into other work.

OrchAI Desktop (`docs/architecture/DESKTOP-APPLICATION.md`) is a single
process running on one person's own Windows machine, reached only over
`127.0.0.1`, with one person using it. There is no second party on the
same deployment to authenticate against, and no network boundary to
defend with a bearer token. Building the desktop shell should not
require deciding, right now, whether or how to start that larger
multi-user refactor --- and it should not discard the IAM implementation
already built and tested.

## Decision

OrchAI Desktop runs with `ORCHAI_AUTH_ENFORCED` left at its default,
`false`. No desktop-specific code ever sets it to `true`. The existing
IAM implementation is reused only for **attribution**, not for
**access control**:

1. On first launch, `apps/desktop/shell/server_runner.py` checks
   whether any `User` row exists (reusing the existing
   `orchai auth bootstrap-admin` logic path). If none exists, it
   silently provisions exactly one local `User` with
   `is_superuser=True`, username derived from the OS account
   (`os.getlogin()` or equivalent), and a random, never-surfaced
   password hash --- there is no login screen, and no code path ever
   verifies this password, since `require_permission` stays inert with
   auth unenforced.
2. A new FastAPI dependency, `require_desktop_local_user()`, distinct
   from both `require_permission()` (inert when unenforced) and
   `require_authenticated_user()` (always requires a real bearer
   token), always resolves to this single local user without checking
   any token. It exists purely so that `requester`/`decided_by` fields
   on `Task`, `Authorization`, and `Audit` records carry a real,
   consistent identity (the local user's `UserId`) instead of the
   free-text literal `"cli-user"` currently hardcoded in
   `run_local_flow`/`run_project_operation`/`run_task_workflow_stage`.
   `apps/desktop/shell/server_runner.py` wires this dependency in place
   of `require_permission`/`require_authenticated_user` only for the
   routes the desktop shell itself calls; the API's existing behavior
   for any other caller (CLI, direct HTTP) is unchanged.
3. This decision explicitly does **not**: set `ORCHAI_AUTH_ENFORCED=true`;
   start the "Scope note" multi-user refactor (multi-user `Project
   Adapter` binding, per-user permission checks on execution); add a
   login screen, password prompt, or credential storage to the desktop
   shell; or remove, deprecate, or alter any part of the existing IAM
   implementation. `docs/TO-DO.md`'s Priority 1 "Scope note" remains
   exactly as un-started as before this ADR.

## Rationale

- **Reuse, don't discard**: the IAM implementation (v0.1.8--v0.1.11) is
  fully built and tested; using it for attribution costs nothing and
  gives real identity values in audit/authorization records instead of
  a hardcoded literal.
- **No login screen for a single-user local process**: a desktop app
  that only one person on one machine ever runs has nothing meaningful
  to authenticate --- there is no other party it is protecting data
  from on that same machine. Requiring a password the code never
  actually checks would be theater, not security.
- **Explicitly not starting the multi-user refactor**: per the user's
  own standing instruction (recorded in `docs/TO-DO.md`'s Priority 1
  Scope note), changes to who-may-do-what require explicit
  authorization before implementation begins. This ADR is scoped
  narrowly to make the desktop shell buildable without implicitly
  deciding that larger, separate question.
- **A distinct dependency (`require_desktop_local_user`), not reuse of
  `require_authenticated_user`**: the latter's contract is "a real,
  verified caller identity is required" (used today by the `/me`
  self-service surface, which has no meaningful unauthenticated
  reading); silently satisfying that contract without verification
  would misrepresent what `require_authenticated_user` guarantees
  everywhere else it is used.

## Consequences

Positive:

- the desktop shell can be built immediately without a pending decision
  on multi-user authorization blocking it;
- `Task`/`Authorization`/`Audit` records produced by the desktop shell
  carry a real `UserId` instead of a hardcoded string, which is a small
  net improvement over the current CLI behavior;
- zero risk of accidentally starting the larger, explicitly-gated
  multi-user refactor as a side effect of shipping the desktop app.

Trade-offs:

- the desktop build offers no actual access control --- anyone with
  local access to the machine and the ability to reach
  `127.0.0.1:<port>` while the app is running has full access, same as
  anyone with local access to a CLI session today; this is accepted as
  appropriate for a single-user local desktop tool, not a gap to close
  later without a deliberate decision to do so;
- if a future desktop feature needs real multi-user separation (e.g.
  shared/synced conversations across machines), this ADR must be
  revisited and superseded, not quietly worked around.

## Non-Goals (this ADR)

- Any form of login UI, password prompt, or credential storage in the
  desktop shell.
- Deciding whether or when to flip `ORCHAI_AUTH_ENFORCED` to `true`
  more broadly --- that remains a separate, un-made decision.
- Starting the multi-user `Project Adapter` / per-user execution
  authorization refactor described in `docs/TO-DO.md`'s Priority 1
  Scope note.

## Supersedes

None. Extends ADR-012 (Authentication and Access Control for the CLI
and API) by defining a desktop-specific, attribution-only usage of the
existing IAM implementation, without altering ADR-012 itself.
