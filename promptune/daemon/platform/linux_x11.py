"""Linux X11 platform backend.

Uses python-xlib for hotkey registration and active window detection,
xclip for clipboard I/O, xdotool for key simulation, and notify-send
for desktop notifications.
"""

from __future__ import annotations

import logging
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

_X11_MOD_MASK: dict[str, int] = {
    "ctrl": 1 << 2,
    "shift": 1 << 0,
    "alt": 1 << 3,
    "super": 1 << 6,
}


def _parse_combo(combo: str) -> tuple[str, int]:
    """Parse 'ctrl+shift+e' into (key_name, modifier_mask)."""
    parts = [p.strip().lower() for p in combo.split("+")]
    key_name = ""
    mask = 0
    for part in parts:
        if part in _X11_MOD_MASK:
            mask |= _X11_MOD_MASK[part]
        else:
            key_name = part
    return key_name, mask


class X11Hotkey(HotkeyBackend):
    """X11 global hotkey via XGrabKey + XNextEvent loop."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._callback: Callable[[], None] | None = None
        self._key_name = ""
        self._mod_mask = 0

    def register(self, combo: str, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._key_name, self._mod_mask = _parse_combo(combo)

    def check_conflict(self, combo: str) -> bool:
        return not self._try_grab(combo)

    def _try_grab(self, combo: str) -> bool:
        try:
            from Xlib import XK, X
            from Xlib import display as xdisplay

            key_name, mod_mask = _parse_combo(combo)
            d = xdisplay.Display()
            root = d.screen().root
            keysym = XK.string_to_keysym(key_name)
            keycode = d.keysym_to_keycode(keysym)

            error_caught = []

            def _error_handler(err, request):  # type: ignore[no-untyped-def]
                error_caught.append(err)

            root.grab_key(
                keycode, mod_mask, True,
                X.GrabModeAsync, X.GrabModeAsync,
                onerror=_error_handler,
            )
            d.sync()

            if error_caught:
                d.close()
                return False

            root.ungrab_key(keycode, mod_mask)
            d.close()
            return True
        except Exception:
            _log.debug("X11 grab test failed", exc_info=True)
            return False

    def listen(self) -> None:
        # TODO(linux-ci): Integration test for this blocking event loop requires
        # a real X11 display. On a Linux X11 machine:
        #   1. Set DISPLAY=:0 (or use Xvfb for headless CI)
        #   2. Use threading to call stop() after a short delay
        #   3. Assert the loop exits cleanly without raising
        # See tests/test_daemon/test_platform/test_linux_x11_integration.py
        try:
            from Xlib import XK, X
            from Xlib import display as xdisplay

            d = xdisplay.Display()
            root = d.screen().root
            keysym = XK.string_to_keysym(self._key_name)
            keycode = d.keysym_to_keycode(keysym)

            root.grab_key(
                keycode, self._mod_mask, True,
                X.GrabModeAsync, X.GrabModeAsync,
            )

            while not self._stop_event.is_set():
                if d.pending_events() > 0:
                    event = d.next_event()
                    if event.type == X.KeyPress and self._callback:
                        self._callback()
                else:
                    time.sleep(0.05)

            root.ungrab_key(keycode, self._mod_mask)
            d.close()
        except Exception:
            _log.error("X11 event loop failed", exc_info=True)

    def stop(self) -> None:
        self._stop_event.set()


class X11Clipboard(ClipboardBackend):
    """X11 clipboard via xclip + xdotool."""

    def __init__(self, settle_ms: int = 100) -> None:
        self._settle_ms = settle_ms

    def read(self) -> str | None:
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.replace("\x00", "")
        except Exception:
            return None

    def write(self, text: str) -> None:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text,
            text=True,
            check=True,
        )

    def copy_selection(self) -> str | None:
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+c"],
            check=True,
        )
        time.sleep(self._settle_ms / 1000.0)
        return self.read()

    def paste_result(self, text: str) -> None:
        self.write(text)
        time.sleep(self._settle_ms / 1000.0)
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
            check=True,
        )


class X11Notify(NotifyBackend):
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


class X11ActiveWindow(ActiveWindowBackend):
    """X11 active window via _NET_ACTIVE_WINDOW property."""

    def get_frontmost_app(self) -> str:
        try:
            return self._get_wm_class()
        except Exception:
            return ""

    def _get_wm_class(self) -> str:
        from Xlib import display as xdisplay

        d = xdisplay.Display()
        root = d.screen().root
        net_active = d.intern_atom("_NET_ACTIVE_WINDOW")
        response = root.get_full_property(net_active, 0)

        if response is None or not response.value:
            d.close()
            return ""

        window_id = response.value[0]
        window = d.create_resource_object("window", window_id)
        wm_class = window.get_wm_class()
        d.close()

        if wm_class:
            return str(wm_class[1])
        return ""
