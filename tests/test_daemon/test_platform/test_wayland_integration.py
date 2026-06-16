"""Real Wayland integration tests (manual / hardware only).

Wayland's hotkey (xdg-desktop-portal GlobalShortcuts), key injection
(ydotool + uinput) and active-window detection cannot be reproduced in a
headless CI runner, so these are NOT run in CI. Run them on a real
GNOME / KDE / sway session:

    pip install -e ".[dev,linux-daemon]"
    pytest -m wayland

Marked ``linux`` + ``wayland`` (excluded by the default ``-m "not linux"``).
Each test self-skips unless a real Wayland session and the needed binaries
are present, so the file is safe to collect anywhere.

See docs/MANUAL_TESTING.md for the full GNOME/KDE/sway sign-off checklist.
"""

from __future__ import annotations

import os
import shutil

import pytest

pytestmark = [pytest.mark.linux, pytest.mark.wayland]

_HAS_WAYLAND = bool(os.environ.get("WAYLAND_DISPLAY"))
_HAS_WL_CLIPBOARD = (
    shutil.which("wl-copy") is not None and shutil.which("wl-paste") is not None
)

requires_wayland_clipboard = pytest.mark.skipif(
    not (_HAS_WAYLAND and _HAS_WL_CLIPBOARD),
    reason="needs a real Wayland session ($WAYLAND_DISPLAY) and wl-clipboard",
)


@requires_wayland_clipboard
def test_clipboard_write_read_roundtrip() -> None:
    """write() then read() returns the same text through wl-copy/wl-paste."""
    from promptune.daemon.platform.linux_wayland import WaylandClipboard

    clip = WaylandClipboard()
    clip.write("promptune-wl-roundtrip-✓")
    assert clip.read() == "promptune-wl-roundtrip-✓"


@requires_wayland_clipboard
def test_write_overwrites_previous_value() -> None:
    from promptune.daemon.platform.linux_wayland import WaylandClipboard

    clip = WaylandClipboard()
    clip.write("first")
    clip.write("second")
    assert clip.read() == "second"
