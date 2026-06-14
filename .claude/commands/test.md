# Run Tests

Run tests with optional scope.

**Input:** $ARGUMENTS

If arguments provided, run: `pytest $ARGUMENTS -v`
If no arguments, run: `pytest --cov=promptune --cov-report=term-missing -v`

Report:
- Pass/fail count
- Coverage percentage (if full suite)
- First failure details (if any)
