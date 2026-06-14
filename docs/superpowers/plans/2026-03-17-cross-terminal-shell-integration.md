# Cross-Terminal Shell Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add bash and fish shell support to `promptune shell-init`, with configurable keybinding, shell auto-detection, and Warp Terminal warning.

**Architecture:** Refactor `shell.py` from a single `generate_zsh_widget()` function into a multi-shell dispatcher with key translation. The CLI `shell-init` command gains `--shell` and `--key` flags. Doctor command gains Warp detection.

**Tech Stack:** Python 3.9+, Click CLI, zsh ZLE, bash readline, fish commandline builtins.

**Spec:** `docs/superpowers/specs/2026-03-17-cross-terminal-shell-integration-design.md`

---

## Chunk 1: Key Translation and Shell Detection

### Task 1: Key Translation — `_translate_key()`

**Files:**
- Modify: `promptune/shell.py`
- Test: `tests/test_shell.py`

- [ ] **Step 1: Write failing tests for key translation**

Add these imports at the top of `tests/test_shell.py` (alongside existing imports):

```python
import pytest
```

Then add the test class:

```python
from promptune.shell import _translate_key


class TestTranslateKey:
    """Key translation from canonical format to shell-native syntax."""

    def test_ctrl_e_zsh(self) -> None:
        assert _translate_key("ctrl+e", "zsh") == "'^E'"

    def test_ctrl_e_bash(self) -> None:
        assert _translate_key("ctrl+e", "bash") == '"\\C-e"'

    def test_ctrl_e_fish(self) -> None:
        assert _translate_key("ctrl+e", "fish") == "\\ce"

    def test_chord_ctrl_x_ctrl_e_zsh(self) -> None:
        assert _translate_key("ctrl+x ctrl+e", "zsh") == "'^X^E'"

    def test_chord_ctrl_x_ctrl_e_bash(self) -> None:
        assert _translate_key("ctrl+x ctrl+e", "bash") == '"\\C-x\\C-e"'

    def test_chord_ctrl_x_ctrl_e_fish(self) -> None:
        assert _translate_key("ctrl+x ctrl+e", "fish") == "\\cx \\ce"

    def test_alt_e_zsh(self) -> None:
        assert _translate_key("alt+e", "zsh") == "'^[e'"

    def test_alt_e_bash(self) -> None:
        assert _translate_key("alt+e", "bash") == '"\\ee"'

    def test_alt_e_fish(self) -> None:
        assert _translate_key("alt+e", "fish") == "\\ee"

    def test_raw_passthrough_zsh_native(self) -> None:
        assert _translate_key("^E", "zsh") == "^E"

    def test_raw_passthrough_bash_native(self) -> None:
        assert _translate_key("\\C-e", "bash") == "\\C-e"

    def test_raw_passthrough_fish_native(self) -> None:
        assert _translate_key("\\ce", "fish") == "\\ce"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py::TestTranslateKey -v`
Expected: FAIL — `_translate_key` does not exist.

- [ ] **Step 3: Implement `_translate_key()` in `shell.py`**

Add to `promptune/shell.py` (after the existing import):

```python
import os
import sys


def _translate_key(canonical: str, shell: str) -> str:
    """Translate canonical key format to shell-native syntax.

    Canonical format: 'ctrl+<char>', 'alt+<char>', 'ctrl+x ctrl+e' (chords).
    If no '+' separator is found, passes through verbatim (raw shell-native key).
    """
    if "+" not in canonical:
        return canonical

    parts = canonical.split()  # Split chord: "ctrl+x ctrl+e" -> ["ctrl+x", "ctrl+e"]

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py::TestTranslateKey -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add promptune/shell.py tests/test_shell.py
git commit -m "feat: add key translation for zsh/bash/fish shell bindings"
```

---

### Task 2: Shell Detection — `detect_shell()`

**Files:**
- Modify: `promptune/shell.py`
- Test: `tests/test_shell.py`

