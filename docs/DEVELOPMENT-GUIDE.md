# Development Guide

## Purpose

This guide defines how OrchAI should be developed, changed, and
maintained. It is the lean, day-to-day engineering-discipline
document — for the product-level narrative, see
[`ARCHITECTURE.md`](ARCHITECTURE.md); for non-negotiable invariants,
see [`ARCHITECTURAL-CONTRACT.md`](ARCHITECTURAL-CONTRACT.md); for how
architecture maps to code responsibilities, see
[`IMPLEMENTATION-MAP.md`](IMPLEMENTATION-MAP.md); for domain-specific
detail, see the relevant `docs/context/*.md` file.

## Development Priorities

1. Preserve the architectural boundaries defined in
   `ARCHITECTURAL-CONTRACT.md` and `docs/context/*.md`
2. Keep domain rules centralized and framework-independent
3. Prefer explicit adapter contracts over ad hoc integration
4. Keep documentation and implementation synchronized
5. Optimize for maintainability before convenience

## Architectural Rules

- follow Clean/Hexagonal Architecture: `interfaces/ → application/ →
  domain/`, with `infrastructure/` depending only on domain and
  application contracts, and `bootstrap/` as the composition root
  (see `docs/context/modules-and-domain-structure.md`)
- domain code never imports FastAPI, Typer, SQLAlchemy, HTTPX,
  provider SDKs, or any concrete infrastructure implementation
- `Task Engine` owns Task lifecycle coordination; `Execution Engine`
  owns Execution coordination; State Machines own valid lifecycle
  transitions — no other component redefines these
- AI resources are reached only through the AI Provider Adapter
  boundary (LiteLLM, see `docs/context/execution-engine.md`); no
  domain rule, CLI, API, or unrelated application service calls a
  provider SDK directly
- connected projects are reached only through `Project Adapter`
  implementations; OrchAI persists project identity, adapter
  configuration, references, and orchestration state, not complete
  project content (see `docs/context/project-adapter-and-security.md`
  and `docs/context/persistence.md`)
- context resolution distinguishes `REQUESTED` / `AUTHORIZED` /
  `RESOLVED` / `PROVIDED` at all times (see
  `docs/context/context-management.md`)
- avoid leaking persistence, transport, or environment-loading
  concerns into domain rules
- keep interface clients (CLI, API, Desktop) as callers of the same
  application services — none of them owns domain rules

## Code Quality Rules

- apply SOLID principles pragmatically
- prefer cohesive modules with clear, single responsibilities
- avoid dead code, commented-out code, and speculative abstractions
- avoid placeholder shared layers or generic kernels unless they have
  a clear present responsibility
- avoid tightly coupling business logic to framework-specific
  behavior
- keep side effects explicit and testable
- favor readability over cleverness

## Scope Control

Changes are acceptable when they:

- strengthen the documented architecture
- improve maintainability without changing project intent
- clarify orchestration, authorization, or state-transition behavior
- improve project readiness, security, or adapter behavior without
  weakening the LEVEL_0-3 readiness gates
- improve testability or observability

Changes require explicit review when they:

- conflict with `ARCHITECTURAL-CONTRACT.md`'s principles or
  Architectural Non-Goals (§3)
- weaken authorization, readiness, or security boundaries
- couple the core directly to a single AI provider instead of using
  the adapter boundary
- bypass the Project Adapter boundary when accessing connected
  project content
- materially reshape the physical module structure or the
  cross-cutting decisions recorded in `ARCHITECTURAL-CONTRACT.md` §6
- start the broader per-user authorization revisit described in
  `docs/context/identity-and-access.md`'s Migration And Rollout
  section without the user's explicit authorization

