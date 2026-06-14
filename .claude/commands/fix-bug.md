# Fix Bug (TDD)

Fix the bug described below using TDD — write a failing test that reproduces the bug first.

**Input:** $ARGUMENTS

## Process

1. **Reproduce** — Understand the bug. Read relevant code and identify the root cause.

2. **RED** — Write a test that fails because of the bug.
   - The test should pass once the bug is fixed
   - Run `pytest <test_file> -v -x` and confirm it FAILS with the expected error
   - Do NOT fix the bug yet

3. **GREEN** — Fix the bug with minimal change.
   - Change only what's necessary to make the test pass
   - Run `pytest <test_file> -v -x` and confirm it PASSES
   - Run `pytest -v` to confirm no regressions

4. **Verify** — Run full check suite.
   - Run `ruff check . && mypy promptune/ && pytest --cov=promptune --cov-report=term-missing -v`

## Rules
- Fix the root cause, not the symptom
- Don't refactor unrelated code in the same change
- The failing test is proof the bug existed