- [ ] **Step 1: Write failing tests for shell detection**

Add to `tests/test_shell.py`:

```python
from promptune.shell import detect_shell


class TestDetectShell:
    """Shell auto-detection from $SHELL env var."""

    def test_detects_zsh(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/bin/zsh")
        assert detect_shell() == "zsh"

    def test_detects_bash(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/usr/bin/bash")
        assert detect_shell() == "bash"

    def test_detects_fish(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SHELL", "/usr/local/bin/fish")
        assert detect_shell() == "fish"

    def test_unsupported_shell_falls_back_to_zsh(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setenv("SHELL", "/bin/dash")
        assert detect_shell() == "zsh"
        captured = capsys.readouterr()
        assert "dash" in captured.err
        assert "falling back" in captured.err.lower()

    def test_unset_shell_falls_back_to_zsh(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("SHELL", raising=False)
        assert detect_shell() == "zsh"
        captured = capsys.readouterr()
        assert "falling back" in captured.err.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py::TestDetectShell -v`
Expected: FAIL — `detect_shell` does not exist.

- [ ] **Step 3: Implement `detect_shell()` in `shell.py`**

Add to `promptune/shell.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py::TestDetectShell -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add promptune/shell.py tests/test_shell.py
git commit -m "feat: add shell auto-detection from \$SHELL env var"
```

---

## Chunk 2: Shell Widget Generators

### Task 3: Zsh Widget Generator — `_generate_zsh_widget()`

**Files:**
- Modify: `promptune/shell.py`
- Test: `tests/test_shell.py`

- [ ] **Step 1: Write failing tests for parameterized zsh widget**

Add to `tests/test_shell.py`:

```python
from promptune.shell import _generate_zsh_widget


class TestGenerateZshWidget:
    """Zsh ZLE widget generation."""

    def test_contains_zle_and_bindkey(self) -> None:
        script = _generate_zsh_widget("'^E'")
        assert "zle -N _promptune_enhance" in script
        assert "bindkey '^E' _promptune_enhance" in script

    def test_contains_buffer_read_and_write(self) -> None:
        script = _generate_zsh_widget("'^E'")
        assert '$BUFFER' in script or '${BUFFER}' in script
        assert 'BUFFER="$enhanced"' in script

    def test_contains_empty_input_guard(self) -> None:
        script = _generate_zsh_widget("'^E'")
        assert '-z "$original"' in script

    def test_contains_promptune_enhance_call(self) -> None:
        script = _generate_zsh_widget("'^E'")
        assert "promptune enhance --no-tui" in script

    def test_custom_key(self) -> None:
        script = _generate_zsh_widget("'^X^E'")
        assert "bindkey '^X^E' _promptune_enhance" in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py::TestGenerateZshWidget -v`
Expected: FAIL — `_generate_zsh_widget` not importable (current name is `generate_zsh_widget`).

- [ ] **Step 3: Implement `_generate_zsh_widget()` in `shell.py`**

Replace the existing `generate_zsh_widget()` body. Keep the old function as a backward-compatible wrapper.

```python
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
    zle redisplay
}}

zle -N _promptune_enhance
bindkey {key} _promptune_enhance
"""


def generate_zsh_widget() -> str:
    """Backward-compatible wrapper. Deprecated: use generate_widget()."""
    return _generate_zsh_widget("'^E'")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py::TestGenerateZshWidget -v`
Expected: All PASS.

- [ ] **Step 5: Add backward compat equivalence test and run old tests**

Add to `tests/test_shell.py`:

```python
def test_generate_zsh_widget_backward_compat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deprecated wrapper produces same output as generate_widget('zsh', 'ctrl+e')."""
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    from promptune.shell import generate_widget, generate_zsh_widget
    assert generate_zsh_widget() == generate_widget("zsh", "ctrl+e")
```

Note: `TERM_PROGRAM` must be unset because `generate_widget()` adds a Warp warning when it detects Warp, but the deprecated `generate_zsh_widget()` wrapper calls `_generate_zsh_widget()` directly and bypasses that check.

