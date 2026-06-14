# Cross-Terminal Shell Integration Design

**Date:** 2026-03-17
**Status:** Draft
**Scope:** Phase 1 — multi-shell keybinding support + Warp fallback
**Note:** This spec un-defers "fish/bash shell widgets" from the Phase 1 Next Iteration spec (2026-03-15).

## Problem

The current shell integration (`shell.py`) generates a zsh-only ZLE widget bound to Ctrl+E. This fails in:

- **Warp Terminal** (~5-8% of dev share): Warp replaces zsh's line editor entirely. ZLE widgets, `bindkey`, and `$BUFFER` are non-functional.
- **Bash/Fish users**: No support at all for non-zsh shells.

## Goals

1. Support zsh, bash, and fish shells with inline Ctrl+E prompt enhancement.
2. Allow users to customize the keybinding via `--key` flag.
3. Auto-detect the user's shell from `$SHELL`.
4. Warn Warp users that the widget won't work and suggest CLI alternatives.

## Non-Goals

- IDE terminal keybinding conflict resolution (VS Code, Cursor, Windsurf, Zed) — deferred beyond Phase 1.
- Global hotkey daemon (Hammerspoon/skhd) integration.
- Warp plugin/workflow integration (blocked on Warp API availability).
- Key format validation — `--key` is passed through verbatim in Phase 1. Invalid keys will produce scripts with invalid bindings. This is an explicit trade-off for simplicity.
- Config file persistence for `--shell` and `--key` — these are CLI-only flags. No TOML config entries.

## Terminal Compatibility

| Category | Terminals | Shell Widget Support | ~Dev Share |
|---|---|---|---|
| Full support | iTerm2, Terminal.app, Kitty, Alacritty, Ghostty, WezTerm, GNOME Terminal, Windows Terminal+WSL | Yes | ~50-65% |
| Partial support | tmux, screen | Pass-through to underlying shell; some key combos may be intercepted by multiplexer config | ~varies |
| No support | Warp | Replaces shell line editor entirely | ~5-8% |

## Design

### CLI Changes

`promptune shell-init` gains two options:

```
promptune shell-init                    # auto-detect $SHELL, default Ctrl+E
promptune shell-init --shell zsh        # force zsh output
promptune shell-init --shell bash       # force bash output
promptune shell-init --shell fish       # force fish output
promptune shell-init --key "\C-e"       # custom key (canonical format)
```

- `--shell`: Accepts `auto` (default), `zsh`, `bash`, `fish`. `auto` reads `$SHELL` env var, extracts basename, falls back to `zsh`.
- `--key`: Accepts a canonical key format. Default is `ctrl+e`. See Key Translation section below.

### Key Translation

Each shell uses different syntax for keybindings. The `--key` flag accepts a **canonical format** and `generate_widget()` translates it to the shell-native syntax.

**Canonical format**: `ctrl+<char>` (e.g., `ctrl+e`, `ctrl+x ctrl+e`).

**Translation table**:

| Canonical | Zsh (`bindkey`) | Bash (`bind -x`) | Fish (`bind`) |
|---|---|---|---|
| `ctrl+e` | `'^E'` | `'"\C-e"'` | `\ce` |
| `ctrl+x ctrl+e` | `'^X^E'` | `'"\C-x\C-e"'` | `\cx \ce` |
| `alt+e` | `'^[e'` | `'"\ee"'` | `\ee` |

The translation is handled by a `_translate_key(canonical: str, shell: str) -> str` helper in `shell.py`.

If the user passes a raw shell-native key (e.g., `--key "^E"`), it is passed through verbatim without translation (detected by absence of `+` separator). This allows power users to bypass canonical format.

### Shell Scripts

All three scripts follow the same pattern: read buffer -> guard empty input -> call `promptune enhance --no-tui` -> replace buffer on success -> preserve original on failure.

#### Zsh (ZLE widget)

```zsh
# Promptune Zsh Widget
_promptune_enhance() {
    local original="$BUFFER"
    if [[ -z "$original" ]]; then
        return
    fi
    local enhanced
    enhanced=$(promptune enhance --no-tui "$original" 2>/dev/null)
    if [[ $? -eq 0 && -n "$enhanced" ]]; then
        BUFFER="$enhanced"
        CURSOR=${#BUFFER}
    fi
    zle redisplay
}

zle -N _promptune_enhance
bindkey <TRANSLATED_KEY> _promptune_enhance
```

#### Bash (readline)

```bash
# Promptune Bash Widget
_promptune_enhance() {
    if [[ -z "$READLINE_LINE" ]]; then
        return
    fi
    local enhanced
    enhanced=$(promptune enhance --no-tui "$READLINE_LINE" 2>/dev/null)
    if [[ $? -eq 0 && -n "$enhanced" ]]; then
        READLINE_LINE="$enhanced"
        READLINE_POINT=${#READLINE_LINE}
    fi
}
bind -x '<TRANSLATED_KEY>: _promptune_enhance'
```

Uses `READLINE_LINE` and `READLINE_POINT` — bash's equivalent of zsh's `$BUFFER` and `$CURSOR`.

