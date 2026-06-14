# Implement Feature (TDD)

Implement the feature or change described below using strict TDD.

**Input:** $ARGUMENTS

## Process

1. **Understand** — Read relevant source files and tests to understand current state.

2. **RED** — Write failing tests first.
   - Create test functions that cover the expected behavior
   - Run `pytest <test_file> -v -x` and confirm they FAIL
   - Do NOT write any implementation yet

3. **GREEN** — Write minimum implementation to pass.
   - Write only enough code to make the failing tests pass
   - Run `pytest <test_file> -v -x` and confirm they PASS
   - Do NOT add anything beyond what the tests require

4. **REFACTOR** — Clean up while green.
   - Improve code quality without changing behavior
   - Run `pytest <test_file> -v -x` to confirm still green

5. **Verify** — Run full check suite.
   - Run `ruff check . && mypy promptune/ && pytest --cov=promptune --cov-report=term-missing -v`
   - Report coverage percentage

## Rules
- Follow SOLID principles (see AGENTS.md)
- Mock external APIs — never make real network calls in tests
- One logical change at a time