Run: `pytest tests/test_shell.py::test_generate_zsh_widget_backward_compat tests/test_shell.py::test_shell_init_outputs_zsh_script tests/test_shell.py::test_shell_init_binds_ctrl_e tests/test_shell.py::test_shell_script_captures_buffer tests/test_shell.py::test_shell_script_calls_promptune tests/test_shell.py::test_shell_script_replaces_buffer -v`
Expected: All PASS — the old `generate_zsh_widget()` wrapper still works.

- [ ] **Step 6: Commit**

```bash
git add promptune/shell.py tests/test_shell.py
git commit -m "feat: parameterize zsh widget key, add backward-compat wrapper"
```

---

### Task 4: Bash Widget Generator — `_generate_bash_widget()`

**Files:**
- Modify: `promptune/shell.py`
- Test: `tests/test_shell.py`

- [ ] **Step 1: Write failing tests for bash widget**

Add to `tests/test_shell.py`:

```python
from promptune.shell import _generate_bash_widget


class TestGenerateBashWidget:
    """Bash readline widget generation."""

    def test_contains_bind_x(self) -> None:
        script = _generate_bash_widget('"\\C-e"')
        assert 'bind -x' in script

    def test_contains_readline_line(self) -> None:
        script = _generate_bash_widget('"\\C-e"')
        assert "READLINE_LINE" in script
        assert "READLINE_POINT" in script

    def test_contains_empty_input_guard(self) -> None:
        script = _generate_bash_widget('"\\C-e"')
        assert '-z "$READLINE_LINE"' in script

    def test_contains_promptune_enhance_call(self) -> None:
        script = _generate_bash_widget('"\\C-e"')
        assert "promptune enhance --no-tui" in script

    def test_custom_key(self) -> None:
        script = _generate_bash_widget('"\\C-x\\C-e"')
        assert '"\\C-x\\C-e"' in script

    def test_does_not_contain_zsh_syntax(self) -> None:
        script = _generate_bash_widget('"\\C-e"')
        assert "zle" not in script
        assert "bindkey" not in script
        assert "$BUFFER" not in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py::TestGenerateBashWidget -v`
Expected: FAIL — `_generate_bash_widget` does not exist.

- [ ] **Step 3: Implement `_generate_bash_widget()` in `shell.py`**

Add to `promptune/shell.py`:

```python
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
}}
bind -x '{key}: _promptune_enhance'
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py::TestGenerateBashWidget -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add promptune/shell.py tests/test_shell.py
git commit -m "feat: add bash readline widget generator"
```

---

### Task 5: Fish Widget Generator — `_generate_fish_widget()`

**Files:**
- Modify: `promptune/shell.py`
- Test: `tests/test_shell.py`

- [ ] **Step 1: Write failing tests for fish widget**

Add to `tests/test_shell.py`:

```python
from promptune.shell import _generate_fish_widget


class TestGenerateFishWidget:
    """Fish shell widget generation."""

    def test_contains_bind(self) -> None:
        script = _generate_fish_widget("\\ce")
        assert "bind \\ce _promptune_enhance" in script

    def test_contains_commandline(self) -> None:
        script = _generate_fish_widget("\\ce")
        assert "commandline" in script

    def test_uses_status_not_dollar_question(self) -> None:
        script = _generate_fish_widget("\\ce")
        assert "$status" in script
        assert "$?" not in script

    def test_contains_empty_input_guard(self) -> None:
        script = _generate_fish_widget("\\ce")
        assert 'test -z "$original"' in script

    def test_contains_promptune_enhance_call(self) -> None:
        script = _generate_fish_widget("\\ce")
        assert "promptune enhance --no-tui" in script

    def test_custom_key(self) -> None:
        script = _generate_fish_widget("\\cx \\ce")
        assert "bind \\cx \\ce _promptune_enhance" in script

    def test_does_not_contain_zsh_or_bash_syntax(self) -> None:
        script = _generate_fish_widget("\\ce")
        assert "zle" not in script
        assert "bindkey" not in script
        assert "READLINE" not in script
        assert "bind -x" not in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py::TestGenerateFishWidget -v`
