# ADR-010 --- Project Readiness and Security Gates

## Status

Accepted

## Context

OrchAI is intended to connect to a wide range of external projects,
including empty directories, low-maturity projects, and large legacy
projects with little or no Git history, documentation, tests, or
traceability.

Blocking connection until a project reaches a predefined maturity level
would make OrchAI less useful for early-stage or recovery work.

However, allowing all project operations immediately after connection
would create major risks:

- unsafe code modification without reversibility;
- weakly grounded testing and validation;
- CI/CD automation based on missing project rules;
- excessive persistence of project knowledge;
- cloud-provider exposure of sensitive or proprietary information.

## Decision

OrchAI will distinguish project connectivity from project operational
readiness.

The project security and readiness layer will define:

- what a connected project allows OrchAI to access;
- what information may be persisted;
- what information may cross provider boundaries;
- which operations require minimum readiness levels.

The readiness model is:

- `LEVEL_0` --- connectable;
- `LEVEL_1` --- changeable;
- `LEVEL_2` --- validatable;
- `LEVEL_3` --- automatable.

Baseline gates:

- code change requires at least `LEVEL_1`;
- test and validation flow requires at least `LEVEL_2`;
- CI/CD flow requires at least `LEVEL_3`.

Baseline prerequisites:

- `LEVEL_1` requires Git initialized and operational;
- `LEVEL_2` requires Git plus minimum documentation sufficient to define
  project objective, scope, and relevant rules or constraints;
- `LEVEL_3` requires Git, documentation, and tests or documented test
  strategy.

OrchAI may help a project reach a higher readiness level, but it may do
so only when explicitly requested and authorized.

## Rationale

This preserves OrchAI's usefulness for low-maturity projects while
preventing unsafe assumptions in more sensitive operations.

It also creates a cleaner trust model:

- broad connection;
- explicit access control;
- explicit persistence control;
- explicit provider-sharing control;
- explicit operational gating.

## Consequences

Positive:

- OrchAI can connect to almost any project shape;
- high-impact operations become safer and more auditable;
- Git becomes an explicit safety prerequisite for code change;
- testing and CI/CD gain documented minimum grounding requirements;
- data minimization and confidentiality become project-level concerns,
  not only task-level concerns.

Trade-offs:

- more policy and authorization concepts must be documented and
  eventually implemented;
- some operations will be blocked until the project reaches a higher
  readiness level;
- onboarding flows become more explicit and slightly more complex.

## Relationship to Existing Decisions

This ADR complements:

- `ADR-005-LOCAL-CLOUD-PROVIDER-BOUNDARY.md`
- `ADR-006-SUGGESTED-AS-DEFAULT-EXECUTION-MODE.md`
- `ADR-009-PROJECT-CONTENT-OWNERSHIP.md`

It does not replace external project ownership. It strengthens the
conditions under which OrchAI may act inside that boundary.

## Invariant

A connected project may be low-maturity, but OrchAI must not treat low
connectability as permission to perform high-impact operations without
explicit readiness and authorization requirements.
