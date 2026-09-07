# OrchAI --- To-Do / Roadmap

## Purpose

This document tracks the next planned steps for OrchAI. It is a
task-planning document, not a project-state document --- for current
implementation state, see [`STATUS.md`](STATUS.md); for architectural
rules, see [`ARCHITECTURAL-CONTRACT.md`](ARCHITECTURAL-CONTRACT.md).
This document should not duplicate the rationale already recorded
there --- it links to it instead.

## Current Implementation Sequence

The completed implementation sequence covers the executable
orchestration foundation (Task/Role/Action/Model/Context/Execution/Event/
Authorization domains, the state machine, the local/cloud AI provider
boundary, and Project Adapters); Identity and Access Management Phases 1
through 4 (an isolated identity domain with Argon2id password hashing,
JWT access/refresh token lifecycle, declarative per-route/per-command
permission enforcement gated behind `ORCHAI_AUTH_ENFORCED`, and an admin
CRUD layer plus a self-service `/me` surface); the LiteLLM provider
migration replacing the Ollama and OpenAI-Codex adapters, routed
entirely through `ORCHAI_AI_MODEL`'s `<provider>/<model>` prefix; the
OrchAI Desktop initiative (a Windows desktop chat application with a
`pywebview` shell, persistent conversations, SSE streaming, explicit
message-to-Task escalation via an Approval Card, and a Module concept
with Forge and Studio modules); Phase 7 hardening (a runtime-configurable
`AutomaticExecutionPolicy`, real execution cancellation, metrics
aggregation, and an `orchestrator.py` decomposition into five sibling
modules); a root `Dockerfile` for the headless CLI/API deployment shape;
and the Git and GitHub delivery-flow foundation (`docs/GIT-GITHUB-FLOW.md`,
the `OrchAI - Full Validation` and `OrchAI - Release Validation`
workflows, and an updated pull request template).

`v0.2.0` consolidates the completed OrchAI Desktop initiative and closes
out Identity and Access Management Phases 1 through 4 as a stable
baseline for authenticated, desktop-capable orchestration. `v0.2.1`
translates `docs/API-ENDPOINTS-REPORT.md` to English and redesigns
`docs/STATUS.md` as a pure status snapshot, archiving its prior
phase-by-phase narrative into a frozen `docs/HISTORY.md`.

The current AI-agent Git identity for automated pull requests is
`0tter-Dev-AI`.

Implemented planning items should be removed from this document as work
progresses so it remains focused on what comes next. Roadmap items
should be granular by default: each numbered step should describe one
coherent pull-request-sized change, not a broad workstream that requires
multiple pull requests to finish. When a planned workstream is still too
broad, split it into sequential steps before implementation starts.

## Next Implementation Roadmap

1. `docs(context): consolidate execution, task, event, and role documentation`

   Objective: begin merging `docs/architecture/` and `docs/domains/`
   into a single `docs/context/`, starting with the execution-facing
   cluster.

   Main scope: create `docs/context/tasks-and-lifecycle.md`,
   `execution-engine.md`, `roles-actions-models.md`, and
   `events-and-state.md` from `domains/TASKS.md`, `domains/EXECUTION.md`,
   `domains/ROLES.md`/`ACTIONS.md`/`MODELS.md`/`CAPABILITIES.md`,
   `domains/EVENTS.md`, `EVENT-STRATEGY.md`, and the matching sections of
   `architecture/COMPONENTS.md` and `ADAPTER-CONTRACTS.md`, using the
   shared Purpose/Objective/Current Status/Key Rules/Main Relationships
   template; delete the superseded source files.

   Likely documents to update: the four new `docs/context/*.md` files,
   the superseded `docs/architecture/`/`docs/domains/` source files
   (removed), `docs/INDEX.md`.

   Expected validation: documentation diff review; grep the repository
   for dangling references to the removed file paths.

   Planned semantic decision: patch bump from `0.2.1` to `0.2.2`, because
   this restructures documented architecture boundaries.

2. `docs(context): consolidate identity, authorization, and security documentation`

   Objective: continue the `docs/context/` consolidation with the
   identity- and security-sensitive cluster.

   Main scope: create `docs/context/authorization-policy.md`,
   `identity-and-access.md`, `project-adapter-and-security.md`,
   `context-management.md`, and `chat-first-and-interfaces.md` from
   `domains/AUTHORIZATION.md`, `IDENTITY-AND-ACCESS-MODEL.md`,
   `domains/PROJECTS.md`, `PROJECT-SECURITY-AND-READINESS.md`,
   `domains/CONTEXT.md`, `CHAT-FIRST-REQUEST-MODEL.md`,
   `API-UI-BOUNDARY.md`, and the matching sections of
   `ADAPTER-CONTRACTS.md` and `COMPONENTS.md`, keeping the
   MANUAL/SUGGESTED/AUTOMATIC authorization mechanics and the LEVEL_0-3
   readiness gates intact rather than summarized; delete the superseded
   source files.

   Likely documents to update: the five new `docs/context/*.md` files,
   the superseded source files (removed), `docs/INDEX.md`.

   Expected validation: documentation diff review; grep for dangling
   references; confirm no authorization or readiness-gate rule was
   dropped rather than relocated.

   Planned semantic decision: patch bump from `0.2.2` to `0.2.3`, because
   this restructures documented security-relevant governance.