#### Fish

```fish
# Promptune Fish Widget
function _promptune_enhance
    set -l original (commandline)
    if test -z "$original"
        return
    end
    set -l enhanced (promptune enhance --no-tui "$original" 2>/dev/null)
    if test $status -eq 0 -a -n "$enhanced"
        commandline -r "$enhanced"
    end
end
bind <TRANSLATED_KEY> _promptune_enhance
```

Uses fish's `commandline` builtin for buffer read/write.

### Code Architecture

**`shell.py`** — refactored from single function to:

| Function | Purpose |
|---|---|
| `generate_widget(shell: str, key: str) -> str` | Dispatcher — resolves shell (via `detect_shell` if `"auto"`), translates key, calls the right generator |
| `_generate_zsh_widget(key: str) -> str` | ZLE widget script (parameterized key, already translated) |
| `_generate_bash_widget(key: str) -> str` | Readline-based bash script |
| `_generate_fish_widget(key: str) -> str` | Fish commandline-based script |
| `detect_shell() -> str` | Reads `$SHELL`, extracts basename, validates against `{"zsh", "bash", "fish"}`. Falls back to `"zsh"` with stderr warning if unsupported or unset. |
| `_translate_key(canonical: str, shell: str) -> str` | Converts canonical key format to shell-native syntax. Passes through verbatim if no `+` separator detected. |

**`cli.py`** — `shell-init` command updated:

- Adds `--shell` option (`auto`/`zsh`/`bash`/`fish`, default `auto`)
- Adds `--key` option (default `ctrl+e`)
- Calls `generate_widget(shell, key)` instead of `generate_zsh_widget()`

**No new files.** All changes in `shell.py` and `cli.py`.

### Warp Fallback

**Detection in `shell-init`**: When `$TERM_PROGRAM == "WarpTerminal"` is detected, `shell-init` emits a comment-based warning at the top of the generated script:

```
# WARNING: Warp Terminal detected. Warp replaces zsh's line editor,
# so the keybinding below will NOT work. Use the CLI directly:
#   promptune enhance "your prompt"
#   alias pe='promptune enhance --no-tui'
```

**Detection in `promptune doctor`**: New check function `_check_shell_widget()` added to the doctor checks list. Checks `$TERM_PROGRAM` for Warp and warns accordingly.

**Documented alternatives** (User Guide troubleshooting section):

- `promptune enhance "my prompt"` — direct CLI usage
- `alias pe='promptune enhance --no-tui'` — shell alias

### User Guide Updates

- Update shell integration section to cover zsh, bash, and fish setup.
- Add `--shell` and `--key` flag documentation.
- Update troubleshooting: Warp limitation with alternatives.
- Update requirements: add bash and fish to supported shells.

## Testing

### Unit tests for generator functions
- Each of zsh, bash, fish generators produces syntactically correct output.
- Zsh output contains `zle`, `bindkey`, `$BUFFER`.
- Bash output contains `bind -x`, `READLINE_LINE`, `READLINE_POINT`.
- Fish output contains `commandline`, `bind`, `$status` (not `$?`).
- All three contain empty-input guards.
- All three contain the translated key, not the canonical format.

### Key translation tests
- `ctrl+e` translates correctly for each shell.
- `ctrl+x ctrl+e` (chord) translates correctly for each shell.
- `alt+e` translates correctly for each shell.
- Raw shell-native keys (no `+` separator) are passed through verbatim.

### Shell detection tests
- `$SHELL=/bin/zsh` → `"zsh"`.
- `$SHELL=/usr/bin/bash` → `"bash"`.
- `$SHELL=/usr/local/bin/fish` → `"fish"`.
- `$SHELL=/bin/dash` → `"zsh"` (fallback) with stderr warning.
- `$SHELL` unset → `"zsh"` (fallback) with stderr warning.

### Dispatch tests
- `generate_widget("zsh", "ctrl+e")` returns zsh script.
- `generate_widget("bash", "ctrl+e")` returns bash script.
- `generate_widget("fish", "ctrl+e")` returns fish script.
- `generate_widget("auto", "ctrl+e")` respects `$SHELL`.

### CLI tests
- `shell-init` with no flags → auto-detected output.
- `shell-init --shell bash` → bash output.
- `shell-init --shell fish --key "ctrl+x ctrl+e"` → fish output with chord key.

### Warp detection tests
- `_check_shell_widget()` with `$TERM_PROGRAM=WarpTerminal` → warning.
- `_check_shell_widget()` with `$TERM_PROGRAM=iTerm2` → OK.
- `shell-init` output with `$TERM_PROGRAM=WarpTerminal` → contains warning comment.

### Backward compatibility
- `generate_zsh_widget()` wrapper returns same output as `generate_widget("zsh", "ctrl+e")`.

## Migration

- `generate_zsh_widget()` becomes a thin wrapper around `generate_widget("zsh", "ctrl+e")` for backward compatibility, then deprecated.
- Users with `eval "$(promptune shell-init)"` in `.zshrc` — no change needed, auto-detection picks zsh.
