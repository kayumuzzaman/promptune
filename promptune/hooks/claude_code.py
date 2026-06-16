"""Claude Code hook installer.

Installs a UserPromptSubmit hook in ~/.claude/settings.json that
pipes every prompt through ``promptune gate``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from promptune.hooks import HookConfigError

CLAUDE_DIR = Path.home() / ".claude"
SETTINGS_PATH = CLAUDE_DIR / "settings.json"
HOOK_COMMAND = "promptune gate"


def _load_settings() -> dict[str, Any]:
    """Load settings.json, or raise rather than clobber an unreadable file."""
    if not SETTINGS_PATH.exists():
        return {}
    try:
        return json.loads(SETTINGS_PATH.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError) as exc:
        raise HookConfigError(
            f"Refusing to overwrite unreadable {SETTINGS_PATH}: {exc}"
        ) from exc


def _save_settings(data: dict[str, Any]) -> None:
    """Atomically write settings.json with owner-only permissions."""
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.chmod(tmp, 0o600)
    os.replace(tmp, SETTINGS_PATH)


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
        if not isinstance(entries, list) or not entries:
            # Leave a missing or malformed (non-list) config untouched rather
            # than rewriting it into a list of dict keys.
            return
        data.setdefault("hooks", {})["UserPromptSubmit"] = [
            entry
            for entry in entries
            if not (
                isinstance(entry, dict)
                and any(
                    HOOK_COMMAND in h.get("command", "")
                    for h in (entry.get("hooks") or [])
                    if isinstance(h, dict)
                )
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
        """Return True if promptune MCP server is registered.

        Read-only status check: a corrupt settings file means "not
        installed" rather than an error, so diagnostics like
        ``promptune doctor`` don't abort.
        """
        try:
            data = _load_settings()
        except HookConfigError:
            return False
        return "promptune" in data.get("mcpServers", {})

    def is_installed(self) -> bool:
        """Return True if promptune hook is in settings.json.

        Tolerates a corrupt settings file (treated as not installed) so
        read-only status checks don't abort; write paths still refuse to
        clobber an unreadable file.
        """
        try:
            data = _load_settings()
        except HookConfigError:
            return False
        entries = data.get("hooks", {}).get(
            "UserPromptSubmit", []
        )
        return any(
            HOOK_COMMAND in h.get("command", "")
            for entry in entries
            if isinstance(entry, dict)
            for h in (entry.get("hooks") or [])
            if isinstance(h, dict)
        )