3. `docs(context): consolidate infrastructure documentation`

   Objective: finish the `docs/context/` consolidation with the
   remaining infrastructure-facing files.

   Main scope: create `docs/context/observability.md`, `configuration.md`,
   `persistence.md`, `modules-and-domain-structure.md`,
   `technology-and-test-strategy.md`, and `deployment-and-desktop.md`
   from `domains/AUDIT.md`/`METRICS.md`/`SUGGESTIONS.md`,
   `domains/CONFIGURATION.md`, `CONFIGURATION-ARCHITECTURE.md`,
   `PERSISTENCE-STRATEGY.md`, `MODULES.md`/`DOMAIN-MODULE-STRUCTURE.md`/
   `APPLICATION-STRUCTURE.md`, `TECHNOLOGY-STACK.md`/`TEST-STRATEGY.md`,
   and `DEPLOYMENT-MODEL.md`/`DESKTOP-APPLICATION.md`; remove the
   now-empty `docs/architecture/` and `docs/domains/` directories along
   with their own `INDEX.md`/`STATUS.md` files.

   Likely documents to update: the six new `docs/context/*.md` files,
   `docs/architecture/` and `docs/domains/` (removed entirely),
   `docs/INDEX.md`.

   Expected validation: documentation diff review; grep for dangling
   references; confirm `docs/architecture/` and `docs/domains/` no
   longer exist.

   Planned semantic decision: patch bump from `0.2.3` to `0.2.4`, because
   this completes a documented architecture restructuring.

4. `docs(decisions): retire the ADR format into docs/archive/decisions`

   Objective: stop using standalone ADRs as the active decision-record
   mechanism, matching the OrchFlow-inspired model.

   Main scope: move all 17 ADRs plus `docs/decisions/README.md` and
   `INDEX.md` verbatim into `docs/archive/decisions/`, with a banner
   marking them historical; fold each ADR's still-relevant decision
   statement into either `ARCHITECTURAL-CONTRACT.md`'s new "Foundational
   Decisions" section (cross-cutting decisions) or the matching
   `docs/context/*.md` file's "Key Rules" section (single-domain
   decisions), without carrying over the superseded rationale/consequences
   prose.

   Likely documents to update: `docs/archive/decisions/` (new location
   for all ADRs), `docs/ARCHITECTURAL-CONTRACT.md`, the affected
   `docs/context/*.md` files, `docs/INDEX.md`.

   Expected validation: documentation diff review; confirm every one of
   the 17 ADRs has both an archive copy and exactly one live landing
   spot for its decision.

   Planned semantic decision: patch bump from `0.2.4` to `0.2.5`, because
   this changes the documented decision-record process.

5. `docs(architecture): add DEVELOPMENT-GUIDE.md and trim ARCHITECTURE.md/IMPLEMENTATION-MAP.md`

   Objective: introduce a lean, OrchFlow-style engineering-discipline
   document without losing the deeper reference material OrchAI's larger
   system needs.

   Main scope: create `docs/DEVELOPMENT-GUIDE.md` from the
   implementation-baseline and boundary sections of `ARCHITECTURE.md`
   and `IMPLEMENTATION-MAP.md`; trim those two documents to remove the
   sections now owned by the new guide, keeping them as the canonical
   conceptual-architecture and roadmap-to-code documents respectively.

   Likely documents to update: `docs/DEVELOPMENT-GUIDE.md` (new),
   `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION-MAP.md`, `docs/INDEX.md`.

   Expected validation: documentation diff review; confirm no sentence
   is lost, only relocated or deduplicated.

   Planned semantic decision: patch bump from `0.2.5` to `0.2.6`, because
   this changes documented engineering governance.

6. `docs(architecture): fold VISION.md into ARCHITECTURAL-CONTRACT.md and retire the old delivery baseline`

   Objective: remove the two remaining root documents superseded by
   earlier steps.

   Main scope: fold `docs/VISION.md`'s product narrative into
   `ARCHITECTURAL-CONTRACT.md` as a new "Product Vision" subsection,
   deduplicating its Forge/Studio description against
   `docs/context/modules-and-domain-structure.md`; delete
   `docs/VISION.md`, `CONTRIBUTING.md`, and
   `docs/engineering/DELIVERY-BASELINE.md` (both already superseded by
   `docs/GIT-GITHUB-FLOW.md`).

   Likely documents to update: `docs/ARCHITECTURAL-CONTRACT.md`,
   `docs/VISION.md` (removed), `CONTRIBUTING.md` (removed),
   `docs/engineering/DELIVERY-BASELINE.md` (removed), `docs/INDEX.md`.

   Expected validation: documentation diff review; grep for remaining
   references to the removed files.

   Planned semantic decision: patch bump from `0.2.6` to `0.2.7`, because
   this retires governance documents still linked from elsewhere.

