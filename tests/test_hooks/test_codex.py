"""Tests for Codex CLI hook installer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptune.hooks import (
    HookConfigError,
    detect_tools,
    get_installers,
)
from promptune.hooks.codex import (
    HOOK_COMMAND,
    CodexInstaller,
)


class TestCodexDetect:
    """Detection of Codex CLI installation."""

    def test_detects_when_codex_dir_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        monkeypatch.setattr(
            "promptune.hooks.codex.CODEX_DIR",
            codex_dir,
        )
        installer = CodexInstaller()
        assert installer.detect() is True

    def test_not_detected_when_no_codex_dir(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "promptune.hooks.codex.CODEX_DIR",
            tmp_path / ".codex_nonexistent",
        )
        installer = CodexInstaller()
        assert installer.detect() is False


class TestCodexInstall:
    """Hook install/uninstall in hooks.json."""

    def test_install_creates_hooks_file_with_hook(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hooks_path = tmp_path / "hooks.json"
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH",
            hooks_path,
        )
        installer = CodexInstaller()
        installer.install()
        assert hooks_path.exists()
        data = json.loads(hooks_path.read_text())
        hooks = data["hooks"]["UserPromptSubmit"]
        commands = [
            h["command"]
            for entry in hooks
            for h in entry["hooks"]
        ]
        assert any(HOOK_COMMAND in cmd for cmd in commands)

    def test_install_merges_with_existing_hooks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hooks_path = tmp_path / "hooks.json"
        hooks_path.write_text(
            json.dumps(
                {
                    "hooks": {
                        "PreToolUse": [
                            {
                                "matcher": "Bash",
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": "other-tool check",
                                    }
                                ],
                            }
                        ]
                    }
                }
            )
        )
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH",
            hooks_path,
        )
        installer = CodexInstaller()
        installer.install()
        data = json.loads(hooks_path.read_text())
        # Pre-existing PreToolUse entry preserved.
        assert "PreToolUse" in data["hooks"]
        pre = data["hooks"]["PreToolUse"][0]["hooks"][0]
        assert pre["command"] == "other-tool check"
        # promptune hook added.
        assert "UserPromptSubmit" in data["hooks"]

    def test_is_installed_returns_true_after_install(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hooks_path = tmp_path / "hooks.json"
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH",
            hooks_path,
        )
        installer = CodexInstaller()
        assert installer.is_installed() is False
        installer.install()
        assert installer.is_installed() is True

    def test_uninstall_removes_hook(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hooks_path = tmp_path / "hooks.json"
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH",
            hooks_path,
        )
        installer = CodexInstaller()
        installer.install()
        assert installer.is_installed() is True
        installer.uninstall()
        assert installer.is_installed() is False

    def test_uninstall_no_hooks_key_does_not_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hooks_path = tmp_path / "hooks.json"
        hooks_path.write_text(json.dumps({"other": "value"}))
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH",
            hooks_path,
        )
        installer = CodexInstaller()
        installer.uninstall()  # should not raise

    def test_is_installed_tolerates_corrupt_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Read-only status check returns False on corrupt JSON, not raises."""
        hooks_path = tmp_path / "hooks.json"
        hooks_path.write_text("{ broken json")
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH",
            hooks_path,
        )
        installer = CodexInstaller()
        assert installer.is_installed() is False

    def test_install_with_str_hooks_raises_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hooks_path = tmp_path / "hooks.json"
        hooks_path.write_text(
            json.dumps({"theme": "dark", "hooks": "nope"})
        )
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH", hooks_path
        )
        installer = CodexInstaller()
        with pytest.raises(HookConfigError):
            installer.install()
        data = json.loads(hooks_path.read_text())
        assert data["theme"] == "dark"
        assert data["hooks"] == "nope"

    def test_install_with_str_userpromptsubmit_raises_config_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hooks_path = tmp_path / "hooks.json"
        hooks_path.write_text(
            json.dumps(
                {"theme": "dark", "hooks": {"UserPromptSubmit": "existing"}}
            )
        )
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH", hooks_path
        )
        installer = CodexInstaller()
        with pytest.raises(HookConfigError):
            installer.install()
        data = json.loads(hooks_path.read_text())
        assert data["theme"] == "dark"

    def test_uninstall_leaves_malformed_dict_config_untouched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A dict-shaped UserPromptSubmit must not be rewritten into a list."""
        hooks_path = tmp_path / "hooks.json"
        original = {"hooks": {"UserPromptSubmit": {"matcher": "", "hooks": []}}}
        hooks_path.write_text(json.dumps(original))
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH",
            hooks_path,
        )
        installer = CodexInstaller()
        installer.uninstall()
        assert json.loads(hooks_path.read_text()) == original

    def test_install_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hooks_path = tmp_path / "hooks.json"
        monkeypatch.setattr(
            "promptune.hooks.codex.HOOKS_PATH",
            hooks_path,
        )
        installer = CodexInstaller()
        installer.install()
        installer.install()
        data = json.loads(hooks_path.read_text())
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


class TestGetInstallers:
    """Codex is registered in the installer registry."""

    def test_get_installers_includes_codex(self) -> None:
        names = [i.name for i in get_installers()]
        assert "Codex" in names

    def test_detect_tools_excludes_codex_when_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "promptune.hooks.codex.CODEX_DIR",
            tmp_path / ".codex_nonexistent",
        )
        monkeypatch.setattr(
            "promptune.hooks.claude_code.CLAUDE_DIR",
            tmp_path / ".claude_nonexistent",
        )
        found = detect_tools()
        names = [i.name for i in found]
        assert "Codex" not in names
