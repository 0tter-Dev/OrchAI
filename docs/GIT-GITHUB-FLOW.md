# Git And GitHub Flow

## Purpose

This document defines the standard Git and GitHub workflow for maintaining, extending, reviewing, and releasing OrchAI. It replaces `CONTRIBUTING.md` and `docs/engineering/DELIVERY-BASELINE.md` as the single source of truth for delivery process.

## Objective

Create a disciplined and lightweight delivery flow that keeps the repository stable and auditable while OrchAI moves from its current implementation baseline (`v0.1.11`) toward a broader public surface.

## Core Principles

- keep `main` stable and reviewable
- prefer short-lived branches
- keep pull requests small and focused
- evolve documentation, tests, and implementation together
- use GitHub as the collaboration and review hub
- use semantic versioning consistently
- add CI quality gates before introducing full CD automation

## Workflow Model

OrchAI uses a simplified GitHub Flow model.

This means:

- `main` is the primary protected branch
- all work starts from `main`
- all changes return through pull requests
- no direct pushes are allowed to `main`
- branches are deleted after merge
- work may be authored either by a human contributor or by an authorized AI agent using a dedicated repository identity

OrchAI does not adopt a heavy Git Flow model at this stage. A simpler branch model reduces process weight and makes maintenance easier while the project's public surface is still stabilizing.

## Branch Strategy

### Primary Branch

- `main`

Rules:

- always releasable
- protected in GitHub
- updated only through reviewed pull requests

### Working Branches

Every implementation, documentation, test, refactor, or CI task uses a short-lived branch created from `main`.

Recommended naming patterns:

- `feat/<short-scope>`
- `fix/<short-scope>`
- `docs/<short-scope>`
- `refactor/<short-scope>`
- `test/<short-scope>`
- `ci/<short-scope>`
- `chore/<short-scope>`

Examples:

- `docs/git-github-flow`
- `ci/release-validation-workflow`
- `feat/chat-first-suggestion-flow`
- `fix/identity-token-lifecycle`

This supersedes the prior `codex/<topic>` convention. Existing `codex/*` branches remain valid until merged or retired, but new branches should use the prefixes above.

### Future Release Branches

Release branches are not part of the default workflow for the current stage. They should only be introduced later if OrchAI needs parallel stabilization work, simultaneous maintenance of multiple supported versions, or a formal pre-release hardening window.

If that becomes necessary, the recommended format is `release/<version>` (for example `release/0.2.0`).

### Future Hotfix Branches

If a critical correction is needed after releases become more formal, hotfix branches may be created from `main` using `hotfix/<short-scope>`. This is a future exception flow, not the normal path for current development.

## Change Unit Discipline

Each branch should solve one coherent problem.

Roadmap items in `docs/TO-DO.md` should be written at the same granularity as pull requests. A roadmap step should normally map to one short-lived branch, one coherent Conventional Commit change unit, and one pull request. If a roadmap theme would require multiple pull requests, split it into smaller ordered steps before implementation starts.

Good examples:

- translate the API endpoints report to English
- redesign `docs/STATUS.md` as a pure status snapshot
- consolidate the execution/task/event/role context documents
- add the release-validation workflow

Avoid mixing unrelated concerns such as:

- documentation restructuring plus unrelated CLI behavior changes
- authorization changes plus repository tooling refactors
- provider adapter logic plus release process changes

## Pull Request Flow

The expected lifecycle for each change is:

1. define or confirm the scope through an issue, roadmap item, or explicit task
2. create a short-lived branch from `main`
3. implement the focused change
4. update tests and documentation as needed
5. validate locally before opening the pull request
6. open a pull request into `main`
7. pass CI checks
8. receive at least one review
9. merge with squash merge
10. delete the branch

For agent-driven code changes, the agent completes the local implementation, documentation alignment, validation, diff review, branch creation, commit, push, and pull request creation itself when the user has explicitly enabled or requested that delivery mode. The pull request remains the handoff point for human review and merge.

