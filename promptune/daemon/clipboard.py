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

    Returns an empty string if the bundle ID cannot be determined.
    """
    workspace = NSWorkspace.sharedWorkspace()
    app = workspace.frontmostApplication()
    if app is None:
        return ""
    bundle_id = app.bundleIdentifier()
    if bundle_id is None:
        return ""
    return str(bundle_id)


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
    )
    return result.stdout


def copy_selection() -> str | None:
    """Trigger a copy of the current selection and return the clipboard text.

    Clears the clipboard first so an empty selection (Cmd+C with nothing
    selected) returns ``None`` instead of the stale prior value, restoring
    that prior value before returning. Raises when pbcopy/pbpaste itself is
    missing or fails, so callers can distinguish a broken tool from a
    genuinely empty selection.
    """
    previous = save_clipboard()
    # Only clear what we can restore — if the prior read failed (None), don't
    # wipe the clipboard, mirroring the Linux backends.
    if previous is not None:
        write_clipboard("")
    simulate_cmd_c()
    time.sleep(CLIPBOARD_SETTLE_MS / 1000.0)
    text = _read_clipboard_raising()
    if text:
        return text
    if previous:
        write_clipboard(previous)
    return None


def paste_result(text: str) -> bool:
    """Write *text* to the clipboard and then trigger a paste.

    Writes the text, waits for the clipboard to settle, then simulates Cmd+V.
    Returns ``True`` once the paste keystroke has been dispatched.
    """
    write_clipboard(text)
    time.sleep(CLIPBOARD_SETTLE_MS / 1000.0)
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
