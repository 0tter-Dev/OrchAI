# OrchAI --- Agent Instructions

## Purpose

This document defines the operating rules for AI agents and human
contributors working on OrchAI. It exists to keep agent-driven and
human-driven changes equally disciplined, so implementation,
documentation, and the architectural contract never quietly drift
apart.

## Source Of Truth

Agents must treat the following documents as the primary source of
truth, in this order:

1.  [`docs/ARCHITECTURAL-CONTRACT.md`](docs/ARCHITECTURAL-CONTRACT.md)
    --- invariants, non-goals, and the product vision (§7)
2.  [`docs/DEVELOPMENT-GUIDE.md`](docs/DEVELOPMENT-GUIDE.md) ---
    engineering discipline: architectural rules, code quality, scope
    control, testing/CI direction, and the technology baseline
3.  [`docs/INDEX.md`](docs/INDEX.md) --- the navigation hub for
    everything else
4.  [`docs/STATUS.md`](docs/STATUS.md) --- what is actually
    implemented right now
5.  [`docs/USER-GUIDE.md`](docs/USER-GUIDE.md) --- how the product is
    used end to end

If two documents appear to conflict, `ARCHITECTURAL-CONTRACT.md` and
`DEVELOPMENT-GUIDE.md` take priority until a maintainer explicitly
revises the documentation (`ARCHITECTURAL-CONTRACT.md` §5).

Before any alteration, agents must ground their understanding in the
applicable root-level documentation under `docs/`. Documentation is
the baseline for implementation decisions, not an optional
post-change check.

### `docs/context/` Authorization Gate

Files inside `docs/context/` are bounded-concept context documents.
**AI agents must not read or rely on any `docs/context/` file by
default, with no exemptions** --- including files a change appears to
touch only incidentally, and including mechanical version-reference
updates during an approved version bump. Agents may consult or update
a `docs/context/` file only when the requesting user explicitly
authorizes that specific file for that specific change.

If an agent determines from `docs/INDEX.md`, `docs/STATUS.md`, or
another root-level document that a `docs/context/` file may be
relevant, the agent must ask the requesting user for explicit
authorization before reading it, rather than reading it first and
explaining afterward.

## Core Rules

1.  Preserve domain boundaries.
2.  Do not place project-specific business logic in the OrchAI core.
3.  Keep TASK, ROLE, ACTION, MODEL, CONTEXT, EXECUTION, EVENT, and
    AUTHORIZATION distinct.
4.  State changes must pass through the State Machine.
5.  Suggestions are not authorization.
6.  Do not expand task scope implicitly.
7.  Keep AI providers behind adapters.
8.  Keep external projects behind Project Adapters.
9.  Preserve auditability and traceability.
10. Prefer explicit behavior over implicit conventions.

## Change Discipline

Before changing code:

1.  Identify the affected domain or boundary.
2.  Read the corresponding root-level architectural documentation;
    request explicit authorization before reading the matching
    `docs/context/*.md` file if the change needs that level of detail.
3.  Confirm whether the change affects CLI, API, persistence,
    provider, project-adapter, or policy contracts.
4.  Confirm `ARCHITECTURAL-CONTRACT.md`'s invariants and non-goals
    remain valid for the change.
5.  Prefer the smallest compatible change.
6.  Update tests and documentation when the behavior or contract
    changes.

If a requested change conflicts with the architectural contract,
surface the conflict instead of silently changing the architecture.

## Domain Ownership

```text
Task lifecycle      → Task / State Machine
Authorization       → Authorization / Policy
Execution           → Execution
AI integration      → AI Provider Adapter
Project integration → Project Adapter
Events              → Event subsystem
Persistence         → Infrastructure
CLI / API / UI      → Interface layer
```

See `docs/context/modules-and-domain-structure.md`'s Implementation
Boundary Mapping for the detailed physical-layer mapping behind this
table (subject to the authorization gate above).

## AI Agent Boundaries

Agents may inspect, propose, implement authorized changes, run
authorized validation, report failures, and suggest next actions.

Agents must not silently expand scope, bypass authorization, change
task state directly, replace architecture with provider-specific
behavior, or assume a suggestion is approval.

## Testing

Changes should preserve coverage across the layers defined in
`docs/context/technology-and-test-strategy.md`'s Test Layers (domain
rules, State Machine transitions, authorization rules, execution
construction, adapter contracts, event handling, persistence, and
API/CLI boundaries). A bug involving a domain invariant normally
produces a regression test alongside its fix.

## Documentation Discipline

When introducing or changing features, agents should update:

-   `docs/STATUS.md` for implementation state
-   the relevant file in `docs/context/`, only when the requesting
    user explicitly authorized consultation or update of that scope
-   `docs/INDEX.md` if cross-feature relationships changed
-   `docs/ARCHITECTURAL-CONTRACT.md` if an invariant, non-goal, or
    cross-cutting foundational decision changed
-   `docs/TO-DO.md` when the planned next steps changed or previously
    planned work was completed

Agents must not treat documentation updates as optional cleanup. If
code behavior changes, the agent must actively verify whether related
documentation needs to change and either update it or state why no
update was required.

### Version-Bump Discipline

Every pull request must evaluate whether the project version should
change, per the semantic-versioning guidance in
[`docs/GIT-GITHUB-FLOW.md`](docs/GIT-GITHUB-FLOW.md). When a bump is
required, update every version-bearing file in the same change set ---
`pyproject.toml`, `uv.lock`, any test asserting version output,
`README.md`, and `docs/STATUS.md` --- and state the decision (and the
files updated) explicitly in the pull request description. If no bump
is required, the pull request must explicitly say so and why. This
applies with no exemptions: even a version bump that only touches a
current-version reference inside `docs/context/` requires the same
explicit per-file authorization as any other `docs/context/` change,
per the gating rule above.

