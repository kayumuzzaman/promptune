# Promptune Design Spec

**Date:** 2026-03-13
**Status:** Approved

## Summary

Promptune is a terminal prompt enhancer for macOS. The user types a rough prompt, presses Ctrl+E in their terminal, and promptune captures the input, sends it to an AI API, and returns an enhanced version. A Rich TUI shows original vs enhanced with Accept/Edit/Reject actions. The shell widget injects the accepted prompt back into the zsh readline buffer.

## Decisions

- **Shell target:** Zsh only (Phase 1)
- **Provider selection:** Config-based `default_provider` with `--provider` CLI override
- **Enhancement style:** User-configurable via `style` setting (`minimal`, `balanced`, `thorough`), default `balanced`
- **Architecture:** Layered monolith — single package with clear module boundaries

## Project Structure

```
promptune/
├── __init__.py          # version
├── __main__.py          # python -m promptune
├── cli.py               # Click commands
├── config.py            # TOML config loading/validation
├── engine.py            # Core enhancement orchestration
├── meta_prompt.py       # Prompt analysis & system prompt construction
├── providers/
│   ├── __init__.py      # Provider registry & base class
│   ├── anthropic.py     # Claude API
│   ├── openai.py        # OpenAI API
│   └── openrouter.py    # OpenRouter API (httpx)
├── tui.py               # Rich TUI: diff view, accept/edit/reject
└── shell.py             # Zsh widget installer & integration

tests/
├── conftest.py
├── test_cli.py
├── test_config.py
├── test_engine.py
├── test_meta_prompt.py
├── test_providers/
│   ├── test_anthropic.py
│   ├── test_openai.py
│   └── test_openrouter.py
├── test_tui.py
└── test_shell.py
```

## Data Flow

User input → `cli.py` → `engine.py` → `meta_prompt.py` (builds system prompt) → `providers/` (API call) → `tui.py` (display diff) → `shell.py` (inject into zle buffer)

All enhanced output goes to stdout only — never writes to files, never modifies history.

## Meta-Prompt Logic

1. Detect intent (coding, writing, research, creative)
2. Detect domain (web dev, data science, DevOps, general)
3. Detect stack (languages, frameworks, tools)
4. Build system prompt with detected context and style setting

### Enhancement Styles

| Style | Behavior |
|-------|----------|
| `minimal` | Fix grammar, clarify ambiguity, preserve scope exactly |
| `balanced` | Add structure, suggest constraints, remove ambiguity, stay lean |
| `thorough` | Full expansion — edge cases, acceptance criteria, tech suggestions |

## Config

Location: `~/.config/promptune/config.toml`

Resolution order: CLI flags → env vars → config file → defaults

Sections: `[general]`, `[providers.claude]`, `[providers.openai]`, `[providers.openrouter]`, `[tui]`

## CLI Commands

- `promptune enhance [PROMPT]` — main command (flags: `--provider`, `--style`, `--no-tui`)
- `promptune config init|show|path` — config management
- `promptune version` — print version
- `promptune shell-init` — output zsh widget script

## TUI Flow

1. Display original + enhanced prompts in Rich panels
2. Action bar: `[A]ccept  [E]dit  [R]eject`
3. Accept → stdout, exit 0. Edit → prompt_toolkit editor. Reject → exit 1.

## Shell Integration

- `eval "$(promptune shell-init)"` in `.zshrc`
- Ctrl+E captures `BUFFER`, pipes to `promptune enhance --no-tui`, replaces `BUFFER`

## Build Order

Steps 0–10 with coverage gates at Step 5 (80%) and Step 7 (85%). TDD is non-negotiable: RED → GREEN → REFACTOR for every step.

## Tech Stack

Python 3.9+, Click, Rich, prompt_toolkit, anthropic SDK, openai SDK, httpx, pytest, ruff, mypy
