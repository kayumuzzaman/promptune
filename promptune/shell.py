"""Shell widget generation for zsh, bash, and fish."""

from __future__ import annotations

import os
import sys

# Shell metacharacters that could break out of the quoted bind line and inject
# commands when the generated widget is eval'd.
_UNSAFE_KEY_CHARS = "'\"`;$\n\r"


def _translate_key(canonical: str, shell: str) -> str:
    """Translate canonical key format to shell-native syntax.

    Canonical format: 'ctrl+<char>', 'alt+<char>', 'ctrl+x ctrl+e' (chords).
    If no '+' separator is found, passes through verbatim (raw shell-native key).
    """
    if "+" not in canonical:
        # Raw shell-native key passthrough. Reject shell metacharacters so a
        # crafted --key can't break out of the generated quoted bind line and
        # inject commands when the widget is eval'd.
        if any(c in canonical for c in _UNSAFE_KEY_CHARS):
            raise ValueError(
                f"Unsafe raw key binding {canonical!r}: contains shell "
                "metacharacters."
            )
        return canonical

    parts = canonical.split()  # Split chord: "ctrl+x ctrl+e" -> ["ctrl+x", "ctrl+e"]

    for part in parts:
        modifier, _, char = part.partition("+")
        modifier = modifier.lower()
        if modifier not in {"ctrl", "alt"}:
            raise ValueError(
                f"Unsupported hotkey modifier {modifier!r} in "
                f"{canonical!r}. Supported modifiers: ctrl, alt."
            )
        # Allow a single character (incl. punctuation like '/' or '-'), but
        # reject shell metacharacters so the char can't break out of the
        # quoted binding.
        if len(char) != 1 or char in _UNSAFE_KEY_CHARS:
            raise ValueError(
                f"Invalid hotkey {part!r} in {canonical!r}: expected a "
                "single non-metacharacter after the modifier."
            )

    if shell == "zsh":
        return _translate_key_zsh(parts)
    elif shell == "bash":
        return _translate_key_bash(parts)
    elif shell == "fish":
        return _translate_key_fish(parts)
    else:
        return canonical


def _translate_key_zsh(parts: list[str]) -> str:
    """Translate to zsh bindkey syntax: '^E', '^X^E', '^[e'."""
    tokens: list[str] = []
    for part in parts:
        modifier, _, char = part.partition("+")
        modifier = modifier.lower()
        if modifier == "ctrl":
            tokens.append(f"^{char.upper()}")
        elif modifier == "alt":
            tokens.append(f"^[{char.lower()}")
    return f"'{''.join(tokens)}'"


def _translate_key_bash(parts: list[str]) -> str:
    r"""Translate to bash bind -x syntax: '"\C-e"', '"\C-x\C-e"'."""
    tokens: list[str] = []
    for part in parts:
        modifier, _, char = part.partition("+")
        modifier = modifier.lower()
        if modifier == "ctrl":
            tokens.append(f"\\C-{char.lower()}")
        elif modifier == "alt":
            tokens.append(f"\\e{char.lower()}")
    return f'"{"".join(tokens)}"'


def _translate_key_fish(parts: list[str]) -> str:
    r"""Translate to fish bind syntax: \ce, \cx \ce, \ee."""
    tokens: list[str] = []
    for part in parts:
        modifier, _, char = part.partition("+")
        modifier = modifier.lower()
        if modifier == "ctrl":
            tokens.append(f"\\c{char.lower()}")
        elif modifier == "alt":
            tokens.append(f"\\e{char.lower()}")
    return " ".join(tokens)


SUPPORTED_SHELLS = {"zsh", "bash", "fish"}


def detect_shell() -> str:
    """Detect the user's shell from $SHELL env var.

    Returns basename of $SHELL if supported, otherwise falls back
    to 'zsh' with a stderr warning.
    """
    shell_path = os.environ.get("SHELL", "")
    if not shell_path:
        print(
            "Warning: $SHELL not set, falling back to zsh.",
            file=sys.stderr,
        )
        return "zsh"

    shell_name = os.path.basename(shell_path)
    if shell_name in SUPPORTED_SHELLS:
        return shell_name

    print(
        f"Warning: Unsupported shell '{shell_name}', falling back to zsh.",
        file=sys.stderr,
    )
    return "zsh"


