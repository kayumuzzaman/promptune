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

# Caps Lock (LockMask) and Num Lock (Mod2Mask) add bits to an event's
# modifier state, so a passive grab for the bare mask never fires while
# either is on — a common desktop state. Grab every combination of the two
# lock bits so the hotkey works regardless of lock state.
_X11_LOCK_MASK = 1 << 1  # LockMask (Caps Lock)
_X11_NUMLOCK_MASK = 1 << 4  # Mod2Mask (Num Lock)
_X11_LOCK_COMBOS: tuple[int, ...] = (
    0,
    _X11_LOCK_MASK,
    _X11_NUMLOCK_MASK,
    _X11_LOCK_MASK | _X11_NUMLOCK_MASK,
)


def _parse_combo(combo: str) -> tuple[str, int]:
    """Parse 'ctrl+shift+e' into (key_name, modifier_mask).

    Empty or whitespace-only segments are ignored.  Modifier tokens
    contribute to the mask; the last non-modifier token wins as the key
    name.  A combo with no key token (e.g. ``"ctrl+shift"`` or ``""``)
    yields an empty key name, which the callers treat as a failed grab.
    """
    key_name = ""
    mask = 0
    for raw in combo.split("+"):
        part = raw.strip().lower()
        if not part:
            continue
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
        d = None
        try:
            from Xlib import XK, X
            from Xlib import display as xdisplay

            key_name, mod_mask = _parse_combo(combo)
            if not key_name:
                _log.debug("X11 grab test: no key in combo %r", combo)
                return False

            d = xdisplay.Display()
            root = d.screen().root
            keysym = XK.string_to_keysym(key_name)
            keycode = d.keysym_to_keycode(keysym)
            if not keycode:
                _log.debug("X11 grab test: unknown key %r", key_name)
                return False

            error_caught = []

            def _error_handler(err, request):  # type: ignore[no-untyped-def]
                error_caught.append(err)

            for extra in _X11_LOCK_COMBOS:
                root.grab_key(
                    keycode, mod_mask | extra, True,
                    X.GrabModeAsync, X.GrabModeAsync,
                    onerror=_error_handler,
                )
            d.sync()

            if error_caught:
                return False

            for extra in _X11_LOCK_COMBOS:
                root.ungrab_key(keycode, mod_mask | extra)
            return True
        except Exception:
            _log.debug("X11 grab test failed", exc_info=True)
            return False
        finally:
            if d is not None:
                try:
                    d.close()
                except Exception:
                    _log.debug("X11 display close failed", exc_info=True)

    def listen(self) -> None:
        # TODO(linux-ci): Integration test for this blocking event loop requires
        # a real X11 display. On a Linux X11 machine:
        #   1. Set DISPLAY=:0 (or use Xvfb for headless CI)
        #   2. Use threading to call stop() after a short delay
        #   3. Assert the loop exits cleanly without raising
        # See tests/test_daemon/test_platform/test_linux_x11_integration.py
        d = None
        keycode = None
        root = None
        try:
            from Xlib import XK, X
            from Xlib import display as xdisplay

            d = xdisplay.Display()
            root = d.screen().root
            keysym = XK.string_to_keysym(self._key_name)
            keycode = d.keysym_to_keycode(keysym)
            if not keycode:
                _log.error("X11 event loop: unknown key %r", self._key_name)
                return

            for extra in _X11_LOCK_COMBOS:
                root.grab_key(
                    keycode, self._mod_mask | extra, True,
                    X.GrabModeAsync, X.GrabModeAsync,
                )

            while not self._stop_event.is_set():
                if d.pending_events() > 0:
                    event = d.next_event()
                    if (
                        event.type == X.KeyPress
                        and event.detail == keycode
                        and self._callback
                    ):
                        self._callback()
                else:
                    time.sleep(0.05)
        except Exception:
            _log.error("X11 event loop failed", exc_info=True)
        finally:
            if root is not None and keycode:
                for extra in _X11_LOCK_COMBOS:
                    try:
                        root.ungrab_key(keycode, self._mod_mask | extra)
                    except Exception:
                        _log.debug("X11 ungrab_key failed", exc_info=True)
            if d is not None:
                try:
                    d.close()
                except Exception:
                    _log.debug("X11 display close failed", exc_info=True)

    def stop(self) -> None:
        self._stop_event.set()


