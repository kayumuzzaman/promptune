# Architecture

## Layer Responsibilities

```
┌─────────────┐
│   cli.py    │  Click commands — parses args, delegates to engine
├─────────────┤
│  setup.py   │  Interactive config wizard — provider/key prompts, validation
├─────────────┤
│  engine.py  │  Tier-based router — scores prompt, applies rules, routes to provider
├─────────────┤
│  scorer.py  │  7-dimension prompt quality scoring
├─────────────┤
│  tier0.py   │  Rule engine — deterministic prompt improvements (free, instant)
├─────────────┤
│meta_prompt.py│  Analysis — detects intent/domain/stack, builds system prompt
├─────────────┤
│  context/   │  Context fingerprinting — git, shell history, tech stack detection
├─────────────┤
│ providers/  │  API adapters — Claude, OpenAI, OpenRouter, local LLM
├─────────────┤
│ formatter.py│  Provider-specific output formatting (XML, Markdown, Plain)
├─────────────┤
│  history.py │  SQLite-backed enhancement history with statistics
├─────────────┤
│   dedup.py  │  TF-based cosine similarity — detects near-duplicate prompts
├─────────────┤
│preferences.py│  Preference learning — rule reject/accept patterns, edit pattern detection
├─────────────┤
│ templates.py│  Team templates — .prompts/ frontmatter parsing, intent/domain matching, variable injection
├─────────────┤
│   tui.py    │  Rich TUI — diff view, quality scores, Accept/Edit/Reject
├─────────────┤
│  shell.py   │  Shell widget generation — Zsh, Bash, Fish
├─────────────┤
│   gate.py   │  Auto-enhance gate — score prompt, enhance if low, inject as hook context
├─────────────┤
│   hooks/    │  AI tool hook detection + installers (Claude Code, extensible)
├─────────────┤
│    mcp/     │  MCP server — exposes enhance + score tools via stdio transport
└─────────────┘
```

## Enhancement Flow (3-Tier)

```
User prompt
    ↓
engine.py: dedup check (if dedup_enabled and history enabled)
    ├─ similarity >= threshold → return cached result (tier_used=-1)
    └─ no match → continue
    ↓
scorer.py: score raw prompt (7 dimensions)
    ↓
tier0.py: apply deterministic rules (always runs)
    ↓
scorer.py: re-score post-Tier 0
    ↓
templates.py: match .prompts/ template (intent + domain) and inject into system prompt
    ↓
engine.py: route based on score
    ├─ score >= 70 → done (Tier 0 only)
    ├─ score < 70, local LLM enabled → Tier 1 (local LLM)
    └─ score < 70, cloud enabled → Tier 2 (cloud API)
    ↓
scorer.py: final score
    ↓
tui.py or stdout: present result
```

## Shell Widget Flow

```
User types prompt in terminal
    ↓
Ctrl+E (shell widget captures command line)
    ↓
promptune enhance --no-tui "$BUFFER"
    ↓
cli.py → engine.py → providers/ → stdout
    ↓
Shell widget replaces command line with stdout
```

Supported shells: **Zsh** (zle + bindkey), **Bash** (bind -x + READLINE_LINE), **Fish** (commandline + bind)

## Daemon Layer (Phase 2 + Phase 3)

