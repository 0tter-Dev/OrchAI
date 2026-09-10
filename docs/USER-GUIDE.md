# OrchAI User Guide

## Purpose

This guide shows the intended OrchAI usage flow from a user
perspective, end to end: install, configure, connect a project, and
run an orchestrated task through explicit authorization to a
completed, audited execution. For the configuration reference,
policy/readiness concepts, full API/CLI surface, and troubleshooting,
see [`OPERATIONS-REFERENCE.md`](OPERATIONS-REFERENCE.md) — this guide
does not repeat that material, only what is needed to follow the flow.

## Example Scenario

A user wants to connect a local project to OrchAI and run its first
AI-assisted task, with an explicit human approval step before anything
executes against the project.

## End-To-End Flow

### 0. Prerequisites And Installation

- Python `3.14`
- `uv`

```powershell
uv sync
```

On Windows, `tools\windows\orchai-setup.bat` runs this same step (plus
`.env` preparation, `db sync`, and a CLI check) as one guided,
first-run-friendly launcher — see
[`OPERATIONS-REFERENCE.md`](OPERATIONS-REFERENCE.md)'s Windows Local
Setup section.

### 1. Configure The Database

OrchAI is PostgreSQL-first for shared or team operation; SQLite
remains available for local setup, smoke flows, and tests.

```powershell
$env:ORCHAI_DATABASE_URL = "postgresql://orchai:password@localhost:5432/orchai"
uv run orchai db sync
```

For a local-only run, use SQLite instead:

```powershell
$env:ORCHAI_DATABASE_URL = "sqlite:///.orchai/orchai.db"
uv run orchai db sync
```

### 2. Configure An AI Provider

Since the LiteLLM provider migration, one adapter covers every real
backend — which one runs is selected by `ORCHAI_AI_MODEL`'s
`"<provider>/<model>"` prefix, not by `ORCHAI_AI_PROVIDER` itself:

```powershell
$env:ORCHAI_AI_PROVIDER = "litellm"
$env:ORCHAI_AI_BASE_URL = "http://localhost:11434"
$env:ORCHAI_AI_MODEL = "ollama/qwen2.5-coder:latest"
```

The deterministic `stub` provider (`$env:ORCHAI_AI_PROVIDER = "stub"`)
needs no network and is useful for a first dry run. See
[`OPERATIONS-REFERENCE.md`](OPERATIONS-REFERENCE.md) for the full
configuration reference, including cloud providers and authentication.

### 3. Start The API

The HTTP API is the main integration boundary — CLI, future clients,
and the OrchAI Desktop application all reach the same orchestration
core through it.

```powershell
uv run orchai api serve
```

Confirm the runtime is healthy before continuing:

```powershell
uv run orchai runtime check
```

### 4. Connect A Project

Register the project so it exists explicitly in OrchAI's persisted
state, then inspect what OrchAI actually observed about it:

```powershell
uv run orchai projects register .
uv run orchai projects readiness .
uv run orchai projects security .
```

Readiness determines which operations are allowed — connecting a
project does not by itself authorize writing code, running tests, or
touching CI/CD. See
[`OPERATIONS-REFERENCE.md`](OPERATIONS-REFERENCE.md#project-readiness-and-security)
for the full `LEVEL_0`–`LEVEL_3` reference.

### 5. Run The First Orchestration Flow

`local-flow` exercises project registration, task creation, suggestion
generation, explicit authorization, execution, and context resolution
in one call:

```powershell
uv run orchai local-flow . docs/INDEX.md --title "Local flow" --approve-suggestion
```

Without `--approve-suggestion`, the default `SUGGESTED` mode presents
the generated suggestion and stops — nothing executes until it is
explicitly approved. This is the same Human Authority /
Suggested-by-Default principle the whole system is built around (see
`docs/ARCHITECTURAL-CONTRACT.md` §2.1–2.2): a suggestion is never an
implicit authorization.

The response's `task_id`, `authorization_id`, and `execution_id` let
you inspect exactly what OrchAI did and why:

```powershell
uv run orchai tasks snapshot <task-id> --history-limit 50
```

### 6. Advance The Task Through Its Staged Workflow

For a more realistic task-centric flow, advance one persisted task
through its next recommended stage — OrchAI keeps authorization,
execution, events, audit, and task state in sync automatically:

```powershell
uv run orchai tasks advance <task-id> --context-path docs/INDEX.md --approve-stage
uv run orchai tasks advance <task-id> --stage TEST --approve-stage
uv run orchai tasks advance <task-id> --stage DOCUMENT --context-path docs/INDEX.md --documentation-path docs/RESULT.md --approve-stage
```

When no explicit `--stage` is given, OrchAI advances to the next
suggested stage for the task's current state. The `TEST` stage runs
through the Project Adapter and requires readiness compatible with
test execution; `DOCUMENT` writes the generated output to the given
path and completes the task on success.

### 7. Run A Protected Project Operation Directly

Outside the staged workflow, protected operations still go through
readiness, policy, authorization, and adapter capability checks —
never directly against the project:

```powershell
uv run orchai projects operate . WRITE_SOURCE --resource src/app.py --content "print('hello')" --approve-operation
uv run orchai projects operate . RUN_TESTS --test-args "-q" --approve-operation
```

### 8. Review What Happened

Every task, authorization, and execution is independently inspectable
after the fact:

```powershell
uv run orchai tasks list
uv run orchai authorizations list --task-id <task-id>
uv run orchai executions list --task-id <task-id>
uv run orchai events list --limit 20
uv run orchai audit list --limit 20
uv run orchai metrics list --limit 20
```

`orchai tasks snapshot <task-id>` (or `GET /tasks/{task_id}/snapshot`)
is the fastest single consolidated read for one task, including its
`available_transitions`.

## Operating Expectations

- `MANUAL` executes only the explicit operation, with no proactive
  suggestion
- `SUGGESTED` is the default: OrchAI may propose a next step, but a
  suggestion is never authorization
- `AUTOMATIC` proceeds only inside explicitly configured policy
  boundaries — never unrestricted autonomy
- a project connection is not itself an authorization to write, test,
  or automate against it — readiness and security gates apply
  independently
- `suggested ≠ authorized ≠ ready ≠ executed` — see
  [`OPERATIONS-REFERENCE.md`](OPERATIONS-REFERENCE.md#policy-authorization-suggestion-execution)
  for the full mental model

## When OrchAI Is A Good Fit Today

Use it now when you want explicit orchestration history, readiness-
gated project operations, controlled local project automation, and a
foundation for API/UI growth. Wait before relying on it as a full
platform when you need mature multi-user workflows, production-ready
deployment automation, or a complete DevSecOps automation surface —
see `docs/STATUS.md` for exactly what is implemented today.
