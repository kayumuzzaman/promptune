"""Abstract base classes for platform-specific daemon backends.

Each backend interface defines the contract that macOS and Linux
implementations must fulfil.  The PlatformBackend dataclass bundles
all backends into a single object returned by the factory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


@dataclass
class DependencyStatus:
    """Status of a single system dependency."""

    name: str
    installed: bool
    required: bool


class HotkeyBackend(ABC):
    """Global hotkey registration and event loop."""

    @abstractmethod
    def register(self, combo: str, callback: Callable[[], None]) -> None:
        """Register *combo* to fire *callback*."""

    @abstractmethod
    def check_conflict(self, combo: str) -> bool:
        """Return True if *combo* is already taken."""

    @abstractmethod
    def listen(self) -> None:
        """Block on the platform event loop until stop() is called."""

    @abstractmethod
    def stop(self) -> None:
        """Signal the event loop to exit."""


class ClipboardBackend(ABC):
    """Clipboard read/write and key-simulation helpers."""

    @abstractmethod
    def read(self) -> str | None:
        """Read the current clipboard text."""

    @abstractmethod
    def write(self, text: str) -> None:
        """Write *text* to the clipboard."""

    @abstractmethod
    def copy_selection(self) -> str | None:
        """Simulate a copy keystroke and return the clipboard text."""

    @abstractmethod
    def paste_result(self, text: str) -> None:
        """Write *text* to the clipboard and simulate a paste keystroke."""


class NotifyBackend(ABC):
    """Desktop notifications."""

    @abstractmethod
    def send(self, title: str, body: str, sound: bool = True) -> None:
        """Display a desktop notification."""


class ServiceBackend(ABC):
    """Daemon service installation and management."""

    @abstractmethod
    def install(self) -> None:
        """Install the daemon as an auto-start service."""

    @abstractmethod
    def uninstall(self) -> None:
        """Remove the daemon auto-start service."""

    @abstractmethod
    def purge(self) -> None:
        """Remove all daemon files."""

    @abstractmethod
    def is_installed(self) -> bool:
        """Return True if the daemon service is installed."""


class ActiveWindowBackend(ABC):
    """Frontmost application detection."""

    @abstractmethod
    def get_frontmost_app(self) -> str:
        """Return an identifier for the currently focused application."""


class DependencyChecker(ABC):
    """System dependency verification."""

    @abstractmethod
    def check(self) -> list[DependencyStatus]:
        """Check all required system dependencies."""

    @abstractmethod
    def get_install_command(self, missing: list[str]) -> str:
        """Return a shell command to install missing packages."""


@dataclass
class PlatformBackend:
    """Bundle of all platform-specific backends."""

    hotkey: HotkeyBackend
    clipboard: ClipboardBackend
    notify: NotifyBackend
    service: ServiceBackend
    active_window: ActiveWindowBackend
