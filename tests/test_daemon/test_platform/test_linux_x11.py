"""Tests for Linux X11 platform backend.

All tests in this file run on macOS via mocked subprocess / python-xlib calls.

TODO(linux-ci): On a real Linux X11 machine, add an integration test module
  tests/test_daemon/test_platform/test_linux_x11_integration.py that:
  - Requires: python-xlib, xclip, xdotool installed
  - Mark each test with @pytest.mark.linux
  - Run with:
    pytest -m linux tests/test_daemon/test_platform/test_linux_x11_integration.py
  See docs/MANUAL_TESTING.md §28.2 for the full manual checklist.
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
from promptune.daemon.platform.linux_x11 import (
    X11ActiveWindow,
    X11Clipboard,
    X11Hotkey,
    X11Notify,
)


class TestX11Hotkey:
    def test_implements_interface(self) -> None:
        assert issubclass(X11Hotkey, HotkeyBackend)

    def test_check_conflict_xgrabkey_badaccess(self) -> None:
        hk = X11Hotkey()
        with patch.object(hk, "_try_grab", return_value=False):
            assert hk.check_conflict("ctrl+shift+e") is True

    def test_check_conflict_no_conflict(self) -> None:
        hk = X11Hotkey()
        with patch.object(
            hk, "_try_grab", return_value=True
        ):
            assert hk.check_conflict("ctrl+shift+e") is False

    def test_stop_sets_event(self) -> None:
        hk = X11Hotkey()
        hk.stop()
        assert hk._stop_event.is_set()


class TestX11Clipboard:
    def test_implements_interface(self) -> None:
        assert issubclass(X11Clipboard, ClipboardBackend)

    def test_read_calls_xclip(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="clipboard text", returncode=0
            )
            result = cb.read()
            assert result == "clipboard text"
            mock_run.assert_called_once_with(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_read_returns_none_on_error(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "xclip")
        with patch("subprocess.run", side_effect=err):
            result = cb.read()
            assert result is None

    def test_write_pipes_to_xclip(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            cb.write("hello")
            mock_run.assert_called_once_with(
                ["xclip", "-selection", "clipboard"],
                input="hello",
                text=True,
                check=True,
            )

    def test_copy_selection_simulates_ctrl_c(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with (
            patch("subprocess.run") as mock_run,
            patch.object(cb, "read", return_value="selected"),
        ):
            result = cb.copy_selection()
            assert mock_run.call_args_list[0] == call(
                ["xdotool", "key", "--clearmodifiers", "ctrl+c"],
                check=True,
            )
            assert result == "selected"

    def test_paste_result_simulates_ctrl_v(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with (
            patch.object(cb, "write") as mock_write,
            patch("subprocess.run") as mock_run,
        ):
            cb.paste_result("enhanced")
            mock_write.assert_called_once_with("enhanced")
            assert mock_run.call_args_list[0] == call(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                check=True,
            )

    def test_read_strips_null_bytes(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="hello\x00world", returncode=0
            )
            result = cb.read()
            assert result == "helloworld"


class TestX11Notify:
    def test_implements_interface(self) -> None:
        assert issubclass(X11Notify, NotifyBackend)

    def test_send_calls_notify_send(self) -> None:
        n = X11Notify()
        with patch("subprocess.run") as mock_run:
            n.send("Title", "Body text")
            mock_run.assert_called_once_with(
                ["notify-send", "Title", "Body text"],
                check=False,
                timeout=5,
            )

    def test_send_truncates_long_body(self) -> None:
        n = X11Notify()
        long_body = "x" * 200
        with patch("subprocess.run") as mock_run:
            n.send("T", long_body)
            sent_body = mock_run.call_args[0][0][2]
            assert len(sent_body) <= 103
            assert sent_body.endswith("...")

    def test_send_no_op_when_missing(self) -> None:
        n = X11Notify()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            n.send("T", "B")


class TestX11ActiveWindow:
    def test_implements_interface(self) -> None:
        assert issubclass(X11ActiveWindow, ActiveWindowBackend)

    def test_returns_empty_on_error(self) -> None:
        aw = X11ActiveWindow()
        with patch.object(aw, "_get_wm_class", side_effect=Exception("no display")):
            assert aw.get_frontmost_app() == ""
