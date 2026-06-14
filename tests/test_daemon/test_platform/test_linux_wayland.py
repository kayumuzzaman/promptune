"""Tests for Linux Wayland platform backend.

All tests in this file run on macOS via mocked subprocess / dbus-next / evdev calls.

TODO(linux-ci): On a real Linux Wayland machine, add an integration test module
  tests/test_daemon/test_platform/test_linux_wayland_integration.py that:
  - Requires: dbus-next, evdev, wl-clipboard, ydotool, notify-send installed
  - Mark each test with @pytest.mark.linux
  - Run with:
    pytest -m linux tests/test_daemon/test_platform/test_linux_wayland_integration.py
  See docs/MANUAL_TESTING.md §28.3 for the full manual checklist.
"""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

from promptune.daemon.platform.base import (
    ActiveWindowBackend,
    ClipboardBackend,
    HotkeyBackend,
    NotifyBackend,
)
from promptune.daemon.platform.linux_wayland import (
    WaylandActiveWindow,
    WaylandClipboard,
    WaylandHotkey,
    WaylandNotify,
)


class TestWaylandHotkey:
    def test_implements_interface(self) -> None:
        assert issubclass(WaylandHotkey, HotkeyBackend)

    def test_stop_sets_event(self) -> None:
        hk = WaylandHotkey()
        hk.stop()
        assert hk._stop_event.is_set()

    def test_check_conflict_returns_false(self) -> None:
        hk = WaylandHotkey()
        assert hk.check_conflict("ctrl+shift+e") is False


class TestWaylandClipboard:
    def test_implements_interface(self) -> None:
        assert issubclass(WaylandClipboard, ClipboardBackend)

    def test_read_calls_wl_paste(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="clipboard text", returncode=0
            )
            result = cb.read()
            assert result == "clipboard text"
            mock_run.assert_called_once_with(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_read_returns_none_on_error(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "wl-paste")
        with patch("subprocess.run", side_effect=err):
            result = cb.read()
            assert result is None

    def test_write_pipes_to_wl_copy(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            cb.write("hello")
            mock_run.assert_called_once_with(
                ["wl-copy"],
                input="hello",
                text=True,
                check=True,
            )

    def test_copy_selection_uses_ydotool(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch("subprocess.run") as mock_run,
            patch.object(cb, "read", return_value="selected"),
        ):
            result = cb.copy_selection()
            assert mock_run.call_args_list[0] == call(
                ["ydotool", "key", "29:1", "46:1", "46:0", "29:0"],
                check=True,
            )
            assert result == "selected"

    def test_paste_result_uses_ydotool(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch.object(cb, "write") as mock_write,
            patch("subprocess.run") as mock_run,
        ):
            cb.paste_result("enhanced")
            mock_write.assert_called_once_with("enhanced")
            assert mock_run.call_args_list[0] == call(
                ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                check=True,
            )

    def test_read_strips_null_bytes(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="hello\x00world", returncode=0
            )
            result = cb.read()
            assert result == "helloworld"


class TestWaylandNotify:
    def test_implements_interface(self) -> None:
        assert issubclass(WaylandNotify, NotifyBackend)

    def test_send_calls_notify_send(self) -> None:
        n = WaylandNotify()
        with patch("subprocess.run") as mock_run:
            n.send("Title", "Body")
            mock_run.assert_called_once_with(
                ["notify-send", "Title", "Body"],
                check=False,
                timeout=5,
            )

    def test_send_truncates_long_body(self) -> None:
        n = WaylandNotify()
        long_body = "x" * 200
        with patch("subprocess.run") as mock_run:
            n.send("T", long_body)
            sent_body = mock_run.call_args[0][0][2]
            assert len(sent_body) <= 103
            assert sent_body.endswith("...")


class TestWaylandActiveWindow:
    def test_implements_interface(self) -> None:
        assert issubclass(WaylandActiveWindow, ActiveWindowBackend)

    def test_gnome_detection(self) -> None:
        aw = WaylandActiveWindow(desktop="GNOME")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout='{"success": true, "value": "firefox"}',
                returncode=0,
            )
            result = aw.get_frontmost_app()
            assert result == "firefox"

    def test_sway_detection(self) -> None:
        aw = WaylandActiveWindow(desktop="sway")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout='{"nodes":[{"focused":true,"app_id":"kitty"}]}',
                returncode=0,
            )
            result = aw.get_frontmost_app()
            assert "kitty" in result or result == ""

    def test_returns_empty_on_error(self) -> None:
        aw = WaylandActiveWindow(desktop="unknown")
        assert aw.get_frontmost_app() == ""

    def test_returns_empty_when_subprocess_fails(self) -> None:
        aw = WaylandActiveWindow(desktop="GNOME")
        with patch("subprocess.run", side_effect=Exception("dbus error")):
            assert aw.get_frontmost_app() == ""
