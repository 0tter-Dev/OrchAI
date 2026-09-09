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
phase-by-phase narrative into a frozen `docs/HISTORY.md`. `v0.2.2`
begins the `docs/context/` consolidation with the execution-facing
cluster (`tasks-and-lifecycle.md`, `execution-engine.md`,
`roles-actions-models.md`, `events-and-state.md`), removing the seven
domain files and one architecture file they fully supersede. `v0.2.3`
continues with the identity/authorization/security cluster
(`authorization-policy.md`, `identity-and-access.md`,
`project-adapter-and-security.md`, `context-management.md`,
`chat-first-and-interfaces.md`), also removing `ADAPTER-CONTRACTS.md`
once both of its sections (AI Provider Adapter, Project Adapter) had
homes across this cluster and the previous one. `v0.2.4` finishes the
`docs/context/` consolidation with the infrastructure cluster
(`observability.md`, `configuration.md`, `persistence.md`,
`modules-and-domain-structure.md`, `technology-and-test-strategy.md`,
`deployment-and-desktop.md`), removing every remaining file in
`docs/architecture/` and `docs/domains/` (including `COMPONENTS.md`
and both directories' own `INDEX.md`) so neither directory exists
anymore. `v0.2.5` retires the ADR format: all 17 ADRs move verbatim
into `docs/archive/decisions/`, and their still-relevant decisions
fold into `ARCHITECTURAL-CONTRACT.md` §6 (4 cross-cutting decisions)
or the matching `docs/context/*.md` file's Key Rules (13 single-domain
decisions, including a new Conversations section in
`chat-first-and-interfaces.md` and a streaming section in
`execution-engine.md` for content that had no prior home). `v0.2.6`
introduces `docs/DEVELOPMENT-GUIDE.md`, a lean, OrchFlow-style
engineering-discipline document (architectural rules, code quality,
scope control, documentation/naming rules, testing and CI/CD
direction, and the selected technology baseline), and trims
`ARCHITECTURE.md`/`IMPLEMENTATION-MAP.md` of the implementation-baseline
sections it now owns, pointing to it and to the relevant
`docs/context/*.md` files instead of restating them. `v0.2.7` folds
`docs/VISION.md`'s product narrative into `ARCHITECTURAL-CONTRACT.md`
§7 (deduplicated against `docs/context/modules-and-domain-structure.md`'s
Forge/Studio definitions) and deletes `docs/VISION.md`,
`CONTRIBUTING.md`, and `docs/engineering/DELIVERY-BASELINE.md`, both
already fully superseded by `docs/GIT-GITHUB-FLOW.md`. `v0.2.8`
replaces `docs/USER-ONBOARDING.md` and `docs/USER-OPERATIONS-GUIDE.md`
with `docs/USER-GUIDE.md` (end-to-end narrative walkthrough) and
`docs/OPERATIONS-REFERENCE.md` (configuration/policy/API/CLI/
troubleshooting reference), deduplicating the config and CLI snippets
repeated across the old pair and `README.md`, and fixes `README.md`'s
stale pre-LiteLLM environment-variable example. `docs/INDEX.md` is
then rewritten as the single navigation hub: a Reading Order, a
one-line purpose per document, and a single "Relationship Overview"
section describing how the documentation set relates, now that every
file referenced has its final name and location (no version bump ---
pure navigation). `v0.2.9` restructures `AGENTS.md` to match the
finished documentation model: a numbered Source-of-Truth order, the
`docs/context/` authorization-gating rule applied to every file with
no exemptions, the dedicated Git identity and agent-driven pull
request delivery sequence, and version-bump-per-PR discipline folded
into documentation discipline --- completing the OrchFlow-model
documentation and delivery-flow refactor this document has tracked
since `v0.1.11`.

The current AI-agent Git identity for automated pull requests is
`0tter-Dev-AI`, now documented in `AGENTS.md` itself.

Implemented planning items should be removed from this document as work
progresses so it remains focused on what comes next. Roadmap items
should be granular by default: each numbered step should describe one
coherent pull-request-sized change, not a broad workstream that requires
multiple pull requests to finish. When a planned workstream is still too
broad, split it into sequential steps before implementation starts.

## Next Implementation Roadmap

The OrchFlow-model documentation and delivery-flow refactor this
section tracked is complete as of `v0.2.9`. The next planned
workstream wires `execute_stream()` (implemented and unit-tested,
per `docs/context/execution-engine.md`, but with no Task-bounded
caller yet) into the Task-bounded execution path, so an escalated
message's real Task execution can stream incrementally the same way
non-escalated conversation messages already do via
`ConversationAIProviderPort.complete_stream()`. It is split into three
sequential steps because it spans the application engine, the API
transport, and the Desktop frontend, and no single pull request can
safely cover all three.

