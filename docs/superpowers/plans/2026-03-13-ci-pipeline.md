# CI Pipeline Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a GitHub Actions CI workflow that validates lint, type checks, and tests with coverage on every PR and push to main.

**Architecture:** Single workflow file with one job (`validate`) using a Python version matrix (3.12, 3.13). Steps run sequentially: checkout → setup → install → lint → typecheck → test+coverage. All gates are hard failures.

**Tech Stack:** GitHub Actions, ruff, mypy, pytest, pytest-cov

---

## Chunk 1: CI Workflow

### Task 1: Create the GitHub Actions workflow file

**Files:**
- Create: `.github/workflows/ci.yml`

- [x]**Step 1: Create the workflow file**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  validate:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13"]

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint
        run: ruff check .

      - name: Type check
        run: mypy promptune/

      - name: Tests with coverage
        run: pytest --cov=promptune --cov-report=term-missing --cov-fail-under=80
```

- [x]**Step 2: Validate the workflow YAML locally**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"`

If `yaml` is not installed, validate with:
```bash
python -c "
import json, re
with open('.github/workflows/ci.yml') as f:
    content = f.read()
# Basic check: file is not empty and contains expected keys
assert 'name: CI' in content
assert 'push:' in content
assert 'pull_request:' in content
assert 'ruff check' in content
assert 'mypy promptune/' in content
assert 'cov-fail-under=80' in content
print('Workflow file looks valid')
"
```

Expected: `Workflow file looks valid`

- [x]**Step 3: Verify existing tests still pass**

Run: `source .venv/bin/activate && pytest --cov=promptune --cov-report=term-missing --cov-fail-under=80`

Expected: 81 passed, coverage >= 80%

- [x]**Step 4: Verify lint and type checks pass**

Run: `source .venv/bin/activate && ruff check . && mypy promptune/`

Expected: Both exit 0 with no errors

- [x]**Step 5: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "Add GitHub Actions CI pipeline with lint, typecheck, and test gates"
```

---

### Task 2: Commit the spec, plan, and user guide docs

**Files:**
- Existing: `docs/superpowers/specs/2026-03-13-ci-pipeline-design.md`
- Existing: `docs/superpowers/plans/2026-03-13-ci-pipeline.md`
- Existing: `docs/USER_GUIDE.md`

- [x]**Step 1: Commit all docs**

```bash
git add docs/
git commit -m "Add CI pipeline spec, plan, and user guide documentation"
```