Future-oriented extensibility is acceptable when it does not add
speculative implementation weight — the project should not pre-build
distributed messaging, multi-tenant, or service-decomposition support
without a concrete validated need (see
`docs/context/technology-and-test-strategy.md`'s Explicit Non-Goals).

## Documentation Rules

- new features must be reflected in `docs/STATUS.md`
- feature behavior belongs in the relevant `docs/context/*.md` file
- architectural invariants belong in `ARCHITECTURAL-CONTRACT.md`;
  engineering discipline belongs in this guide
- cross-feature relationship changes belong in `docs/INDEX.md`
- user-facing workflow changes must be reflected in the user-facing
  guides referenced from `docs/INDEX.md`
- relevant documentation must be updated alongside meaningful
  implementation changes, especially code changes
- pull requests must include a semantic version decision and must
  update all version-bearing files when the change requires a bump
- `docs/TO-DO.md` must remain focused on the next planned steps and
  must not retain work that is already implemented
- `docs/TO-DO.md` roadmap steps must be granular enough for one
  branch and one pull request; broader themes must be split into
  ordered steps before implementation starts
- before implementing any `docs/TO-DO.md` roadmap step, verify the
  remote `main` branch state, update local `main`, and branch from
  that synchronized baseline, per
  [`GIT-GITHUB-FLOW.md`](GIT-GITHUB-FLOW.md)
- changes to established foundations — the selected technology
  baseline, architectural invariants, or documented non-goals —
  require explicit user approval before they are applied

## Naming Rules

- prefer kebab-case for new documentation files, non-Python
  source-adjacent files, branch names, and free-form repository
  artifact names
- avoid spaces in file and directory names
- use underscores only when a language, framework, platform, or
  external tool requires an exact name
- keep standardized dotfiles and externally required repository names
  unchanged

Examples of valid required exceptions:

- `.github/ISSUE_TEMPLATE/`
- `.github/PULL_REQUEST_TEMPLATE.md`
- Python dunder files such as `__init__.py`
- Git-standard files such as `.gitignore`

## Testing Direction

Test layers, from narrowest to broadest:

```text
UNIT → CONTRACT → INTEGRATION → END-TO-END
```

- **Unit** — State Machine, authorization rules, domain invariants,
  execution construction, context resolution, suggestion rules,
  configuration validation
- **Contract** — AI Provider Adapter contract, Project Adapter
  contract, repository contract, event consumer contract
- **Integration** — persistence, event dispatch, application
  services, API, CLI, adapter integration
- **End-to-end** — at least one complete workflow (`TASK → PLAN →
  AUTHORIZATION → IMPLEMENT → REVIEW → VALIDATION → COMPLETION`),
  including failure and rework paths
- **Security** — unauthorized execution, unauthorized context,
  cross-role progression, cloud context restriction, capability
  mismatch, expired/revoked authorization

A bug involving a domain invariant normally produces a regression
test alongside its fix. See
`docs/context/technology-and-test-strategy.md` for the full test
strategy and its relationship to the technology baseline.

## Git And GitHub Direction

The full delivery flow — branching, Conventional Commits, version
discipline, squash-merge, the dedicated AI-agent Git identity, and the
agent-driven pull request sequence — is documented in
[`GIT-GITHUB-FLOW.md`](GIT-GITHUB-FLOW.md) and is not restated here.
In summary: keep changes small and reviewable, prefer short-lived
branches, require pull-request review for `main`, and treat
documentation and tests as part of the expected change set for every
pull request.

## CI/CD Direction

`OrchAI - Full Validation` (`.github/workflows/OrchAI-FullValidation.yml`)
gates every pull request and push to `main` with dependency sync,
lockfile-consistency check, `ruff`, `pytest`, and a CLI smoke test.
`OrchAI - Release Validation`
(`.github/workflows/OrchAI-Release.yml`) is a manual,
`workflow_dispatch`-triggered workflow that validates a release tag
against `pyproject.toml`'s version and generates release notes via
`scripts/release.py`. Deployment automation may be added later, but
CI quality gates are expected to stay ahead of it.

## Selected Technology Baseline

The current implementation baseline is:

| Concern | Baseline |
|---|---|
| Language | Python 3.14 |
| Dependency / Environment Management | `uv` |
| API | FastAPI |
| CLI | Typer |
| Persistence Toolkit | SQLAlchemy 2.x |
| Primary / Local Database | PostgreSQL / SQLite |
| Async Runtime | `asyncio` |
| Testing | pytest |
| Linting / Formatting | `ruff` (pinned) |
| AI Provider Access | LiteLLM |
| Desktop Shell | `pywebview` on Windows WebView2 |
| Desktop Frontend (build-time only) | Vite + React |
| Containerization | Docker |

The full baseline, including the rationale for each entry and the
explicit non-goals for the current stack, lives in
`docs/context/technology-and-test-strategy.md` — this table is a
pointer, not a second source of truth.

## Technology Decision Policy

The core technology direction is selected and stable. Future changes
to it should still be evaluated according to:

- fit for the documented architecture
- testability
- maintainability
- operational clarity
- whether a concrete, validated need exists — not speculative
  future-proofing

Changes to the selected baseline require explicit user approval, per
the Documentation Rules above.
