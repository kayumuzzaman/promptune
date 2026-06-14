"""macOS platform backend — adapter over existing daemon modules.

Wraps hotkey.py, clipboard.py, notify.py, and launchagent.py behind
the abstract interfaces defined in base.py.  No behaviour change.
"""

from __future__ import annotations

import sys
from typing import Callable

if sys.platform != "darwin":
    raise ImportError("promptune.daemon.platform.macos requires macOS.")

from promptune.daemon import clipboard as clip_mod
from promptune.daemon import hotkey as hotkey_mod
from promptune.daemon import launchagent as la_mod
from promptune.daemon import notify as notify_mod
from promptune.daemon.platform.base import (
    ActiveWindowBackend,
    ClipboardBackend,
    HotkeyBackend,
    NotifyBackend,
    ServiceBackend,
)


class MacOSHotkey(HotkeyBackend):
    """macOS global hotkey via CGEventTap."""

    def __init__(self) -> None:
        self._callback: Callable[[], None] | None = None

    def register(self, combo: str, callback: Callable[[], None]) -> None:
        keycode, modifier_mask = hotkey_mod.parse_hotkey(combo)
        self._callback = callback
        hotkey_mod.register_hotkey(callback, keycode, modifier_mask)

    def check_conflict(self, combo: str) -> bool:
        return False

    def listen(self) -> None:
        hotkey_mod.start_run_loop()

    def stop(self) -> None:
        hotkey_mod.stop_run_loop()


class MacOSClipboard(ClipboardBackend):
    """macOS clipboard via pbcopy/pbpaste and CGEvent key simulation."""

    def read(self) -> str | None:
        return clip_mod.save_clipboard()

    def write(self, text: str) -> None:
        clip_mod.write_clipboard(text)

    def copy_selection(self) -> str | None:
        return clip_mod.copy_selection()

    def paste_result(self, text: str) -> None:
        clip_mod.paste_result(text)


class MacOSNotify(NotifyBackend):
    """macOS notifications via osascript."""

    def send(self, title: str, body: str, sound: bool = True) -> None:
        notify_mod.notify(title, body, sound=sound)


class MacOSService(ServiceBackend):
    """macOS LaunchAgent service management."""

    def install(self) -> None:
        la_mod.install_login_item()

    def uninstall(self) -> None:
        la_mod.uninstall_login_item()

    def purge(self) -> None:
        la_mod.uninstall_login_item()

    def is_installed(self) -> bool:
        return la_mod.is_installed()


class MacOSActiveWindow(ActiveWindowBackend):
    """macOS frontmost app detection via NSWorkspace."""

    def get_frontmost_app(self) -> str:
        return clip_mod.get_frontmost_app()
