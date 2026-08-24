# Contributing to OrchAI

## Purpose

This document defines the practical contribution baseline for OrchAI.

For architectural invariants, always read
[`AGENTS.md`](AGENTS.md) and the documents linked from
[`docs/INDEX.md`](docs/INDEX.md) first.

## Branch baseline

- Use an explicit topic branch such as `codex/<topic>` for feature,
  refactor, or automation work.
- Keep `main` as the integration branch.
- Do not mix unrelated architecture, product, and operational changes in
  one branch when they can be separated safely.

## Before changing code

1. Identify the affected domain or boundary.
2. Read the corresponding architectural or domain document.
3. Confirm whether the change affects CLI, API, persistence, provider,
   project-adapter, or policy contracts.
4. Update tests and docs when the behavior or contract changes.

## Local setup

```powershell
uv sync
```

## Recommended local validation

Run the standard validation flow before opening a PR:

```powershell
uv run ruff check
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
uv run pytest --basetemp ".pytest-tmp/run-$timestamp"
uv run orchai --help
```

If the workspace temp directory is blocked on Windows, use a writable
system temp path instead:

```powershell
$timestamp = Get-Date -Format "yyyyMMddHHmmss"
$base = Join-Path ([System.IO.Path]::GetTempPath()) "orchai-pytest-$timestamp"
.venv\Scripts\python.exe -m pytest --basetemp $base
```

Avoid reusing the same `--basetemp` directory across repeated Windows
runs because `pytest` may fail while recreating the directory.

## Pull request baseline

Every PR should make the following clear:

- what changed for users or contributors;
- how the change was validated;
- whether architectural boundaries, policies, readiness gates, or
  provider/project-adapter contracts were affected;
- whether docs were updated.

The repository PR template reflects this same baseline.

## CI baseline

GitHub Actions currently provides the lightweight delivery floor:

- dependency sync with `uv`;
- lockfile consistency check;
- lint validation with `ruff` (pinned `==0.15.11` in `pyproject.toml`, run via `uv run ruff check`, not `uv tool run`/`uvx`);
- full test suite with explicit `--basetemp`;
- CLI smoke check.

This is intentionally not yet a full deployment or DevSecOps pipeline.

## Dependency and security baseline

The current repository baseline includes:

- explicit dependency declarations in `pyproject.toml`;
- committed lockfile tracking via `uv.lock`;
- GitHub Actions validation for lock consistency;
- Dependabot updates for Python dependencies and GitHub Actions.

Heavier release automation, deployment workflows, and advanced
DevSecOps gates remain intentionally deferred until the public surface
and onboarding flow stabilize further.
