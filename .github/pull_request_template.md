## Summary

Describe the change and the problem it solves.

## Why

Explain why this change is necessary now.

## Scope

- Type:
- Area:
- Related issue or roadmap item:

## Main Changes

- 

## Architecture And Behavior Notes

Describe any important architectural, workflow, or behavior decisions.

## Version Decision

- Version bump:
- Reason:
- Version-bearing files updated:

## Commit Convention

- Conventional Commit type/scope:
- Commit message matches the change:
- Breaking change marker used only if intentional:

## Validation

List the checks you ran locally.

- [ ] `uv sync --dev`
- [ ] `uv lock --check`
- [ ] `uv run ruff check`
- [ ] `uv run pytest --basetemp ".pytest-tmp/run-<timestamp>"`
- [ ] `uv run orchai --help`
- [ ] Not applicable for this pull request

## Documentation Checklist

- [ ] Version decision documented above
- [ ] Version-bearing files updated, or no version bump required
- [ ] `docs/STATUS.md` reviewed
- [ ] `docs/INDEX.md` reviewed
- [ ] `docs/TO-DO.md` updated
- [ ] Relevant architecture/domain document reviewed
- [ ] `docs/GIT-GITHUB-FLOW.md` reviewed when workflow or delivery rules changed
- [ ] User-facing docs reviewed when user-facing behavior changed
- [ ] No documentation update was required

## Review Notes

Highlight anything that deserves extra attention during review.

## Follow-Up

List any intentional follow-up work that is out of scope for this pull request.