7. `docs(user-guide): merge the onboarding and operations guides`

   Objective: replace two overlapping user documents with a walkthrough
   plus a reference, matching the OrchFlow split.

   Main scope: create `docs/USER-GUIDE.md` (end-to-end narrative
   walkthrough) and `docs/OPERATIONS-REFERENCE.md`
   (configuration/policy/troubleshooting reference) from
   `docs/USER-ONBOARDING.md` and `docs/USER-OPERATIONS-GUIDE.md`,
   deduplicating the config/CLI snippets currently repeated across both
   plus `README.md`; fix `README.md`'s stale pre-LiteLLM
   environment-variable example in the same change.

   Likely documents to update: `docs/USER-GUIDE.md` (new),
   `docs/OPERATIONS-REFERENCE.md` (new), `docs/USER-ONBOARDING.md`
   (removed), `docs/USER-OPERATIONS-GUIDE.md` (removed), `README.md`,
   `docs/INDEX.md`.

   Expected validation: documentation diff review; confirm the corrected
   environment-variable example matches the current LiteLLM adapter.

   Planned semantic decision: patch bump from `0.2.7` to `0.2.8`, because
   this changes documented user-facing setup guidance.

8. `docs(index): rewrite INDEX.md as the single navigation hub`

    Objective: give the now-final documentation set one authoritative
    entry point.

    Main scope: rewrite `docs/INDEX.md` with a reading order, a one-line
    purpose per document, and a single "Relationship Overview" section
    describing how documents relate, now that every file referenced has
    its final name and location.

    Likely documents to update: `docs/INDEX.md`.

    Expected validation: documentation diff review; check every link in
    the rewritten index for a broken reference.

    Planned semantic decision: no version bump; pure navigation, no
    documented behavior or governance change.

9. `docs(agents): restructure AGENTS.md`

    Objective: align OrchAI's agent rulebook with the finished
    documentation model.

    Main scope: add an explicit numbered Source-of-Truth order
    (`ARCHITECTURAL-CONTRACT.md` -> `DEVELOPMENT-GUIDE.md` ->
    `INDEX.md` -> `STATUS.md` -> `USER-GUIDE.md`); add the
    `docs/context/` authorization-gating rule for AI agents, applying to
    every file with no exemptions; add the dedicated Git identity and
    agent-driven pull request delivery sequence; fold
    version-bump-per-PR discipline into the documentation-discipline
    section; preserve every existing OrchAI-specific safety rule,
    re-homed rather than rewritten.

    Likely documents to update: `AGENTS.md`.

    Expected validation: documentation diff review; confirm every
    existing safety rule survives the restructure.

    Planned semantic decision: patch bump from `0.2.8` to `0.2.9`,
    because this changes documented agent governance.

## Cross-Cutting Rules

- before starting any roadmap step, verify the remote `main` state,
  fast-forward local `main`, and branch from that synchronized baseline,
  per [`GIT-GITHUB-FLOW.md`](GIT-GITHUB-FLOW.md)
- implement each roadmap step as one coherent Conventional Commit change
  unit and one pull request; document the version decision in the PR
- keep each roadmap step small enough for one branch and one pull
  request; split larger themes into separate ordered steps before
  implementation starts
- evaluate version impact before starting a step and confirm it once the
  diff is complete
- never drop an ADR's decision content during retirement (item 4): every
  decision lands in exactly one place, cross-checked against the mapping
  table in the OrchFlow-inspired refactor plan before its source ADR is
  archived
- keep `docs/ARCHITECTURAL-CONTRACT.md`'s 23 numbered principles verbatim
  through every consolidation step; summarize or link to them, never
  restate them with drift
- after any file move or rename, grep the repository for references to
  the old path before merging
- do not start the broader per-user authorization revisit (multi-user
  Project Adapter binding, per-user action/role/model authorization)
  without the user's explicit authorization --- Phase 4 of Identity and
  Access Management was an explicit prerequisite the user asked for
  first, not the start of that refactor; see
  `docs/architecture/IDENTITY-AND-ACCESS-MODEL.md` §6 (folding into
  `docs/context/authorization-policy.md` per item 2 above)
- do not add a roadmap item that conflicts with
  `docs/ARCHITECTURAL-CONTRACT.md`'s non-goals without first revisiting
  the contract explicitly

## Open Conceptual Questions

These do not block current implementation but should be resolved with
an explicit documented decision before more code accretes around an
ambiguous boundary:

- Agent as an explicit domain concept versus a composition of role,
  policy, model, and capabilities.
- Workflow responsibility versus State Machine responsibility.
- Task Engine versus Application Orchestration as distinct concepts.
- Execution Engine versus Execution domain.
- Model Manager versus model/provider contracts.
- Context Manager versus Context domain.
- Project Adapter boundary versus Project domain.
- Concurrency/parallel-task execution readiness
  (`docs/IMPLEMENTATION-MAP.md` §16) --- no implementation is needed
  now, but new features should keep task/execution identity, scope, and
  modifications explicit so this remains possible later.