```
┌──────────────────────────────────────────────────────┐
│                   promptune daemon                    │
│                   (background process)                │
│                                                       │
│  ┌─────────────────────────────────────────────────┐  │
│  │          platform/ (abstraction layer)           │  │
│  │                                                   │  │
│  │  base.py — ABCs: HotkeyBackend, ClipboardBackend,│  │
│  │            NotifyBackend, ServiceBackend,          │  │
│  │            ActiveWindowBackend, DependencyChecker  │  │
│  │                                                   │  │
│  │  __init__.py — get_platform() factory             │  │
│  │    ├─ darwin  → macos.py (CGEventTap, pbcopy,     │  │
│  │    │            osascript, LaunchAgent)            │  │
│  │    ├─ linux/x11 → linux_x11.py (XGrabKey, xclip, │  │
│  │    │              xdotool, _NET_ACTIVE_WINDOW)     │  │
│  │    └─ linux/wayland → linux_wayland.py (portal/   │  │
│  │                 evdev, wl-clipboard, ydotool)      │  │
│  │                                                   │  │
│  │  linux_service.py — systemd user service manager  │  │
│  └─────────────────────────────────────────────────┘  │
│                          │                            │
│  ┌───────────────────────v───────────────────────┐   │
│  │           daemon.py (main loop)               │   │
│  │  Hotkey → clipboard → engine → paste back     │   │
│  └──────────────────┬────────────────────────────┘   │
│                     │                                │
│        ┌────────────┼────────────┐                   │
│        v            v            v                   │
│   engine.py    ipc.py      prewarm.py                │
│   (existing)   (Unix sock)  (Ollama warm)            │
└──────────────────────────────────────────────────────┘
```

**Data flow:** User selects text → Ctrl+Shift+E → platform hotkey fires → clipboard pipeline (copy selection, read, enhance, paste result) → platform notification. Silent mode — no TUI, Ctrl+Z to undo.

**Platform abstraction:** `daemon/platform/base.py` defines 6 ABCs. `daemon/platform/__init__.py` provides `get_platform()` factory that detects macOS vs Linux (X11/Wayland) at runtime. WSL is detected and blocked with a clear error message.

**macOS modules:** `daemon/hotkey.py` (CGEventTap, accessibility), `daemon/clipboard.py` (pbcopy/pbpaste, key simulation, undo buffer), `daemon/notify.py` (osascript notifications), `daemon/launchagent.py` (launchd plist management). Wrapped by `daemon/platform/macos.py` adapter.

**Linux X11 modules:** `daemon/platform/linux_x11.py` — XGrabKey hotkey, xclip clipboard, xdotool key simulation, `_NET_ACTIVE_WINDOW` detection.

**Linux Wayland modules:** `daemon/platform/linux_wayland.py` — Portal GlobalShortcuts (dbus-next) with evdev fallback hotkey, wl-clipboard, ydotool key simulation, GNOME/KDE/sway active window detection.

**Linux service:** `daemon/platform/linux_service.py` — systemd user service install/uninstall/purge, dependency checker with package manager detection (apt/dnf/pacman/zypper).

**Shared modules:** `daemon/ipc.py` (Unix socket for shell CWD tracking), `daemon/prewarm.py` (Ollama keep-alive), `daemon/daemon.py` (lifecycle orchestration via platform factory).

**CLI:** `promptune daemon start|stop|restart|status|setup|diagnose|install|uninstall|purge` (plus legacy macOS `install-login-item|uninstall-login-item`)

## Technical Decisions

### 3-Tier Enhancement

- **Tier 0** — Deterministic rules (free, instant, always runs). Handles output format, vague verbs, constraints, role injection, etc.
- **Tier 1** — Local LLM via OpenAI-compatible API (e.g., Ollama). Fast, private, no API cost.
- **Tier 2** — Cloud API (Claude, OpenAI, OpenRouter). Highest quality, requires API key.

Graceful degradation: if a higher tier fails, falls back to the tier below.

### stdout-Only Output

Enhanced prompts are written exclusively to stdout. This enables:

- Clean piping: `promptune enhance "prompt" | pbcopy`
- Shell widget integration: widget reads stdout to replace buffer
- Predictable behavior: output goes exactly where you expect

### Provider Architecture

All providers implement `BaseProvider` ABC with a single `enhance(prompt: str, system_prompt: str) -> str` method. The provider registry (`get_registry()`) maps string names to provider classes.

Adding a new provider:
1. Create `providers/new_provider.py` implementing `BaseProvider`
2. Add a `register(registry)` function
3. Register it in `engine.py:get_registry()`

### Context Fingerprinting

`context/` module collects environmental signals (git branch, recent commits, modified files, shell history errors, tech stack) and ranks them by relevance within a token budget. This context is appended to the system prompt for AI tiers.

