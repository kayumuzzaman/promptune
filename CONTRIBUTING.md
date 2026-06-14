# Contributing to Promptune

## Development Setup

```bash
git clone https://github.com/kayumuzzaman/promptune.git
cd promptune
pip install -e ".[dev]"
```

## TDD Rules (Non-Negotiable)

Every change follows **RED → GREEN → REFACTOR**:

1. **RED**: Write failing tests first. Run them. Confirm they fail.
2. **GREEN**: Write the minimum code to make tests pass.
3. **REFACTOR**: Clean up while keeping tests green.

Never submit a PR without tests. Never write implementation before tests.

## Code Standards

- **Linting**: `ruff check .` must pass
- **Type checking**: `mypy promptune/` must pass
- **Tests**: `pytest --cov=promptune --cov-report=term-missing`
- **Coverage**: Must not decrease from current level
- **Python**: 3.9+ compatible, no f-string walrus operators or 3.10+ features

## Running Tests

```bash
# Full test suite with coverage
pytest --cov=promptune --cov-report=term-missing

# Specific test file
pytest tests/test_config.py

# Specific test
pytest tests/test_config.py::test_load_valid_config -v
```

## PR Process

1. Create a feature branch from `main`
2. Write tests first (RED)
3. Implement until tests pass (GREEN)
4. Refactor if needed (REFACTOR)
5. Ensure `ruff check`, `mypy`, and `pytest` all pass
6. Submit PR using the PR template
7. Address review feedback

## Commit Messages

Use conventional format:
- `feat: add OpenAI provider`
- `fix: handle empty API response`
- `test: add config validation tests`
- `docs: update README with shell-init instructions`
- `refactor: extract provider registry`

## Project Architecture

See `docs/ARCHITECTURE.md` for data flow and layer responsibilities.
