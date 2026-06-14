# Promptune

An intelligent AI prompt enhancer. Write a rough prompt, let Promptune analyze and improve it using rule-based, local, or cloud AI — then review the result in a rich TUI before using it.

## Features

- **Zero-config first run**: works instantly — no setup needed for Tier 0 rule-based enhancement
- **3-tier enhancement**: deterministic rules (free, instant) → local LLM → cloud API
- **Quality scoring**: 7-dimension prompt analysis with before/after comparison
- **Context-aware**: auto-detects git branch, tech stack, shell history, and environment
- **Provider-flexible**: Claude, OpenAI, OpenRouter, or any OpenAI-compatible local LLM
- **Rich TUI**: side-by-side diff with Accept/Edit/Reject workflow
- **System-wide daemon**: background hotkey daemon (Ctrl+Shift+E) — enhances selected text in any macOS or Linux app
- **Shell integration**: Ctrl+E widget for Zsh, Bash, and Fish — enhances prompts inline
- **Provider-specific formatting**: auto-selects XML, Markdown, or Plain based on target model
- **Interactive setup wizard**: guided config init with provider selection, masked API key input
- **Semantic deduplication**: auto-detects near-duplicate prompts and returns cached results instantly
- **Preference learning**: learns from accept/reject/edit decisions to skip disliked rules automatically
- **Team templates**: `.prompts/` directory with intent/domain matching and variable injection
- **Enhancement history**: SQLite-backed history with statistics and acceptance tracking
- **MCP server**: `promptune mcp` exposes enhance and score tools to any MCP-compatible AI tool (Claude Code, Cursor, Codex)
- **Auto-enhance**: hooks into AI coding tools to silently intercept low-quality prompts, enhance them, and copy the result to clipboard
- **Score command**: `promptune score` rates any prompt across 7 quality dimensions with actionable suggestions
- **System health check**: `promptune doctor` verifies config, tiers, shell compatibility, and auto-enhance hook status
- Configurable enhancement styles: minimal, balanced, detailed
- TOML-based configuration

## Installation

### Quick Install (macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/kayumuzzaman/promptune/main/install.sh | bash
```

Or safer (inspect before running):

```bash
curl -fsSL https://raw.githubusercontent.com/kayumuzzaman/promptune/main/install.sh -o install.sh
bash install.sh
```

### Using pipx (recommended)

```bash
pipx install git+https://github.com/kayumuzzaman/promptune.git
```

### Using pip

```bash
pip install git+https://github.com/kayumuzzaman/promptune.git
```

### For development

```bash
git clone https://github.com/kayumuzzaman/promptune.git
cd promptune
pip install -e ".[dev]"
```

## Quick Start

```bash
# 1. Interactive setup wizard (provider, API key, options)
promptune config init

# 2. Enhance a prompt
promptune enhance "make a todo app"

# 3. Set up the shell widget (Zsh/Bash/Fish)
echo 'eval "$(promptune shell-init)"' >> ~/.zshrc
source ~/.zshrc
```

Now press **Ctrl+E** in your terminal to enhance the current line.

## CLI Commands

### `promptune enhance`

Enhance a prompt using AI. Opens a TUI with Accept/Edit/Reject workflow by default.

```bash
# Basic — opens TUI with before/after comparison
promptune enhance "make a todo app"

# Override provider for this command
promptune enhance -p openai "optimize this SQL query"

# Override enhancement style
promptune enhance -s detailed "build a payment system"

# Force a specific tier (0=rules only, 1=local LLM, 2=cloud API)
promptune enhance --tier 0 "fix the login bug"

# Force output format
promptune enhance --format markdown "explain kubernetes networking"

# Skip TUI, print enhanced prompt directly to stdout
promptune enhance --no-tui "add dark mode to my react app"

# Get structured JSON output
promptune enhance --json "write unit tests for the auth module"

# Pipe input
echo "build a REST API" | promptune enhance --no-tui

# Enhance and copy to clipboard (macOS)
promptune enhance --no-tui "refactor the user service" | pbcopy