Expected: FAIL — `_generate_fish_widget` does not exist.

- [ ] **Step 3: Implement `_generate_fish_widget()` in `shell.py`**

Add to `promptune/shell.py`:

```python
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
end
bind {key} _promptune_enhance
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py::TestGenerateFishWidget -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add promptune/shell.py tests/test_shell.py
git commit -m "feat: add fish shell widget generator"
```

---

## Chunk 3: Dispatcher, Warp Detection, and CLI

### Task 6: Widget Dispatcher — `generate_widget()`

**Files:**
- Modify: `promptune/shell.py`
- Test: `tests/test_shell.py`

- [ ] **Step 1: Write failing tests for dispatcher**

Add to `tests/test_shell.py`:

```python
from promptune.shell import generate_widget


class TestGenerateWidget:
    """Dispatcher routes to correct shell generator."""

    def test_dispatch_zsh(self) -> None:
        script = generate_widget("zsh", "ctrl+e")
        assert "bindkey" in script
        assert "zle" in script

    def test_dispatch_bash(self) -> None:
        script = generate_widget("bash", "ctrl+e")
        assert "bind -x" in script
        assert "READLINE_LINE" in script

    def test_dispatch_fish(self) -> None:
        script = generate_widget("fish", "ctrl+e")
        assert "commandline" in script
        assert "bind" in script

    def test_dispatch_auto_detects_shell(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SHELL", "/bin/bash")
        script = generate_widget("auto", "ctrl+e")
        assert "READLINE_LINE" in script

    def test_translates_canonical_key_for_zsh(self) -> None:
        script = generate_widget("zsh", "ctrl+e")
        assert "'^E'" in script

    def test_translates_canonical_key_for_bash(self) -> None:
        script = generate_widget("bash", "ctrl+e")
        assert "\\C-e" in script

    def test_translates_canonical_key_for_fish(self) -> None:
        script = generate_widget("fish", "ctrl+e")
        assert "\\ce" in script

    def test_unsupported_shell_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported shell"):
            generate_widget("nushell", "ctrl+e")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py::TestGenerateWidget -v`
Expected: FAIL — `generate_widget` does not exist.

- [ ] **Step 3: Implement `generate_widget()` in `shell.py`**

Add to `promptune/shell.py`:

```python
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

    return generator(translated_key)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py::TestGenerateWidget -v`
Expected: All PASS.

- [ ] **Step 5: Commit**

```bash
git add promptune/shell.py tests/test_shell.py
git commit -m "feat: add generate_widget() dispatcher with auto-detection"
```

---

### Task 7: Warp Detection

