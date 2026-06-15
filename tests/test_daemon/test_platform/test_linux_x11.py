"""Tests for Linux X11 platform backend.

All tests in this file run on macOS via mocked subprocess / python-xlib calls.
python-xlib is not installed on the dev/CI machine, so a fake ``Xlib`` module
tree is injected into ``sys.modules`` for the tests that exercise the
display-backed code paths (``X11Hotkey._try_grab`` / ``listen`` and
``X11ActiveWindow._get_wm_class``).

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
import sys
import types
from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, call, patch

import pytest

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
    _parse_combo,
)

# Sentinel constants used by the fake X / XK modules.
_KEY_PRESS = 2
_GRAB_MODE_ASYNC = 1


def _make_fake_xlib(
    *,
    display: MagicMock,
    keycode: int = 38,
) -> dict[str, types.ModuleType]:
    """Build a fake ``Xlib`` module tree wired to *display*.

    ``Xlib.display.Display()`` returns *display*.  ``XK.string_to_keysym``
    returns a dummy keysym and the display's ``keysym_to_keycode`` is
    pre-seeded with *keycode* unless the caller overrode it.
    """
    xlib = types.ModuleType("Xlib")

    xk = types.ModuleType("Xlib.XK")
    xk.string_to_keysym = MagicMock(return_value=0x65)  # type: ignore[attr-defined]

    x_mod = types.ModuleType("Xlib.X")
    x_mod.KeyPress = _KEY_PRESS  # type: ignore[attr-defined]
    x_mod.GrabModeAsync = _GRAB_MODE_ASYNC  # type: ignore[attr-defined]

    display_mod = types.ModuleType("Xlib.display")
    display_mod.Display = MagicMock(return_value=display)  # type: ignore[attr-defined]

    if display.keysym_to_keycode.return_value is None:
        display.keysym_to_keycode.return_value = keycode

    return {
        "Xlib": xlib,
        "Xlib.XK": xk,
        "Xlib.X": x_mod,
        "Xlib.display": display_mod,
    }


@contextmanager
def _fake_xlib(display: MagicMock, keycode: int = 38) -> Iterator[None]:
    """Install the fake Xlib tree into sys.modules for the block."""
    modules = _make_fake_xlib(display=display, keycode=keycode)
    with patch.dict(sys.modules, modules):
        yield


def _make_display(keycode: int = 38) -> MagicMock:
    """A fake python-xlib Display with a root window."""
    d = MagicMock(name="Display")
    root = MagicMock(name="root")
    d.screen.return_value.root = root
    d.keysym_to_keycode.return_value = keycode
    return d


# ---------------------------------------------------------------------------
# _parse_combo
# ---------------------------------------------------------------------------
class TestParseCombo:
    def test_full_combo(self) -> None:
        key, mask = _parse_combo("ctrl+shift+e")
        assert key == "e"
        assert mask == (1 << 2) | (1 << 0)

    def test_all_modifiers(self) -> None:
        key, mask = _parse_combo("ctrl+shift+alt+super+q")
        assert key == "q"
        assert mask == (1 << 2) | (1 << 0) | (1 << 3) | (1 << 6)

    def test_case_and_whitespace_insensitive(self) -> None:
        key, mask = _parse_combo("  CTRL +  Shift + E ")
        assert key == "e"
        assert mask == (1 << 2) | (1 << 0)

    def test_no_key_only_modifiers(self) -> None:
        key, mask = _parse_combo("ctrl+shift")
        assert key == ""
        assert mask == (1 << 2) | (1 << 0)

    def test_empty_string(self) -> None:
        key, mask = _parse_combo("")
        assert key == ""
        assert mask == 0

    def test_empty_segments_ignored(self) -> None:
        key, mask = _parse_combo("ctrl++e")
        assert key == "e"
        assert mask == (1 << 2)

    def test_non_letter_key(self) -> None:
        key, mask = _parse_combo("ctrl+space")
        assert key == "space"
        assert mask == (1 << 2)

    def test_last_non_modifier_wins(self) -> None:
        key, _ = _parse_combo("ctrl+a+b")
        assert key == "b"


# ---------------------------------------------------------------------------
# X11Hotkey
# ---------------------------------------------------------------------------
class TestX11Hotkey:
    def test_implements_interface(self) -> None:
        assert issubclass(X11Hotkey, HotkeyBackend)

    def test_register_parses_combo(self) -> None:
        hk = X11Hotkey()
        cb = MagicMock()
        hk.register("ctrl+shift+e", cb)
        assert hk._callback is cb
        assert hk._key_name == "e"
        assert hk._mod_mask == (1 << 2) | (1 << 0)

    def test_check_conflict_xgrabkey_badaccess(self) -> None:
        hk = X11Hotkey()
        with patch.object(hk, "_try_grab", return_value=False):
            assert hk.check_conflict("ctrl+shift+e") is True

    def test_check_conflict_no_conflict(self) -> None:
        hk = X11Hotkey()
        with patch.object(hk, "_try_grab", return_value=True):
            assert hk.check_conflict("ctrl+shift+e") is False

    def test_stop_sets_event(self) -> None:
        hk = X11Hotkey()
        hk.stop()
        assert hk._stop_event.is_set()

    # -- _try_grab ----------------------------------------------------------
    def test_try_grab_success_closes_display(self) -> None:
        hk = X11Hotkey()
        d = _make_display()
        with _fake_xlib(d):
            assert hk._try_grab("ctrl+shift+e") is True
        d.screen.return_value.root.grab_key.assert_called_once()
        d.screen.return_value.root.ungrab_key.assert_called_once()
        d.close.assert_called_once()

    def test_try_grab_no_key_returns_false_no_display(self) -> None:
        hk = X11Hotkey()
        d = _make_display()
        with _fake_xlib(d):
            assert hk._try_grab("ctrl+shift") is False
        # Display() should never have been opened for an empty key.
        d.close.assert_not_called()

    def test_try_grab_unknown_key_returns_false_closes_display(self) -> None:
        hk = X11Hotkey()
        d = _make_display(keycode=0)  # keysym_to_keycode -> 0 (unknown)
        with _fake_xlib(d, keycode=0):
            assert hk._try_grab("ctrl+nope") is False
        d.close.assert_called_once()

    def test_try_grab_error_handler_caught_returns_false_closes(self) -> None:
        hk = X11Hotkey()
        d = _make_display()
        root = d.screen.return_value.root

        def _grab(*args, **kwargs):  # type: ignore[no-untyped-def]
            kwargs["onerror"]("badaccess", "req")

        root.grab_key.side_effect = _grab
        with _fake_xlib(d):
            assert hk._try_grab("ctrl+shift+e") is False
        root.ungrab_key.assert_not_called()
        d.close.assert_called_once()

    def test_try_grab_exception_returns_false_closes_display(self) -> None:
        hk = X11Hotkey()
        d = _make_display()
        d.screen.return_value.root.grab_key.side_effect = RuntimeError("boom")
        with _fake_xlib(d):
            assert hk._try_grab("ctrl+shift+e") is False
        d.close.assert_called_once()

    def test_try_grab_import_error_returns_false(self) -> None:
        hk = X11Hotkey()
        # No fake Xlib installed -> ImportError inside the try block.
        with patch.dict(sys.modules, {"Xlib": None}):
            assert hk._try_grab("ctrl+shift+e") is False

    def test_try_grab_close_failure_is_swallowed(self) -> None:
        hk = X11Hotkey()
        d = _make_display()
        d.close.side_effect = RuntimeError("close failed")
        with _fake_xlib(d):
            # Even though close() raises, the grab still returns True.
            assert hk._try_grab("ctrl+shift+e") is True

    # -- listen -------------------------------------------------------------
    def test_listen_fires_callback_then_stops(self) -> None:
        hk = X11Hotkey()
        cb = MagicMock()
        hk.register("ctrl+shift+e", cb)
        d = _make_display()
        root = d.screen.return_value.root

        # One pending KeyPress event, then drain and let stop() end the loop.
        d.pending_events.side_effect = [1, 0]
        key_event = MagicMock()
        key_event.type = _KEY_PRESS
        d.next_event.return_value = key_event

        def _stop_after_first_sleep(_secs: float) -> None:
            hk.stop()

        with _fake_xlib(d), patch("time.sleep", side_effect=_stop_after_first_sleep):
            hk.listen()

        cb.assert_called_once()
        root.grab_key.assert_called_once()
        root.ungrab_key.assert_called_once()
        d.close.assert_called_once()

    def test_listen_ignores_non_keypress(self) -> None:
        hk = X11Hotkey()
        cb = MagicMock()
        hk.register("ctrl+shift+e", cb)
        d = _make_display()

        d.pending_events.side_effect = [1, 0]
        other = MagicMock()
        other.type = 999  # not KeyPress
        d.next_event.return_value = other

        with _fake_xlib(d), patch("time.sleep", side_effect=lambda _s: hk.stop()):
            hk.listen()

        cb.assert_not_called()
        d.close.assert_called_once()

    def test_listen_already_stopped_skips_loop_but_cleans_up(self) -> None:
        hk = X11Hotkey()
        hk.register("ctrl+shift+e", MagicMock())
        hk.stop()  # pre-set so the while loop body never runs
        d = _make_display()
        with _fake_xlib(d):
            hk.listen()
        d.screen.return_value.root.grab_key.assert_called_once()
        d.screen.return_value.root.ungrab_key.assert_called_once()
        d.close.assert_called_once()

    def test_listen_unknown_key_returns_without_grab(self) -> None:
        hk = X11Hotkey()
        hk.register("ctrl+shift+e", MagicMock())
        d = _make_display(keycode=0)
        with _fake_xlib(d, keycode=0):
            hk.listen()
        d.screen.return_value.root.grab_key.assert_not_called()
        # keycode is falsy, so ungrab is skipped, but display still closed.
        d.screen.return_value.root.ungrab_key.assert_not_called()
        d.close.assert_called_once()

    def test_listen_exception_mid_loop_still_cleans_up(self) -> None:
        hk = X11Hotkey()
        hk.register("ctrl+shift+e", MagicMock())
        d = _make_display()
        root = d.screen.return_value.root
        d.pending_events.side_effect = RuntimeError("boom")
        with _fake_xlib(d):
            # Should not raise; finally must run.
            hk.listen()
        root.ungrab_key.assert_called_once()
        d.close.assert_called_once()

    def test_listen_import_error_logs_and_returns(self) -> None:
        hk = X11Hotkey()
        hk.register("ctrl+shift+e", MagicMock())
        with patch.dict(sys.modules, {"Xlib": None}):
            hk.listen()  # must not raise

    def test_listen_cleanup_swallows_ungrab_and_close_failures(self) -> None:
        hk = X11Hotkey()
        hk.register("ctrl+shift+e", MagicMock())
        hk.stop()  # skip the loop body
        d = _make_display()
        root = d.screen.return_value.root
        root.ungrab_key.side_effect = RuntimeError("ungrab boom")
        d.close.side_effect = RuntimeError("close boom")
        with _fake_xlib(d):
            hk.listen()  # both cleanup failures must be swallowed
        root.ungrab_key.assert_called_once()
        d.close.assert_called_once()


# ---------------------------------------------------------------------------
# X11Clipboard
# ---------------------------------------------------------------------------
class TestX11Clipboard:
    def test_implements_interface(self) -> None:
        assert issubclass(X11Clipboard, ClipboardBackend)

    def test_read_calls_xclip(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="clipboard text", returncode=0)
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
            assert cb.read() is None

    def test_read_returns_none_when_xclip_missing(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert cb.read() is None

    def test_read_strips_null_bytes(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="hello\x00world", returncode=0)
            assert cb.read() == "helloworld"

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

    def test_write_raises_when_xclip_missing(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with (
            patch("subprocess.run", side_effect=FileNotFoundError),
            pytest.raises(RuntimeError, match="xclip failed"),
        ):
            cb.write("hello")

    def test_write_raises_on_called_process_error(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "xclip")
        with (
            patch("subprocess.run", side_effect=err),
            pytest.raises(RuntimeError, match="xclip failed"),
        ):
            cb.write("hello")

    def test_internal_write_returns_true_on_success(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with patch("subprocess.run"):
            assert cb._write("hi") is True

    def test_internal_write_returns_false_on_failure(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert cb._write("hi") is False

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

    def test_copy_selection_returns_none_when_xdotool_missing(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with (
            patch("subprocess.run", side_effect=FileNotFoundError),
            patch.object(cb, "read") as mock_read,
        ):
            assert cb.copy_selection() is None
            mock_read.assert_not_called()

    def test_copy_selection_returns_none_on_xdotool_error(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "xdotool")
        with (
            patch("subprocess.run", side_effect=err),
            patch.object(cb, "read") as mock_read,
        ):
            assert cb.copy_selection() is None
            mock_read.assert_not_called()

    def test_paste_result_simulates_ctrl_v(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with (
            patch.object(cb, "_write", return_value=True) as mock_write,
            patch("subprocess.run") as mock_run,
        ):
            cb.paste_result("enhanced")
            mock_write.assert_called_once_with("enhanced")
            assert mock_run.call_args_list[0] == call(
                ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
                check=True,
            )

    def test_paste_result_aborts_when_write_fails(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with (
            patch.object(cb, "_write", return_value=False),
            patch("subprocess.run") as mock_run,
            pytest.raises(RuntimeError, match="xclip failed"),
        ):
            cb.paste_result("enhanced")
        mock_run.assert_not_called()  # no paste keystroke

    def test_paste_result_keeps_text_when_xdotool_missing(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        with (
            patch.object(cb, "_write", return_value=True),
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            cb.paste_result("enhanced")  # must not raise; text already written

    def test_paste_result_keeps_text_on_xdotool_error(self) -> None:
        cb = X11Clipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "xdotool")
        with (
            patch.object(cb, "_write", return_value=True),
            patch("subprocess.run", side_effect=err),
        ):
            cb.paste_result("enhanced")  # must not raise


# ---------------------------------------------------------------------------
# X11Notify
# ---------------------------------------------------------------------------
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

    def test_send_short_body_not_truncated(self) -> None:
        n = X11Notify()
        with patch("subprocess.run") as mock_run:
            n.send("T", "short")
            assert mock_run.call_args[0][0][2] == "short"

    def test_send_no_op_when_missing(self) -> None:
        n = X11Notify()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            n.send("T", "B")  # must not raise

    def test_send_swallows_other_errors(self) -> None:
        n = X11Notify()
        with patch("subprocess.run", side_effect=RuntimeError("boom")):
            n.send("T", "B")  # must not raise


# ---------------------------------------------------------------------------
# X11ActiveWindow
# ---------------------------------------------------------------------------
class TestX11ActiveWindow:
    def test_implements_interface(self) -> None:
        assert issubclass(X11ActiveWindow, ActiveWindowBackend)

    def test_returns_empty_on_error(self) -> None:
        aw = X11ActiveWindow()
        with patch.object(aw, "_get_wm_class", side_effect=Exception("no display")):
            assert aw.get_frontmost_app() == ""

    def test_returns_wm_class(self) -> None:
        aw = X11ActiveWindow()
        with patch.object(aw, "_get_wm_class", return_value="firefox"):
            assert aw.get_frontmost_app() == "firefox"

    def _wire_display(self, *, response: MagicMock | None, wm_class) -> MagicMock:  # type: ignore[no-untyped-def]
        d = MagicMock(name="Display")
        root = MagicMock(name="root")
        d.screen.return_value.root = root
        d.intern_atom.return_value = 42
        root.get_full_property.return_value = response
        window = MagicMock(name="window")
        window.get_wm_class.return_value = wm_class
        d.create_resource_object.return_value = window
        return d

    def test_get_wm_class_parses_class(self) -> None:
        aw = X11ActiveWindow()
        resp = MagicMock()
        resp.value = [0x123]
        d = self._wire_display(response=resp, wm_class=("firefox", "Firefox"))
        with _fake_xlib(d):
            assert aw._get_wm_class() == "Firefox"
        d.close.assert_called_once()

    def test_get_wm_class_none_response_returns_empty(self) -> None:
        aw = X11ActiveWindow()
        d = self._wire_display(response=None, wm_class=None)
        with _fake_xlib(d):
            assert aw._get_wm_class() == ""
        d.close.assert_called_once()

    def test_get_wm_class_empty_value_returns_empty(self) -> None:
        aw = X11ActiveWindow()
        resp = MagicMock()
        resp.value = []
        d = self._wire_display(response=resp, wm_class=None)
        with _fake_xlib(d):
            assert aw._get_wm_class() == ""
        d.close.assert_called_once()

    def test_get_wm_class_no_wm_class_returns_empty(self) -> None:
        aw = X11ActiveWindow()
        resp = MagicMock()
        resp.value = [0x123]
        d = self._wire_display(response=resp, wm_class=None)
        with _fake_xlib(d):
            assert aw._get_wm_class() == ""
        d.close.assert_called_once()

    def test_get_wm_class_closes_display_on_exception(self) -> None:
        aw = X11ActiveWindow()
        d = self._wire_display(response=MagicMock(), wm_class=None)
        d.screen.return_value.root.get_full_property.side_effect = RuntimeError(
            "boom"
        )
        with _fake_xlib(d), pytest.raises(RuntimeError):
            aw._get_wm_class()
        d.close.assert_called_once()

    def test_get_wm_class_swallows_close_failure(self) -> None:
        aw = X11ActiveWindow()
        resp = MagicMock()
        resp.value = [0x123]
        d = self._wire_display(response=resp, wm_class=("firefox", "Firefox"))
        d.close.side_effect = RuntimeError("close boom")
        with _fake_xlib(d):
            # close() raises but the result is still returned cleanly.
            assert aw._get_wm_class() == "Firefox"
        d.close.assert_called_once()

    def test_get_frontmost_app_swallows_get_wm_class_exception(self) -> None:
        # End-to-end: a display-layer exception bubbles to get_frontmost_app
        # which returns "" (and the display is still closed by _get_wm_class).
        aw = X11ActiveWindow()
        d = self._wire_display(response=MagicMock(), wm_class=None)
        d.screen.return_value.root.get_full_property.side_effect = RuntimeError(
            "boom"
        )
        with _fake_xlib(d):
            assert aw.get_frontmost_app() == ""
        d.close.assert_called_once()


@pytest.mark.linux
class TestX11RealDisplay:
    """Smoke tests that require a real X11 server (skipped on macOS CI)."""

    def test_try_grab_against_real_display(self) -> None:
        # On a real X11 box this exercises the genuine XGrabKey round-trip.
        hk = X11Hotkey()
        assert isinstance(hk._try_grab("ctrl+shift+e"), bool)
