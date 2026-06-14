"""Tests for platform factory runtime detection."""

from __future__ import annotations

from unittest.mock import MagicMock, mock_open, patch

import pytest

from promptune.daemon.platform import (
    PlatformError,
    detect_session_type,
    get_platform,
    is_wsl,
)
from promptune.daemon.platform.base import PlatformBackend

_MACOS_MOD = "promptune.daemon.platform.macos"
_X11_MOD = "promptune.daemon.platform.linux_x11"
_WL_MOD = "promptune.daemon.platform.linux_wayland"
_SVC_MOD = "promptune.daemon.platform.linux_service"


class TestDetectSessionType:
    def test_xdg_session_type_wayland(self) -> None:
        env = {"XDG_SESSION_TYPE": "wayland"}
        with patch.dict("os.environ", env, clear=False):
            assert detect_session_type() == "wayland"

    def test_xdg_session_type_x11(self) -> None:
        env = {"XDG_SESSION_TYPE": "x11"}
        with patch.dict("os.environ", env, clear=False):
            assert detect_session_type() == "x11"

    def test_fallback_wayland_display(self) -> None:
        env = {"WAYLAND_DISPLAY": "wayland-0"}
        with patch.dict("os.environ", env, clear=True):
            assert detect_session_type() == "wayland"

    def test_fallback_display(self) -> None:
        env = {"DISPLAY": ":0"}
        with patch.dict("os.environ", env, clear=True):
            assert detect_session_type() == "x11"

    def test_no_display_raises(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            pytest.raises(
                PlatformError, match="display server"
            ),
        ):
            detect_session_type()


class TestIsWSL:
    def test_wsl_detected(self) -> None:
        data = (
            "Linux version 5.15.0-1044-"
            "microsoft-standard"
        )
        with patch(
            "builtins.open", mock_open(read_data=data)
        ):
            assert is_wsl() is True

    def test_not_wsl(self) -> None:
        data = "Linux version 6.8.0-40-generic"
        with patch(
            "builtins.open", mock_open(read_data=data)
        ):
            assert is_wsl() is False

    def test_no_proc_version(self) -> None:
        with patch(
            "builtins.open",
            side_effect=FileNotFoundError,
        ):
            assert is_wsl() is False


class TestGetPlatformDarwin:
    def test_darwin_returns_macos_backend(self) -> None:
        with patch("sys.platform", "darwin"):
            mock_macos = MagicMock()
            mods = {_MACOS_MOD: mock_macos}
            with patch.dict("sys.modules", mods):
                for attr in (
                    "MacOSHotkey",
                    "MacOSClipboard",
                    "MacOSNotify",
                    "MacOSService",
                    "MacOSActiveWindow",
                ):
                    getattr(
                        mock_macos, attr
                    ).return_value = MagicMock()

                result = get_platform()
                assert isinstance(
                    result, PlatformBackend
                )


class TestGetPlatformLinux:
    def test_wsl_raises(self) -> None:
        with (
            patch("sys.platform", "linux"),
            patch(
                "promptune.daemon.platform.is_wsl",
                return_value=True,
            ),
            pytest.raises(PlatformError, match="WSL"),
        ):
            get_platform()

    def test_x11_returns_x11_backend(self) -> None:
        with (
            patch("sys.platform", "linux"),
            patch(
                "promptune.daemon.platform.is_wsl",
                return_value=False,
            ),
            patch(
                "promptune.daemon.platform"
                ".detect_session_type",
                return_value="x11",
            ),
        ):
            mock_x11 = MagicMock()
            mods = {_X11_MOD: mock_x11}
            with patch.dict("sys.modules", mods):
                for attr in (
                    "X11Hotkey",
                    "X11Clipboard",
                    "X11Notify",
                    "X11ActiveWindow",
                ):
                    getattr(
                        mock_x11, attr
                    ).return_value = MagicMock()

                mock_svc = MagicMock()
                svc_mods = {_SVC_MOD: mock_svc}
                with patch.dict(
                    "sys.modules", svc_mods
                ):
                    mock_svc.LinuxService.return_value = (
                        MagicMock()
                    )
                    result = get_platform()
                    assert isinstance(
                        result, PlatformBackend
                    )

    def test_wayland_returns_wayland_backend(
        self,
    ) -> None:
        with (
            patch("sys.platform", "linux"),
            patch(
                "promptune.daemon.platform.is_wsl",
                return_value=False,
            ),
            patch(
                "promptune.daemon.platform"
                ".detect_session_type",
                return_value="wayland",
            ),
        ):
            mock_wl = MagicMock()
            mods = {_WL_MOD: mock_wl}
            with patch.dict("sys.modules", mods):
                for attr in (
                    "WaylandHotkey",
                    "WaylandClipboard",
                    "WaylandNotify",
                    "WaylandActiveWindow",
                ):
                    getattr(
                        mock_wl, attr
                    ).return_value = MagicMock()

                mock_svc = MagicMock()
                svc_mods = {_SVC_MOD: mock_svc}
                with patch.dict(
                    "sys.modules", svc_mods
                ):
                    mock_svc.LinuxService.return_value = (
                        MagicMock()
                    )
                    result = get_platform()
                    assert isinstance(
                        result, PlatformBackend
                    )

    def test_unsupported_platform_raises(self) -> None:
        with (
            patch("sys.platform", "win32"),
            pytest.raises(
                PlatformError, match="[Uu]nsupported"
            ),
        ):
            get_platform()
