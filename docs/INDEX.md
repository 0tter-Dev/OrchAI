# OrchAI Documentation Index

## Purpose

This is the single authoritative entry point into OrchAI's
documentation. It does not replace the documents it references —
only summarize what each one is for and how they relate, so a human
or an AI agent can find the right document without duplicating any of
their content here.

## Reading Order

1. [`ARCHITECTURAL-CONTRACT.md`](ARCHITECTURAL-CONTRACT.md) — invariants, non-goals, product vision
2. [`ARCHITECTURE.md`](ARCHITECTURE.md) — conceptual system architecture
3. [`DEVELOPMENT-GUIDE.md`](DEVELOPMENT-GUIDE.md) — engineering discipline
4. [`IMPLEMENTATION-MAP.md`](IMPLEMENTATION-MAP.md) — architecture-to-code bridge
5. [`STATUS.md`](STATUS.md) — what is actually implemented right now
6. `docs/context/*.md` — the specific bounded concept relevant to the change
7. [`USER-GUIDE.md`](USER-GUIDE.md) / [`OPERATIONS-REFERENCE.md`](OPERATIONS-REFERENCE.md) — using OrchAI as a product
8. [`GIT-GITHUB-FLOW.md`](GIT-GITHUB-FLOW.md) — how a change actually ships
9. [`TO-DO.md`](TO-DO.md) — what is planned next

## Documentation Map

### Architectural Foundation

-   [`ARCHITECTURAL-CONTRACT.md`](ARCHITECTURAL-CONTRACT.md) ---
    Architectural invariants and non-negotiable principles; §6 folds
    in still-relevant cross-cutting decisions from the retired ADR
    format, §7 carries the product-level narrative folded in from the
    retired `VISION.md`.
-   [`ARCHITECTURE.md`](ARCHITECTURE.md) --- The conceptual system
    architecture: layers, core concepts, execution modes, and
    architectural boundaries. Implementation-baseline detail lives in
    `DEVELOPMENT-GUIDE.md` and `docs/context/*.md` instead of here.
-   [`DEVELOPMENT-GUIDE.md`](DEVELOPMENT-GUIDE.md) --- Day-to-day
    engineering discipline: architectural rules, code quality, scope
    control, documentation/naming rules, testing and CI/CD direction,
    and the selected technology baseline.
-   [`IMPLEMENTATION-MAP.md`](IMPLEMENTATION-MAP.md) --- The bridge
    from architecture to concrete code responsibilities: component
    mapping, configuration layers, boundaries, execution-mode flows,
    capability model, and testing/security boundaries.

### Project State And Planning

-   [`STATUS.md`](STATUS.md) --- The single, sole status document; a
    pure implementation-state snapshot, nothing else.
-   [`HISTORY.md`](HISTORY.md) --- A one-time, frozen archive of how
    the project reached its current state; never extended going
    forward.
-   [`TO-DO.md`](TO-DO.md) --- The forward-looking backlog: the
    current implementation sequence and the next planned roadmap
    steps.

### Context Documentation

`docs/context/` is the consolidation of the former
`docs/architecture/` and `docs/domains/` directories into one file per
bounded concept. Each follows the same template: Purpose, Objective,
Current Status, domain-specific sections, Key Rules, Main
Relationships.

-   [`context/tasks-and-lifecycle.md`](context/tasks-and-lifecycle.md)
    --- Task identity, scope, lifecycle, and the state machine.
-   [`context/execution-engine.md`](context/execution-engine.md) ---
    Execution construction, results, and the AI Provider Adapter
    boundary, including streaming.
-   [`context/roles-actions-models.md`](context/roles-actions-models.md)
    --- Roles, Actions, Models, and Capabilities.
-   [`context/events-and-state.md`](context/events-and-state.md) ---
    Event contract, dispatch strategy, and the State Machine
    relationship.
-   [`context/authorization-policy.md`](context/authorization-policy.md)
    --- Authorization concepts and the MANUAL/SUGGESTED/AUTOMATIC
    execution modes.
-   [`context/identity-and-access.md`](context/identity-and-access.md)
    --- Users, access roles, permissions, JWT authentication, and the
    desktop single-user identity simplification.
-   [`context/project-adapter-and-security.md`](context/project-adapter-and-security.md)
    --- Project Adapter boundary, security profile, and the LEVEL_0-3
    readiness gates.
-   [`context/context-management.md`](context/context-management.md)
    --- Context lifecycle and authorization for AI execution.
-   [`context/chat-first-and-interfaces.md`](context/chat-first-and-interfaces.md)
    --- The `/requests` chat-first projection, the CLI/API/UI
    boundary, and the Conversation/Message domain.
-   [`context/observability.md`](context/observability.md) --- Audit,
    Metrics, and Suggestions.
-   [`context/configuration.md`](context/configuration.md) --- The
    layered configuration contract and current environment variables.
-   [`context/persistence.md`](context/persistence.md) --- What OrchAI
    persists, the repository boundary, and the relational model.
-   [`context/modules-and-domain-structure.md`](context/modules-and-domain-structure.md)
    --- Physical source-tree organization, domain purity, and the
    Module concept (Forge, Studio).
