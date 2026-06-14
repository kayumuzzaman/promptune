# Promptune — Claude Code Config

Read `AGENTS.md` in the project root for development principles (TDD, SOLID, code style, error handling). This file covers Claude Code-specific configuration only.

## Project Structure

```
promptune/
├── AGENTS.md                          # Cross-tool dev rules (TDD, SOLID, style)
├── .claude/
│   ├── CLAUDE.md                      # THIS FILE — Claude Code specific
│   └── commands/                      # Custom slash commands
├── promptune/
│   ├── __init__.py                    # __version__
│   ├── __main__.py                    # python -m promptune
│   ├── cli.py                         # Click commands (11 commands + daemon group)
│   ├── config.py                      # TOML config load/validate/defaults
│   ├── setup.py                       # Interactive config wizard
│   ├── engine.py                      # Tier-based router engine
│   ├── meta_prompt.py                 # Intent/domain/stack detection
│   ├── scorer.py                      # 7-dimension quality scoring
│   ├── tier0.py                       # 9-rule deterministic engine
│   ├── pqs.py                         # Prompt Quality Score display
│   ├── formatter.py                   # Provider-specific formatting (XML/MD/Plain)
│   ├── history.py                     # SQLite history store
│   ├── dedup.py                       # Semantic deduplication (TF cosine similarity)
│   ├── preferences.py                 # Preference learning from history
│   ├── templates.py                   # Team .prompts/ template matching
│   ├── providers/
│   │   ├── __init__.py                # BaseProvider ABC, registry
│   │   ├── anthropic.py               # Claude provider
│   │   ├── openai.py                  # OpenAI provider
│   │   ├── openrouter.py              # OpenRouter provider (httpx)
│   │   └── local.py                   # Local LLM provider (OpenAI-compatible)
│   ├── context/                       # Context fingerprinting
│   │   ├── __init__.py                # Parallel collection with timeout
│   │   ├── collectors.py              # Git, shell history, tech stack, env
│   │   ├── sanitizer.py               # Secret removal
│   │   └── ranker.py                  # Priority-based context ranking
│   ├── daemon/                        # OS-level hotkey daemon (macOS + Linux)
│   │   ├── __init__.py                # Package docstring
│   │   ├── hotkey.py                  # macOS CGEventTap hotkey registration
│   │   ├── clipboard.py              # macOS clipboard ops, Cmd+C/V, undo
│   │   ├── notify.py                  # macOS notifications via osascript
│   │   ├── ipc.py                     # Unix socket server for CWD tracking
│   │   ├── prewarm.py                 # Ollama model keep-alive timer
│   │   ├── launchagent.py             # macOS LaunchAgent plist management
│   │   ├── daemon.py                  # Lifecycle orchestration via platform factory
│   │   └── platform/                  # Platform abstraction layer
│   │       ├── __init__.py            # get_platform() factory, detection
│   │       ├── base.py                # 6 ABCs + dataclasses
│   │       ├── macos.py               # macOS adapter (wraps existing modules)
│   │       ├── linux_x11.py           # X11: XGrabKey, xclip, xdotool
│   │       ├── linux_wayland.py       # Wayland: portal/evdev, wl-clipboard
│   │       └── linux_service.py       # systemd service + dependency checker
│   ├── gate.py                        # Auto-enhance gate (score → enhance → clipboard)
│   ├── hooks/
│   │   ├── __init__.py                # HookInstaller protocol, get_installers(), detect_tools()
│   │   └── claude_code.py             # Claude Code hook installer (settings.json)
│   ├── mcp/
│   │   ├── __init__.py                # Package marker
│   │   └── server.py                  # FastMCP server (enhance + score tools, stdio)
│   ├── tui.py                         # Rich TUI with toggles
│   └── shell.py                       # Shell widget (Zsh/Bash/Fish) + IPC
├── tests/                             # Mirrors source structure
├── docs/
│   ├── ARCHITECTURE.md
│   ├── USER_GUIDE.md
│   └── superpowers/                   # Specs, plans, blueprints
└── pyproject.toml
```

## Quick Commands

```bash
# Full check (lint + types + tests)
ruff check . && mypy promptune/ && pytest --cov=promptune --cov-report=term-missing -v

# Tests only
pytest -v

# Single test file
pytest tests/test_engine.py -v

# Coverage report
pytest --cov=promptune --cov-report=term-missing
```

## Implementation Plans

Completed plans:
- `docs/superpowers/plans/2026-03-15-phase1-next-iteration.md` — 3-tier engine, scoring, context, history
- `docs/superpowers/plans/2026-03-17-cross-terminal-shell-integration.md` — Zsh/Bash/Fish widgets
- `docs/superpowers/plans/2026-03-17-interactive-config-setup.md` — Config setup wizard
- `docs/superpowers/plans/2026-03-28-enhancement-phase.md` — Dedup, preferences, templates, Ollama auto-check
- `docs/superpowers/plans/2026-03-28-phase2-os-hotkey-daemon.md` — OS-level hotkey daemon (macOS)
- `docs/superpowers/plans/2026-03-29-phase3-linux-daemon.md` — Linux daemon (X11/Wayland platform abstraction)
- `docs/superpowers/plans/2026-04-05-mcp-server-and-auto-enhance.md` — MCP server, auto-enhance gate, hooks, score command

## Config Schema (Current)

```toml
[provider]
default = "claude"                        # claude | openai | openrouter
format_style = "auto"                     # auto | xml | markdown | plain
model_claude = "claude-haiku-4-5-20251001"
model_openai = "gpt-4o-mini"
model_openrouter = "anthropic/claude-haiku"

[api_keys]
claude = "sk-ant-..."
openai = "sk-..."
openrouter = "sk-or-..."

[enhancement]
max_tier = 2                              # 0=rules only, 1=+local, 2=+cloud
default_mode = "balanced"                 # minimal | balanced | detailed
max_tokens_output = 400
timeout_seconds = 10
dedup_enabled = true                      # semantic dedup on/off
dedup_threshold = 0.85                    # cosine similarity threshold
dedup_window = 50                         # recent history entries to check
preference_learning = true                # learn from accept/reject/edit
preference_min_samples = 5               # min samples before applying

[local_llm]
enabled = true
host = "http://localhost:11434"
model = "qwen2.5:3b"
api_key = ""

[context]
use_git = true
use_shell_history = true
use_stack_detection = true
max_context_tokens = 500
shell_history_lines = 20

[history]
enabled = true
max_entries = 10000
db_path = "~/.local/share/promptune/history.db"

[tui]
show_pqs_scores = true
show_tier_used = true
show_latency = true
theme = "dark"
show_diff = true

[daemon]
hotkey = "ctrl+shift+e"              # global hotkey combo
clipboard_settle_ms = 100            # ms to wait after Cmd+C
notify = true                        # macOS notifications
notify_sound = true                  # notification sound
ollama_prewarm = true                # keep Ollama model warm
ollama_keepalive_minutes = 30        # prewarm interval
log_level = "info"                   # daemon log level

[auto_enhance]
enabled = true                       # auto-enhance in AI tools
threshold = 40                       # PQS score below which to enhance
min_words = 5                        # skip prompts shorter than this
bypass_prefix = "!"                  # prefix to skip auto-enhance
```

## Coverage Target

≥ 90% — check with `pytest --cov=promptune`
