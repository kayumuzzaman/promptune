"""Tests for platform abstract base classes."""

from __future__ import annotations

import pytest

from promptune.daemon.platform.base import (
    ActiveWindowBackend,
    ClipboardBackend,
    DependencyChecker,
    DependencyStatus,
    HotkeyBackend,
    NotifyBackend,
    PlatformBackend,
    ServiceBackend,
)


class TestABCEnforcement:
    """Cannot instantiate abstract classes directly."""

    def test_hotkey_backend_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            HotkeyBackend()  # type: ignore[abstract]

    def test_clipboard_backend_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            ClipboardBackend()  # type: ignore[abstract]

    def test_notify_backend_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            NotifyBackend()  # type: ignore[abstract]

    def test_service_backend_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            ServiceBackend()  # type: ignore[abstract]

    def test_active_window_backend_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            ActiveWindowBackend()  # type: ignore[abstract]

    def test_dependency_checker_abstract(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            DependencyChecker()  # type: ignore[abstract]


class TestDependencyStatus:
    """DependencyStatus dataclass works as expected."""

    def test_installed(self) -> None:
        ds = DependencyStatus(name="xclip", installed=True, required=True)
        assert ds.name == "xclip"
        assert ds.installed is True
        assert ds.required is True

    def test_missing_optional(self) -> None:
        ds = DependencyStatus(name="notify-send", installed=False, required=False)
        assert ds.installed is False
        assert ds.required is False


class TestPlatformBackend:
    """PlatformBackend bundles all backends together."""

    def test_platform_backend_fields(self) -> None:
        class StubHotkey(HotkeyBackend):
            def register(self, combo, callback):
                pass
            def check_conflict(self, combo):
                return False
            def listen(self):
                pass
            def stop(self):
                pass

        class StubClipboard(ClipboardBackend):
            def read(self):
                return None
            def write(self, text):
                pass
            def copy_selection(self):
                return None
            def paste_result(self, text):
                pass

        class StubNotify(NotifyBackend):
            def send(self, title, body, sound=True):
                pass

        class StubService(ServiceBackend):
            def install(self):
                pass
            def uninstall(self):
                pass
            def purge(self):
                pass
            def is_installed(self):
                return False

        class StubActiveWindow(ActiveWindowBackend):
            def get_frontmost_app(self):
                return ""

        pb = PlatformBackend(
            hotkey=StubHotkey(),
            clipboard=StubClipboard(),
            notify=StubNotify(),
            service=StubService(),
            active_window=StubActiveWindow(),
        )
        assert isinstance(pb.hotkey, HotkeyBackend)
        assert isinstance(pb.clipboard, ClipboardBackend)
        assert isinstance(pb.notify, NotifyBackend)
        assert isinstance(pb.service, ServiceBackend)
        assert isinstance(pb.active_window, ActiveWindowBackend)