-   [`context/technology-and-test-strategy.md`](context/technology-and-test-strategy.md)
    --- The accepted technology baseline and testing layers.
-   [`context/deployment-and-desktop.md`](context/deployment-and-desktop.md)
    --- Headless and desktop deployment shapes.

### Using OrchAI

-   [`USER-GUIDE.md`](USER-GUIDE.md) --- End-to-end narrative
    walkthrough for users adopting OrchAI in real projects.
-   [`OPERATIONS-REFERENCE.md`](OPERATIONS-REFERENCE.md) --- Detailed
    configuration, policy/readiness, API/CLI, and troubleshooting
    reference for real-project usage.
-   [`API-ENDPOINTS-REPORT.md`](API-ENDPOINTS-REPORT.md) --- A
    point-in-time (`v0.1.11`) verification report of API behavior;
    historical, not kept current — see `STATUS.md` for current state.

### Delivery And Contribution

-   [`../AGENTS.md`](../AGENTS.md) --- Rules and constraints for human
    and AI contributors.
-   [`GIT-GITHUB-FLOW.md`](GIT-GITHUB-FLOW.md) --- Branch, commit,
    version, and pull request discipline, including the dedicated
    AI-agent Git identity and delivery sequence.

### Archived Decisions

The ADR format is retired as the active decision-record mechanism.
Still-relevant decisions now live in
[`ARCHITECTURAL-CONTRACT.md`](ARCHITECTURAL-CONTRACT.md) §6
(cross-cutting) or the matching `docs/context/*.md` file's "Key Rules"
section (single-domain) above.

-   [`archive/decisions/INDEX.md`](archive/decisions/INDEX.md) --- All
    17 ADRs, preserved verbatim for historical record.

## Relationship Overview

Documentation flows in one direction, mirroring the dependency
direction of the code itself:
`ARCHITECTURAL-CONTRACT.md` (invariants and non-goals) constrains
`ARCHITECTURE.md` (the conceptual model), which `docs/context/*.md`
elaborates per bounded concept, which `IMPLEMENTATION-MAP.md` bridges
to actual code responsibilities. `DEVELOPMENT-GUIDE.md` runs alongside
this chain rather than inside it — it is the engineering-discipline
layer (architectural rules, code quality, scope control, technology
baseline) that every step above must respect, and the only place that
baseline is documented once. A future implementation decision that
conflicts with any of these documents must not silently redefine them
(`ARCHITECTURAL-CONTRACT.md` §5) — the conflict is resolved explicitly
first.

Within `docs/context/`, the fifteen bounded-concept files split into
three clusters that mirror how they were consolidated and how they
depend on each other: an execution-facing cluster
(`tasks-and-lifecycle.md`, `execution-engine.md`,
`roles-actions-models.md`, `events-and-state.md`) that the
Orchestrator coordinates directly; an identity/authorization/security
cluster (`authorization-policy.md`, `identity-and-access.md`,
`project-adapter-and-security.md`, `context-management.md`,
`chat-first-and-interfaces.md`) that gates what the execution cluster
is allowed to do and through which surface; and an infrastructure
cluster (`observability.md`, `configuration.md`, `persistence.md`,
`modules-and-domain-structure.md`, `technology-and-test-strategy.md`,
`deployment-and-desktop.md`) that the other two run on top of.
`archive/decisions/` sits outside this flow entirely — it is a
historical record, not a source of active rules; every decision still
in force was folded into the live document that owns it.

`STATUS.md`, `HISTORY.md`, and `TO-DO.md` track time rather than
architecture: `STATUS.md` is what is true right now, `HISTORY.md` is a
frozen account of how the project got there, and `TO-DO.md` is what
comes next. None of the three restates architectural rules — they
link to the documents above instead.

`USER-GUIDE.md` and `OPERATIONS-REFERENCE.md` are the product-facing
projection of the same architecture: the execution modes, readiness
gates, and policy/authorization/suggestion distinctions a user
encounters are the same ones `ARCHITECTURAL-CONTRACT.md` and
`docs/context/authorization-policy.md` define, just described from the
outside. `GIT-GITHUB-FLOW.md` and `AGENTS.md` govern how any of this
documentation or code actually changes — the former is the process any
contributor (human or agent) follows, the latter is the rulebook an AI
agent specifically must follow, including which of the documents above
it may consult without the user's explicit authorization.

## Navigation Rule

When investigating a topic:

1.  Start here to locate the authoritative document.
2.  Follow the most specific document available.
3.  Do not duplicate authoritative information in an index.
4.  If implementation and documentation disagree, consult `STATUS.md`
    and the relevant architectural contract before changing either.

## Status Authority

The root [`STATUS.md`](STATUS.md) is the single, sole status document
for the project — it describes overall project state as a pure
snapshot. No other document tracks status; there is nothing left to
diverge from it.

For how the project reached its current state, see
[`HISTORY.md`](HISTORY.md), a one-time, frozen archive that is never
extended. Going forward, what changed release-over-release is covered
by generated release notes (`scripts/release.py`), not a document like
this one.
