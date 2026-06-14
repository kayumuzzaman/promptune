"""Claude Code hook installer.

Installs a UserPromptSubmit hook in ~/.claude/settings.json that
pipes every prompt through ``promptune gate``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
HOOK_COMMAND = "promptune gate"


def _load_settings() -> dict[str, Any]:
    """Load settings.json or return empty dict."""
    if SETTINGS_PATH.exists():
        try:
            return json.loads(SETTINGS_PATH.read_text())  # type: ignore[no-any-return]
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_settings(data: dict[str, Any]) -> None:
    """Write settings.json, creating parent dirs if needed."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_PATH.write_text(json.dumps(data, indent=2))


class ClaudeCodeInstaller:
    """Hook installer for Claude Code."""

    name = "Claude Code"

    def detect(self) -> bool:
        """Return True if ~/.claude/ directory exists."""
        return CLAUDE_DIR.exists()

    def install(self) -> None:
        """Add UserPromptSubmit hook to settings.json."""
        if self.is_installed():
            return

        data = _load_settings()
        data.setdefault("hooks", {})
        data["hooks"].setdefault("UserPromptSubmit", [])

        hook_entry = {
            "matcher": "",
            "hooks": [
                {"type": "command", "command": HOOK_COMMAND}
            ],
        }
        data["hooks"]["UserPromptSubmit"].append(hook_entry)
        _save_settings(data)

    def uninstall(self) -> None:
        """Remove promptune UserPromptSubmit hook."""
        data = _load_settings()
        entries = data.get("hooks", {}).get(
            "UserPromptSubmit", []
        )
        if not entries:
            return
        data.setdefault("hooks", {})["UserPromptSubmit"] = [
            entry
            for entry in entries
            if not any(
                HOOK_COMMAND in h.get("command", "")
                for h in entry.get("hooks", [])
            )
        ]
        _save_settings(data)

    def install_mcp(self) -> None:
        """Add promptune MCP server to settings.json."""
        if self.is_mcp_installed():
            return

        data = _load_settings()
        data.setdefault("mcpServers", {})
        data["mcpServers"]["promptune"] = {
            "command": "promptune",
            "args": ["mcp"],
        }
        _save_settings(data)

    def is_mcp_installed(self) -> bool:
        """Return True if promptune MCP server is registered."""
        data = _load_settings()
        return "promptune" in data.get("mcpServers", {})

    def is_installed(self) -> bool:
        """Return True if promptune hook is in settings.json."""
        data = _load_settings()
        entries = data.get("hooks", {}).get(
            "UserPromptSubmit", []
        )
        return any(
            HOOK_COMMAND in h.get("command", "")
            for entry in entries
            for h in entry.get("hooks", [])
        )
