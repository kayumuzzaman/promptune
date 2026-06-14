"""Linux Wayland platform backend.

Hotkey: xdg-desktop-portal GlobalShortcuts (dbus-next) with evdev fallback.
Clipboard: wl-paste / wl-copy.
Key simulation: ydotool.
Active window: GNOME Shell DBus / KDE KWin / sway IPC.
Notifications: notify-send.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from typing import Callable

from promptune.daemon.platform.base import (
    ActiveWindowBackend,
    ClipboardBackend,
    HotkeyBackend,
    NotifyBackend,
)

_log = logging.getLogger(__name__)


class WaylandHotkey(HotkeyBackend):
    """Wayland hotkey via portal GlobalShortcuts, with evdev fallback."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._callback: Callable[[], None] | None = None
        self._combo = ""

    def register(self, combo: str, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._combo = combo

    def check_conflict(self, combo: str) -> bool:
        return False

    def listen(self) -> None:
        try:
            self._listen_portal()
        except Exception:
            _log.info("Portal GlobalShortcuts unavailable, falling back to evdev")
            try:
                self._listen_evdev()
            except Exception:
                _log.error("Both portal and evdev hotkey failed", exc_info=True)

    def _listen_portal(self) -> None:
        # TODO(linux-ci): Integration test requires a running xdg-desktop-portal
        # with GlobalShortcuts support (GNOME ≥ 42, KDE Plasma ≥ 5.27, or niri).
        # On a real Wayland machine:
        #   1. Ensure DBUS_SESSION_BUS_ADDRESS is set
        #   2. Mock portal signals or use a test portal stub
        #   3. Send a synthetic D-Bus Activated signal and assert callback fires
        # See tests/test_daemon/test_platform/test_linux_wayland_integration.py
        import asyncio

        from dbus_next.aio import MessageBus  # type: ignore[import]

        async def _portal_loop() -> None:
            bus = await MessageBus().connect()
            introspection = await bus.introspect(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
            )
            proxy = bus.get_proxy_object(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                introspection,
            )
            shortcuts = proxy.get_interface(
                "org.freedesktop.portal.GlobalShortcuts"
            )
            result = await shortcuts.call_create_session({})
            session_handle = result
            await shortcuts.call_bind_shortcuts(
                session_handle,
                [("promptune-enhance", {"description": "Enhance prompt"})],
                "",
                {},
            )

            def on_activated(
                session: str, shortcut_id: str, timestamp: int, options: dict
            ) -> None:
                if self._callback:
                    self._callback()

            shortcuts.on_activated(on_activated)

            while not self._stop_event.is_set():
                await asyncio.sleep(0.1)

            bus.disconnect()

        asyncio.run(_portal_loop())

    def _listen_evdev(self) -> None:
        # TODO(linux-ci): Integration test requires the 'input' group membership
        # and physical keyboard devices under /dev/input/. On a real Linux machine:
        #   1. Add CI user to 'input' group: sudo usermod -aG input $USER
        #   2. Use uinput to create a virtual keyboard (requires uinput module)
        #   3. Inject a key event and assert the callback fires
        # Note: evdev is the fallback when portal GlobalShortcuts is unavailable
        # (e.g., on sway/i3 without a portal implementation).
        # See tests/test_daemon/test_platform/test_linux_wayland_integration.py
        from evdev import (  # type: ignore[import]
            InputDevice,
            categorize,
            ecodes,
            list_devices,
        )

        _log.warning("Using evdev hotkey listener — requires 'input' group membership")
        devices = [InputDevice(path) for path in list_devices()]
        keyboards = [d for d in devices if ecodes.EV_KEY in d.capabilities()]

        if not keyboards:
            raise RuntimeError("No keyboard input devices found")

        combo_parts = [p.strip().lower() for p in self._combo.split("+")]
        evdev_keys = {
            "ctrl": ecodes.KEY_LEFTCTRL,
            "shift": ecodes.KEY_LEFTSHIFT,
            "alt": ecodes.KEY_LEFTALT,
            "super": ecodes.KEY_LEFTMETA,
        }
        mod_keys = set()
        main_key = None
        for part in combo_parts:
            if part in evdev_keys:
                mod_keys.add(evdev_keys[part])
            else:
                key_attr = f"KEY_{part.upper()}"
                main_key = getattr(ecodes, key_attr, None)

        if main_key is None:
            raise ValueError(f"Cannot map key from combo: {self._combo}")

        pressed: set[int] = set()
        import select

        while not self._stop_event.is_set():
            readable, _, _ = select.select(keyboards, [], [], 0.1)
            for dev in readable:
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    key_event = categorize(event)
                    if key_event.keystate == key_event.key_down:
                        pressed.add(key_event.scancode)
                    elif key_event.keystate == key_event.key_up:
                        pressed.discard(key_event.scancode)
                    if (
                        main_key in pressed
                        and mod_keys.issubset(pressed)
                        and self._callback
                    ):
                        self._callback()
                        pressed.clear()

    def stop(self) -> None:
        self._stop_event.set()


class WaylandClipboard(ClipboardBackend):
    """Wayland clipboard via wl-paste / wl-copy + ydotool."""

    def __init__(self, settle_ms: int = 100) -> None:
        self._settle_ms = settle_ms

    def read(self) -> str | None:
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.replace("\x00", "")
        except Exception:
            return None

    def write(self, text: str) -> None:
        subprocess.run(
            ["wl-copy"],
            input=text,
            text=True,
            check=True,
        )

    def copy_selection(self) -> str | None:
        subprocess.run(
            ["ydotool", "key", "29:1", "46:1", "46:0", "29:0"],
            check=True,
        )
        time.sleep(self._settle_ms / 1000.0)
        return self.read()

    def paste_result(self, text: str) -> None:
        self.write(text)
        time.sleep(self._settle_ms / 1000.0)
        subprocess.run(
            ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
            check=True,
        )


class WaylandNotify(NotifyBackend):
    """Linux notifications via notify-send."""

    def send(self, title: str, body: str, sound: bool = True) -> None:
        if len(body) > 100:
            body = body[:100] + "..."
        try:
            subprocess.run(
                ["notify-send", title, body],
                check=False,
                timeout=5,
            )
        except FileNotFoundError:
            _log.debug("notify-send not found, skipping notification")
        except Exception:
            _log.debug("notify-send failed", exc_info=True)


class WaylandActiveWindow(ActiveWindowBackend):
    """Wayland active window via DE-specific methods."""

    def __init__(self, desktop: str = "") -> None:
        self._desktop = desktop or os.environ.get("XDG_CURRENT_DESKTOP", "")

    def get_frontmost_app(self) -> str:
        try:
            lower = self._desktop.lower()
            if "gnome" in lower or "pop" in lower or "ubuntu" in lower:
                return self._gnome_active_window()
            elif "kde" in lower or "plasma" in lower:
                return self._kde_active_window()
            elif "sway" in lower:
                return self._sway_active_window()
            return ""
        except Exception:
            return ""

    def _gnome_active_window(self) -> str:
        result = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell",
                "--object-path", "/org/gnome/Shell",
                "--method", "org.gnome.Shell.Eval",
                "global.display.focus_window"
                " ? global.display.focus_window.get_wm_class()"
                " : ''",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        # Try plain JSON first (test format: {"success": true, "value": "firefox"})
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                val = data.get("value", "")
                return str(val).strip('"') if val else ""
        except (json.JSONDecodeError, ValueError):
            pass
        # Fall back to gdbus tuple format: (true, 'value')
        try:
            normalized = (
                result.stdout
                .replace("(", "[")
                .replace(")", "]")
                .replace("'", '"')
            )
            data = json.loads(normalized)
            if data[0] and data[1]:
                return str(data[1]).strip('"')
        except (json.JSONDecodeError, IndexError, TypeError):
            pass
        return ""

    def _kde_active_window(self) -> str:
        result = subprocess.run(
            ["qdbus", "org.kde.KWin", "/KWin", "org.kde.KWin.activeWindow"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()

    def _sway_active_window(self) -> str:
        result = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        tree = json.loads(result.stdout)
        return self._find_focused(tree)

    def _find_focused(self, node: dict) -> str:
        if node.get("focused"):
            return str(node.get("app_id", "") or node.get("name", ""))
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            result = self._find_focused(child)
            if result:
                return result
        return ""