**Files:**
- Modify: `promptune/shell.py` (Warp warning in generated script)
- Modify: `promptune/cli.py` (doctor check)
- Test: `tests/test_shell.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for Warp warning in generated script**

Add to `tests/test_shell.py`:

```python
class TestWarpDetection:
    """Warp Terminal warning in generated scripts."""

    def test_warp_warning_in_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERM_PROGRAM", "WarpTerminal")
        script = generate_widget("zsh", "ctrl+e")
        assert "WARNING" in script
        assert "Warp" in script

    def test_no_warning_for_iterm(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
        script = generate_widget("zsh", "ctrl+e")
        assert "WARNING" not in script

    def test_no_warning_when_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("TERM_PROGRAM", raising=False)
        script = generate_widget("zsh", "ctrl+e")
        assert "WARNING" not in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py::TestWarpDetection -v`
Expected: FAIL — no Warp warning logic yet.

- [ ] **Step 3: Add Warp warning to `generate_widget()`**

Update `generate_widget()` in `promptune/shell.py` — add Warp detection before returning:

```python
def generate_widget(shell: str, key: str) -> str:
    """Generate shell widget script for the given shell and key."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py::TestWarpDetection -v`
Expected: All PASS.

- [ ] **Step 5: Write failing test for doctor Warp check**

Add to `tests/test_cli.py`:

```python
def test_doctor_warns_warp_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor warns when Warp Terminal is detected."""
    monkeypatch.setenv("TERM_PROGRAM", "WarpTerminal")
    # Mock checks that have side effects (config loading, network calls)
    monkeypatch.setattr("promptune.cli._check_tier1", lambda: (True, "Mocked"))
    monkeypatch.setattr("promptune.cli._check_tier2", lambda: (True, "Mocked"))
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0
    assert "Warp" in result.output


def test_doctor_ok_for_iterm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Doctor shows OK for standard terminals."""
    monkeypatch.setenv("TERM_PROGRAM", "iTerm.app")
    monkeypatch.setattr("promptune.cli._check_tier1", lambda: (True, "Mocked"))
    monkeypatch.setattr("promptune.cli._check_tier2", lambda: (True, "Mocked"))
    runner = CliRunner()
    result = runner.invoke(main, ["doctor"])
    assert "Warp" not in result.output
    assert "Shell widget compatible" in result.output
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::test_doctor_warns_warp_terminal tests/test_cli.py::test_doctor_ok_for_iterm -v`
Expected: FAIL — no Warp check in doctor yet.

- [ ] **Step 7: Add `_check_shell_widget()` to doctor in `cli.py`**

Add to `promptune/cli.py`, after the existing `_check_tier2()` function:

```python
def _check_shell_widget() -> tuple[bool, str]:
    term = os.environ.get("TERM_PROGRAM", "")
    if term == "WarpTerminal":
        return False, "Warp Terminal — Ctrl+E widget not supported (use CLI: promptune enhance)"
    return True, "Shell widget compatible"
```

Add `import os` at the top of `cli.py` (after the existing imports, before the Click commands). This is required for `os.environ.get()`.

Add to the `checks` list in `doctor_cmd()`:

```python
checks = [
    ("Python", _check_python),
    ("Config", _check_config),
    ("Tier 0", _check_tier0),
    ("Tier 1", _check_tier1),
    ("Tier 2", _check_tier2),
    ("Shell Widget", _check_shell_widget),
]
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::test_doctor_warns_warp_terminal tests/test_cli.py::test_doctor_ok_for_iterm -v`
Expected: All PASS.

- [ ] **Step 9: Commit**

```bash
git add promptune/shell.py promptune/cli.py tests/test_shell.py tests/test_cli.py
git commit -m "feat: add Warp Terminal detection in shell-init and doctor"
```

---

### Task 8: Update CLI `shell-init` Command

**Files:**
- Modify: `promptune/cli.py:336-339`
- Test: `tests/test_shell.py` (existing `test_shell_init_cli_command`)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests for updated CLI command**

Add to `tests/test_cli.py` (CLI integration tests belong in `test_cli.py` per project convention):

```python
class TestShellInitCLI:
    """CLI shell-init command with --shell and --key flags."""

    def test_default_outputs_zsh(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["shell-init"])
        assert result.exit_code == 0
        assert "bindkey" in result.output

    def test_shell_bash_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["shell-init", "--shell", "bash"])
        assert result.exit_code == 0
        assert "bind -x" in result.output
        assert "READLINE_LINE" in result.output

    def test_shell_fish_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["shell-init", "--shell", "fish"])
        assert result.exit_code == 0
        assert "commandline" in result.output

    def test_custom_key_flag(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["shell-init", "--shell", "zsh", "--key", "ctrl+x ctrl+e"]
        )
        assert result.exit_code == 0
        assert "'^X^E'" in result.output

    def test_shell_fish_with_custom_key(self) -> None:
        runner = CliRunner()
        result = runner.invoke(
            main, ["shell-init", "--shell", "fish", "--key", "alt+e"]
        )
        assert result.exit_code == 0
        assert "\\ee" in result.output
```

Ensure these imports are at the top of `tests/test_cli.py` (should already be present):

```python
from click.testing import CliRunner
from promptune.cli import main
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestShellInitCLI -v`
Expected: FAIL — `shell-init` doesn't accept `--shell` or `--key` yet.

- [ ] **Step 3: Update `shell_init()` in `cli.py`**

Replace the `shell_init` command in `promptune/cli.py:336-339`:

```python
@main.command("shell-init")
@click.option(
    "--shell",
    type=click.Choice(["auto", "zsh", "bash", "fish"]),
    default="auto",
    help="Target shell (auto-detects from $SHELL).",
)
@click.option(
    "--key",
    default="ctrl+e",
    help="Keybinding in canonical format (e.g., ctrl+e, alt+e, ctrl+x ctrl+e).",
)
def shell_init(shell: str, key: str) -> None:
    """Output shell widget script for prompt enhancement."""
    click.echo(generate_widget(shell, key))
```

Update the import at top of `cli.py` — change:

```python
from promptune.shell import generate_zsh_widget
```

to:

```python
from promptune.shell import generate_widget, generate_zsh_widget
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::TestShellInitCLI -v`
Expected: All PASS.

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/test_shell.py tests/test_cli.py -v`
Expected: All PASS including old backward-compat tests.

- [ ] **Step 6: Commit**

```bash
git add promptune/cli.py promptune/shell.py tests/test_cli.py
git commit -m "feat: add --shell and --key flags to shell-init command"
```

---

## Chunk 4: Documentation and Module Docstring Update

### Task 9: Update `shell.py` Module Docstring

**Files:**
- Modify: `promptune/shell.py:1`

- [ ] **Step 1: Update module docstring**

Change line 1 of `promptune/shell.py` from:

```python
"""Zsh shell widget: shell-init command and zle integration."""
```

to:

```python
"""Shell widget generation for zsh, bash, and fish."""
```

- [ ] **Step 2: Run full test suite to verify nothing broke**

Run: `pytest tests/test_shell.py tests/test_cli.py -v`
Expected: All PASS.

- [ ] **Step 3: Commit**

```bash
git add promptune/shell.py
git commit -m "docs: update shell.py module docstring for multi-shell support"
```

---

### Task 10: Update User Guide

**Files:**
- Modify: `docs/USER_GUIDE.md`

- [ ] **Step 1: Update shell integration section**

In `docs/USER_GUIDE.md`, replace the "Shell Integration (Zsh)" section (lines 175-199) with:

```markdown
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
```

- [ ] **Step 2: Update troubleshooting section**

Replace the "Ctrl+E doesn't work in terminal" troubleshooting entry (lines 399-408) with:

```markdown
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
```

- [ ] **Step 3: Update requirements section**

Replace line 418 (`- **Shell:** Zsh (for shell widget)`) with:

```markdown
- **Shell:** Zsh, Bash, or Fish (for shell widget)
```

- [ ] **Step 4: Commit**

```bash
git add docs/USER_GUIDE.md
git commit -m "docs: update user guide for multi-shell support and Warp limitation"
```

---

### Task 11: Final Verification

- [ ] **Step 1: Run full test suite with coverage**

Run: `ruff check . && mypy promptune/ && pytest --cov=promptune --cov-report=term-missing -v`
Expected: All checks pass, coverage ≥ 90%.

- [ ] **Step 2: Manual smoke test**

Run: `promptune shell-init` — should output zsh script (auto-detected).
Run: `promptune shell-init --shell bash` — should output bash script.
Run: `promptune shell-init --shell fish` — should output fish script.
Run: `promptune shell-init --shell zsh --key "alt+e"` — should output zsh script with Alt+E binding.
Run: `promptune doctor` — should show Shell Widget check.

- [ ] **Step 3: Final commit if any fixes needed**

Only if smoke testing reveals issues not caught by automated tests.
