# Run All Checks

Run the full quality gate: lint, type check, and tests with coverage.

```bash
ruff check . && mypy promptune/ && pytest --cov=promptune --cov-report=term-missing -v
```

Report results concisely:
- If all pass: confirm pass with coverage percentage
- If any fail: show the first failure and stop