After a pull request is merged and the remote branch is deleted, contributors and agents should prune stale remote-tracking references and delete the corresponding local branch once `main` has been updated.

## Contributor Modes

OrchAI supports two compatible delivery modes:

- human-driven pull requests, where the contributor authors the branch, commit, and pull request directly
- agent-driven pull requests, where an authorized AI agent performs the Git work on behalf of the repository using a dedicated repository identity

Both modes must follow the same protected-branch, validation, documentation, and review requirements.

## Agent-Driven Pull Request Rules

When agent-driven delivery is enabled for this repository:

- the agent may create branches, commit changes, push branches, and open pull requests
- the agent must use only `git` and `gh` through the CLI for branch, commit, push, and pull request operations
- the agent must not use GitHub web UI automation, remote GitHub write connectors, or hidden repository operations for this workflow
- the agent must not merge its own pull requests
- final review and merge authority remains with a human maintainer who has repository admin access
- the agent uses a dedicated repository identity instead of the machine-global Git identity (see Repository Identity Guidance below)
- that identity policy is documented in `AGENTS.md`

## Pull Request Rules

Every pull request should:

- target `main`
- solve one coherent objective
- use `.github/pull_request_template.md` as the standard description template
- explain why the change exists
- list the main technical decisions
- describe any architecture impact
- state the validation performed
- mention documentation updates
- state the version bump decision and list the files updated when the version changes
- mention follow-up work if relevant

Pull requests should be considered incomplete if they change behavior without updating the relevant documentation or without documenting the version bump decision.

## Merge Strategy

The standard merge mode is `Squash and merge`.

Reasons:

- keeps `main` history compact
- makes the release history easier to read
- reduces noisy branch-level commit history in the permanent timeline
- works well with short-lived branches and PR review discipline

`Rebase and merge` may be tolerated later for very disciplined contributor flows, but it is not the default. `Merge commit` remains disabled for now.

## Commit Convention

OrchAI uses Conventional Commits for human-authored and agent-authored commits.

Commit messages follow:

- `<type>: <imperative summary>`
- `<type>(<scope>): <imperative summary>`
- `<type>!: <imperative summary>` for intentional breaking changes
- `<type>(<scope>)!: <imperative summary>` for scoped intentional breaking changes

Recommended commit types: `feat`, `fix`, `docs`, `refactor`, `test`, `ci`, `chore`.

Recommended scopes: `core`, `api`, `cli`, `desktop`, `provider`, `adapter`, `policy`, `docs`, `ci`.

Examples:

- `feat(api): add chat-first request approval endpoint`
- `fix(policy): correct readiness gate threshold check`
- `docs(git): define release process`
- `ci(repo): add release validation workflow`
- `feat(provider): add LiteLLM streaming capability check`

Rules:

- write commits in imperative form
- keep each commit coherent
- avoid vague messages such as `update`, `changes`, or `misc`
- use `!` only when a change intentionally introduces a breaking contract
- choose a scope that matches the primary area changed
- align the commit type with the version decision documented in the pull request

## Versioning Model

OrchAI uses Semantic Versioning. The project is currently in the `0.x` phase, so versioning should be interpreted with extra discipline:

- patch increments (`0.1.11` to `0.1.12`) for fixes, small internal improvements, documentation refinements, test additions, and CI changes that do not redefine product scope
- minor increments (`0.1.x` to `0.2.0`) for meaningful increments in product capability, public workflow shape, or project maturity
- `1.0.0` only when the public baseline is stable enough that breaking behavior becomes exceptional instead of expected

### Version Bump Guidance

Every pull request must evaluate whether the project version should change. When a bump is required, update all relevant version-bearing files in the same change set:

- `pyproject.toml` (`project.version`)
- `uv.lock`
- any test asserting version output
- `README.md`
- `docs/STATUS.md`

If no bump is required, the pull request should explicitly say so.

