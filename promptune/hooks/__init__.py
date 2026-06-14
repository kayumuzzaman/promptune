"""Hook detection and installer registry for AI coding tools."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HookInstaller(Protocol):
    """Protocol for tool-specific hook installers."""

    name: str

    def detect(self) -> bool:
        """Return True if the tool is installed on this machine."""
        ...

    def install(self) -> None:
        """Install the promptune gate hook into the tool's config."""
        ...

    def uninstall(self) -> None:
        """Remove the promptune gate hook from the tool's config."""
        ...

    def is_installed(self) -> bool:
        """Return True if the hook is currently installed."""
        ...


def get_installers() -> list[HookInstaller]:
    """Return all known hook installers."""
    from promptune.hooks.claude_code import ClaudeCodeInstaller
    from promptune.hooks.codex import CodexInstaller

    return [ClaudeCodeInstaller(), CodexInstaller()]


def detect_tools() -> list[HookInstaller]:
    """Return installers for tools detected on this machine."""
    return [i for i in get_installers() if i.detect()]
