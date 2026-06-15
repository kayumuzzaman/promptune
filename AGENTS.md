# Promptune — Agent Instructions

Universal development rules for any AI coding assistant working on this project.

## Project

Promptune is an intelligent AI prompt enhancer with 3-tier architecture (rules → local LLM → cloud API), quality scoring, context fingerprinting, and provider-specific formatting.

- **Language:** Python 3.9+
- **CLI:** Click | **TUI:** Rich | **Testing:** pytest
- **Linting:** ruff | **Types:** mypy (strict)

## Commands

```bash
# Install
pip install -e ".[dev]"

# Test
pytest --cov=promptune --cov-report=term-missing -v

# Lint + type check
ruff check .
mypy promptune/

# All checks (run before any commit)
ruff check . && mypy promptune/ && pytest --cov=promptune --cov-report=term-missing -v
```

## TDD — Non-Negotiable

Every change follows **RED → GREEN → REFACTOR**. No exceptions.

1. **RED:** Write a failing test first. Run it. Confirm it fails with the expected error.
2. **GREEN:** Write the minimum code to make the test pass. Nothing more.
3. **REFACTOR:** Clean up while keeping all tests green.

Rules:
- Never write implementation before its test exists and fails
- Never skip the RED phase — even for "obvious" code
- Every public function has at least one test
- Run `pytest` after every change to confirm state (red or green)
- Mock external APIs (anthropic, openai, httpx) — never make real API calls in tests
- Use `pytest-mock` for mocking, `pytest-cov` for coverage
- Coverage target: ≥ 85%

## SOLID Principles

Apply to every class, module, and function:

- **Single Responsibility:** Each module/class/function does one thing. If you need "and" to describe it, split it.
- **Open/Closed:** Extend behavior by adding new code (new provider, new rule, new collector), not modifying existing working code.
- **Liskov Substitution:** Any `BaseProvider` subclass must work anywhere `BaseProvider` is expected. No special-casing by type.
- **Interface Segregation:** Keep interfaces small and focused. A provider needs `enhance()`, not `enhance()` + `validate()` + `format()`.
- **Dependency Inversion:** Depend on abstractions (ABC, Protocol), not concrete implementations. The router depends on `BaseProvider`, not `ClaudeProvider`.

## Design Patterns

Use these when they fit — don't force them:

- **Strategy:** Provider selection, tier handlers, format styles
- **Registry:** Provider registry for name → class mapping
- **Factory:** Creating provider instances from config
- **Collector:** Context fingerprinting parallel data gathering
- **Dataclass:** All data containers — `EnhanceResult`, `ScoreResult`, `HistoryEntry`

## Code Style

- Type annotations on all function signatures
- `from __future__ import annotations` at top of every module
- Docstrings on public functions only — one line, what it does, not how
- No comments unless the logic is non-obvious. Code should be self-documenting.
- No unnecessary abstractions — three similar lines are better than a premature helper
- Max function length: aim for ≤ 20 lines. Split if longer.
- Max file length: aim for ≤ 300 lines. Split by responsibility if longer.

## Error Handling

- Custom exceptions: `ConfigError`, `ProviderError` — never raise bare `Exception`
- Catch specific exceptions, never bare `except:`
- Fail fast at system boundaries (config loading, API responses)
- Graceful degradation in tier routing — always fall back to tier below

## Git Conventions

- Commit messages: `feat:`, `fix:`, `refactor:`, `test:`, `docs:` prefixes
- One logical change per commit
- Never commit: secrets, .env files, build artifacts, .DS_Store, IDE configs

## What NOT To Do

- Don't add features beyond what was asked
- Don't refactor code you didn't change
- Don't add comments, docstrings, or type annotations to unchanged code
- Don't create helpers or abstractions for one-time operations
- Don't add error handling for scenarios that can't happen
- Don't use `# type: ignore` — fix the type issue instead
- Don't mock more than necessary — mock at the boundary, not internals