### Commit Type And Version Relationship

The commit type does not mechanically determine the version bump, but it should guide the decision:

- `feat`: usually requires a version bump; patch for narrow increments, minor for larger capability phases
- `fix`: usually requires a patch bump when user-visible behavior changes
- `docs`: may require a patch bump when it changes governance, workflow policy, architecture, or documented product scope; may avoid a bump for wording-only corrections
- `refactor`: may require a patch bump if it changes operational behavior, public contracts, or supported workflows
- `test`: usually does not require a bump unless tests formalize a new public contract or release rule
- `ci`: may require a patch bump when CI changes release, validation, or merge requirements
- `chore`: should explain why the change is not product-visible; dependency or tooling changes may still require a bump

### Release Tag Format

Git tags use the format `v0.1.11`, `v0.1.12`, `v0.2.0`. The GitHub release title should match the tag version.

Before publishing a release, maintainers should run the manual `OrchAI - Release Validation` workflow with the intended tag. The workflow validates that the tag uses the documented format, matches the version in `pyproject.toml`, and produces a release-notes artifact from the Git commit history.

## Release Discipline

Each release should include a version tag, release notes, a concise change summary, notable documentation updates when relevant, and a list of known limitations when relevant.

Before creating a release, confirm:

- CI is green on `main`
- documentation is aligned
- the repository is in a stable state
- the version in project metadata matches the intended release
- the manual release validation workflow passed for the intended tag
- the generated release-notes artifact was reviewed

## Local Validation Before Pull Request

Before opening a pull request, contributors run:

```powershell
uv sync --dev
uv lock --check
uv run ruff check
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
uv run pytest --basetemp ".pytest-tmp/run-$timestamp"
uv run orchai --help
```

`ruff` is pinned exactly (`==0.15.11` in `pyproject.toml`) and must run via `uv run ruff check`, not `uv tool run`/`uvx`, to avoid resolving a different Ruff version with a different rule set.

If the workspace temp directory is blocked on Windows, use a writable system temp path instead:

```powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$base = Join-Path ([System.IO.Path]::GetTempPath()) "orchai-pytest-$timestamp"
.venv\Scripts\python.exe -m pytest --basetemp $base
```

Avoid reusing the same `--basetemp` directory across repeated Windows runs, since `pytest` may fail while recreating the directory.

## Documentation Gate

Changes should update documentation whenever they alter architecture or policy, workflow expectations, setup or operational guidance, module behavior, or implementation status.

At minimum, contributors should evaluate whether the change requires updates to `docs/STATUS.md`, `docs/INDEX.md`, the relevant architecture or domain document for the affected area, the user-facing guides, and this document.

This section will be tightened once the `docs/context/` consolidation lands: at that point, AI agents must not read or rely on `docs/context/` unless the requesting user explicitly authorizes the specific file, mirroring the same rule documented in `AGENTS.md`.

## Current CI Baseline

The `OrchAI - Full Validation` workflow (`.github/workflows/OrchAI-FullValidation.yml`) runs a single `Backend Quality` job on pull requests targeting `main`, on pushes to `main`, and on manual dispatch:

- checkout
- install `uv`
- Python 3.14 setup
- `uv sync --dev`
- `uv lock --check`
- `uv run ruff check`
- `uv run pytest --basetemp=...`
- `uv run orchai --help` (CLI smoke check)

There is no `frontend` job yet: `apps/desktop/frontend/` is not yet committed and has no `lint`/`test` scripts defined. A `frontend` job should be added to this same workflow file once the desktop frontend is committed and gains real lint/test tooling — mirroring how OrchFlow's equivalent workflow validates its backend and frontend as two jobs inside one centralized file, rather than as separate workflow files.

There is no `mypy` gate yet, and no step builds or tests the repository's `Dockerfile`.

## CI Direction

### Stage 1 (current)

The repository has the backend quality baseline described above for `v0.1.11`.

