# Promptune User Guide

## What is Promptune?

Promptune is a terminal prompt enhancer for macOS and Linux. It takes your rough, quick prompts and transforms them into clear, well-structured prompts using AI — right from your terminal.

**Example:**

```
Your input:    "make a todo app"
Enhanced:      "Build a full-stack todo application with the following requirements:
                - RESTful API backend with CRUD operations for tasks
                - Task properties: title, description, status (pending/done), due date
                - Persistent storage using SQLite
                - Simple frontend with add, edit, delete, and mark-complete functionality
                - Input validation and error handling"
```

## Installation

### Recommended — pipx (macOS + Linux)

```bash
pipx install promptune        # or: python3 -m pip install --user promptune
```

For optional extras (MCP server, Linux daemon) and the one-line installer, see the [README](../README.md#installation).

### Verify installation

```bash
promptune --version
# Output: promptune, version 0.1.0
```

## Getting Started

### Quick Start (zero config)

Promptune works immediately with no setup — Tier 0 deterministic rules run free and instant:

```bash
promptune enhance "make a todo app"
```

To unlock AI-powered enhancement (Tier 1 local LLM, Tier 2 cloud API), run the setup wizard.

### Step 1: Run the setup wizard

```bash
promptune config init
```

In an interactive terminal, the wizard first prints a tier overview so you know what costs money:

```
  Tier 0  Rule-based rewrite       FREE  · offline, no key
  Tier 1  Local LLM (Ollama, …)    FREE  · private, no key
  Tier 2  Cloud LLM (Claude/GPT)   PAID  · needs an API key
```

Then it walks you through configuration step by step:

1. **Provider** — choose your default provider (claude, openai, openrouter)
2. **API key** — optional. Enter a key to enable Tier 2 (cloud), or **leave it blank** to stay on the free tiers (rules + local LLM). Masked input, format validated.
3. **Model** — choose the model name for your provider (pre-filled with default)
4. **Advanced settings** (optional) — style, max tier, format
5. **Local LLM** (optional, shown when max tier >= 1) — enable/disable, host, model name
6. **Auto-enhance** (automatic) — detects installed AI tools (Claude Code, etc.) and offers to install a prompt-quality gate hook

Existing config values are pre-filled as defaults when re-running the wizard.

**Non-interactive environments** (pipes, CI): creates a default config file and prints instructions to stderr.

You can also set individual values directly:

```bash
# Set API key for a provider
promptune config --set-key claude sk-ant-your-key-here

# Set max tier
promptune config --set-tier 2
```

### Step 2: Enhance your first prompt

```bash
promptune enhance "make a todo app"
```

The TUI will display your original prompt and the enhanced version side by side. Choose:

- **[A]ccept** — use the enhanced prompt
- **[E]dit** — modify the enhanced prompt before accepting
- **[R]eject** — discard and exit

## CLI Commands

### `promptune enhance`

The main command. Enhances a prompt using your configured AI provider.

```bash
# Basic usage — opens TUI with before/after comparison
promptune enhance "your rough prompt here"

# Override the default provider
promptune enhance -p openai "optimize this SQL query"

# Override the enhancement style
promptune enhance -s detailed "build a payment system"

# Force a specific tier (0=rules only, 1=local LLM, 2=cloud API)
promptune enhance --tier 0 "fix the login bug"

# Skip the TUI, print directly to stdout
promptune enhance --no-tui "add dark mode to my react app"

# Structured JSON output (scores, tier, latency)
promptune enhance --json "write unit tests for the auth module"

# Pipe input from another command
echo "build a REST API" | promptune enhance --no-tui

# Enhance and copy to clipboard (macOS)
promptune enhance --no-tui "your prompt" | pbcopy

# Combine multiple flags
promptune enhance -p openrouter -s detailed --no-tui "design a caching layer"
```

**Flags:**

| Flag | Short | Description |
|------|-------|-------------|
| `--provider` | `-p` | Override default provider (claude, openai, openrouter) |
| `--style` | `-s` | Override default style (minimal, balanced, detailed) |
| `--tier` | | Force specific tier: 0 (rules only), 1 (local LLM), 2 (cloud API) |
| `--no-tui` | | Print result directly, skip interactive TUI |
| `--json` | | Output structured JSON with scores, tier, latency |

### `promptune score`

Score a prompt across 7 quality dimensions without enhancing it.

```bash
# Score a prompt (prints PQS total and per-dimension breakdown)
promptune score "make a todo app"

# JSON output (for scripting)
promptune score --json "build a REST API with authentication"

# Pipe input
echo "fix the bug" | promptune score
```

**Flags:**

| Flag | Description |
|------|-------------|
| `--json` | Output structured JSON with total, intent, and dimension scores |

### `promptune mcp`

Start the MCP server for use with AI coding tools (Claude Code, Cursor, Codex, etc.).

```bash
# Start MCP server on stdio transport
promptune mcp
```

Requires the optional MCP dependency: `pip install "promptune[mcp]"`

The MCP server exposes two tools:
- **`enhance_prompt`** — enhance a prompt using the 3-tier engine (accepts style, tier overrides)
- **`score_prompt_quality`** — score a prompt across 7 dimensions (returns total, intent, per-dimension detail)

To use with Claude Code, add to your MCP config:
```json
{
  "mcpServers": {
    "promptune": {
      "command": "promptune",
      "args": ["mcp"]
    }
  }
}
```

### Auto-Enhance (AI Tool Integration)

Promptune can automatically intercept low-quality prompts in AI coding tools before they're sent. When a prompt scores below the threshold (default: PQS < 40), promptune enhances it and silently injects the enhanced version into the conversation as context — no clipboard, no manual paste.

**Which tools auto-trigger?** A tool can only auto-trigger if it exposes a `UserPromptSubmit` hook *and* Promptune ships an installer for it. For everything else, use the MCP server (ask the tool to enhance) or run `promptune enhance` manually first.

| Tool | Auto-trigger on prompt submit? | How |
|------|-------------------------------|-----|
| **Claude Code** | ✅ Yes | `UserPromptSubmit` hook in `~/.claude/settings.json` |
| **Codex CLI** | ✅ Yes | `UserPromptSubmit` hook in `~/.codex/hooks.json` |
| **Cursor / other MCP clients** | ❌ No | Use the MCP server, or run `promptune enhance` manually and paste/pipe the result |

**Setup:** The `config init` wizard auto-detects installed AI tools (Claude Code, Codex CLI, …) and offers to install the hook. You can also check status with `promptune doctor`, which prints an Auto-enhance status line per detected tool.

**How it works:**
1. You type a prompt in Claude Code, Codex CLI, or another supported tool
2. Promptune scores the prompt against 7 quality dimensions
3. If the score is below threshold: the prompt is enhanced and the enhanced version is injected into the model's context via the hook's `additionalContext` output (exit 0, the prompt proceeds), so the model acts on the enhanced version automatically
4. No clipboard, no paste — it happens silently on submit

> **Note on injection vs. replacement:** the gate does **not** literally replace or overwrite the prompt text you typed — neither Claude Code nor Codex allows a hook to do that. It **injects the enhanced prompt as additional context alongside your original**, so the model receives both and acts on the enhanced version. The `!` bypass prefix still sends your prompt through raw, with no enhancement and no injection.

Both supported tools use the same hook shape — a `UserPromptSubmit` entry running `promptune gate` — written to `~/.claude/settings.json` (Claude Code) or `~/.codex/hooks.json` (Codex CLI).

**Configuration:**

```toml
[auto_enhance]
enabled = true       # Enable/disable auto-enhance
threshold = 40       # PQS score below which auto-enhance triggers (0-100)
min_words = 5        # Skip prompts shorter than this
bypass_prefix = "!"  # Prefix to skip auto-enhance (e.g. "! my prompt")
```

To bypass auto-enhance for a single prompt, prefix it with `!` (or your configured prefix):

```
! deploy the app to production
```

### `promptune config`

Manage your configuration.

```bash
# Interactive setup wizard (walks through provider, API key, options)
promptune config init

# Set API key directly
promptune config --set-key claude sk-ant-your-key

# Set max tier
promptune config --set-tier 1

# Reset to defaults
promptune config --reset

# Show current configuration
promptune config show

# Print config file path
promptune config path
```

### `promptune shell-init`

Output the shell widget script for shell integration. Auto-detects your shell from `$SHELL`, or specify one explicitly. Supports a custom keybinding via `--key`.

```bash
# Preview the script (auto-detects shell)
promptune shell-init

# Force a specific shell
promptune shell-init --shell bash
promptune shell-init --shell fish

# Use a custom keybinding
promptune shell-init --key "alt+e"
promptune shell-init --key "ctrl+x ctrl+e"

# Install permanently
# Zsh (~/.zshrc):
echo 'eval "$(promptune shell-init)"' >> ~/.zshrc
source ~/.zshrc

# Bash (~/.bashrc):
echo 'eval "$(promptune shell-init)"' >> ~/.bashrc
source ~/.bashrc

# Fish (~/.config/fish/config.fish):
echo 'promptune shell-init | source' >> ~/.config/fish/config.fish
```

### `promptune doctor`

Run a system health check. Verifies Python version, config file, tier availability (rules, local LLM, cloud API), and shell widget compatibility.

```bash
promptune doctor
#   Python         ✓  3.13.5 (>=3.9 required)
#   Config         ✓  ~/.config/promptune/config.toml
#   Tier 0         ✓  Rule engine ready
#   Tier 1         ✗  Not configured
#   Tier 2         ✓  API key set for claude
#   Shell Widget   ✓  Shell widget compatible
```

### `promptune history`

View and manage enhancement history (stored in SQLite).

```bash
# Show recent entries (default: last 20)
promptune history

# Show last 50 entries
promptune history --n 50

# Show statistics (acceptance rate, avg score improvement)
promptune history --stats

# Clear all history (requires confirmation)
promptune history --clear

# Show learned preferences (rule accept/reject patterns, edit patterns)
promptune history --preferences
```

### `promptune local-llm-status`

Check connectivity to local LLM (Ollama or any OpenAI-compatible server).

```bash
promptune local-llm-status
#   Local LLM  ✓  qwen2.5:3b responding at http://localhost:11434
```

### `promptune daemon`

Background daemon for system-wide prompt enhancement on macOS and Linux. Registers a global hotkey (default: Ctrl+Shift+E) that works in any application — select text, press the hotkey, and the selected text is enhanced and pasted back.

```bash
# Start the daemon in the foreground (useful for debugging)
promptune daemon start --foreground

# Start as a background process
promptune daemon start

# Check daemon status (PID, uptime, enhancement count)
promptune daemon status

# Stop the daemon
promptune daemon stop

# Restart the daemon
promptune daemon restart

# Platform-aware setup (accessibility on macOS, dependencies on Linux)
promptune daemon setup

# Run diagnostics
promptune daemon diagnose

# Install as system service (systemd on Linux, LaunchAgent on macOS)
promptune daemon install

# Uninstall system service
promptune daemon uninstall

# Remove all daemon files (service, socket, PID, logs)
promptune daemon purge

# Legacy macOS-only commands
promptune daemon install-login-item
promptune daemon uninstall-login-item
```

#### How the daemon works

1. The daemon detects your platform (macOS, Linux X11, or Linux Wayland) and loads the appropriate backend
2. When you press the hotkey with text selected in any app, the daemon:
   - Copies the selected text (simulates Ctrl+C / Cmd+C)
   - Reads the clipboard
   - Enhances the prompt through the existing engine (Tier 0 → Tier 1 → Tier 2)
   - Pastes the enhanced text back (simulates Ctrl+V / Cmd+V)
   - Shows a desktop notification with score improvement
3. If the app loses focus during enhancement, the result is placed on the clipboard instead of pasted
4. Press Ctrl+Z / Cmd+Z to undo (the daemon saves an undo buffer)

#### Platform support

**macOS:** Uses CGEventTap for hotkeys, pbcopy/pbpaste for clipboard, osascript for notifications. Requires Accessibility permissions (`promptune daemon setup`).

**Linux X11:** Uses python-xlib (XGrabKey) for hotkeys, xclip for clipboard, xdotool for key simulation. Install dependencies: `sudo apt install xclip xdotool` (or equivalent for your distro).

**Linux Wayland:** Uses XDG Desktop Portal GlobalShortcuts (dbus-next) for hotkeys with evdev fallback, wl-clipboard for clipboard, ydotool for key simulation. Install dependencies: `sudo apt install wl-clipboard ydotool` (or equivalent). Active window detection supports GNOME, KDE Plasma, and sway.

**WSL:** Not supported — detected and blocked with a clear error message.

#### Linux setup

```bash
# 1. Install system dependencies
promptune daemon setup   # checks tools, shows install command

# 2. Install Python extras
pip install "promptune[linux-daemon]"

# 3. Start the daemon
promptune daemon start --foreground

# 4. (Optional) Install as systemd service for auto-start
promptune daemon install
```

#### macOS accessibility permissions

The daemon requires macOS Accessibility permissions to register global hotkeys. Run `promptune daemon setup` for a guided walkthrough, or grant access manually:

**System Settings → Privacy & Security → Accessibility → Add your terminal app**

#### Daemon configuration

```toml
[daemon]
hotkey = "ctrl+shift+e"         # Global hotkey combo
clipboard_settle_ms = 100       # Wait after copy before reading clipboard
notify = true                   # Show desktop notifications
notify_sound = true             # Play sound with notifications
ollama_prewarm = true           # Keep Ollama model loaded in memory
ollama_keepalive_minutes = 30   # Prewarm interval
log_level = "info"              # debug | info | warning | error
```

### `promptune version`

Print the current version.

```bash
promptune version
# Output: 0.1.0
```

## Shell Integration

The killer feature: enhance prompts without leaving your terminal.

### Setup

**Zsh** — add to `~/.zshrc`:

```bash
eval "$(promptune shell-init)"
```

**Bash** — add to `~/.bashrc`:

```bash
eval "$(promptune shell-init)"
```

**Fish** — add to `~/.config/fish/config.fish`:

```fish
promptune shell-init | source
```

Then reload your shell (open a new tab or `source` the config file).

### Custom Keybinding

By default, the widget binds to **Ctrl+E**. To use a different key:

```bash
# Alt+E instead of Ctrl+E
eval "$(promptune shell-init --key 'alt+e')"

# Ctrl+X Ctrl+E (chord)
eval "$(promptune shell-init --key 'ctrl+x ctrl+e')"
```

### Usage

1. Type a rough prompt at your terminal
2. Press **Ctrl+E** (or your custom key)
3. Your prompt is replaced with the enhanced version

**How it works:** The shell widget captures your current command line, sends it to `promptune enhance --no-tui`, and replaces the line with the result. If enhancement fails, your original text is preserved.

## Enhancement Styles

Promptune supports three enhancement styles, configured in your config file or overridden per command with `-s`.

### `minimal`

Fixes grammar, improves clarity, and preserves your original scope exactly. No new requirements are added.

**Best for:** Quick cleanups, when you know what you want and just need it polished.

```bash
promptune enhance -s minimal "fix the login bug where users cant reset password"
```

### `balanced` (default)

Adds structure, suggests constraints, removes ambiguity, and stays lean. Preserves your core intent while making the prompt more actionable.

**Best for:** Most everyday use. Good balance of enhancement without over-engineering.

```bash
promptune enhance -s balanced "build a REST API for users"
```

### `detailed`

Expands the prompt with edge cases, acceptance criteria, and technical suggestions. Comprehensive but stays relevant.

**Best for:** Complex tasks where you want the AI to help think through details.

```bash
promptune enhance -s detailed "build a payment system"
```

## Configuration Reference

Config file location: `~/.config/promptune/config.toml`

Run `promptune config init` for the interactive setup wizard, or edit the file directly.

### Full config example

```toml
[provider]
default = "claude"                        # claude | openai | openrouter
model_claude = "claude-haiku-4-5-20251001"
model_openai = "gpt-4o-mini"
model_openrouter = "anthropic/claude-haiku-4.5"

[api_keys]
claude = "sk-ant-your-key-here"
openai = "sk-your-key-here"
openrouter = "sk-or-your-key-here"

[enhancement]
max_tier = 2                              # 0=rules only, 1=+local LLM, 2=+cloud API
default_mode = "balanced"                 # minimal | balanced | detailed
max_tokens_output = 400
timeout_seconds = 10
dedup_enabled = true                      # skip near-duplicate prompts
dedup_threshold = 0.85                    # cosine similarity threshold (0.0–1.0)
dedup_window = 50                         # number of recent history entries to check
preference_learning = true                # learn from accept/reject/edit actions
preference_min_samples = 5               # min samples before applying learned rules

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
hotkey = "ctrl+shift+e"              # Global hotkey (modifier+key format)
clipboard_settle_ms = 100            # Wait after Cmd+C before reading clipboard
notify = true                        # Show macOS notifications
notify_sound = true                  # Play sound with notifications
ollama_prewarm = true                # Pre-load Ollama model on daemon start
ollama_keepalive_minutes = 30        # Ollama keep_alive duration
log_level = "info"                   # debug | info | warning | error

[auto_enhance]
enabled = true                       # Auto-enhance low-quality prompts in AI tools
threshold = 40                       # PQS score below which auto-enhance triggers (0-100)
min_words = 5                        # Skip prompts shorter than this (commands, not prompts)
bypass_prefix = "!"                  # Prefix to skip auto-enhance (e.g. "! my prompt")
```

### Config resolution order

Settings are resolved in this order (first wins):

1. **CLI flags** — `--provider`, `--style`
2. **Environment variables** — `PROMPTUNE_PROVIDER`, `PROMPTUNE_STYLE`
3. **Config file** — `~/.config/promptune/config.toml`
4. **Defaults** — Claude provider, balanced style

### Environment variables

```bash
# Override provider for a single command
PROMPTUNE_PROVIDER=openai promptune enhance "your prompt"

# Override style
PROMPTUNE_STYLE=thorough promptune enhance "your prompt"

# Set permanently in your shell profile
export PROMPTUNE_PROVIDER="claude"
export PROMPTUNE_STYLE="balanced"
```

## Supported Providers

### Claude (Anthropic)

- **SDK:** `anthropic`
- **Get API key:** https://console.anthropic.com/
- **Config:** `[api_keys] claude = "sk-ant-..."` and `[provider] model_claude = "..."`
- **Default model:** `claude-haiku-4-5-20251001`
- **Note:** Requires a separate API key with pay-per-use billing. Claude Pro/Max subscriptions cannot be used.

### OpenAI

- **SDK:** `openai`
- **Get API key:** https://platform.openai.com/api-keys
- **Config:** `[api_keys] openai = "sk-..."` and `[provider] model_openai = "..."`
- **Default model:** `gpt-4o-mini`
- **Note:** Requires a separate API key. ChatGPT Plus/Pro subscriptions do not include API access.

### OpenRouter

- **SDK:** `httpx` (HTTP client)
- **Get API key:** https://openrouter.ai/keys
- **Config:** `[api_keys] openrouter = "sk-or-..."` and `[provider] model_openrouter = "..."`
- **Default model:** `anthropic/claude-haiku-4.5`
- **Note:** Access to 200+ models through a single API key. Pay-per-use.

## TUI Controls

When the TUI displays your original and enhanced prompts, keys trigger instantly on press — no Enter required:

| Key | Action |
|-----|--------|
| `A` | **Accept** — output the enhanced prompt and exit |
| `E` | **Edit** — open an editor to modify the enhanced prompt, then accept |
| `R` | **Reject** — discard the enhancement and exit with error code |
| `?` | **More** — reveal additional toggle keys (Q/D/C) |
| `Q` | **Quality** — toggle quality score breakdown (expanded mode) |
| `D` | **Details** — toggle rules/details applied (expanded mode) |
| `C` | **Context** — toggle context fingerprint (expanded mode) |

**Layout:** If your terminal is 100+ columns wide, prompts are displayed side by side. Otherwise, they're stacked vertically.

**Editing:** When you press `E`, a multiline editor opens with the enhanced prompt pre-filled. Press `Esc` then `Enter` to finish editing.

## Usage Examples

### Everyday prompt enhancement

```bash
# Quick coding task
promptune enhance "add dark mode to my react app"

# Writing task
promptune enhance "write an email to the team about the deadline change"

# Research
promptune enhance "explain kubernetes networking"
```

### Scripting and automation

```bash
# Enhance and copy to clipboard
promptune enhance --no-tui "build a login page" | pbcopy

# Enhance from a file
cat prompt.txt | promptune enhance --no-tui

# Use in a script
ENHANCED=$(promptune enhance --no-tui "your prompt")
echo "$ENHANCED"
```

### Provider switching

```bash
# Use OpenAI for this one prompt
promptune enhance -p openai "optimize this SQL query"

# Use thorough style with OpenRouter
promptune enhance -p openrouter -s thorough "design a microservices architecture"
```

## Semantic Deduplication

Promptune remembers prompts you've enhanced before. When you submit a prompt that closely matches one from your recent history (same project), Promptune returns the cached result instantly — no LLM call, no scoring, no delay.

- Similarity is measured using TF-based cosine similarity (threshold: 0.85 by default)
- Only prompts you accepted or edited are reused; rejected prompts are excluded
- Edited prompts return your edited version, not the original AI output
- Scoped per project (based on git root or working directory)
- Prompts shorter than 3 words are never deduplicated

When a cached result is returned, the TUI shows `tier_used: -1` to indicate a cache hit.

**Configuration:**

```toml
[enhancement]
dedup_enabled = true          # enable/disable deduplication
dedup_threshold = 0.85        # similarity threshold (0.0–1.0)
dedup_window = 50             # number of recent entries to check
```

## Preference Learning

Promptune learns from your Accept/Reject/Edit decisions over time. If you consistently reject prompts that use a particular Tier 0 rule, Promptune will automatically skip that rule in future enhancements.

**How it works:**

- After accumulating enough history (`preference_min_samples`, default 5), Promptune analyses your decisions per rule
- Rules rejected >60% of the time are automatically skipped
- If you consistently edit out role-assignment prefixes or format suffixes, those rules are suppressed too
- View your current learned preferences with `promptune history --preferences`

**Configuration:**

```toml
[enhancement]
preference_learning = true       # enable/disable preference learning
preference_min_samples = 5       # min samples before learning kicks in
```

## Team Templates

Create shared prompt templates for your team by adding `.md` files to a `.prompts/` directory in your project root. Templates are automatically matched based on intent and domain.

**Template format:**

```markdown
---
intent: debug
domain: python
---
## Debug Context
Stack: {{stack}}
Branch: {{branch}}

Focus on identifying the root cause before suggesting fixes.
```

**Frontmatter fields:**

- `intent` — matches the detected prompt intent (e.g., debug, build, refactor)
- `domain` — matches the detected tech domain (e.g., python, javascript, rust)

Templates with both `intent` and `domain` are preferred over single-field matches. Available variables: `{{intent}}`, `{{domain}}`, `{{project_root}}`, `{{branch}}`, `{{stack}}`.

## Troubleshooting

### "Missing api_key for provider"

You haven't set an API key for your default provider. Edit your config:

```bash
nano $(promptune config path)
```

### "Invalid provider" or "Invalid style"

Check your config for typos. Valid providers: `claude`, `openai`, `openrouter`. Valid styles: `minimal`, `balanced`, `detailed`.

### "Connection refused" or network errors

Check your internet connection and verify your API key is valid. Try:

```bash
# Test with a simple prompt
promptune enhance --no-tui "hello"
```

### Ctrl+E doesn't work in terminal

1. Make sure you've added shell integration to your shell config file (see Setup above).
2. Reload your shell: open a new terminal tab or `source` your config file.
3. **Warp Terminal:** Warp replaces the shell's line editor, so keybindings cannot work. Use the CLI directly instead:
   ```bash
   promptune enhance "your prompt"
   # Or create an alias:
   alias pe='promptune enhance --no-tui'
   ```
4. Run `promptune doctor` to check for issues.

### Empty or unexpected output

Try using `--no-tui` to see raw output. Check that your API key has sufficient credits/balance.

### Daemon: "Could not create CGEventTap" (macOS)

The daemon needs Accessibility permissions. Run:

```bash
promptune daemon setup
```

Or grant manually: **System Settings → Privacy & Security → Accessibility** → add your terminal app. Then restart the daemon.

### Daemon: missing tools (Linux)

Run `promptune daemon setup` to check dependencies. For X11: install `xclip` and `xdotool`. For Wayland: install `wl-clipboard` and `ydotool`. The setup command shows the exact install command for your package manager.

### Daemon: hotkey doesn't fire

1. Check `promptune daemon status` — verify the daemon is running
2. Run `promptune daemon diagnose` — checks platform-specific issues
3. **macOS:** If "Secure input active" is reported, a password field or secure app is blocking global key events
4. **Linux Wayland:** If Portal GlobalShortcuts is unavailable, the daemon falls back to evdev (requires `input` group membership)
5. Verify the hotkey isn't claimed by another app

### Daemon: "No text selected"

You pressed the hotkey without selecting text first. Select text in any app, then press the hotkey.

### Daemon: "Unsupported platform: WSL"

The daemon does not support WSL (Windows Subsystem for Linux). Use the CLI directly or the shell widget instead.

## Requirements

- **Python:** 3.9+
- **OS:** macOS or Linux (X11 / Wayland)
- **Shell:** Zsh, Bash, or Fish (for shell widget)
- **API key:** At least one provider (Claude, OpenAI, or OpenRouter)
- **Linux daemon extras:** `pip install "promptune[linux-daemon]"` for python-xlib, dbus-next, evdev
