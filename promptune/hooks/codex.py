"""Codex CLI hook installer.

Installs a UserPromptSubmit hook in ~/.codex/hooks.json that
pipes every prompt through ``promptune gate``. The hooks.json schema
matches Claude Code's settings.json "hooks" block, so the same gate
payload (which includes a ``prompt`` field) works unchanged.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from promptune.hooks import HookConfigError

CODEX_DIR = Path.home() / ".codex"
HOOKS_PATH = CODEX_DIR / "hooks.json"
HOOK_COMMAND = "promptune gate"


def _load_hooks() -> dict[str, Any]:
    """Load hooks.json, or raise rather than clobber an unreadable file."""
    if not HOOKS_PATH.exists():
        return {}
    try:
        return json.loads(HOOKS_PATH.read_text())  # type: ignore[no-any-return]
    except (json.JSONDecodeError, OSError) as exc:
        raise HookConfigError(
            f"Refusing to overwrite unreadable {HOOKS_PATH}: {exc}"
        ) from exc


def _save_hooks(data: dict[str, Any]) -> None:
    """Atomically write hooks.json with owner-only permissions."""
    HOOKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = HOOKS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.chmod(tmp, 0o600)
    os.replace(tmp, HOOKS_PATH)


class CodexInstaller:
    """Hook installer for the Codex CLI."""

    name = "Codex"

    def detect(self) -> bool:
        """Return True if ~/.codex/ directory exists."""
        return CODEX_DIR.exists()

    def install(self) -> None:
        """Add UserPromptSubmit hook to hooks.json."""
        if self.is_installed():
            return

        data = _load_hooks()
        data.setdefault("hooks", {})
        data["hooks"].setdefault("UserPromptSubmit", [])

        hook_entry = {
            "matcher": "",
            "hooks": [
                {"type": "command", "command": HOOK_COMMAND}
            ],
        }
        data["hooks"]["UserPromptSubmit"].append(hook_entry)
        _save_hooks(data)

    def uninstall(self) -> None:
        """Remove promptune UserPromptSubmit hook."""
        data = _load_hooks()
        entries = data.get("hooks", {}).get(
            "UserPromptSubmit", []
        )
        if not entries:
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
        _save_hooks(data)

    def is_installed(self) -> bool:
        """Return True if promptune hook is in hooks.json."""
        data = _load_hooks()
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
