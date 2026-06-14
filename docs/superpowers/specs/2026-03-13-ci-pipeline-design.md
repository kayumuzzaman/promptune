# CI Pipeline Design — Promptune

## Summary

Add a GitHub Actions CI pipeline that validates code quality on every pull request and push to `main`. Single workflow, one job per Python version (matrix), sequential steps within each job. Hard quality gates block merge on failure.

## Trigger Events

- **Pull requests** targeting `main`
- **Pushes** to `main`

### Concurrency

Cancel redundant runs on the same branch:

```yaml
concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

### Permissions

Restrict to read-only (CI validation only):

```yaml
permissions:
  contents: read
```

## Runner & Matrix

- **Runner:** `ubuntu-latest`
- **Python versions:** 3.12, 3.13

## Workflow File

`.github/workflows/ci.yml`

### Job: `validate`

The matrix produces one job instance per Python version (2 total, running in parallel). Steps run sequentially within each job:

| Step | Command | Gate |
|------|---------|------|
| Checkout | `actions/checkout@v4` | — |
| Setup Python | `actions/setup-python@v5` (matrix) | — |
| Install deps | `pip install -e ".[dev]"` | — |
| Lint | `ruff check .` | Hard fail |
| Type check | `mypy promptune/` | Hard fail |
| Tests + coverage | `pytest --cov=promptune --cov-report=term-missing --cov-fail-under=80` | Hard fail |

### Quality Gates

All gates are hard failures — the build fails and merge is blocked if any gate fails:

- **ruff** must exit 0 (no lint errors)
- **mypy** must exit 0 (no type errors)
- **All tests** must pass
- **Coverage** must be >= 80%

## Excluded by Design

- No dependency caching (install is fast, caching adds complexity)
- No publishing or deployment steps
- No external coverage reporting (Codecov, etc.)
- No separate workflow files per check
- No `ruff format` check (not currently used in the project)

## Rationale

- **Single job:** 81 tests run in ~1s. Overhead of parallel jobs is not justified at this scale.
- **Python 3.12+:** User chose modern-only matrix to keep CI fast.
- **80% coverage gate:** Practical threshold that catches regressions without being overly strict. Current coverage is 90%.
- **Sequential steps:** Lint fails fast before slower test execution. Simple to debug.
- **Python 3.12+ CI vs `requires-python >= 3.9`:** The project allows installation on Python 3.9+, but CI only validates 3.12+. This is a deliberate trade-off for CI speed. Older versions are untested in CI.

## Follow-up

- Configure GitHub branch protection rules to require the `validate` status check before merging to `main`.
