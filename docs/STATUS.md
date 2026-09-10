# OrchAI Project Status

## Purpose

This document tracks the current implementation state of major OrchAI
capabilities. It is a project-state snapshot, not a task backlog (see
[`TO-DO.md`](TO-DO.md)) and not a replacement for architectural
documentation (see [`ARCHITECTURAL-CONTRACT.md`](ARCHITECTURAL-CONTRACT.md)).
It does not narrate how the project got here — see
[`HISTORY.md`](HISTORY.md) for the frozen historical account, and future
release notes (generated from the Git log) for what changes going
forward.

## Legend

- `planned`: defined in documentation but not started
- `in_progress`: currently being implemented
- `implemented`: available in the product
- `review_needed`: present but requires design or behavior review

## Current Project Stage

OrchAI is currently in the `v0.2.10` implementation stage as of
`2026-09-09`.

## Feature Table

| Feature | Purpose | Status | Notes |
| --- | --- | --- | --- |
| Architectural Contract | Define the system's non-negotiable invariants and non-goals | implemented | Documentation only; 23 numbered principles in `ARCHITECTURAL-CONTRACT.md` |
| High-Level Architecture | Describe the system's layers, core concepts, and execution modes | implemented | Documentation only, `ARCHITECTURE.md` |
| Component Boundaries | Define each logical component's responsibilities | implemented | Documentation only, distributed across `docs/context/*.md` |
| Development Guide | Day-to-day engineering discipline: architectural rules, code quality, scope control, testing/CI direction | implemented | Documentation only, `DEVELOPMENT-GUIDE.md` |
| Implementation Map | Map architecture to concrete code modules and ordering | implemented | Documentation only, `IMPLEMENTATION-MAP.md` |
| Core Domain Model | Task/Role/Action/Model/Context/Execution/Event/Authorization entities | implemented | — |
| Authorization | MANUAL/SUGGESTED/AUTOMATIC authorization workflow | implemented | — |
| Task Lifecycle | Task state machine and stage transitions | implemented | — |
| Execution Model | Authorized execution construction and lifecycle | implemented | — |
| Event Model | Domain event publishing and history | implemented | — |
| Roles and Actions | Role/Action vocabulary independent of provider or model | implemented | — |
| Models and Providers | Model/provider selection independent of adapter implementation | implemented | — |
| Context Management | Context minimization, resolution, and authorization | implemented | — |
| Project Integration | Project Adapter boundary for external project access | implemented | Filesystem and media-workspace adapters |
| Capabilities | Declared per-adapter operation capabilities | implemented | — |
| Audit and Metrics | Automatic audit trail plus metrics recording and aggregation | implemented | `GET /metrics/summary` added in Phase 7.3 |
| Suggestions | State-aware next-step suggestion engine | implemented | — |
| Configuration | Environment-based configuration contract | implemented | — |
| Modular Monolith Structure | Domain/application/infrastructure/interfaces layering rule | implemented | Documentation plus enforced by `test_dependency_boundaries.py` |
| Physical Repository Structure | Source-tree organization | implemented | — |
| Technology Stack | Accepted language/framework/library baseline | implemented | — |
| Persistence Strategy | Repository boundaries and relational model | implemented | — |
| Event Dispatch Strategy | In-process event dispatch design | implemented | — |
| Async Execution Baseline | asyncio-based execution runtime | implemented | — |
| AI Provider Boundary | Local/cloud AI provider adapter boundary | implemented | — |
| Project Content Ownership Boundary | Connected-project content stays project-owned | implemented | — |
| Project Security / Readiness Gates | LEVEL_0-3 readiness and security profile | implemented | — |
| API/UI Boundary | CLI/API/future-UI boundary rules | implemented | — |
| Chat-First Request Interface | `/requests` as the primary external entry point | implemented | — |
| Identity and Access Management | Users, JWT auth, RBAC permissions | implemented | Enforcement is opt-in via `ORCHAI_AUTH_ENFORCED` (default `false`) |
| Execution Mode Baseline | MANUAL/SUGGESTED/AUTOMATIC execution mode enforcement | implemented | — |
| AI Provider Adapter (LiteLLM) | Single adapter covering OpenAI/Anthropic/Gemini/Ollama and other OpenAI-API-compatible runtimes | implemented | Replaced the separate Ollama/OpenAI-Codex adapters |
| AI Provider Streaming (execute_stream) | Task-bounded streaming execution | in_progress | `ExecutionEngine.run_stream()` reassembles chunks into one atomic terminal result (unit-tested); no API/CLI/Desktop caller wired yet |
| Conversation Domain Model | Persistent conversation/message history | implemented | Streaming supported |
| Module Concept (Forge, Studio) | Pluggable module registry | in_progress | Forge fully wired; Studio is a discovery-plus-chat skeleton |
| Desktop Single-User Identity | Single local user for the desktop shell | implemented | — |
| Desktop Application Shell | `pywebview`-based Windows desktop app | implemented | All 7 phases complete, including PyInstaller packaging |
| Forge Task Escalation (Approval Card) | Escalate a chat message into a real Task | implemented | — |
| Application Implementation | Application-layer services and orchestration | in_progress | — |
| Domain Implementation | Domain-layer entities and rules | implemented | — |
| Infrastructure Implementation | Persistence, provider, and adapter implementations | in_progress | — |
| API Implementation (operational) | Fine-grained `/tasks`, `/authorizations`, `/executions`, etc. | implemented | — |
| API Implementation (chat-first) | `/requests` surface | implemented | — |
| CLI Implementation | `orchai` command surface | implemented | — |
| Automated Test Suite | Unit and integration coverage | implemented | 296 tests passing |
| Deployment Implementation | Container/deployment automation | in_progress | Root `Dockerfile` exists and was validated manually; no CI build step, compose file, or deployment automation yet |

## Implementation Notes

- OrchAI is currently a Windows desktop chat application (Forge and Studio modules) built on top of an existing headless CLI/API orchestration core; both deployment shapes are documented in `docs/context/deployment-and-desktop.md`.
- `ORCHAI_AUTH_ENFORCED` remains `false` by default; identity/access enforcement is fully implemented but not yet turned on.
- The broader per-user action/role/model authorization revisit (multi-user Project Adapter binding) is deliberately not started; it requires the user's explicit authorization first, per `docs/TO-DO.md`'s Cross-Cutting Rules.
- `AutomaticExecutionPolicy`'s allowed-operations list remains hardcoded; no CLI/API surface configures it yet.
- The full test suite is 296 tests, `uv run ruff check` clean, `uv lock --check` consistent.
- For the detailed history of how the project reached this state, see `docs/HISTORY.md`, frozen as of this redesign (`2026-09-07`). Going forward this document is a snapshot, not a changelog; release notes generated from the Git log cover what changed release-over-release.
