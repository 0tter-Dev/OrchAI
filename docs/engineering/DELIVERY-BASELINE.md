# OrchAI Delivery Baseline

## Purpose

This document captures the current lightweight Git/GitHub/CI baseline
for OrchAI. It is intentionally incremental and does not yet define a
complete DevOps or DevSecOps program.

## Branch and versioning baseline

- Feature and automation work should use `codex/*` or another explicit
  topic branch.
- `main` remains the protected integration branch.
- The repository version remains explicit in `pyproject.toml`.
- Lockfile consistency is part of CI validation.
- Dependency update automation is intentionally lightweight and handled
  through Dependabot for Python dependencies and GitHub Actions.

## Pull request baseline

Every PR should describe:

- the behavioral or architectural change;
- how it was validated;
- whether docs and boundary rules were affected.

The repository now includes a pull request template to keep that
baseline consistent.

Recommended required checks for PR merge are:

- CI
- review of documentation impact when contracts changed

## CI baseline

The initial GitHub Actions workflow validates:

- dependency sync with `uv`;
- lockfile consistency;
- incremental lint on the new HTTP interface surface with `ruff`;
- full test suite;
- a minimal CLI smoke check.
- automated dependency update proposals through Dependabot.

This is the current safety floor, not the final delivery pipeline.

## What is intentionally not implemented yet

The following remain deferred:

- release automation;
- package publishing;
- deployment workflows;
- environment promotion strategy;
- advanced secret scanning and dependency security gates;
- full DevSecOps controls and approvals.

These should be introduced after the API surface, onboarding guidance,
and public contracts stabilize further.