# Shell-agnostic IPC snippet (POSIX).  Inserted into each widget to report
# the shell's CWD to the daemon via its Unix socket.  The backslash-newline
# keeps the echo + socat pipeline readable while staying under 88 columns
# in the Python source.
_IPC_POSIX = (
    "command -v socat >/dev/null 2>&1 && "
    "echo '{\"action\":\"report_cwd\","
    "\"cwd\":\"'\"$PWD\"'\","
    "\"project_root\":\"'\"$(git rev-parse"
    " --show-toplevel 2>/dev/null)\"'\"}' | \\\n"
    "        socat - UNIX-CONNECT:"
    "~/.local/share/promptune/promptune.sock"
    " >/dev/null 2>&1 &"
)

_IPC_FISH = (
    "command -v socat >/dev/null 2>&1; and "
    "echo '{\"action\":\"report_cwd\","
    "\"cwd\":\"'(pwd)'\","
    "\"project_root\":\"'(git rev-parse"
    " --show-toplevel 2>/dev/null)'\"}' | \\\n"
    "        socat - UNIX-CONNECT:"
    "~/.local/share/promptune/promptune.sock"
    " >/dev/null 2>&1 &"
)


def _generate_zsh_widget(key: str) -> str:
    """Generate zsh ZLE widget script with parameterized key."""
    return f"""\
# Promptune Zsh Widget
# Add to .zshrc: eval "$(promptune shell-init)"

_promptune_enhance() {{
    local original="$BUFFER"
    if [[ -z "$original" ]]; then
        return
    fi
    local enhanced
    enhanced=$(promptune enhance --no-tui "$original" 2>/dev/null)
    if [[ $? -eq 0 && -n "$enhanced" ]]; then
        BUFFER="$enhanced"
        CURSOR=${{#BUFFER}}
    fi
    # Report CWD to daemon (non-blocking, best-effort)
    {_IPC_POSIX}
    zle redisplay
}}

zle -N _promptune_enhance
bindkey {key} _promptune_enhance
"""


def _generate_bash_widget(key: str) -> str:
    """Generate bash readline widget script with parameterized key."""
    return f"""\
# Promptune Bash Widget
# Add to .bashrc: eval "$(promptune shell-init)"

_promptune_enhance() {{
    if [[ -z "$READLINE_LINE" ]]; then
        return
    fi
    local enhanced
    enhanced=$(promptune enhance --no-tui "$READLINE_LINE" 2>/dev/null)
    if [[ $? -eq 0 && -n "$enhanced" ]]; then
        READLINE_LINE="$enhanced"
        READLINE_POINT=${{#READLINE_LINE}}
    fi
    # Report CWD to daemon (non-blocking, best-effort)
    {_IPC_POSIX}
}}
bind -x '{key}: _promptune_enhance'
"""


def _generate_fish_widget(key: str) -> str:
    """Generate fish shell widget script with parameterized key."""
    return f"""\
# Promptune Fish Widget
# Add to config.fish: promptune shell-init | source

function _promptune_enhance
    set -l original (commandline)
    if test -z "$original"
        return
    end
    set -l enhanced (promptune enhance --no-tui "$original" 2>/dev/null)
    if test $status -eq 0 -a -n "$enhanced"
        commandline -r "$enhanced"
    end
    # Report CWD to daemon (non-blocking, best-effort)
    {_IPC_FISH}
end
bind {key} _promptune_enhance
"""


def generate_widget(shell: str, key: str) -> str:
    """Generate shell widget script for the given shell and key.

    Args:
        shell: 'zsh', 'bash', 'fish', or 'auto' (auto-detects from $SHELL).
        key: Canonical key format (e.g., 'ctrl+e') or raw shell-native key.

    Returns:
        Shell script string ready for eval.

    Raises:
        ValueError: If shell is not supported.
    """
    if shell == "auto":
        shell = detect_shell()

    translated_key = _translate_key(key, shell)

    generators = {
        "zsh": _generate_zsh_widget,
        "bash": _generate_bash_widget,
        "fish": _generate_fish_widget,
    }

    generator = generators.get(shell)
    if generator is None:
        raise ValueError(f"Unsupported shell: {shell!r}")

    script = generator(translated_key)

    if os.environ.get("TERM_PROGRAM") == "WarpTerminal":
        warp_warning = """\
# WARNING: Warp Terminal detected. Warp replaces your shell's line editor,
# so the keybinding below will NOT work. Use the CLI directly:
#   promptune enhance "your prompt"
#   alias pe='promptune enhance --no-tui'

"""
        script = warp_warning + script

    return script


def generate_zsh_widget() -> str:
    """Backward-compatible wrapper. Deprecated: use generate_widget()."""
    return _generate_zsh_widget("'^E'")