# Combine flags
promptune enhance -p openrouter -s detailed --format xml --no-tui "design a caching layer"
```

**All flags:**

| Flag | Short | Description |
|------|-------|-------------|
| `--provider` | `-p` | Override default provider (claude, openai, openrouter) |
| `--style` | `-s` | Override enhancement style (minimal, balanced, detailed) |
| `--tier` | | Force specific tier: 0 (rules only), 1 (local LLM), 2 (cloud API) |
| `--format` | | Force output format: xml, markdown, plain |
| `--no-tui` | | Print result directly to stdout, skip interactive TUI |
| `--json` | | Output structured JSON with scores, tier, latency |

### `promptune score`

Score a prompt across 7 quality dimensions (0-100 PQS) without enhancing it — shows a per-dimension breakdown and actionable suggestions.

```bash
# Score a prompt
promptune score "make a todo app"

# Structured JSON output
promptune score --json "build a REST API with JWT auth"

# Pipe input
echo "add dark mode" | promptune score
```

### `promptune config`

Manage configuration.

```bash
# Interactive setup wizard
promptune config init

# Set API key for a provider
promptune config --set-key claude sk-ant-your-key-here

# Set max enhancement tier
promptune config --set-tier 2

# Reset config to defaults
promptune config --reset

# Show current configuration
promptune config show

# Print config file path
promptune config path
```

### `promptune shell-init`

Output shell widget script. Auto-detects shell, or specify one.

```bash
# Auto-detect shell
eval "$(promptune shell-init)"

# Force a specific shell
eval "$(promptune shell-init --shell bash)"

# Custom keybinding
eval "$(promptune shell-init --key 'alt+e')"
eval "$(promptune shell-init --key 'ctrl+x ctrl+e')"
```

### `promptune doctor`

Run system health check — verifies Python version, config, tier availability, and shell widget compatibility.

```bash
promptune doctor
```

### `promptune history`

View enhancement history stored in SQLite.

```bash
# Show recent entries
promptune history

# Show last 50 entries
promptune history --n 50

# Show statistics (acceptance rate, score improvements)
promptune history --stats

# Clear all history
promptune history --clear

# Show learned preferences
promptune history --preferences
```

### `promptune daemon`

Background daemon for system-wide prompt enhancement (macOS and Linux). Registers a global hotkey that works in any application.

```bash
# Start the daemon (foreground for debugging)
promptune daemon start --foreground

# Start as background process
promptune daemon start

# Check status
promptune daemon status

# Stop
promptune daemon stop

# Setup permissions (accessibility on macOS, dependencies on Linux)
promptune daemon setup

# Run diagnostics
promptune daemon diagnose

# Install as system service (systemd on Linux, LaunchAgent on macOS)
promptune daemon install
promptune daemon uninstall

# Remove all daemon files
promptune daemon purge

# Legacy macOS-only commands
promptune daemon install-login-item
promptune daemon uninstall-login-item
```

### `promptune local-llm-status`

Check local LLM (Ollama) connectivity.

```bash
promptune local-llm-status
```

### `promptune mcp`

Start an MCP server (stdio transport) that exposes `enhance` and `score` tools to any MCP-compatible AI tool (Claude Code, Cursor, Codex). Requires the `mcp` extra (`pip install promptune[mcp]`).

```bash
promptune mcp
```

### `promptune version`

```bash
promptune version
```

## Configuration

Config lives at `~/.config/promptune/config.toml`. See `config.example.toml` for all options.

**Config resolution order:** CLI flags > environment variables > config file > defaults

Environment variables: `PROMPTUNE_PROVIDER`, `PROMPTUNE_STYLE`

## Supported Providers

| Provider | SDK | Config Key |
|----------|-----|-----------|
| Claude | `anthropic` | `[api_keys] claude = "sk-ant-..."` |
| OpenAI | `openai` | `[api_keys] openai = "sk-..."` |
| OpenRouter | `httpx` | `[api_keys] openrouter = "sk-or-..."` |

## Roadmap

- [x] Phase 1: Core CLI, providers, TUI, shell integration (Zsh/Bash/Fish)
- [x] Phase 1.1: 3-tier enhancement, quality scoring, context fingerprinting, SQLite history
- [x] Phase 1.2: Interactive config setup wizard
- [x] Enhancement Phase: Preference learning, semantic deduplication, team templates, Ollama auto-check
- [x] Phase 2: OS-level hotkey daemon (macOS) — system-wide Ctrl+Shift+E
- [x] Phase 3: Linux hotkey daemon — X11 and Wayland support via platform abstraction

## License

MIT
