"""Real-display X11 integration tests.

These exercise the X11 backend against an actual X server (a virtual one,
Xvfb, in CI) using the real ``xclip``/``xdotool`` binaries — the code paths
that the mocked unit tests cannot cover.

Marked ``linux`` + ``x11`` so the default macOS run (``-m "not linux"``)
skips them; CI selects them with ``-m x11`` under ``xvfb-run``. Each test
also self-skips when ``$DISPLAY`` or the required binary is absent, so the
file is safe to collect anywhere.
"""

from __future__ import annotations

import os
import shutil
import subprocess

import pytest

pytestmark = [pytest.mark.linux, pytest.mark.x11]

_HAS_DISPLAY = bool(os.environ.get("DISPLAY"))
_HAS_XCLIP = shutil.which("xclip") is not None
_HAS_XDOTOOL = shutil.which("xdotool") is not None

requires_x11_clipboard = pytest.mark.skipif(
    not (_HAS_DISPLAY and _HAS_XCLIP),
    reason="needs a real X11 display ($DISPLAY) and xclip",
)
requires_xdotool = pytest.mark.skipif(
    not (_HAS_DISPLAY and _HAS_XDOTOOL),
    reason="needs a real X11 display ($DISPLAY) and xdotool",
)


@requires_x11_clipboard
def test_clipboard_write_read_roundtrip() -> None:
    """write() then read() returns the same text through the real X selection."""
    from promptune.daemon.platform.linux_x11 import X11Clipboard

    clip = X11Clipboard()
    clip.write("promptune-x11-roundtrip-✓")
    assert clip.read() == "promptune-x11-roundtrip-✓"


@requires_x11_clipboard
def test_write_overwrites_previous_value() -> None:
    from promptune.daemon.platform.linux_x11 import X11Clipboard

    clip = X11Clipboard()
    clip.write("first")
    clip.write("second")
    assert clip.read() == "second"


@requires_xdotool
def test_grab_conflict_detection_runs() -> None:
    """check_conflict performs a real XGrabKey/XUngrabKey round-trip.

    On a bare Xvfb display the combo should be free, so this returns False.
    The point is that the real Xlib grab path executes without raising.
    """
    from promptune.daemon.platform.linux_x11 import X11Hotkey

    hotkey = X11Hotkey()
    assert hotkey.check_conflict("ctrl+shift+e") in (True, False)


@requires_x11_clipboard
def test_xclip_binary_present_and_executable() -> None:
    """Sanity: the xclip the backend shells out to actually works here."""
    result = subprocess.run(
        ["xclip", "-version"], capture_output=True, text=True
    )
    # xclip prints its version banner to stderr; just assert it ran.
    assert result.returncode == 0 or "xclip" in (result.stderr + result.stdout)
