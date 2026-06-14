"""Platform abstraction layer for the promptune daemon.

Provides runtime detection and backend selection for macOS, Linux X11,
and Linux Wayland.  Import ``get_platform()`` to get the current
platform's backend bundle.
"""

from __future__ import annotations

import os
import sys

from promptune.daemon.platform.base import PlatformBackend


class PlatformError(Exception):
    """Raised when the platform cannot support the daemon."""


def detect_session_type() -> str:
    """Detect whether the Linux session is X11 or Wayland.

    Checks ``$XDG_SESSION_TYPE`` first, then falls back to
    ``$WAYLAND_DISPLAY`` and ``$DISPLAY`` presence.

    Raises:
        PlatformError: If no display server can be detected.
    """
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session in ("wayland", "x11"):
        return session

    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"

    raise PlatformError(
        "No display server detected. Set $XDG_SESSION_TYPE or "
        "ensure $DISPLAY / $WAYLAND_DISPLAY is set. "
        "Use CLI mode instead: promptune enhance"
    )


def is_wsl() -> bool:
    """Detect Windows Subsystem for Linux via /proc/version."""
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except (FileNotFoundError, PermissionError):
        return False


def get_platform() -> PlatformBackend:
    """Detect the current platform and return the appropriate backend bundle.

    Returns:
        A :class:`PlatformBackend` with all backends configured for the
        current platform and display server.

    Raises:
        PlatformError: If the platform is unsupported or the daemon
            cannot run (WSL, no display, etc.).
    """
    if sys.platform == "darwin":
        from promptune.daemon.platform.macos import (
            MacOSActiveWindow,
            MacOSClipboard,
            MacOSHotkey,
            MacOSNotify,
            MacOSService,
        )

        return PlatformBackend(
            hotkey=MacOSHotkey(),
            clipboard=MacOSClipboard(),
            notify=MacOSNotify(),
            service=MacOSService(),
            active_window=MacOSActiveWindow(),
        )

    if sys.platform == "linux":
        if is_wsl():
            raise PlatformError(
                "WSL detected. The daemon is not supported under WSL. "
                "Use CLI mode instead: promptune enhance"
            )

        # TODO(linux-ci): Docker/container environments also lack a display.
        # detect_session_type() raises PlatformError when $DISPLAY and
        # $WAYLAND_DISPLAY are both unset — this covers the container case
        # implicitly. On a Linux CI machine, add an integration test that:
        #   1. Unsets DISPLAY, WAYLAND_DISPLAY, XDG_SESSION_TYPE
        #   2. Calls get_platform() and asserts PlatformError is raised
        # See tests/test_daemon/test_platform/test_platform_integration.py

        session = detect_session_type()

        from promptune.daemon.platform.linux_service import LinuxService

        if session == "x11":
            from promptune.daemon.platform.linux_x11 import (
                X11ActiveWindow,
                X11Clipboard,
                X11Hotkey,
                X11Notify,
            )

            return PlatformBackend(
                hotkey=X11Hotkey(),
                clipboard=X11Clipboard(),
                notify=X11Notify(),
                service=LinuxService(),
                active_window=X11ActiveWindow(),
            )

        # Wayland
        from promptune.daemon.platform.linux_wayland import (
            WaylandActiveWindow,
            WaylandClipboard,
            WaylandHotkey,
            WaylandNotify,
        )

        return PlatformBackend(
            hotkey=WaylandHotkey(),
            clipboard=WaylandClipboard(),
            notify=WaylandNotify(),
            service=LinuxService(),
            active_window=WaylandActiveWindow(),
        )

    raise PlatformError(
        f"Unsupported platform: {sys.platform}. "
        "The daemon requires macOS or Linux."
    )
