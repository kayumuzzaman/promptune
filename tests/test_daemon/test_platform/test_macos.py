"""Tests for macOS platform adapter."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

if sys.platform != "darwin":
    pytest.skip("macOS-only", allow_module_level=True)

from promptune.daemon.platform.base import (  # noqa: E402
    ActiveWindowBackend,
    ClipboardBackend,
    HotkeyBackend,
    NotifyBackend,
    ServiceBackend,
)
from promptune.daemon.platform.macos import (  # noqa: E402
    MacOSActiveWindow,
    MacOSClipboard,
    MacOSHotkey,
    MacOSNotify,
    MacOSService,
)

_P = "promptune.daemon.platform.macos"
_HK = f"{_P}.hotkey_mod"
_CL = f"{_P}.clip_mod"
_NT = f"{_P}.notify_mod"
_LA = f"{_P}.la_mod"


class TestMacOSHotkey:
    def test_implements_interface(self) -> None:
        assert issubclass(MacOSHotkey, HotkeyBackend)

    def test_register_delegates(self) -> None:
        hk = MacOSHotkey()
        cb = MagicMock()
        with (
            patch(
                f"{_HK}.parse_hotkey",
                return_value=(14, 0x60000),
            ) as mock_parse,
            patch(
                f"{_HK}.register_hotkey"
            ) as mock_reg,
        ):
            hk.register("ctrl+shift+e", cb)
            mock_parse.assert_called_once_with(
                "ctrl+shift+e"
            )
            mock_reg.assert_called_once()

    def test_check_conflict_returns_false(self) -> None:
        hk = MacOSHotkey()
        assert (
            hk.check_conflict("ctrl+shift+e") is False
        )

    def test_stop_delegates(self) -> None:
        hk = MacOSHotkey()
        with patch(
            f"{_HK}.stop_run_loop"
        ) as mock_stop:
            hk.stop()
            mock_stop.assert_called_once()


class TestMacOSClipboard:
    def test_implements_interface(self) -> None:
        assert issubclass(
            MacOSClipboard, ClipboardBackend
        )

    def test_read_delegates(self) -> None:
        cb = MacOSClipboard()
        with patch(
            f"{_CL}.save_clipboard",
            return_value="text",
        ) as mock_read:
            result = cb.read()
            assert result == "text"
            mock_read.assert_called_once()

    def test_write_delegates(self) -> None:
        cb = MacOSClipboard()
        with patch(
            f"{_CL}.write_clipboard"
        ) as mock_write:
            cb.write("hello")
            mock_write.assert_called_once_with("hello")

    def test_copy_selection_delegates(self) -> None:
        cb = MacOSClipboard()
        with patch(
            f"{_CL}.copy_selection",
            return_value="sel",
        ) as mock_copy:
            result = cb.copy_selection()
            assert result == "sel"
            mock_copy.assert_called_once()

    def test_paste_result_delegates(self) -> None:
        cb = MacOSClipboard()
        with patch(
            f"{_CL}.paste_result"
        ) as mock_paste:
            cb.paste_result("enhanced")
            mock_paste.assert_called_once_with(
                "enhanced", settle_ms=100
            )

    def test_settle_ms_is_forwarded(self) -> None:
        """A configured settle_ms reaches the underlying clipboard calls."""
        cb = MacOSClipboard(settle_ms=250)
        with patch(f"{_CL}.copy_selection") as mock_copy, patch(
            f"{_CL}.paste_result"
        ) as mock_paste:
            cb.copy_selection()
            cb.paste_result("x")
            mock_copy.assert_called_once_with(settle_ms=250)
            mock_paste.assert_called_once_with("x", settle_ms=250)


class TestMacOSNotify:
    def test_implements_interface(self) -> None:
        assert issubclass(MacOSNotify, NotifyBackend)

    def test_send_delegates(self) -> None:
        n = MacOSNotify()
        with patch(
            f"{_NT}.notify"
        ) as mock_notify:
            n.send("title", "body", sound=True)
            mock_notify.assert_called_once_with(
                "title", "body", sound=True
            )


class TestMacOSService:
    def test_implements_interface(self) -> None:
        assert issubclass(MacOSService, ServiceBackend)

    def test_install_delegates(self) -> None:
        svc = MacOSService()
        with patch(
            f"{_LA}.install_login_item"
        ) as mock_install:
            svc.install()
            mock_install.assert_called_once()

    def test_uninstall_delegates(self) -> None:
        svc = MacOSService()
        with patch(
            f"{_LA}.uninstall_login_item"
        ) as mock_uninstall:
            svc.uninstall()
            mock_uninstall.assert_called_once()

    def test_is_installed_delegates(self) -> None:
        svc = MacOSService()
        with patch(
            f"{_LA}.is_installed",
            return_value=True,
        ) as mock_check:
            result = svc.is_installed()
            assert result is True
            mock_check.assert_called_once()

    def test_purge_calls_uninstall(self) -> None:
        svc = MacOSService()
        with patch(
            f"{_LA}.uninstall_login_item"
        ) as mock_uninstall:
            svc.purge()
            mock_uninstall.assert_called_once()


class TestMacOSActiveWindow:
    def test_implements_interface(self) -> None:
        assert issubclass(
            MacOSActiveWindow, ActiveWindowBackend
        )

    def test_get_frontmost_app_delegates(self) -> None:
        aw = MacOSActiveWindow()
        with patch(
            f"{_CL}.get_frontmost_app",
            return_value="com.apple.Terminal",
        ) as mock_get:
            result = aw.get_frontmost_app()
            assert result == "com.apple.Terminal"
            mock_get.assert_called_once()