class X11Clipboard(ClipboardBackend):
    """X11 clipboard via xclip + xdotool."""

    def __init__(self, settle_ms: int = 100) -> None:
        self._settle_ms = settle_ms

    def read(self) -> str | None:
        """Best-effort clipboard read; returns None if xclip is missing/fails."""
        try:
            return self._read()
        except Exception:
            return None

    def _read(self) -> str:
        """Read the clipboard, raising if xclip is missing or fails."""
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-o"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.replace("\x00", "")

    def write(self, text: str) -> None:
        """Write *text* to the clipboard.

        Raises RuntimeError if xclip is missing or fails so daemon delivery can
        notify the user instead of reporting success.
        """
        if not self._write(text):
            raise RuntimeError("xclip failed to write clipboard")

    def _write(self, text: str) -> bool:
        """Write to the clipboard, returning True on success."""
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                input=text,
                text=True,
                check=True,
            )
            return True
        except FileNotFoundError:
            _log.error("xclip not found — cannot write clipboard")
            return False
        except Exception:
            _log.error("xclip write failed", exc_info=True)
            return False

    def copy_selection(self) -> str | None:
        # Clear the clipboard before synthesizing the copy so that a clipboard
        # left unchanged afterwards (nothing selected, or the focused app
        # ignored Ctrl+C) is distinguishable from a real selection — even one
        # whose text matches the previous clipboard contents. Restore the
        # previous value if nothing was copied so the hotkey never wipes it.
        previous = self.read()
        # Only clear when the prior contents are restorable text. If read()
        # returned None (non-text payload like an image, or a read failure),
        # clearing would destroy data we cannot put back — and there is no
        # text that could masquerade as a selection, so the clear isn't
        # needed for detection anyway.
        cleared = previous is not None
        if cleared:
            self._write("")  # best-effort; _read() below surfaces tool errors
        copied = False
        try:
            try:
                subprocess.run(
                    ["xdotool", "key", "--clearmodifiers", "ctrl+c"],
                    check=True,
                )
            except FileNotFoundError as exc:
                _log.error("xdotool not found — cannot simulate copy")
                raise RuntimeError(
                    "xdotool not found; install xdotool to read the selection"
                ) from exc
            except Exception as exc:
                _log.error("xdotool copy failed", exc_info=True)
                raise RuntimeError(f"xdotool copy failed: {exc}") from exc
            time.sleep(self._settle_ms / 1000.0)
            # A read-tool failure (xclip missing/broken) must raise so the
            # daemon reports the broken copy tool instead of "No text
            # selected"; a genuinely empty clipboard returns None below.
            try:
                text = self._read()
            except FileNotFoundError as exc:
                _log.error("xclip not found — cannot read selection")
                raise RuntimeError(
                    "xclip not found; install xclip to read the selection"
                ) from exc
            except Exception as exc:
                _log.error("xclip read failed", exc_info=True)
                raise RuntimeError(f"xclip read failed: {exc}") from exc
            if text:
                copied = True
                return text
            return None
        finally:
            # Restore the prior clipboard on no-selection or any failure.
            if not copied and previous:
                self._write(previous)

    def paste_result(self, text: str) -> bool:
        # Put the text on the clipboard first so it is never lost even if
        # the paste keystroke cannot be simulated.
        if not self._write(text):
            _log.error("Could not place result on clipboard; paste aborted")
            raise RuntimeError("xclip failed to write clipboard")
        time.sleep(self._settle_ms / 1000.0)
        try:
            subprocess.run(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                check=True,
            )
        except FileNotFoundError:
            _log.warning(
                "xdotool not found — result is on the clipboard, "
                "paste it manually"
            )
            return False
        except Exception:
            _log.warning(
                "xdotool paste failed — result is on the clipboard, "
                "paste it manually",
                exc_info=True,
            )
            return False
        return True


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
        try:
            root = d.screen().root
            net_active = d.intern_atom("_NET_ACTIVE_WINDOW")
            response = root.get_full_property(net_active, 0)

            if response is None or not response.value:
                return ""

            window_id = response.value[0]
            window = d.create_resource_object("window", window_id)
            wm_class = window.get_wm_class()

            if wm_class:
                return str(wm_class[1])
            return ""
        finally:
            try:
                d.close()
            except Exception:
                _log.debug("X11 display close failed", exc_info=True)