Every agent-authored commit must use the Conventional Commit format
documented in `docs/GIT-GITHUB-FLOW.md`, with a commit type and scope
matching the actual change area.

## Code Delivery Workflow

For code-changing or documentation-changing work, agents must follow
[`docs/GIT-GITHUB-FLOW.md`](docs/GIT-GITHUB-FLOW.md) when agent-driven
delivery is enabled or explicitly requested. The expected sequence is:

1.  for a `docs/TO-DO.md` roadmap step, verify the remote `main`
    branch state, update local `main`, and create the work branch from
    that synchronized baseline
2.  read the applicable root-level documentation under `docs/`;
    request explicit authorization before reading any needed
    `docs/context/` file
3.  make the focused code and documentation changes
4.  run the relevant local validation commands
    (`uv run ruff check`, `uv run pytest --basetemp=...`,
    `uv run orchai --help`, `uv lock --check`)
5.  inspect the resulting diff and working tree status
6.  commit the validated change with a Conventional Commit message
7.  push the branch to the remote repository
8.  open a pull request into `main` using
    `.github/pull_request_template.md` as the description structure,
    explicitly stating the version-bump decision

Agent-driven branch, commit, push, and pull request operations must
use only `git` and `gh` through the CLI. Agents must not use GitHub
web UI automation, remote GitHub write connectors, or hidden
repository operations for this workflow, must not merge their own
pull requests, and must leave final review and merge authority to a
human maintainer with repository admin access.

### Repository Git Identity

Agent-driven work on this repository uses a dedicated, repository-
local Git identity instead of the machine-global one:
`0tter-Dev-AI <otter.dev.ai@gmail.com>`. This identity is configured
repository-locally (never in global Git config), authenticates
through its own SSH key and `gh` session, and is the default author
for AI-agent commits and pull requests on OrchAI unless a maintainer
explicitly configures a replacement. See
`docs/GIT-GITHUB-FLOW.md`'s Repository Identity Guidance for the full
setup model.

## Architectural Boundaries

-   **Dependency direction**: `Interfaces → Application → Domain`,
    with `Infrastructure` depending only on domain/application
    contracts. Domain code must not depend on concrete infrastructure
    providers (FastAPI, Typer, SQLAlchemy, HTTPX, provider SDKs). See
    `docs/context/modules-and-domain-structure.md`.
-   **Physical architecture**: the established modular-monolith
    structure (`src/orchai/{domain,application,infrastructure,
    interfaces,bootstrap}/`) is not re-derived here --- see
    `docs/context/modules-and-domain-structure.md`. Logical components
    must remain inside their appropriate architectural layer even when
    they share the same process.
-   **Technology baseline**: the accepted stack is documented once in
    `docs/DEVELOPMENT-GUIDE.md`'s Selected Technology Baseline and
    `docs/context/technology-and-test-strategy.md`. Do not introduce a
    replacement technology for convenience without checking those
    documents and confirming the change against
    `docs/DEVELOPMENT-GUIDE.md`'s Scope Control section.
-   **Runtime**: long-running execution is asynchronous and uses
    `asyncio` tasks; do not introduce RabbitMQ, Redis, Celery, Kafka,
    or another distributed queue without an explicit, documented
    architectural decision. Task lifecycle belongs to the Task Engine,
    Execution lifecycle to the Execution Engine, and State Machines
    remain authoritative for lifecycle transitions.
-   **Project ownership**: connected projects remain external systems.
    Do not mirror complete project source trees or documentation into
    OrchAI by default; access project resources only through Project
    Adapters; persist references, metadata, context-resolution
    information, and orchestration history as required; treat project
    content as project-owned even when an agent can read or modify it.
-   **AI providers**: AI providers remain behind provider adapters.
    Domain and application code must not import provider SDKs
    directly. Model selection uses provider-independent concepts and
    explicit capabilities.

## Error Handling

Keep errors associated with their originating boundary:

```text
Domain Error
Authorization Error
State Transition Error
Execution Error
Provider Error
Project Adapter Error
Context Error
Persistence Error
Configuration Error
```

Do not convert every error into task failure.

## Security

Treat external AI providers as untrusted execution resources.

Sensitive project context may cross a provider boundary only when
authorization and policy permit it.

Never place secrets in source code or documentation.

## Completion Standard

A change is complete only when implementation, tests, documentation,
and the architectural contract remain consistent.

## Naming Discipline

Agents should prefer kebab-case for new free-form file and directory
names, and must preserve externally required names when a platform,
framework, language, or repository convention depends on them (see
`docs/DEVELOPMENT-GUIDE.md`'s Naming Rules for the full list of
exceptions).

## Safety Rules

Agents must not:

-   silently redefine OrchAI's architectural contract or product
    vision
-   bypass documented authorization, policy, or readiness rules
-   introduce autonomous AI control over task/execution progression
    beyond what the configured execution mode already permits
-   treat generated analysis or suggestions as verified operational
    truth
-   erase or weaken the documentation-first workflow without
    authorization
-   read or rely on a `docs/context/` file without the requesting
    user's explicit authorization for that specific file
-   run Git commands such as `git add`, `git commit`, `git push`,
    `git merge`, `git rebase`, or any remote GitHub write operation
    unless the user explicitly requests that action or has explicitly
    enabled the documented agent-driven Git workflow for this
    repository
-   use the machine-global Git identity when operating in an
    agent-driven Git workflow instead of the repository-local
    `0tter-Dev-AI` identity documented above

When Git actions are needed but were not explicitly requested, agents
should explain the required commands and let the user run them
manually.
