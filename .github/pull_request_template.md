## Summary

- describe the user-facing or architectural change

## Validation

- [ ] `uv run pytest --basetemp ".pytest-tmp/run-<timestamp>"`
- [ ] CLI/API behavior checked when relevant
- [ ] docs updated when behavior/contracts changed

## Risk Review

- [ ] domain/application/infrastructure boundaries preserved
- [ ] authorization/policy behavior reviewed
- [ ] readiness/security impact reviewed