### Config Resolution

CLI flags → environment variables → auto-downgrade → config file → defaults

**Auto-downgrade:** When no API keys are configured, `max_tier` is automatically capped — tier 1 if local LLM is enabled, tier 0 otherwise. This ensures `promptune enhance` works instantly with zero config (Tier 0 rules are free and instant). CLI `--tier` overrides the auto-downgrade.

### Interactive Setup

`setup.py` provides a Click-based wizard that walks users through mandatory fields (provider, API key, model name) and optional settings (style, max tier, format). When advanced settings are enabled and max tier >= 1, the wizard also prompts for local LLM configuration (enabled, host, model). After all settings, the wizard auto-detects installed AI tools (via `hooks.detect_tools()`) and offers to install auto-enhance hooks. Uses `get_registry()` for dynamic provider listing. All fields are pre-filled with existing or default values. Handles re-runs with pre-filled defaults and non-interactive fallback.

### Auto-Enhance Gate

`gate.py` implements the auto-enhance hook pipeline. When invoked via `promptune gate` (which reads JSON from stdin), it: (1) checks if auto-enhance is enabled, prompt does not start with the bypass prefix, and meets minimum word count, (2) scores the prompt using `scorer.score_prompt()`, (3) if below threshold — enhances via `engine.enhance()` and silently injects the enhanced prompt by writing a `UserPromptSubmit` `hookSpecificOutput` JSON (`additionalContext`) to stdout, then prints a one-line transparency note to stderr. The gate always exits 0, so the original prompt proceeds and the model sees the enhanced version as added context (the hook cannot replace the typed prompt). This shared stdout contract works for both Claude Code and Codex `UserPromptSubmit` hooks. Gracefully degrades: invalid JSON, missing prompt key, or config errors all exit 0 with no stdout output.

### Hook Installers

`hooks/__init__.py` defines the `HookInstaller` protocol (detect, install, uninstall, is_installed) and provides `get_installers()` (registry) and `detect_tools()` (filtered by detection). `hooks/claude_code.py` implements the first installer for Claude Code — it manages a `UserPromptSubmit` hook entry in `~/.claude/settings.json`. New AI tool support (Codex, Cursor, etc.) requires only a new installer class implementing the protocol.

### MCP Server

`mcp/server.py` wraps `engine.enhance()` and `scorer.score_prompt()` as MCP tools using FastMCP (optional dependency: `pip install promptune[mcp]`). The server runs on stdio transport — AI tools launch it as a subprocess. Two tools are exposed: `enhance_prompt` (with style/tier/format overrides) and `score_prompt_quality`. The `mcp` package is import-guarded; missing dependency produces a clear error message.

### Preference Learning

`preferences.py` learns from user history to suppress disliked Tier 0 rules. `analyse_rule_preferences()` counts accept/reject decisions per rule — rules rejected >60% of the time are added to a `skip_rules` set passed to `apply_rules()`. `analyse_edit_patterns()` detects consistent removal of role-assignment prefixes or format suffixes via regex, mapping those patterns to rule names for suppression. Gated by `preference_learning` config key; requires `preference_min_samples` entries before activating.

### Team Templates

`templates.py` loads `.prompts/*.md` files from the project root. Each template has YAML-like frontmatter with `intent` and/or `domain` fields. `match_template()` finds the best match for the detected intent/domain using specificity ranking (intent+domain > intent-only > domain-only), with alphabetical tiebreaking. `inject_variables()` replaces `{{variable}}` placeholders (intent, domain, project_root, branch, stack) before appending the template body to the system prompt.

### Semantic Deduplication

`dedup.py` computes TF-based cosine similarity (stdlib only — no numpy/sklearn) between a new prompt and recent history entries for the same project. If a match exceeds `dedup_threshold` (default 0.85), the cached enhanced prompt is returned immediately — skipping LLM calls entirely. Entries with `decision="reject"` are excluded; `decision="edit"` entries use the user-edited result. Prompts shorter than 3 tokens are never checked.