The Studio module and the multi-user/per-user authorization revisit
are explicitly deferred and not part of this workstream --- see the
Cross-Cutting Rules below for the latter's prerequisite.

1. `feat(execution): stream execute_stream() through ExecutionEngine into one atomic terminal result`

   Objective: give `ExecutionEngine` a streaming execution path without
   weakening the rule that an `Execution` always records exactly one
   atomic terminal result, streamed or not.

   Main scope: add a streaming counterpart to
   `ExecutionEngine.run()` (e.g. `run_stream()`) that calls
   `AIProviderPort.execute_stream()`, yields `AIProviderStreamChunk`s
   to its caller, and reassembles the accumulated deltas into the same
   `AIProviderExecutionResult` shape `run()` already produces, so the
   existing completion/event/audit recording path needs no branching
   by streamed-vs-not. Purely additive: `run()` and non-streaming
   callers are unaffected, and cost estimation stays `None` for
   streamed results per the already-documented tradeoff. No public
   API or CLI surface changes yet --- this step is internal to the
   application layer, exercised only by tests until step 2.

   Likely documents to update:
   `src/orchai/application/executions/engine.py`,
   `docs/context/execution-engine.md` (remove the "not wired yet"
   caveat once this step lands; requires the requesting user's
   explicit authorization to touch this file per `AGENTS.md`'s
   `docs/context/` gate).

   Expected validation: unit tests with a fake streaming provider
   covering partial-chunk accumulation, a failure mid-stream, and
   confirmation that exactly one terminal `Execution` state is
   recorded; existing non-streaming tests remain green.

   Planned semantic decision: patch bump from `0.2.9` to `0.2.10`, a
   narrow, non-public-facing engine capability addition.

2. `feat(api): expose Task-bounded execution streaming via SSE`

   Objective: let an external client receive incremental output for a
   real, authorized Task execution, mirroring the conversation
   streaming transport already in place.

   Main scope: add a streaming variant of the execution-run step
   reachable from `/requests`'s advance flow (or a dedicated
   `executions` endpoint, decided during implementation against
   `docs/context/chat-first-and-interfaces.md`'s Request Lifecycle),
   returning `StreamingResponse(..., media_type="text/event-stream")`
   the same way `POST /conversations/{id}/messages` already does; add
   the matching CLI behavior or an explicit, documented decision to
   leave the CLI on the non-streaming path (the CLI's one-shot process
   model already forces a synchronous fallback for async execution
   dispatch, per `docs/OPERATIONS-REFERENCE.md`).

   Likely documents to update: `src/orchai/interfaces/api/main.py`,
   `src/orchai/interfaces/cli/main.py` (or an explicit note that it is
   intentionally unchanged), `docs/context/chat-first-and-interfaces.md`
   and `docs/context/execution-engine.md` (both require explicit
   per-file authorization), `docs/API-ENDPOINTS-REPORT.md`,
   `docs/OPERATIONS-REFERENCE.md`'s API Reference section.

   Expected validation: an integration test driving a full
   `/requests` → advance → stream flow with a fake streaming provider,
   confirming the SSE event shape matches the conversation-streaming
   precedent and that the recorded `Execution`/audit/event trail is
   identical to the non-streaming path.

   Planned semantic decision: minor bump from `0.2.10` to `0.3.0` --- a
   new public streaming contract for the primary orchestration flow is
   a meaningful capability increase, not a narrow fix.

3. `feat(desktop): consume Task execution streaming in the Approval Card`

   Objective: make the now-public streaming contract visible where
   users actually experience Task execution --- the Desktop chat
   transcript and Approval Card.

   Main scope: extend `apps/desktop/frontend/src/hooks/useConversationChat.js`
   (or a sibling hook) and `apps/desktop/frontend/src/screens/ApprovalCard.jsx`
   to render an escalated message's Task execution incrementally,
   reusing the same streaming-placeholder-then-replace pattern already
   used for non-escalated conversation streaming, instead of waiting
   for the final result.

   Likely documents to update:
   `apps/desktop/frontend/src/hooks/useConversationChat.js`,
   `apps/desktop/frontend/src/screens/ApprovalCard.jsx`,
   `docs/context/deployment-and-desktop.md` (requires explicit
   per-file authorization).

   Expected validation: manual verification in the running Desktop
   shell (escalate a message, confirm incremental rendering through to
   the Approval Card's final state); existing conversation-streaming
   behavior unaffected.

   Planned semantic decision: patch bump from `0.3.0` to `0.3.1` --- UI
   consumption of an already-shipped public contract, not a new one.

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
  `docs/context/identity-and-access.md`'s Migration And Rollout section
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
