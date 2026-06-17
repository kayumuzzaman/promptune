"""macOS global hotkey registration using Quartz CGEventTap.

This module requires macOS and the pyobjc-framework-Quartz and
pyobjc-framework-ApplicationServices packages.
"""

from __future__ import annotations

import sys
from typing import Callable

if sys.platform != "darwin":
    raise ImportError(
        "promptune.daemon.hotkey requires macOS."
    )

import ApplicationServices
import Quartz

# ---------------------------------------------------------------------------
# Key / modifier maps
# ---------------------------------------------------------------------------

KEYCODE_MAP: dict[str, int] = {
    "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3,
    "g": 5, "h": 4, "i": 34, "j": 38, "k": 40, "l": 37,
    "m": 46, "n": 45, "o": 31, "p": 35, "q": 12, "r": 15,
    "s": 1, "t": 17, "u": 32, "v": 9, "w": 13, "x": 7,
    "y": 16, "z": 6, "space": 49,
}

MODIFIER_MAP: dict[str, int] = {
    "ctrl": Quartz.kCGEventFlagMaskControl,
    "shift": Quartz.kCGEventFlagMaskShift,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "cmd": Quartz.kCGEventFlagMaskCommand,
}

DEFAULT_HOTKEY_KEYCODE: int = 14  # 'e'

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

_run_loop_ref: object | None = None
_event_tap_ref: object | None = None


# ---------------------------------------------------------------------------
# Hotkey parsing
# ---------------------------------------------------------------------------

def parse_hotkey(hotkey: str) -> tuple[int, int]:
    """Parse a hotkey string like 'ctrl+shift+e' into (keycode, modifier_mask).

    Args:
        hotkey: A '+'-separated string of modifier names and a key name.
                Modifiers: ctrl, shift, alt, cmd.
                Keys: a-z, space.
                Case-insensitive.

    Returns:
        A tuple of (keycode, modifier_mask) as integers.

    Raises:
        ValueError: If an unknown key or modifier is encountered.
    """
    parts = [p.strip().lower() for p in hotkey.split("+")]

    keycode: int | None = None
    modifier_mask: int = 0

    for part in parts:
        if part in MODIFIER_MAP:
            modifier_mask |= MODIFIER_MAP[part]
        elif part in KEYCODE_MAP:
            keycode = KEYCODE_MAP[part]
        else:
            raise ValueError(
                f"Unknown key or modifier: '{part}'. "
                f"Valid modifiers: {list(MODIFIER_MAP.keys())}. "
                f"Valid keys: {list(KEYCODE_MAP.keys())}."
            )

    if keycode is None:
        raise ValueError(
            f"No valid key found in hotkey string: '{hotkey}'. "
            f"Must include one of: {list(KEYCODE_MAP.keys())}."
        )

    return keycode, modifier_mask


# ---------------------------------------------------------------------------
# Accessibility
# ---------------------------------------------------------------------------

def check_accessibility() -> bool:
    """Check whether this process has accessibility (AX) permissions.

    Returns:
        True if the process is trusted, False otherwise.
    """
    return bool(
        ApplicationServices.AXIsProcessTrustedWithOptions(None)
    )


def request_accessibility() -> bool:
    """Request accessibility permissions, showing the system prompt to the user.

    Returns:
        True if already trusted (prompt not needed), False if permission
        dialog was shown or access is denied.
    """
    options = {
        ApplicationServices.kAXTrustedCheckOptionPrompt: True
    }
    return bool(
        ApplicationServices.AXIsProcessTrustedWithOptions(options)
    )


# ---------------------------------------------------------------------------
# Secure input detection
# ---------------------------------------------------------------------------

def is_secure_input_active() -> bool:
    """Return True if secure keyboard entry is currently active.

    When active, CGEventTap will not receive key events.
    """
    return bool(Quartz.CGSIsSecureEventInputSet())


# ---------------------------------------------------------------------------
# Event tap / hotkey registration
# ---------------------------------------------------------------------------

def _event_callback(
    callback: Callable[[], None],
    keycode: int,
    modifier_mask: int,
) -> Callable:
    """Return a CGEventTap callback that fires *callback* when the hotkey matches."""

    def _handler(proxy, event_type, event, refcon):  # type: ignore[no-untyped-def]
        if event_type == Quartz.kCGEventKeyDown:
            # Ignore OS key-repeat events fired while the hotkey is held; only
            # the initial press should trigger one enhancement run.
            if Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventAutorepeat
            ):
                return event
            ev_keycode = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventKeycode
            )
            ev_flags = Quartz.CGEventGetFlags(event)
            # Mask to only the modifier bits we care about
            relevant_flags = ev_flags & (
                Quartz.kCGEventFlagMaskControl
                | Quartz.kCGEventFlagMaskShift
                | Quartz.kCGEventFlagMaskAlternate
                | Quartz.kCGEventFlagMaskCommand
            )
            if ev_keycode == keycode and relevant_flags == modifier_mask:
                callback()
        return event

    return _handler


def register_hotkey(
    callback: Callable[[], None],
    keycode: int,
    modifier_mask: int,
) -> object:
    """Register a global hotkey via CGEventTap.

    Args:
        callback: Zero-argument callable invoked when the hotkey fires.
        keycode: macOS virtual keycode (see KEYCODE_MAP).
        modifier_mask: Quartz modifier flag bitmask (see MODIFIER_MAP).

    Returns:
        The CGEventTap reference (opaque object). Keep alive for as long as
        the hotkey should remain active.

    Raises:
        PermissionError: If the event tap could not be created (typically
            because accessibility permissions are not granted).
    """
    handler = _event_callback(callback, keycode, modifier_mask)

    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionDefault,
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
        handler,
        None,
    )

    if tap is None:
        raise PermissionError(
            "Could not create CGEventTap. "
            "Grant accessibility permissions in System Settings → "
            "Privacy & Security → Accessibility."
        )

    global _event_tap_ref
    _event_tap_ref = tap
    return tap


# ---------------------------------------------------------------------------
# Run loop
# ---------------------------------------------------------------------------

def start_run_loop() -> None:
    """Add the current event tap to the main CFRunLoop and start it.

    Blocks until stop_run_loop() is called.
    """
    global _run_loop_ref

    if _event_tap_ref is None:
        raise RuntimeError("No event tap registered. Call register_hotkey() first.")

    run_loop_source = Quartz.CFMachPortCreateRunLoopSource(
        None, _event_tap_ref, 0
    )
    _run_loop_ref = Quartz.CFRunLoopGetCurrent()
    Quartz.CFRunLoopAddSource(
        _run_loop_ref,
        run_loop_source,
        Quartz.kCFRunLoopCommonModes,
    )
    Quartz.CGEventTapEnable(_event_tap_ref, True)
    Quartz.CFRunLoopRun()


def stop_run_loop() -> None:
    """Stop the CFRunLoop started by start_run_loop()."""
    global _run_loop_ref

    if _run_loop_ref is not None:
        Quartz.CFRunLoopStop(_run_loop_ref)
        _run_loop_ref = None
