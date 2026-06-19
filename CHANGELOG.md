# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- Tier 0 politeness removal no longer strips politeness words that appear as substrings inside larger words (e.g. "pleased" was being mangled to "d"); phrases now match on word boundaries only
- Tier 0 politeness removal no longer leaves orphaned or doubled punctuation after stripping a phrase (e.g. "fix the parser, please." now yields "fix the parser." instead of "fix the parser,."); legitimate sentence-final `.`/`!`/`?` are preserved
- `engine.enhance()` now logs swallowed history/dedup/preferences and template-injection failures at `warning` level (was `debug`), surfacing silent best-effort feature loss without breaking graceful degradation
- `promptune history` command — SQLite connection now properly closed via `try/finally` after each invocation, preventing resource leaks in long-running sessions
- Test fixtures in `test_preferences` and `test_dedup` now teardown `HistoryStore` connections, eliminating `ResourceWarning: unclosed database` noise from the test suite
- Daemon process-identity check (`_is_daemon_process`) now recognises a running daemon installed under a path containing spaces (e.g. macOS `Library/Application Support` or a user's full name); previously `stop` could orphan the real daemon and `start` could launch a duplicate. The check still rejects unrelated processes that merely pass `promptune daemon start` as arguments
- Tech-stack detection no longer false-matches common English words via inflections — `nested`/`nodes`/`pipes`/`expressed`/`reacted` no longer report TypeScript/JavaScript/Python/React; exact mentions (`pip`, `node`, `nest`, `express`, `react`) still detect the stack
- Preference learning now detects removal of the output-format instruction even when later tier-0 rules append text after it (constraints, the short-prompt `[Note: …]` hint); the `removes_format` signal was previously never learned for the low-quality prompts that most need it
- Shell-widget daemon IPC snippet now references the socket via `$HOME` instead of a mid-argument `~` (which neither the shell nor socat expands), so per-directory CWD reporting from the Zsh/Bash/Fish widgets actually reaches the daemon
- Auto-enhance gate now calls `enhance(record=False)` — it has no accept/reject surface, so it no longer records every gated prompt to history as a confirmed `accept` (which polluted dedup and preference learning with unconfirmed outcomes)
- macOS `paste_result()` now returns `False` when accessibility permission is missing (the synthetic Cmd+V is silently dropped by the OS), so the daemon reports "paste manually" instead of clobbering the clipboard with the user's original — mirroring the X11/Wayland backends
- `HistoryStore.set_decision()` now debug-logs when the target row was already pruned (`rowcount == 0`) instead of silently doing nothing

### Added

#### MCP Server
- `promptune mcp` — starts an MCP server (stdio transport) exposing `enhance_prompt` and `score_prompt_quality` tools, usable by any MCP-compatible AI tool (Claude Code, Cursor, Codex, etc.)
- Optional dependency: `pip install promptune[mcp]` (requires `mcp>=1.0`)

#### Auto-Enhance Gate
- `promptune gate` — hidden CLI command that reads a JSON payload from stdin (`{"prompt": "..."}`) and auto-enhances prompts scoring below a configurable PQS threshold; always exits 0 and, for a low-quality prompt, emits the enhanced version as `additionalContext` JSON on stdout for the host AI tool to inject (no clipboard, never blocks)
- `[auto_enhance]` config section — `enabled`, `threshold` (default 60), `min_words` (default 5)
- Hook installer framework (`promptune/hooks/`) with `HookInstaller` protocol for extensible AI tool support
- Claude Code hook installer — detects `~/.claude/` and installs a `UserPromptSubmit` hook in `settings.json`
- `config init` wizard auto-detects installed AI tools and offers to install the auto-enhance hook
- `promptune doctor` now shows auto-enhance hook status per detected AI tool

#### Rule Explanations
- `rules_explained` field added to `Tier0Result` and `EnhanceResult` — each applied rule now carries a human-readable description (e.g. "Replaced vague verbs with specific alternatives")
- CLI `enhance --json` output now includes `rules_explained` array of `{rule, reason}` objects
- MCP `enhance_prompt` tool output now includes `rules_explained` array

#### Bypass Prefix
- Auto-enhance gate supports a bypass prefix (default `!`) — prompts starting with `!` skip auto-enhance entirely
- Configurable via `[auto_enhance] bypass_prefix` in config

#### MCP Auto-Registration
- `config init` wizard now auto-registers the promptune MCP server in Claude Code's `settings.json` alongside the hook installation
- `ClaudeCodeInstaller.install_mcp()` / `is_mcp_installed()` methods for programmatic MCP server management

#### Score Command
- `promptune score "your prompt"` — scores a prompt across 7 quality dimensions (0-100 PQS) with per-dimension breakdown and actionable suggestions
- `--json` flag for structured JSON output

#### Zero-Config First Run
- `promptune enhance "text"` now works instantly without running `config init` — Tier 0 deterministic rules apply with zero setup
- Auto-downgrade: when no API keys are configured, `max_tier` is automatically capped (tier 1 if local LLM enabled, tier 0 otherwise)
- CLI `--tier` flag overrides the auto-downgrade for explicit tier forcing

### Changed
- Auto-enhance threshold lowered from PQS 60 to PQS 40 — reduces over-intervention so auto-enhance only triggers on genuinely low-quality prompts

#### Team Prompt Templates
- `promptune/templates.py` — `.prompts/` directory support: YAML-like frontmatter parsing (`parse_template`), directory loading (`load_templates`), intent/domain matching with specificity ranking (`match_template`), and `{{variable}}` placeholder injection (`inject_variables`)
- `Template` dataclass — carries `intent`, `domain`, `body`, `filename`, and computed `specificity` (0–2)
- `engine.enhance()` — template injection step: after context collection, matches a `.prompts/` template for the detected intent/domain, injects `{{intent}}`, `{{domain}}`, `{{project_root}}`, `{{branch}}`, and `{{stack}}` variables, and appends the rendered body to the system prompt; failures are silently swallowed so enhancement always proceeds
- `tests/test_templates.py` — full coverage of parsing, loading, matching, and variable injection

#### Preference Learning
- `promptune history --preferences` CLI flag — displays learned rule preferences (name, action, confidence, sample count) and edit patterns (description, frequency, sample count); prints "No preferences learned yet." when history is insufficient
- `promptune/preferences.py` — learns user preferences from enhancement history
- `Preference` dataclass — carries `rule_name`, `action` ("skip"/"keep"), `confidence`, and `sample_count`
- `analyse_rule_preferences()` — counts accept/reject decisions per Tier 0 rule; emits `Preference(action="skip")` when reject rate > 60%, `Preference(action="keep")` when accept rate > 60%; skips rules with fewer than `min_samples` entries or conflicting signals (neither rate > 60%)
- `EditPattern` dataclass — carries `pattern_type` ("removes_role"/"removes_format"), `description`, `frequency`, and `sample_count`
- `analyse_edit_patterns()` — scans edit history for consistent removal of role-assignment prefixes (`_ROLE_PREFIXES`) or output-format hint paragraphs (`_FORMAT_HINTS`); returns patterns whose frequency exceeds 60% of edit entries; returns empty list when fewer than `min_samples` edits exist
- `tests/test_preferences.py` — 9 tests covering disliked/liked rule detection, insufficient samples, conflicting signals, empty history, role/format removal detection, and no-edits edge cases
- `apply_rules()` in `tier0.py` — optional `skip_rules: set[str] | None` parameter; named rules in the set are silently bypassed in the pipeline, enabling preference-driven suppression without altering rule logic
- `engine.enhance()` — preference learning integration: before scoring, reads history to build a `skip_rules` set via `analyse_rule_preferences()` and `analyse_edit_patterns()`; rules with >60% reject rate or consistent user removal are added to the skip set and passed to `apply_rules()`; gated by `preference_learning` config key; failures are silently swallowed so enhancement always proceeds

#### Semantic Deduplication
- `promptune/dedup.py` — TF-based cosine similarity (`tokenize`, `_term_freq`, `cosine_similarity`) using stdlib only (no numpy/sklearn)
- `dedup_check()` — checks a prompt against recent project history; returns `DedupHit` (enhanced text + similarity score) above threshold, skips rejected entries and prompts under 3 tokens, uses user-edited result for `decision="edit"` entries
- `DedupHit` dataclass — carries `enhanced`, `similarity`, and `original_prompt`
- `tests/test_dedup.py` — 17 tests covering tokenization, similarity edge cases, and all `dedup_check` scenarios
- `engine.enhance()` — dedup early-exit: when `dedup_enabled=true` and a similar prompt is found in history, returns cached `EnhanceResult` with `tier_used=-1` immediately, skipping all scoring and LLM calls; dedup failures are silently swallowed so enhancement always proceeds
- `_detect_project_root()` helper in `engine.py` — detects git root via subprocess or falls back to `cwd()`

#### Ollama Auto-Check in Installer
- `install.sh` — `check_ollama()` function runs after install: detects Ollama binary on PATH, checks if server is running (curl localhost:11434), and verifies `qwen2.5:3b` model availability; informational only — never blocks or installs anything

#### Phase 2: OS-Level Hotkey Daemon (macOS)
- `promptune/daemon/` package — background daemon that registers a global hotkey (Ctrl+Shift+E via CGEventTap), captures selected text through clipboard, enhances it via the existing engine, and pastes the result back — works in any macOS application
- `promptune/daemon/hotkey.py` — CGEventTap global hotkey registration, `parse_hotkey()` for configurable key combos, accessibility permission checks (`check_accessibility`, `request_accessibility`), secure input detection
- `promptune/daemon/clipboard.py` — clipboard save/restore, CGEvent key simulation (Cmd+C/Cmd+V), frontmost app detection via NSWorkspace, undo buffer (`~/.local/share/promptune/undo.json`)
- `promptune/daemon/notify.py` — macOS notifications via osascript with score display and error messages
- `promptune/daemon/ipc.py` — Unix domain socket server for shell widget CWD tracking; `DaemonState` dataclass for shared state; handles `report_cwd` and `status` messages
- `promptune/daemon/prewarm.py` — Ollama model keep-alive timer with `_RepeatingTimer` (shared stop event for clean cancellation); `start_prewarm_timer()` for periodic warmup
- `promptune/daemon/launchagent.py` — LaunchAgent plist generation, install/uninstall for macOS auto-start on login
- `promptune/daemon/daemon.py` — daemon lifecycle (fork, setsid, PID file), enhancement pipeline with debounce, app-focus safety check, error recovery
- `promptune daemon start|stop|restart|status` CLI commands — daemon lifecycle management (--foreground flag for debugging)
- `promptune daemon setup|diagnose` — accessibility permission wizard and diagnostic checks
- `promptune daemon install-login-item|uninstall-login-item` — LaunchAgent plist management
- Shell widgets (Zsh/Bash/Fish) now include non-blocking IPC CWD reporting via socat to the daemon's Unix socket
- 95 daemon tests across 8 test files with full TDD coverage

#### Phase 3: Linux OS-Level Hotkey Daemon
- `promptune/daemon/platform/` package — platform abstraction layer with Strategy pattern for cross-platform daemon support
- `promptune/daemon/platform/base.py` — 6 ABCs (`HotkeyBackend`, `ClipboardBackend`, `NotifyBackend`, `ServiceBackend`, `ActiveWindowBackend`, `DependencyChecker`) + `DependencyStatus` and `PlatformBackend` dataclasses
- `promptune/daemon/platform/__init__.py` — runtime platform detection factory (`get_platform()`), `detect_session_type()` (X11/Wayland via `XDG_SESSION_TYPE` with `WAYLAND_DISPLAY`/`DISPLAY` fallback), `is_wsl()` detection (blocks with `PlatformError`)
- `promptune/daemon/platform/macos.py` — adapter wrapping existing `hotkey.py`, `clipboard.py`, `notify.py`, `launchagent.py` behind abstract interfaces
- `promptune/daemon/platform/linux_x11.py` — X11 backend: `XGrabKey` hotkey listener with `_X11_MOD_MASK` parsing, `xclip` clipboard read/write, `xdotool` key simulation (Ctrl+C/V), `_NET_ACTIVE_WINDOW` active window detection
- `promptune/daemon/platform/linux_wayland.py` — Wayland backend: Portal GlobalShortcuts (dbus-next) with evdev fallback hotkey, `wl-paste`/`wl-copy` clipboard, `ydotool` key simulation, GNOME Shell/KDE KWin/sway active window detection
- `promptune/daemon/platform/linux_service.py` — systemd user service management (install/uninstall/purge/is_installed), `LinuxDependencyChecker` with package manager detection (apt/dnf/pacman/zypper), `get_install_command()` for missing tool installation hints
- `promptune/daemon/daemon.py` — refactored to use `get_platform()` factory instead of direct macOS imports; `_on_hotkey()` takes `PlatformBackend` parameter; inline JSON undo buffer; macOS accessibility check conditionally applied
- `promptune daemon install|uninstall|purge` CLI commands — platform-aware service management
- `promptune daemon setup` — dispatches to macOS or Linux setup based on detected platform
- `promptune daemon diagnose` — platform-aware diagnostics using `get_platform()` factory
- `pyproject.toml` — `linux-daemon` optional dependency group (`python-xlib`, `dbus-next`, `evdev`); added Linux classifier
- 83 platform tests across 7 test files with TDD coverage

#### Daemon Config Defaults
- `DEFAULT_CONFIG["daemon"]` new section — `hotkey` ("ctrl+shift+e"), `clipboard_settle_ms` (100), `notify` (true), `notify_sound` (true), `ollama_prewarm` (true), `ollama_keepalive_minutes` (30), `log_level` ("info")
- `config.example.toml` updated with `[daemon]` section and inline comments
- `docs/USER_GUIDE.md` config reference updated to include `[daemon]` section

#### Enhancement Phase Config Defaults
- `DEFAULT_CONFIG["enhancement"]` now includes dedup and preference-learning keys: `dedup_enabled` (true), `dedup_threshold` (0.85), `dedup_window` (50), `preference_learning` (true), `preference_min_samples` (5)
- `config.example.toml` updated to document the new enhancement keys with inline comments

#### Interactive Config Setup Wizard
- `promptune config init` interactive wizard — walks user through provider selection, masked API key input, and optional advanced settings; pre-fills existing config on re-run; non-interactive fallback creates defaults with instructions
- `promptune/setup.py` module — `validate_key_format()`, `mask_key()`, `write_config()`, `run_interactive_setup()` and supporting prompt functions
- `get_registry()` public function in `engine.py` — exposes provider registry for dynamic provider listing

#### 3-Tier Enhancement Engine
- `promptune/engine.py` tier-based router — scores prompt, applies Tier 0 rules (always), then routes to Tier 1 (local LLM) or Tier 2 (cloud API) based on score threshold (70) with graceful fallback
- `--tier` flag on `promptune enhance` — force specific tier (0/1/2)
- `--json` flag on `promptune enhance` — structured JSON output with scores, tier, latency

#### 7-Dimension Quality Scoring
- `promptune/scorer.py` — scores prompts across specificity, clarity, structure, actionability, context, completeness, and conciseness (0-100 scale with sigmoid calibration)
- `promptune/pqs.py` — 5-dimension display mapping with color-coded bar visualization (red/yellow/green)

#### Rule Engine (Tier 0)
- `promptune/tier0.py` — 9-rule deterministic pipeline: politeness removal, negation rewrite, vague verb replacement, role assignment, output format injection, constraint addition, code delimiters, contradiction flagging, short prompt warning

#### Context Fingerprinting
- `promptune/context/` module — parallel collection (git, shell history, tech stack, environment) with 400ms timeout
- `promptune/context/collectors.py` — git branch/commits/modified files, shell history with error patterns and session intent, tech stack detection (languages/frameworks/package manager), environment flags (venv/container/CI/SSH)
- `promptune/context/ranker.py` — priority-based context ranking within token budget
- `promptune/context/sanitizer.py` — secret removal (API keys, tokens, passwords, high-entropy strings)

#### Local LLM Provider
- `promptune/providers/local.py` — OpenAI-compatible local LLM support (Ollama, LM Studio, llama.cpp, vLLM, etc.)
- `promptune local-llm-status` command — check local LLM connectivity

#### Enhancement History
- `promptune/history.py` — SQLite-backed history with WAL mode, auto-pruning, accept/reject/edit tracking
- `promptune history` command — view recent entries, show statistics (`--stats`), clear history (`--clear`)

#### System Health Check
- `promptune doctor` command — checks Python version, config file, Tier 0/1/2 availability, shell widget compatibility (with Warp Terminal warning)

#### Cross-Shell Widget Support
- Shell widget generation for Zsh (`zle` + `bindkey`), Bash (`bind -x` + `READLINE_LINE`), and Fish (`commandline` + `bind`)
- `detect_shell()` — auto-detects shell from `$SHELL`; supports zsh, bash, fish
- `_translate_key()` — translates canonical key format (`ctrl+e`, `alt+e`, chords) to shell-native syntax
- `generate_widget(shell, key)` — public dispatcher with `--shell` and `--key` flags on `promptune shell-init`
- Warp Terminal detection with incompatibility warning

### Changed

- TUI action keys (A/E/R/Q/D/C/?) now trigger instantly on keypress — no Enter required (uses `readchar`)
- TUI toggle panels: [?] More → [Q] Quality scores, [D] Details/rules, [C] Context fingerprint

## [0.1.0] - 2026-03-13

### Added

- `promptune enhance` command with `--provider`, `--style`, `--no-tui` flags
- TOML-based config system at `~/.config/promptune/config.toml`
- `promptune config init|show|path` commands
- Claude provider (Anthropic SDK)
- OpenAI provider (OpenAI SDK)
- OpenRouter provider (httpx)
- Meta-prompt engine with intent/domain/stack detection
- Enhancement styles: minimal, balanced, thorough
- Rich TUI with original vs enhanced diff view
- Accept/Edit/Reject workflow with prompt_toolkit editor
- Zsh shell widget (`promptune shell-init`) with Ctrl+E binding
- Piped input support (`echo "prompt" | promptune enhance`)
- 81 tests at 90% coverage