### Stage 2 (future)

- stricter unit, integration, and contract test separation as the suite grows
- more focused API contract assertions for chat-first and identity/access endpoints
- a smoke check that builds and runs the `Dockerfile` image
- a desktop-shell smoke check once the desktop packaging stabilizes

### Stage 3 (this pull request)

- version tag validation through the manual `OrchAI - Release Validation` workflow
- release-notes generation from Git commit history through the same manual workflow
- release asset preparation remains future work

## CD And DevOps Future Direction

Full CD should not be implemented before the product has stable build outputs worth distributing. The recommended evolution is:

1. repository governance
2. CI quality gates
3. release discipline
4. packaging and artifact generation
5. delivery automation for stable product outputs

## GitHub Repository Configuration Standard

The remote repository should be configured to support this flow. Required settings:

- protect `main`
- require pull requests before merge
- require at least one approval
- require status checks before merge
- require branches to be up to date before merge when CI is enabled
- disable direct pushes to `main`
- enable branch deletion after merge
- allow squash merge
- disable merge commits

These are GitHub repository settings, not code, and must be applied by a maintainer with admin access.

### Review Model Notes

GitHub does not allow a pull request author to satisfy the required approval with their own review. Because of that, repositories using agent-driven pull requests should treat the reviewer as a distinct human maintainer account from the PR author identity.

For a solo-maintainer repository, the recommended practical setup is:

- keep the primary maintainer account as the admin reviewer and merger
- create one dedicated GitHub identity for agent-authored pull requests
- grant that identity only the minimum repository access needed to create branches and pull requests
- authenticate local agent tooling with that dedicated identity instead of the maintainer identity

## Repository Identity Guidance

The preferred identity model for agent-driven work is:

- one dedicated GitHub user for repository automation and AI-authored pull requests
- a dedicated SSH key for that identity (`IdentitiesOnly=yes`), not the maintainer's key
- repository-local Git `user.name` and `user.email` configuration matching that identity
- repository-scoped authentication for `git` and `gh`
- no reliance on the machine-global Git identity for agent-authored work

Recommended setup sequence:

1. create a dedicated GitHub account for agent-authored work
2. invite that account to the repository with write access
3. generate a dedicated SSH key for that identity
4. add the public key to the dedicated account and configure an SSH host alias with `IdentitiesOnly=yes`
5. switch the repository's remote from HTTPS to that SSH host alias
6. set repository-local `git config user.name` and `git config user.email` to the dedicated identity
7. keep the maintainer account as the reviewer and merger on protected branches

This account and key creation is a manual step performed by the repository owner; an AI agent must not create GitHub accounts or authenticate as a human user.

## Initial Label Model

Recommended labels:

- `type:feature`, `type:bug`, `type:docs`, `type:refactor`, `type:test`, `type:ci`, `type:chore`
- `area:core`, `area:api`, `area:cli`, `area:desktop`, `area:docs`, `area:devops`
- `priority:high`, `priority:medium`, `priority:low`

## Operating Notes For Agents And Contributors

- do not bypass pull request review on protected branches
- do not treat documentation as optional
- do not bundle unrelated work into a single branch
- do not leave merged local working branches around as active work; prune and delete them after confirming the merge is present on local `main`
- do not introduce release automation before basic CI is stable
- do not treat a green CI run as a substitute for design review
- do not let an agent use the maintainer's Git identity for authorship when a dedicated repository identity is expected

## Current Adoption State

As of `2026-09-06`, this document establishes the Git and GitHub delivery flow for OrchAI, replacing `CONTRIBUTING.md` and `docs/engineering/DELIVERY-BASELINE.md` as the source of truth for delivery process. Those two documents remain in place until the root documentation consolidation step retires them.

The repository should continue evolving with:

- the dedicated AI-agent identity, once created by the repository owner
- the `docs/context/` migration and its authorization-gating rule
- deeper CI quality gates as implementation scope grows
