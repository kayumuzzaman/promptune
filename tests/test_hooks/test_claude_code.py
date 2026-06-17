"""Tests for Claude Code hook installer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptune.hooks import (
    HookConfigError,
    detect_tools,
    get_installers,
)
from promptune.hooks.claude_code import (
    HOOK_COMMAND,
    ClaudeCodeInstaller,
)


class TestClaudeCodeDetect:
    """Detection of Claude Code installation."""

    def test_detects_when_claude_dir_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        monkeypatch.setattr(
            "promptune.hooks.claude_code.CLAUDE_DIR",
            claude_dir,
        )
        installer = ClaudeCodeInstaller()
        assert installer.detect() is True

    def test_not_detected_when_no_claude_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "promptune.hooks.claude_code.CLAUDE_DIR",
            tmp_path / ".claude_nonexistent",
        )
        installer = ClaudeCodeInstaller()
        assert installer.detect() is False


class TestClaudeCodeInstall:
    """Hook install/uninstall in settings.json."""

    def test_install_creates_settings_with_hook(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install()
        assert settings_path.exists()
        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["UserPromptSubmit"]
        commands = [
            h["command"]
            for entry in hooks
            for h in entry["hooks"]
        ]
        assert any(HOOK_COMMAND in cmd for cmd in commands)

    def test_install_merges_with_existing_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps({"theme": "dark", "hooks": {}})
        )
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install()
        data = json.loads(settings_path.read_text())
        assert data["theme"] == "dark"
        assert "UserPromptSubmit" in data["hooks"]

    def test_is_installed_tolerates_non_dict_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps(
                {"hooks": {"UserPromptSubmit": ["shorthand", {"foo": 1}]}}
            )
        )
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        # Must not raise AttributeError on the bare-string entry.
        assert installer.is_installed() is False

    def test_install_with_str_hooks_raises_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps({"theme": "dark", "hooks": "nope"})
        )
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH", settings_path
        )
        installer = ClaudeCodeInstaller()
        with pytest.raises(HookConfigError):
            installer.install()
        # Unrelated settings preserved (file not clobbered).
        data = json.loads(settings_path.read_text())
        assert data["theme"] == "dark"
        assert data["hooks"] == "nope"

    def test_install_with_str_userpromptsubmit_raises_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps(
                {"theme": "dark", "hooks": {"UserPromptSubmit": "existing"}}
            )
        )
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH", settings_path
        )
        installer = ClaudeCodeInstaller()
        with pytest.raises(HookConfigError):
            installer.install()
        data = json.loads(settings_path.read_text())
        assert data["theme"] == "dark"

    def test_is_installed_tolerates_corrupt_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read-only status check returns False on corrupt JSON, not raises.

        ``promptune doctor`` calls is_installed(); a broken settings file must
        report "not installed" instead of aborting the diagnostic.
        """
        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{ not valid json")
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        assert installer.is_installed() is False
        assert installer.is_mcp_installed() is False

    def test_is_installed_tolerates_null_hooks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(
            json.dumps(
                {"hooks": {"UserPromptSubmit": [{"matcher": "", "hooks": None}]}}
            )
        )
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        # "hooks": null must not raise TypeError.
        assert installer.is_installed() is False

    def test_install_refuses_to_clobber_corrupt_settings(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from promptune.hooks import HookConfigError

        settings_path = tmp_path / "settings.json"
        settings_path.write_text("{ not valid json ")
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        with pytest.raises(HookConfigError):
            installer.install()
        # Original (corrupt) file is left untouched, not overwritten.
        assert settings_path.read_text() == "{ not valid json "

    def test_is_installed_returns_true_after_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        assert installer.is_installed() is False
        installer.install()
        assert installer.is_installed() is True

    def test_uninstall_removes_hook(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install()
        assert installer.is_installed() is True
        installer.uninstall()
        assert installer.is_installed() is False

    def test_uninstall_no_hooks_key_does_not_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"theme": "dark"}))
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.uninstall()  # should not raise

    def test_uninstall_leaves_malformed_dict_config_untouched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dict-shaped UserPromptSubmit must not be rewritten into a list."""
        settings_path = tmp_path / "settings.json"
        original = {"hooks": {"UserPromptSubmit": {"matcher": "", "hooks": []}}}
        settings_path.write_text(json.dumps(original))
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.uninstall()
        assert json.loads(settings_path.read_text()) == original

    def test_uninstall_tolerates_non_dict_hooks_block(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-dict 'hooks' value must not crash uninstall."""
        settings_path = tmp_path / "settings.json"
        original = {"hooks": "garbage"}
        settings_path.write_text(json.dumps(original))
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.uninstall()
        assert json.loads(settings_path.read_text()) == original

    def test_install_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install()
        installer.install()
        data = json.loads(settings_path.read_text())
        hooks = data["hooks"]["UserPromptSubmit"]
        commands = [
            h["command"]
            for entry in hooks
            for h in entry["hooks"]
        ]
        matching = [
            cmd for cmd in commands if HOOK_COMMAND in cmd
        ]
        assert len(matching) == 1


class TestClaudeCodeMcpRegistration:
    """MCP server registration in settings.json."""

    def test_install_mcp_adds_server_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install_mcp()
        data = json.loads(settings_path.read_text())
        assert "promptune" in data.get("mcpServers", {})
        server = data["mcpServers"]["promptune"]
        assert server["command"] == "promptune"
        assert server["args"] == ["mcp"]

    def test_install_mcp_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install_mcp()
        installer.install_mcp()
        data = json.loads(settings_path.read_text())
        assert "promptune" in data["mcpServers"]

    @pytest.mark.parametrize("bad", [[], "x", 5, True])
    def test_install_mcp_rejects_non_dict_mcpservers(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        bad: object,
    ) -> None:
        """A corrupt non-dict mcpServers block raises rather than crashing.

        Covers iterable (``[]``, ``"x"``) and non-iterable scalar (``5``,
        ``True``) values; the scalar path used to crash in is_mcp_installed.
        """
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"mcpServers": bad}))
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        with pytest.raises(HookConfigError):
            installer.install_mcp()

    def test_is_mcp_installed_false_on_non_dict_mcpservers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Scalar mcpServers reports 'not installed', not a TypeError."""
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({"mcpServers": 5}))
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        assert installer.is_mcp_installed() is False

    def test_is_mcp_installed_returns_correct_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        assert installer.is_mcp_installed() is False
        installer.install_mcp()
        assert installer.is_mcp_installed() is True

    def test_install_mcp_merges_with_existing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        settings_path = tmp_path / "settings.json"
        settings_path.write_text(json.dumps({
            "mcpServers": {"other": {"command": "other-tool"}},
        }))
        monkeypatch.setattr(
            "promptune.hooks.claude_code.SETTINGS_PATH",
            settings_path,
        )
        installer = ClaudeCodeInstaller()
        installer.install_mcp()
        data = json.loads(settings_path.read_text())
        assert "other" in data["mcpServers"]
        assert "promptune" in data["mcpServers"]


class TestGetInstallers:
    """Installer registry."""

    def test_get_installers_returns_list(self) -> None:
        installers = get_installers()
        assert isinstance(installers, list)
        assert len(installers) >= 1

    def test_installer_has_name(self) -> None:
        for installer in get_installers():
            assert hasattr(installer, "name")
            assert isinstance(installer.name, str)

    def test_detect_tools_returns_only_detected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "promptune.hooks.claude_code.CLAUDE_DIR",
            tmp_path / ".claude_nonexistent",
        )
        found = detect_tools()
        names = [i.name for i in found]
        assert "Claude Code" not in names
