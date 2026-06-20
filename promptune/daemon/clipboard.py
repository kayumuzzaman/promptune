"""Clipboard utilities for the macOS daemon pipeline.

Provides pbpaste/pbcopy wrappers, CGEvent-based key simulation,
frontmost-app detection, and an undo buffer.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

if sys.platform != "darwin":
    raise ImportError(
        "promptune.daemon.clipboard requires macOS."
    )

try:
    import Quartz  # type: ignore[import]
except ImportError:  # pragma: no cover
    Quartz = None  # type: ignore[assignment]

try:
    from AppKit import NSWorkspace  # type: ignore[import]
except ImportError:  # pragma: no cover
    NSWorkspace = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

UNDO_FILE = Path("~/.local/share/promptune/undo.txt").expanduser()
CLIPBOARD_SETTLE_MS = 100
CLIPBOARD_COMMAND_TIMEOUT = 2.0


# ---------------------------------------------------------------------------
# Low-level clipboard I/O
# ---------------------------------------------------------------------------


def save_clipboard() -> str | None:
    """Read the current clipboard contents via pbpaste.

    Returns the clipboard text, or None on failure.
    """
    try:
        result = subprocess.run(
            ["pbpaste"],
            capture_output=True,
            text=True,
            check=True,
            timeout=CLIPBOARD_COMMAND_TIMEOUT,
        )
        return result.stdout
    except Exception:
        return None


def write_clipboard(text: str) -> None:
    """Write *text* to the clipboard via pbcopy."""
    subprocess.run(
        ["pbcopy"],
        input=text,
        text=True,
        check=True,
        timeout=CLIPBOARD_COMMAND_TIMEOUT,
    )


# ---------------------------------------------------------------------------
# CGEvent key simulation
# ---------------------------------------------------------------------------


def _simulate_key_combo(keycode: int, modifier: int) -> None:
    """Simulate a key-down / key-up event pair with *modifier* flags.

    Uses Quartz.CGEvent to synthesise the event.
    """
    src = Quartz.CGEventSourceCreate(
        Quartz.kCGEventSourceStateHIDSystemState
    )

    key_down = Quartz.CGEventCreateKeyboardEvent(src, keycode, True)
    Quartz.CGEventSetFlags(key_down, modifier)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, key_down)

    key_up = Quartz.CGEventCreateKeyboardEvent(src, keycode, False)
    Quartz.CGEventSetFlags(key_up, modifier)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, key_up)


def simulate_cmd_c() -> None:
    """Simulate Cmd+C (copy) — keycode 8."""
    _simulate_key_combo(8, Quartz.kCGEventFlagMaskCommand)


def simulate_cmd_v() -> None:
    """Simulate Cmd+V (paste) — keycode 9."""
    _simulate_key_combo(9, Quartz.kCGEventFlagMaskCommand)


# ---------------------------------------------------------------------------
# App detection
# ---------------------------------------------------------------------------


def get_frontmost_app() -> str:
    """Return the bundle identifier of the currently frontmost application.

    Returns an empty string if the bundle ID cannot be determined. PyObjC can
    raise transiently during an app switch (stale NSRunningApplication), so any
    failure degrades to "" — matching the X11/Wayland backends — rather than
    crashing the hotkey thread and silently no-opping the enhancement.
    """
    try:
        workspace = NSWorkspace.sharedWorkspace()
        app = workspace.frontmostApplication()
        if app is None:
            return ""
        bundle_id = app.bundleIdentifier()
        if bundle_id is None:
            return ""
        return str(bundle_id)
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# High-level clipboard pipeline helpers
# ---------------------------------------------------------------------------


def _read_clipboard_raising() -> str:
    """Read the clipboard via pbpaste, letting tool failures propagate."""
    result = subprocess.run(
        ["pbpaste"],
        capture_output=True,
        text=True,
        check=True,
        timeout=CLIPBOARD_COMMAND_TIMEOUT,
    )
    return result.stdout


def copy_selection(settle_ms: int = CLIPBOARD_SETTLE_MS) -> str | None:
    """Trigger a copy of the current selection and return the clipboard text.

    Clears the clipboard first so an empty selection (Cmd+C with nothing
    selected) returns ``None`` instead of the stale prior value, restoring
    that prior value before returning. Raises when pbcopy/pbpaste itself is
    missing or fails, so callers can distinguish a broken tool from a
    genuinely empty selection.

    *settle_ms* is how long to wait after the copy keystroke before reading
    the clipboard back (configurable for slow apps via ``clipboard_settle_ms``).
    """
    previous = save_clipboard()
    # Only clear what we can put back: skip the clear when the prior read
    # failed (None) or is empty text (""), which is also what pbpaste returns
    # for a non-text clipboard such as an image — clearing then would wipe it
    # with no way to restore. Mirrors the Linux backends.
    if previous:
        write_clipboard("")
    try:
        simulate_cmd_c()
        time.sleep(settle_ms / 1000.0)
        text = _read_clipboard_raising()
    except Exception:
        # A failed copy/read after the clear must not leave the user's
        # clipboard wiped — restore the prior value before propagating.
        if previous:
            write_clipboard(previous)
        raise
    if text:
        return text
    if previous:
        write_clipboard(previous)
    return None


def paste_result(text: str, settle_ms: int = CLIPBOARD_SETTLE_MS) -> bool:
    """Write *text* to the clipboard and then trigger a paste.

    Writes the text, waits *settle_ms* for the clipboard to settle, then
    simulates Cmd+V. Returns ``True`` if the paste keystroke was dispatched, or
    ``False`` if accessibility permission is missing — in which case the
    synthetic Cmd+V is silently dropped by the OS, so we report failure (the
    text is on the clipboard) instead of letting the daemon clobber it with the
    user's original after a no-op paste. Mirrors the X11/Wayland backends, which
    return False when the paste tool fails.
    """
    from promptune.daemon.hotkey import check_accessibility

    write_clipboard(text)
    if not check_accessibility():
        return False
    time.sleep(settle_ms / 1000.0)
    simulate_cmd_v()
    return True


# ---------------------------------------------------------------------------
# Undo buffer
# ---------------------------------------------------------------------------


def save_undo(
    original_clipboard: str | None,
    selected_text: str,
) -> None:
    """Persist an undo record to *UNDO_FILE* as JSON.

    Stores *original_clipboard* (may be None) and *selected_text* so the
    daemon can restore the previous state on an undo request.
    """
    UNDO_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {
        "original_clipboard": original_clipboard,
        "selected_text": selected_text,
    }
    UNDO_FILE.write_text(json.dumps(payload), encoding="utf-8")
    UNDO_FILE.chmod(0o600)
