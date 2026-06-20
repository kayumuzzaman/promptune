"""Step 9: Shell Integration — tests."""

import pytest
from click.testing import CliRunner

from promptune.cli import main
from promptune.shell import (
    _generate_bash_widget,
    _generate_fish_widget,
    _generate_zsh_widget,
    _translate_key,
    detect_shell,
    generate_widget,
    generate_zsh_widget,
)


def test_shell_init_outputs_zsh_script() -> None:
    """Output contains zsh function."""
    script = generate_zsh_widget()
    assert "function" in script or "()" in script
    assert "zle" in script


def test_shell_init_binds_ctrl_e() -> None:
    """Output contains bindkey for Ctrl+E."""
    script = generate_zsh_widget()
    assert "bindkey" in script
    assert r"\C-e" in script or "\\^E" in script or "'^E'" in script


def test_shell_script_captures_buffer() -> None:
    """Zsh function reads $BUFFER."""
    script = generate_zsh_widget()
    assert "$BUFFER" in script or "${BUFFER}" in script


def test_shell_script_calls_promptune() -> None:
    """Function invokes promptune enhance."""
    script = generate_zsh_widget()
    assert "promptune enhance" in script or "promptune" in script


def test_shell_script_replaces_buffer() -> None:
    """Function sets BUFFER= with result."""
    script = generate_zsh_widget()
    assert "BUFFER=" in script


def test_shell_init_cli_command() -> None:
    """'promptune shell-init' exits 0."""
    runner = CliRunner()
    # Pin $SHELL so detection is deterministic across CI platforms.
    result = runner.invoke(main, ["shell-init"], env={"SHELL": "/bin/zsh"})
    assert result.exit_code == 0
    assert "bindkey" in result.output


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

    def test_unsupported_modifier_raises(self) -> None:
        import pytest

        for combo in ("shift+e", "super+e", "cmd+e"):
            with pytest.raises(ValueError, match="Unsupported"):
                _translate_key(combo, "zsh")

    def test_raw_passthrough_with_shell_metachars_rejected(self) -> None:
        import pytest

        # A crafted raw key must not be able to break out of the generated
        # quoted bind line and inject shell commands.
        with pytest.raises(ValueError):
            _translate_key("'; rm -rf X; '", "bash")

    def test_empty_char_after_modifier_rejected(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            _translate_key("ctrl+", "zsh")

    def test_multichar_after_modifier_rejected(self) -> None:
        import pytest

        with pytest.raises(ValueError):
            _translate_key("ctrl+abc", "zsh")

    def test_punctuation_char_after_modifier_allowed(self) -> None:
        # Legit combos like ctrl+/ or ctrl+- must still work.
        assert _translate_key("ctrl+/", "zsh") == "'^/'"
        assert _translate_key("ctrl+-", "zsh") == "'^-'"

    def test_metacharacter_char_after_modifier_rejected(self) -> None:
        import pytest

        for bad in ("ctrl+;", "ctrl+$", "alt+`"):
            with pytest.raises(ValueError):
                _translate_key(bad, "zsh")



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

    @pytest.mark.parametrize("raw_key", ["^E && touch /tmp/pwned", "^E | cat"])
    def test_raw_key_rejects_shell_control_operators(
        self, raw_key: str
    ) -> None:
        with pytest.raises(ValueError, match="Unsafe raw key"):
            generate_widget("zsh", raw_key)


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


def test_generate_zsh_widget_backward_compat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deprecated wrapper produces same output as generate_widget('zsh', 'ctrl+e')."""
    monkeypatch.delenv("TERM_PROGRAM", raising=False)
    assert generate_zsh_widget() == generate_widget("zsh", "ctrl+e")


# ── IPC CWD reporting tests ─────────────────────────────────────


class TestIPCReporting:
    """Test that shell widgets include daemon IPC CWD reporting."""

    def test_zsh_widget_includes_ipc(self) -> None:
        script = _generate_zsh_widget("'^E'")
        assert "report-cwd" in script
        assert "daemon report-cwd" in script

    def test_bash_widget_includes_ipc(self) -> None:
        script = _generate_bash_widget('"\\C-e"')
        assert "report-cwd" in script
        assert "daemon report-cwd" in script

    def test_fish_widget_includes_ipc(self) -> None:
        script = _generate_fish_widget("\\ce")
        assert "report-cwd" in script
        assert "daemon report-cwd" in script

    def test_ipc_socket_path_uses_home_not_tilde(self) -> None:
        """IPC helper must not rely on an unexpanded literal tilde path."""
        for gen, key in [
            (_generate_zsh_widget, "'^E'"),
            (_generate_bash_widget, '"\\C-e"'),
            (_generate_fish_widget, "\\ce"),
        ]:
            script = gen(key)
            assert "UNIX-CONNECT:~" not in script
            assert "~/.local/share/promptune" not in script

    def test_ipc_is_nonblocking(self) -> None:
        """IPC line runs in background (&) and discards both stdout/stderr.

        stdout must be discarded too: the daemon acks ``report_cwd`` over the
        socket, and ``socat -`` would otherwise print that ack into the
        user's prompt.
        """
        for gen, key in [
            (_generate_zsh_widget, "'^E'"),
            (_generate_bash_widget, '"\\C-e"'),
            (_generate_fish_widget, "\\ce"),
        ]:
            script = gen(key)
            assert ">/dev/null 2>&1 &" in script

    def test_ipc_payload_is_not_raw_echoed_json(self) -> None:
        """CWD reporting must escape cwd/project_root as JSON, not raw echo."""
        for gen, key in [
            (_generate_zsh_widget, "'^E'"),
            (_generate_bash_widget, '"\\C-e"'),
            (_generate_fish_widget, "\\ce"),
        ]:
            script = gen(key)
            assert "echo '{\"action\":\"report_cwd\"" not in script
            assert "daemon report-cwd" in script
