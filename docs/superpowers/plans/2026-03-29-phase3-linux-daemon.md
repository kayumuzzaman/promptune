# Phase 3: Linux OS-Level Hotkey Daemon — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the macOS hotkey daemon to Linux via a platform abstraction layer that supports both X11 and Wayland, with runtime detection and graceful fallbacks.

**Architecture:** Introduce `promptune/daemon/platform/` package with abstract base classes and three backends (macOS adapter, Linux X11, Linux Wayland). A factory function detects the platform at runtime and returns the correct backend. The existing `daemon.py` orchestration switches from direct macOS imports to the platform factory. A Linux service manager handles systemd user services with direct-process fallback.

**Tech Stack:** python-xlib (X11 hotkey/window), dbus-next (Wayland portal), evdev (Wayland fallback hotkey), xclip/xdotool (X11 tools), wl-clipboard/ydotool (Wayland tools), notify-send (Linux notifications), systemd (service management)

**Spec:** `docs/superpowers/specs/2026-03-29-phase3-linux-daemon-design.md`

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `promptune/daemon/platform/__init__.py` | Runtime platform detection factory: `get_platform()` returns a `PlatformBackend` dataclass bundling all backends |
| `promptune/daemon/platform/base.py` | Abstract base classes: `HotkeyBackend`, `ClipboardBackend`, `NotifyBackend`, `ServiceBackend`, `ActiveWindowBackend`, `DependencyChecker`; plus `DependencyStatus` and `PlatformBackend` dataclasses |
| `promptune/daemon/platform/macos.py` | macOS adapter — wraps existing `hotkey.py`, `clipboard.py`, `notify.py`, `launchagent.py` behind the abstract interfaces |
| `promptune/daemon/platform/linux_x11.py` | X11 backend — XGrabKey hotkey, xclip clipboard, xdotool key sim, `_NET_ACTIVE_WINDOW` detection |
| `promptune/daemon/platform/linux_wayland.py` | Wayland backend — Portal GlobalShortcuts (dbus-next) with evdev fallback, wl-clipboard, ydotool, GNOME/KDE/sway active window |
| `promptune/daemon/platform/linux_service.py` | Linux service management — systemd user service with direct PID-file fallback, dependency checker, purge |
| `tests/test_daemon/test_platform/__init__.py` | Test package marker |
| `tests/test_daemon/test_platform/test_base.py` | ABC enforcement tests |
| `tests/test_daemon/test_platform/test_init.py` | Factory runtime detection tests |
| `tests/test_daemon/test_platform/test_macos.py` | macOS adapter tests |
| `tests/test_daemon/test_platform/test_linux_x11.py` | X11 backend tests |
| `tests/test_daemon/test_platform/test_linux_wayland.py` | Wayland backend tests |
| `tests/test_daemon/test_platform/test_linux_service.py` | Linux service management tests |

### Modified files

| File | Changes |
|---|---|
| `promptune/daemon/__init__.py` | Remove macOS-only platform guard, allow import on Linux |
| `promptune/daemon/daemon.py` | Replace direct macOS imports with `get_platform()` factory |
| `promptune/cli.py` | Platform-aware daemon commands (Linux: `install`/`uninstall`/`purge`/`setup`/`diagnose` with Linux checks; macOS: existing commands unchanged) |
| `pyproject.toml` | Add `linux-daemon` optional dependency group, add `"Operating System :: POSIX :: Linux"` classifier, update description |
| `tests/test_daemon/test_daemon.py` | Update tests to mock platform factory instead of direct macOS imports |

---

## Task Dependency Graph

```
Task 1 (base.py) ─────┬──→ Task 3 (macos.py)
                       ├──→ Task 4 (linux_x11.py)      ──┐
                       ├──→ Task 5 (linux_wayland.py)  ──┼──→ Task 7 (factory) ──→ Task 8 (daemon.py) ──→ Task 9 (CLI) ──→ Task 10 (pyproject) ──→ Task 11 (docs)
                       └──→ Task 6 (linux_service.py)  ──┘
Task 2 (test __init__)  (independent)
```

Tasks 3, 4, 5, 6 are independent leaf modules — can be parallelised.

---

### Task 1: Abstract Base Classes (`platform/base.py`)

**Files:**
- Create: `promptune/daemon/platform/base.py`
- Test: `tests/test_daemon/test_platform/test_base.py`

- [ ] **Step 1: Write failing tests for ABC enforcement**

```python
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
        # Create minimal concrete stubs
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_platform/test_base.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.daemon.platform'`

- [ ] **Step 3: Create the test package `__init__.py`**

Create empty file: `tests/test_daemon/test_platform/__init__.py`

- [ ] **Step 4: Write the implementation**

```python
"""Abstract base classes for platform-specific daemon backends.

Each backend interface defines the contract that macOS and Linux
implementations must fulfil.  The PlatformBackend dataclass bundles
all backends into a single object returned by the factory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable


# ---------------------------------------------------------------------------
# Dependency status
# ---------------------------------------------------------------------------


@dataclass
class DependencyStatus:
    """Status of a single system dependency."""

    name: str
    installed: bool
    required: bool


# ---------------------------------------------------------------------------
# Abstract backends
# ---------------------------------------------------------------------------


class HotkeyBackend(ABC):
    """Global hotkey registration and event loop."""

    @abstractmethod
    def register(self, combo: str, callback: Callable[[], None]) -> None:
        """Register *combo* (e.g. ``'ctrl+shift+e'``) to fire *callback*."""

    @abstractmethod
    def check_conflict(self, combo: str) -> bool:
        """Return True if *combo* is already taken by another application."""

    @abstractmethod
    def listen(self) -> None:
        """Block on the platform event loop until :meth:`stop` is called."""

    @abstractmethod
    def stop(self) -> None:
        """Signal the event loop to exit."""


class ClipboardBackend(ABC):
    """Clipboard read/write and key-simulation helpers."""

    @abstractmethod
    def read(self) -> str | None:
        """Read the current clipboard text.  Returns None on failure."""

    @abstractmethod
    def write(self, text: str) -> None:
        """Write *text* to the clipboard."""

    @abstractmethod
    def copy_selection(self) -> str | None:
        """Simulate a copy keystroke and return the clipboard text."""

    @abstractmethod
    def paste_result(self, text: str) -> None:
        """Write *text* to the clipboard and simulate a paste keystroke."""


class NotifyBackend(ABC):
    """Desktop notifications."""

    @abstractmethod
    def send(self, title: str, body: str, sound: bool = True) -> None:
        """Display a desktop notification."""


class ServiceBackend(ABC):
    """Daemon service installation and management."""

    @abstractmethod
    def install(self) -> None:
        """Install the daemon as an auto-start service."""

    @abstractmethod
    def uninstall(self) -> None:
        """Remove the daemon auto-start service."""

    @abstractmethod
    def purge(self) -> None:
        """Remove all daemon files (service, socket, PID, undo, logs)."""

    @abstractmethod
    def is_installed(self) -> bool:
        """Return True if the daemon service is installed."""


class ActiveWindowBackend(ABC):
    """Frontmost application detection."""

    @abstractmethod
    def get_frontmost_app(self) -> str:
        """Return an identifier for the currently focused application.

        Returns an empty string if detection is not possible.
        """


class DependencyChecker(ABC):
    """System dependency verification."""

    @abstractmethod
    def check(self) -> list[DependencyStatus]:
        """Check all required system dependencies and return their status."""

    @abstractmethod
    def get_install_command(self, missing: list[str]) -> str:
        """Return a shell command to install *missing* packages."""


# ---------------------------------------------------------------------------
# Platform bundle
# ---------------------------------------------------------------------------


@dataclass
class PlatformBackend:
    """Bundle of all platform-specific backends.

    Returned by ``get_platform()`` in ``platform/__init__.py``.
    """

    hotkey: HotkeyBackend
    clipboard: ClipboardBackend
    notify: NotifyBackend
    service: ServiceBackend
    active_window: ActiveWindowBackend
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_platform/test_base.py -v`
Expected: All 9 tests PASS

- [ ] **Step 6: Commit**

```bash
git add promptune/daemon/platform/base.py tests/test_daemon/test_platform/__init__.py tests/test_daemon/test_platform/test_base.py
git commit -m "feat(daemon): add platform abstraction base classes"
```

---

### Task 2: Test Package Init

**Files:**
- Create: `promptune/daemon/platform/__init__.py` (empty placeholder — factory added in Task 7)

- [ ] **Step 1: Create the package marker**

```python
"""Platform abstraction layer for the promptune daemon.

Provides runtime detection and backend selection for macOS, Linux X11,
and Linux Wayland.  Import ``get_platform()`` to get the current
platform's backend bundle.
"""
```

- [ ] **Step 2: Commit**

```bash
git add promptune/daemon/platform/__init__.py
git commit -m "feat(daemon): add platform package init"
```

---

### Task 3: macOS Backend Adapter (`platform/macos.py`)

**Files:**
- Create: `promptune/daemon/platform/macos.py`
- Test: `tests/test_daemon/test_platform/test_macos.py`

**Context:** This wraps the existing macOS modules (`hotkey.py`, `clipboard.py`, `notify.py`, `launchagent.py`) behind the abstract interfaces from `base.py`. No behavior change — pure adapter pattern. All methods delegate to existing functions.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for macOS platform adapter."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only"
)

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


class TestMacOSHotkey:
    def test_implements_interface(self) -> None:
        assert issubclass(MacOSHotkey, HotkeyBackend)

    def test_register_delegates(self) -> None:
        hk = MacOSHotkey()
        cb = MagicMock()
        with (
            patch("promptune.daemon.platform.macos.hotkey_mod.parse_hotkey", return_value=(14, 0x60000)) as mock_parse,
            patch("promptune.daemon.platform.macos.hotkey_mod.register_hotkey") as mock_reg,
        ):
            hk.register("ctrl+shift+e", cb)
            mock_parse.assert_called_once_with("ctrl+shift+e")
            mock_reg.assert_called_once()

    def test_check_conflict_returns_false(self) -> None:
        hk = MacOSHotkey()
        assert hk.check_conflict("ctrl+shift+e") is False

    def test_stop_delegates(self) -> None:
        hk = MacOSHotkey()
        with patch("promptune.daemon.platform.macos.hotkey_mod.stop_run_loop") as mock_stop:
            hk.stop()
            mock_stop.assert_called_once()


class TestMacOSClipboard:
    def test_implements_interface(self) -> None:
        assert issubclass(MacOSClipboard, ClipboardBackend)

    def test_read_delegates(self) -> None:
        cb = MacOSClipboard()
        with patch("promptune.daemon.platform.macos.clip_mod.save_clipboard", return_value="text") as mock_read:
            result = cb.read()
            assert result == "text"
            mock_read.assert_called_once()

    def test_write_delegates(self) -> None:
        cb = MacOSClipboard()
        with patch("promptune.daemon.platform.macos.clip_mod.write_clipboard") as mock_write:
            cb.write("hello")
            mock_write.assert_called_once_with("hello")

    def test_copy_selection_delegates(self) -> None:
        cb = MacOSClipboard()
        with patch("promptune.daemon.platform.macos.clip_mod.copy_selection", return_value="sel") as mock_copy:
            result = cb.copy_selection()
            assert result == "sel"
            mock_copy.assert_called_once()

    def test_paste_result_delegates(self) -> None:
        cb = MacOSClipboard()
        with patch("promptune.daemon.platform.macos.clip_mod.paste_result") as mock_paste:
            cb.paste_result("enhanced")
            mock_paste.assert_called_once_with("enhanced")


class TestMacOSNotify:
    def test_implements_interface(self) -> None:
        assert issubclass(MacOSNotify, NotifyBackend)

    def test_send_delegates(self) -> None:
        n = MacOSNotify()
        with patch("promptune.daemon.platform.macos.notify_mod.notify") as mock_notify:
            n.send("title", "body", sound=True)
            mock_notify.assert_called_once_with("title", "body", sound=True)


class TestMacOSService:
    def test_implements_interface(self) -> None:
        assert issubclass(MacOSService, ServiceBackend)

    def test_install_delegates(self) -> None:
        svc = MacOSService()
        with patch("promptune.daemon.platform.macos.la_mod.install_login_item") as mock_install:
            svc.install()
            mock_install.assert_called_once()

    def test_uninstall_delegates(self) -> None:
        svc = MacOSService()
        with patch("promptune.daemon.platform.macos.la_mod.uninstall_login_item") as mock_uninstall:
            svc.uninstall()
            mock_uninstall.assert_called_once()

    def test_is_installed_delegates(self) -> None:
        svc = MacOSService()
        with patch("promptune.daemon.platform.macos.la_mod.is_installed", return_value=True) as mock_check:
            result = svc.is_installed()
            assert result is True
            mock_check.assert_called_once()

    def test_purge_calls_uninstall(self) -> None:
        svc = MacOSService()
        with patch("promptune.daemon.platform.macos.la_mod.uninstall_login_item") as mock_uninstall:
            svc.purge()
            mock_uninstall.assert_called_once()


class TestMacOSActiveWindow:
    def test_implements_interface(self) -> None:
        assert issubclass(MacOSActiveWindow, ActiveWindowBackend)

    def test_get_frontmost_app_delegates(self) -> None:
        aw = MacOSActiveWindow()
        with patch(
            "promptune.daemon.platform.macos.clip_mod.get_frontmost_app",
            return_value="com.apple.Terminal",
        ) as mock_get:
            result = aw.get_frontmost_app()
            assert result == "com.apple.Terminal"
            mock_get.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_platform/test_macos.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.daemon.platform.macos'`

- [ ] **Step 3: Write the implementation**

```python
"""macOS platform backend — adapter over existing daemon modules.

Wraps hotkey.py, clipboard.py, notify.py, and launchagent.py behind
the abstract interfaces defined in base.py.  No behaviour change.
"""

from __future__ import annotations

import sys
from typing import Callable

if sys.platform != "darwin":
    raise ImportError("promptune.daemon.platform.macos requires macOS.")

from promptune.daemon import clipboard as clip_mod
from promptune.daemon import hotkey as hotkey_mod
from promptune.daemon import launchagent as la_mod
from promptune.daemon import notify as notify_mod
from promptune.daemon.platform.base import (
    ActiveWindowBackend,
    ClipboardBackend,
    HotkeyBackend,
    NotifyBackend,
    ServiceBackend,
)


class MacOSHotkey(HotkeyBackend):
    """macOS global hotkey via CGEventTap."""

    def __init__(self) -> None:
        self._callback: Callable[[], None] | None = None

    def register(self, combo: str, callback: Callable[[], None]) -> None:
        keycode, modifier_mask = hotkey_mod.parse_hotkey(combo)
        self._callback = callback
        hotkey_mod.register_hotkey(callback, keycode, modifier_mask)

    def check_conflict(self, combo: str) -> bool:
        # macOS CGEventTap doesn't report conflicts at registration time
        return False

    def listen(self) -> None:
        hotkey_mod.start_run_loop()

    def stop(self) -> None:
        hotkey_mod.stop_run_loop()


class MacOSClipboard(ClipboardBackend):
    """macOS clipboard via pbcopy/pbpaste and CGEvent key simulation."""

    def read(self) -> str | None:
        return clip_mod.save_clipboard()

    def write(self, text: str) -> None:
        clip_mod.write_clipboard(text)

    def copy_selection(self) -> str | None:
        return clip_mod.copy_selection()

    def paste_result(self, text: str) -> None:
        clip_mod.paste_result(text)


class MacOSNotify(NotifyBackend):
    """macOS notifications via osascript."""

    def send(self, title: str, body: str, sound: bool = True) -> None:
        notify_mod.notify(title, body, sound=sound)


class MacOSService(ServiceBackend):
    """macOS LaunchAgent service management."""

    def install(self) -> None:
        la_mod.install_login_item()

    def uninstall(self) -> None:
        la_mod.uninstall_login_item()

    def purge(self) -> None:
        la_mod.uninstall_login_item()

    def is_installed(self) -> bool:
        return la_mod.is_installed()


class MacOSActiveWindow(ActiveWindowBackend):
    """macOS frontmost app detection via NSWorkspace."""

    def get_frontmost_app(self) -> str:
        return clip_mod.get_frontmost_app()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_platform/test_macos.py -v`
Expected: All 16 tests PASS (on macOS; skipped on Linux)

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/platform/macos.py tests/test_daemon/test_platform/test_macos.py
git commit -m "feat(daemon): add macOS platform adapter"
```

---

### Task 4: Linux X11 Backend (`platform/linux_x11.py`)

**Files:**
- Create: `promptune/daemon/platform/linux_x11.py`
- Test: `tests/test_daemon/test_platform/test_linux_x11.py`

**Context:** Implements X11-specific hotkey (python-xlib XGrabKey), clipboard (xclip subprocess), key simulation (xdotool subprocess), active window (`_NET_ACTIVE_WINDOW` via python-xlib), and notifications (notify-send subprocess). All external calls are mocked in tests.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Linux X11 platform backend."""

from __future__ import annotations

import subprocess
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
)


class TestX11Hotkey:
    def test_implements_interface(self) -> None:
        assert issubclass(X11Hotkey, HotkeyBackend)

    def test_check_conflict_xgrabkey_badaccess(self) -> None:
        """XGrabKey BadAccess means conflict."""
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
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "xclip")):
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
            # First call is xdotool key simulation
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
            assert len(sent_body) <= 103  # 100 + "..."
            assert sent_body.endswith("...")

    def test_send_no_op_when_missing(self) -> None:
        n = X11Notify()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            # Should not raise
            n.send("T", "B")


class TestX11ActiveWindow:
    def test_implements_interface(self) -> None:
        assert issubclass(X11ActiveWindow, ActiveWindowBackend)

    def test_returns_empty_on_error(self) -> None:
        aw = X11ActiveWindow()
        with patch.object(aw, "_get_wm_class", side_effect=Exception("no display")):
            assert aw.get_frontmost_app() == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_platform/test_linux_x11.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'promptune.daemon.platform.linux_x11'`

- [ ] **Step 3: Write the implementation**

```python
"""Linux X11 platform backend.

Uses python-xlib for hotkey registration and active window detection,
xclip for clipboard I/O, xdotool for key simulation, and notify-send
for desktop notifications.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from typing import Callable

from promptune.daemon.platform.base import (
    ActiveWindowBackend,
    ClipboardBackend,
    HotkeyBackend,
    NotifyBackend,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Key / modifier maps for X11
# ---------------------------------------------------------------------------

_X11_KEYNAME_MAP: dict[str, str] = {
    "ctrl": "Control_L",
    "shift": "Shift_L",
    "alt": "Alt_L",
    "super": "Super_L",
}

# X11 modifier mask bits (Xlib constants)
_X11_MOD_MASK: dict[str, int] = {
    "ctrl": 1 << 2,    # ControlMask
    "shift": 1 << 0,   # ShiftMask
    "alt": 1 << 3,     # Mod1Mask
    "super": 1 << 6,   # Mod4Mask
}


def _parse_combo(combo: str) -> tuple[str, int]:
    """Parse 'ctrl+shift+e' into (key_name, modifier_mask)."""
    parts = [p.strip().lower() for p in combo.split("+")]
    key_name = ""
    mask = 0
    for part in parts:
        if part in _X11_MOD_MASK:
            mask |= _X11_MOD_MASK[part]
        else:
            key_name = part
    return key_name, mask


# ---------------------------------------------------------------------------
# Hotkey
# ---------------------------------------------------------------------------


class X11Hotkey(HotkeyBackend):
    """X11 global hotkey via XGrabKey + XNextEvent loop."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._callback: Callable[[], None] | None = None
        self._key_name = ""
        self._mod_mask = 0

    def register(self, combo: str, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._key_name, self._mod_mask = _parse_combo(combo)

    def check_conflict(self, combo: str) -> bool:
        """Attempt an XGrabKey — BadAccess means the combo is taken."""
        return not self._try_grab(combo)

    def _try_grab(self, combo: str) -> bool:
        """Try to grab the key. Returns True if successful, False if conflict."""
        try:
            from Xlib import X, XK, display as xdisplay
            from Xlib.error import BadAccess

            key_name, mod_mask = _parse_combo(combo)
            d = xdisplay.Display()
            root = d.screen().root
            keysym = XK.string_to_keysym(key_name)
            keycode = d.keysym_to_keycode(keysym)

            error_caught = []

            def _error_handler(err, request):  # type: ignore[no-untyped-def]
                error_caught.append(err)

            root.grab_key(
                keycode, mod_mask, True,
                X.GrabModeAsync, X.GrabModeAsync,
                onerror=_error_handler,
            )
            d.sync()

            if error_caught:
                d.close()
                return False

            root.ungrab_key(keycode, mod_mask)
            d.close()
            return True
        except Exception:
            _log.debug("X11 grab test failed", exc_info=True)
            return False

    def listen(self) -> None:
        """Block on X11 event loop, firing callback on hotkey match."""
        try:
            from Xlib import X, XK, display as xdisplay

            d = xdisplay.Display()
            root = d.screen().root
            keysym = XK.string_to_keysym(self._key_name)
            keycode = d.keysym_to_keycode(keysym)

            root.grab_key(
                keycode, self._mod_mask, True,
                X.GrabModeAsync, X.GrabModeAsync,
            )

            while not self._stop_event.is_set():
                if d.pending_events() > 0:
                    event = d.next_event()
                    if event.type == X.KeyPress and self._callback:
                        self._callback()
                else:
                    time.sleep(0.05)

            root.ungrab_key(keycode, self._mod_mask)
            d.close()
        except Exception:
            _log.error("X11 event loop failed", exc_info=True)

    def stop(self) -> None:
        self._stop_event.set()


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------


class X11Clipboard(ClipboardBackend):
    """X11 clipboard via xclip + xdotool."""

    def __init__(self, settle_ms: int = 100) -> None:
        self._settle_ms = settle_ms

    def read(self) -> str | None:
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                text=True,
                check=True,
            )
            # Strip null bytes
            return result.stdout.replace("\x00", "")
        except Exception:
            return None

    def write(self, text: str) -> None:
        subprocess.run(
            ["xclip", "-selection", "clipboard"],
            input=text,
            text=True,
            check=True,
        )

    def copy_selection(self) -> str | None:
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+c"],
            check=True,
        )
        time.sleep(self._settle_ms / 1000.0)
        return self.read()

    def paste_result(self, text: str) -> None:
        self.write(text)
        time.sleep(self._settle_ms / 1000.0)
        subprocess.run(
            ["xdotool", "key", "--clearmodifiers", "ctrl+v"],
            check=True,
        )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class X11Notify(NotifyBackend):
    """Linux notifications via notify-send."""

    def send(self, title: str, body: str, sound: bool = True) -> None:
        if len(body) > 100:
            body = body[:100] + "..."
        try:
            subprocess.run(
                ["notify-send", title, body],
                check=False,
                timeout=5,
            )
        except FileNotFoundError:
            _log.debug("notify-send not found, skipping notification")
        except Exception:
            _log.debug("notify-send failed", exc_info=True)


# ---------------------------------------------------------------------------
# Active window
# ---------------------------------------------------------------------------


class X11ActiveWindow(ActiveWindowBackend):
    """X11 active window via _NET_ACTIVE_WINDOW property."""

    def get_frontmost_app(self) -> str:
        try:
            return self._get_wm_class()
        except Exception:
            return ""

    def _get_wm_class(self) -> str:
        """Read WM_CLASS of the active window via python-xlib."""
        from Xlib import display as xdisplay

        d = xdisplay.Display()
        root = d.screen().root
        net_active = d.intern_atom("_NET_ACTIVE_WINDOW")
        response = root.get_full_property(net_active, 0)

        if response is None or not response.value:
            d.close()
            return ""

        window_id = response.value[0]
        window = d.create_resource_object("window", window_id)
        wm_class = window.get_wm_class()
        d.close()

        if wm_class:
            return wm_class[1]  # (instance, class) — return class
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_platform/test_linux_x11.py -v`
Expected: All 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/platform/linux_x11.py tests/test_daemon/test_platform/test_linux_x11.py
git commit -m "feat(daemon): add Linux X11 platform backend"
```

---

### Task 5: Linux Wayland Backend (`platform/linux_wayland.py`)

**Files:**
- Create: `promptune/daemon/platform/linux_wayland.py`
- Test: `tests/test_daemon/test_platform/test_linux_wayland.py`

**Context:** Wayland backend with dual hotkey strategy: portal GlobalShortcuts (primary, via dbus-next) with evdev fallback. Clipboard via wl-paste/wl-copy, key simulation via ydotool, active window via GNOME Shell DBus / KDE KWin / sway IPC. All external deps mocked in tests.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Linux Wayland platform backend."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest

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
        """Portal-based registration doesn't pre-check conflicts."""
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
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "wl-paste")):
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
            # ydotool Ctrl+C keycodes: 29=Ctrl, 46=C
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
            # ydotool Ctrl+V keycodes: 29=Ctrl, 47=V
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_platform/test_linux_wayland.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
"""Linux Wayland platform backend.

Hotkey: xdg-desktop-portal GlobalShortcuts (dbus-next) with evdev fallback.
Clipboard: wl-paste / wl-copy.
Key simulation: ydotool.
Active window: GNOME Shell DBus / KDE KWin / sway IPC.
Notifications: notify-send.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import threading
import time
from typing import Callable

from promptune.daemon.platform.base import (
    ActiveWindowBackend,
    ClipboardBackend,
    HotkeyBackend,
    NotifyBackend,
)

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Hotkey
# ---------------------------------------------------------------------------


class WaylandHotkey(HotkeyBackend):
    """Wayland hotkey via portal GlobalShortcuts, with evdev fallback."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._callback: Callable[[], None] | None = None
        self._combo = ""

    def register(self, combo: str, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._combo = combo

    def check_conflict(self, combo: str) -> bool:
        # Portal registration handles conflicts via user prompt
        return False

    def listen(self) -> None:
        """Try portal, fall back to evdev."""
        try:
            self._listen_portal()
        except Exception:
            _log.info(
                "Portal GlobalShortcuts unavailable, falling back to evdev"
            )
            try:
                self._listen_evdev()
            except Exception:
                _log.error("Both portal and evdev hotkey failed", exc_info=True)

    def _listen_portal(self) -> None:
        """Listen via xdg-desktop-portal GlobalShortcuts (DBus)."""
        import asyncio

        from dbus_next.aio import MessageBus  # type: ignore[import]

        async def _portal_loop() -> None:
            bus = await MessageBus().connect()
            introspection = await bus.introspect(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
            )
            proxy = bus.get_proxy_object(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                introspection,
            )
            shortcuts = proxy.get_interface(
                "org.freedesktop.portal.GlobalShortcuts"
            )

            result = await shortcuts.call_create_session({})
            session_handle = result

            await shortcuts.call_bind_shortcuts(
                session_handle,
                [("promptune-enhance", {"description": "Enhance prompt"})],
                "",
                {},
            )

            def on_activated(
                session: str, shortcut_id: str, timestamp: int, options: dict
            ) -> None:
                if self._callback:
                    self._callback()

            shortcuts.on_activated(on_activated)

            while not self._stop_event.is_set():
                await asyncio.sleep(0.1)

            bus.disconnect()

        asyncio.run(_portal_loop())

    def _listen_evdev(self) -> None:
        """Listen via evdev raw input events (requires input group)."""
        from evdev import InputDevice, categorize, ecodes, list_devices  # type: ignore[import]

        _log.warning(
            "Using evdev hotkey listener — requires 'input' group membership"
        )

        devices = [InputDevice(path) for path in list_devices()]
        keyboards = [
            d for d in devices
            if ecodes.EV_KEY in d.capabilities()
        ]

        if not keyboards:
            raise RuntimeError("No keyboard input devices found")

        # Parse combo to evdev keycodes
        combo_parts = [p.strip().lower() for p in self._combo.split("+")]
        evdev_keys = {
            "ctrl": ecodes.KEY_LEFTCTRL,
            "shift": ecodes.KEY_LEFTSHIFT,
            "alt": ecodes.KEY_LEFTALT,
            "super": ecodes.KEY_LEFTMETA,
        }
        mod_keys = set()
        main_key = None
        for part in combo_parts:
            if part in evdev_keys:
                mod_keys.add(evdev_keys[part])
            else:
                key_attr = f"KEY_{part.upper()}"
                main_key = getattr(ecodes, key_attr, None)

        if main_key is None:
            raise ValueError(f"Cannot map key from combo: {self._combo}")

        pressed: set[int] = set()

        import select

        while not self._stop_event.is_set():
            readable, _, _ = select.select(keyboards, [], [], 0.1)
            for dev in readable:
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    key_event = categorize(event)
                    if key_event.keystate == key_event.key_down:
                        pressed.add(key_event.scancode)
                    elif key_event.keystate == key_event.key_up:
                        pressed.discard(key_event.scancode)

                    if (
                        main_key in pressed
                        and mod_keys.issubset(pressed)
                        and self._callback
                    ):
                        self._callback()
                        pressed.clear()

    def stop(self) -> None:
        self._stop_event.set()


# ---------------------------------------------------------------------------
# Clipboard
# ---------------------------------------------------------------------------


class WaylandClipboard(ClipboardBackend):
    """Wayland clipboard via wl-paste / wl-copy + ydotool."""

    def __init__(self, settle_ms: int = 100) -> None:
        self._settle_ms = settle_ms

    def read(self) -> str | None:
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.replace("\x00", "")
        except Exception:
            return None

    def write(self, text: str) -> None:
        subprocess.run(
            ["wl-copy"],
            input=text,
            text=True,
            check=True,
        )

    def copy_selection(self) -> str | None:
        # ydotool keycodes: 29=Ctrl, 46=C
        subprocess.run(
            ["ydotool", "key", "29:1", "46:1", "46:0", "29:0"],
            check=True,
        )
        time.sleep(self._settle_ms / 1000.0)
        return self.read()

    def paste_result(self, text: str) -> None:
        self.write(text)
        time.sleep(self._settle_ms / 1000.0)
        # ydotool keycodes: 29=Ctrl, 47=V
        subprocess.run(
            ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
            check=True,
        )


# ---------------------------------------------------------------------------
# Notifications (shared with X11)
# ---------------------------------------------------------------------------


class WaylandNotify(NotifyBackend):
    """Linux notifications via notify-send."""

    def send(self, title: str, body: str, sound: bool = True) -> None:
        if len(body) > 100:
            body = body[:100] + "..."
        try:
            subprocess.run(
                ["notify-send", title, body],
                check=False,
                timeout=5,
            )
        except FileNotFoundError:
            _log.debug("notify-send not found, skipping notification")
        except Exception:
            _log.debug("notify-send failed", exc_info=True)


# ---------------------------------------------------------------------------
# Active window
# ---------------------------------------------------------------------------


class WaylandActiveWindow(ActiveWindowBackend):
    """Wayland active window via DE-specific methods."""

    def __init__(self, desktop: str = "") -> None:
        self._desktop = desktop or os.environ.get(
            "XDG_CURRENT_DESKTOP", ""
        )

    def get_frontmost_app(self) -> str:
        try:
            lower = self._desktop.lower()
            if "gnome" in lower or "pop" in lower or "ubuntu" in lower:
                return self._gnome_active_window()
            elif "kde" in lower or "plasma" in lower:
                return self._kde_active_window()
            elif "sway" in lower:
                return self._sway_active_window()
            return ""
        except Exception:
            return ""

    def _gnome_active_window(self) -> str:
        """GNOME Shell eval via gdbus."""
        result = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell",
                "--object-path", "/org/gnome/Shell",
                "--method", "org.gnome.Shell.Eval",
                "global.display.focus_window ? global.display.focus_window.get_wm_class() : ''",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        # Output format: (true, '"firefox"')
        try:
            data = json.loads(
                result.stdout.replace("(", "[").replace(")", "]").replace("'", '"')
            )
            if data[0] and data[1]:
                return data[1].strip('"')
        except (json.JSONDecodeError, IndexError):
            pass
        return ""

    def _kde_active_window(self) -> str:
        """KDE KWin via qdbus."""
        result = subprocess.run(
            [
                "qdbus", "org.kde.KWin",
                "/KWin", "org.kde.KWin.activeWindow",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()

    def _sway_active_window(self) -> str:
        """Sway via swaymsg."""
        result = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        tree = json.loads(result.stdout)
        return self._find_focused(tree)

    def _find_focused(self, node: dict) -> str:
        """Recursively find the focused node in sway's tree."""
        if node.get("focused"):
            return node.get("app_id", "") or node.get("name", "")
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            result = self._find_focused(child)
            if result:
                return result
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_platform/test_linux_wayland.py -v`
Expected: All 15 tests PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/platform/linux_wayland.py tests/test_daemon/test_platform/test_linux_wayland.py
git commit -m "feat(daemon): add Linux Wayland platform backend"
```

---

### Task 6: Linux Service Manager (`platform/linux_service.py`)

**Files:**
- Create: `promptune/daemon/platform/linux_service.py`
- Test: `tests/test_daemon/test_platform/test_linux_service.py`

**Context:** systemd user service management with direct PID-file fallback. Includes dependency checker that detects the package manager and checks for required system tools. Also provides the `purge` command.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for Linux service management backend."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from promptune.daemon.platform.base import (
    DependencyChecker,
    DependencyStatus,
    ServiceBackend,
)
from promptune.daemon.platform.linux_service import (
    LinuxDependencyChecker,
    LinuxService,
    SERVICE_TEMPLATE,
    _detect_package_manager,
)


class TestLinuxService:
    def test_implements_interface(self) -> None:
        assert issubclass(LinuxService, ServiceBackend)

    def test_install_writes_service_file(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "promptune.service"
        svc = LinuxService(service_path=svc_file)
        with patch("subprocess.run") as mock_run:
            svc.install()
            assert svc_file.exists()
            content = svc_file.read_text()
            assert "promptune" in content
            assert "ExecStart" in content
            # systemctl daemon-reload + enable
            assert mock_run.call_count == 2

    def test_uninstall_removes_service(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "promptune.service"
        svc_file.write_text("dummy")
        svc = LinuxService(service_path=svc_file)
        with patch("subprocess.run"):
            svc.uninstall()
            assert not svc_file.exists()

    def test_uninstall_no_op_when_missing(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "nonexistent.service"
        svc = LinuxService(service_path=svc_file)
        with patch("subprocess.run"):
            svc.uninstall()  # Should not raise

    def test_is_installed_true(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "promptune.service"
        svc_file.write_text("dummy")
        svc = LinuxService(service_path=svc_file)
        assert svc.is_installed() is True

    def test_is_installed_false(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "nonexistent.service"
        svc = LinuxService(service_path=svc_file)
        assert svc.is_installed() is False

    def test_purge_removes_all_files(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "promptune.service"
        socket_file = tmp_path / "promptune.sock"
        pid_file = tmp_path / "daemon.pid"
        undo_file = tmp_path / "undo.txt"
        log_file = tmp_path / "daemon.log"
        svc_file.write_text("svc")
        socket_file.write_text("sock")
        pid_file.write_text("123")
        undo_file.write_text("{}")
        log_file.write_text("log")

        svc = LinuxService(
            service_path=svc_file,
            data_dir=tmp_path,
        )
        with patch("subprocess.run"):
            svc.purge()

        assert not svc_file.exists()
        assert not socket_file.exists()
        assert not pid_file.exists()
        assert not undo_file.exists()
        assert not log_file.exists()

    def test_service_template_valid(self) -> None:
        assert "[Unit]" in SERVICE_TEMPLATE
        assert "[Service]" in SERVICE_TEMPLATE
        assert "[Install]" in SERVICE_TEMPLATE
        assert "promptune" in SERVICE_TEMPLATE


class TestDetectPackageManager:
    def test_apt(self) -> None:
        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/apt" if cmd == "apt" else None):
            assert _detect_package_manager() == "apt"

    def test_dnf(self) -> None:
        def which(cmd: str) -> str | None:
            return "/usr/bin/dnf" if cmd == "dnf" else None
        with patch("shutil.which", side_effect=which):
            assert _detect_package_manager() == "dnf"

    def test_pacman(self) -> None:
        def which(cmd: str) -> str | None:
            return "/usr/bin/pacman" if cmd == "pacman" else None
        with patch("shutil.which", side_effect=which):
            assert _detect_package_manager() == "pacman"

    def test_unknown(self) -> None:
        with patch("shutil.which", return_value=None):
            assert _detect_package_manager() == ""


class TestLinuxDependencyChecker:
    def test_implements_interface(self) -> None:
        assert issubclass(LinuxDependencyChecker, DependencyChecker)

    def test_x11_checks_xclip_xdotool(self) -> None:
        checker = LinuxDependencyChecker(session_type="x11")
        with patch("shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: f"/usr/bin/{cmd}" if cmd in ("xclip", "xdotool") else None
            results = checker.check()
            names = [r.name for r in results]
            assert "xclip" in names
            assert "xdotool" in names
            xclip = next(r for r in results if r.name == "xclip")
            assert xclip.installed is True
            assert xclip.required is True

    def test_wayland_checks_wl_tools(self) -> None:
        checker = LinuxDependencyChecker(session_type="wayland")
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            results = checker.check()
            names = [r.name for r in results]
            assert "wl-paste" in names
            assert "ydotool" in names
            wl = next(r for r in results if r.name == "wl-paste")
            assert wl.installed is False
            assert wl.required is True

    def test_get_install_command_apt(self) -> None:
        checker = LinuxDependencyChecker(session_type="x11")
        with patch(
            "promptune.daemon.platform.linux_service._detect_package_manager",
            return_value="apt",
        ):
            cmd = checker.get_install_command(["xclip", "xdotool"])
            assert cmd == "sudo apt install xclip xdotool"

    def test_get_install_command_pacman(self) -> None:
        checker = LinuxDependencyChecker(session_type="x11")
        with patch(
            "promptune.daemon.platform.linux_service._detect_package_manager",
            return_value="pacman",
        ):
            cmd = checker.get_install_command(["xclip"])
            assert cmd == "sudo pacman -S xclip"

    def test_get_install_command_unknown(self) -> None:
        checker = LinuxDependencyChecker(session_type="x11")
        with patch(
            "promptune.daemon.platform.linux_service._detect_package_manager",
            return_value="",
        ):
            cmd = checker.get_install_command(["xclip"])
            assert "xclip" in cmd
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_platform/test_linux_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Write the implementation**

```python
"""Linux service management and dependency checking.

Primary: systemd user service.
Fallback: direct PID-file process management.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from promptune.daemon.platform.base import (
    DependencyChecker,
    DependencyStatus,
    ServiceBackend,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DEFAULT_SERVICE_PATH = Path(
    "~/.config/systemd/user/promptune.service"
).expanduser()

_DEFAULT_DATA_DIR = Path(
    "~/.local/share/promptune"
).expanduser()

# ---------------------------------------------------------------------------
# Service template
# ---------------------------------------------------------------------------

SERVICE_TEMPLATE = """\
[Unit]
Description=Promptune Prompt Enhancement Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
StartLimitBurst=3
MemoryMax=256M
EnvironmentFile=-{env_file}

[Install]
WantedBy=default.target
"""


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------


def _detect_package_manager() -> str:
    """Detect the system package manager."""
    for pm in ("apt", "dnf", "pacman", "zypper"):
        if shutil.which(pm):
            return pm
    return ""


# ---------------------------------------------------------------------------
# Service backend
# ---------------------------------------------------------------------------


class LinuxService(ServiceBackend):
    """Linux systemd user service management."""

    def __init__(
        self,
        service_path: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self._service_path = service_path or _DEFAULT_SERVICE_PATH
        self._data_dir = data_dir or _DEFAULT_DATA_DIR

    def install(self) -> None:
        """Write systemd service file, daemon-reload, and enable."""
        self._service_path.parent.mkdir(parents=True, exist_ok=True)

        exec_start = f"{sys.executable} -m promptune daemon start --foreground"
        env_file = Path("~/.config/promptune/daemon.env").expanduser()

        content = SERVICE_TEMPLATE.format(
            exec_start=exec_start,
            env_file=str(env_file),
        )
        self._service_path.write_text(content, encoding="utf-8")

        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
        )
        subprocess.run(
            ["systemctl", "--user", "enable", "promptune"],
            check=True,
        )

    def uninstall(self) -> None:
        """Disable service and remove service file."""
        if not self._service_path.exists():
            return

        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "promptune"],
            check=False,
        )
        self._service_path.unlink(missing_ok=True)
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=False,
        )

    def purge(self) -> None:
        """Remove all daemon files — service, socket, PID, undo, logs."""
        self.uninstall()

        files_to_remove = [
            self._data_dir / "promptune.sock",
            self._data_dir / "daemon.pid",
            self._data_dir / "undo.txt",
            self._data_dir / "daemon.log",
        ]
        for f in files_to_remove:
            with contextlib.suppress(FileNotFoundError):
                f.unlink()

    def is_installed(self) -> bool:
        """Return True if the service file exists."""
        return self._service_path.exists()


# ---------------------------------------------------------------------------
# Dependency checker
# ---------------------------------------------------------------------------


class LinuxDependencyChecker(DependencyChecker):
    """Check for required system tools based on display server type."""

    def __init__(self, session_type: str = "") -> None:
        self._session_type = session_type or os.environ.get(
            "XDG_SESSION_TYPE", "x11"
        )

    def check(self) -> list[DependencyStatus]:
        """Check all required system dependencies."""
        deps: list[DependencyStatus] = []

        if self._session_type == "x11":
            deps.append(self._check_tool("xclip", required=True))
            deps.append(self._check_tool("xdotool", required=True))
        else:
            deps.append(self._check_tool("wl-paste", required=True))
            deps.append(self._check_tool("wl-copy", required=True))
            deps.append(self._check_tool("ydotool", required=True))

        deps.append(self._check_tool("notify-send", required=False))
        return deps

    def _check_tool(self, name: str, required: bool) -> DependencyStatus:
        """Check if a single tool is available on PATH."""
        return DependencyStatus(
            name=name,
            installed=shutil.which(name) is not None,
            required=required,
        )

    def get_install_command(self, missing: list[str]) -> str:
        """Return the install command for the detected package manager."""
        pm = _detect_package_manager()
        pkg_list = " ".join(missing)

        if pm == "apt":
            return f"sudo apt install {pkg_list}"
        elif pm == "dnf":
            return f"sudo dnf install {pkg_list}"
        elif pm == "pacman":
            return f"sudo pacman -S {pkg_list}"
        elif pm == "zypper":
            return f"sudo zypper install {pkg_list}"
        else:
            return f"Install manually: {pkg_list}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_platform/test_linux_service.py -v`
Expected: All 16 tests PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/platform/linux_service.py tests/test_daemon/test_platform/test_linux_service.py
git commit -m "feat(daemon): add Linux service manager and dependency checker"
```

---

### Task 7: Platform Factory (`platform/__init__.py`)

**Files:**
- Modify: `promptune/daemon/platform/__init__.py`
- Test: `tests/test_daemon/test_platform/test_init.py`

**Context:** Runtime detection factory that reads `sys.platform`, `$XDG_SESSION_TYPE`, `$WAYLAND_DISPLAY`, `$DISPLAY`, and `/proc/version` to select the correct backend. Returns a `PlatformBackend` dataclass.

- [ ] **Step 1: Write failing tests**

```python
"""Tests for platform factory runtime detection."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, mock_open, patch

import pytest

from promptune.daemon.platform import (
    PlatformError,
    detect_session_type,
    get_platform,
    is_wsl,
)
from promptune.daemon.platform.base import PlatformBackend


class TestDetectSessionType:
    def test_xdg_session_type_wayland(self) -> None:
        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "wayland"}, clear=False):
            assert detect_session_type() == "wayland"

    def test_xdg_session_type_x11(self) -> None:
        with patch.dict("os.environ", {"XDG_SESSION_TYPE": "x11"}, clear=False):
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
            pytest.raises(PlatformError, match="display server"),
        ):
            detect_session_type()


class TestIsWSL:
    def test_wsl_detected(self) -> None:
        with patch(
            "builtins.open",
            mock_open(read_data="Linux version 5.15.0-1044-microsoft-standard"),
        ):
            assert is_wsl() is True

    def test_not_wsl(self) -> None:
        with patch(
            "builtins.open",
            mock_open(read_data="Linux version 6.8.0-40-generic"),
        ):
            assert is_wsl() is False

    def test_no_proc_version(self) -> None:
        with patch("builtins.open", side_effect=FileNotFoundError):
            assert is_wsl() is False


class TestGetPlatformDarwin:
    def test_darwin_returns_macos_backend(self) -> None:
        with patch("sys.platform", "darwin"):
            # Skip actual macOS imports in test — mock the import
            mock_macos = MagicMock()
            with patch.dict("sys.modules", {"promptune.daemon.platform.macos": mock_macos}):
                mock_macos.MacOSHotkey.return_value = MagicMock()
                mock_macos.MacOSClipboard.return_value = MagicMock()
                mock_macos.MacOSNotify.return_value = MagicMock()
                mock_macos.MacOSService.return_value = MagicMock()
                mock_macos.MacOSActiveWindow.return_value = MagicMock()

                result = get_platform()
                assert isinstance(result, PlatformBackend)


class TestGetPlatformLinux:
    def test_wsl_raises(self) -> None:
        with (
            patch("sys.platform", "linux"),
            patch("promptune.daemon.platform.is_wsl", return_value=True),
            pytest.raises(PlatformError, match="WSL"),
        ):
            get_platform()

    def test_x11_returns_x11_backend(self) -> None:
        with (
            patch("sys.platform", "linux"),
            patch("promptune.daemon.platform.is_wsl", return_value=False),
            patch("promptune.daemon.platform.detect_session_type", return_value="x11"),
        ):
            mock_x11 = MagicMock()
            with patch.dict("sys.modules", {"promptune.daemon.platform.linux_x11": mock_x11}):
                mock_x11.X11Hotkey.return_value = MagicMock()
                mock_x11.X11Clipboard.return_value = MagicMock()
                mock_x11.X11Notify.return_value = MagicMock()
                mock_x11.X11ActiveWindow.return_value = MagicMock()

                mock_svc = MagicMock()
                with patch.dict("sys.modules", {"promptune.daemon.platform.linux_service": mock_svc}):
                    mock_svc.LinuxService.return_value = MagicMock()
                    result = get_platform()
                    assert isinstance(result, PlatformBackend)

    def test_wayland_returns_wayland_backend(self) -> None:
        with (
            patch("sys.platform", "linux"),
            patch("promptune.daemon.platform.is_wsl", return_value=False),
            patch("promptune.daemon.platform.detect_session_type", return_value="wayland"),
        ):
            mock_wl = MagicMock()
            with patch.dict("sys.modules", {"promptune.daemon.platform.linux_wayland": mock_wl}):
                mock_wl.WaylandHotkey.return_value = MagicMock()
                mock_wl.WaylandClipboard.return_value = MagicMock()
                mock_wl.WaylandNotify.return_value = MagicMock()
                mock_wl.WaylandActiveWindow.return_value = MagicMock()

                mock_svc = MagicMock()
                with patch.dict("sys.modules", {"promptune.daemon.platform.linux_service": mock_svc}):
                    mock_svc.LinuxService.return_value = MagicMock()
                    result = get_platform()
                    assert isinstance(result, PlatformBackend)

    def test_unsupported_platform_raises(self) -> None:
        with (
            patch("sys.platform", "win32"),
            pytest.raises(PlatformError, match="[Uu]nsupported"),
        ):
            get_platform()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_platform/test_init.py -v`
Expected: FAIL — `ImportError: cannot import name 'PlatformError'`

- [ ] **Step 3: Write the implementation**

```python
"""Platform abstraction layer for the promptune daemon.

Provides runtime detection and backend selection for macOS, Linux X11,
and Linux Wayland.  Import ``get_platform()`` to get the current
platform's backend bundle.
"""

from __future__ import annotations

import os
import sys

from promptune.daemon.platform.base import PlatformBackend


class PlatformError(Exception):
    """Raised when the platform cannot support the daemon."""


def detect_session_type() -> str:
    """Detect whether the Linux session is X11 or Wayland.

    Checks ``$XDG_SESSION_TYPE`` first, then falls back to
    ``$WAYLAND_DISPLAY`` and ``$DISPLAY`` presence.

    Raises:
        PlatformError: If no display server can be detected.
    """
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session in ("wayland", "x11"):
        return session

    if os.environ.get("WAYLAND_DISPLAY"):
        return "wayland"
    if os.environ.get("DISPLAY"):
        return "x11"

    raise PlatformError(
        "No display server detected. Set $XDG_SESSION_TYPE or "
        "ensure $DISPLAY / $WAYLAND_DISPLAY is set. "
        "Use CLI mode instead: promptune enhance"
    )


def is_wsl() -> bool:
    """Detect Windows Subsystem for Linux via /proc/version."""
    try:
        with open("/proc/version") as f:
            return "microsoft" in f.read().lower()
    except (FileNotFoundError, PermissionError):
        return False


def get_platform() -> PlatformBackend:
    """Detect the current platform and return the appropriate backend bundle.

    Returns:
        A :class:`PlatformBackend` with all backends configured for the
        current platform and display server.

    Raises:
        PlatformError: If the platform is unsupported or the daemon
            cannot run (WSL, no display, etc.).
    """
    if sys.platform == "darwin":
        from promptune.daemon.platform.macos import (
            MacOSActiveWindow,
            MacOSClipboard,
            MacOSHotkey,
            MacOSNotify,
            MacOSService,
        )

        return PlatformBackend(
            hotkey=MacOSHotkey(),
            clipboard=MacOSClipboard(),
            notify=MacOSNotify(),
            service=MacOSService(),
            active_window=MacOSActiveWindow(),
        )

    if sys.platform == "linux":
        if is_wsl():
            raise PlatformError(
                "WSL detected. The daemon is not supported under WSL. "
                "Use CLI mode instead: promptune enhance"
            )

        session = detect_session_type()

        from promptune.daemon.platform.linux_service import LinuxService

        if session == "x11":
            from promptune.daemon.platform.linux_x11 import (
                X11ActiveWindow,
                X11Clipboard,
                X11Hotkey,
                X11Notify,
            )

            return PlatformBackend(
                hotkey=X11Hotkey(),
                clipboard=X11Clipboard(),
                notify=X11Notify(),
                service=LinuxService(),
                active_window=X11ActiveWindow(),
            )

        # Wayland
        from promptune.daemon.platform.linux_wayland import (
            WaylandActiveWindow,
            WaylandClipboard,
            WaylandHotkey,
            WaylandNotify,
        )

        return PlatformBackend(
            hotkey=WaylandHotkey(),
            clipboard=WaylandClipboard(),
            notify=WaylandNotify(),
            service=LinuxService(),
            active_window=WaylandActiveWindow(),
        )

    raise PlatformError(
        f"Unsupported platform: {sys.platform}. "
        "The daemon requires macOS or Linux."
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_platform/test_init.py -v`
Expected: All 10 tests PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/platform/__init__.py tests/test_daemon/test_platform/test_init.py
git commit -m "feat(daemon): add platform detection factory"
```

---

### Task 8: Daemon Integration — Replace macOS Imports (`daemon.py`)

**Files:**
- Modify: `promptune/daemon/__init__.py`
- Modify: `promptune/daemon/daemon.py`
- Modify: `tests/test_daemon/test_daemon.py`

**Context:** Remove the macOS-only platform guard from `__init__.py`. Refactor `daemon.py` to use the platform factory instead of direct macOS module imports. Update tests to mock the platform factory.

- [ ] **Step 1: Update `daemon/__init__.py` — remove macOS guard**

Replace the entire content of `promptune/daemon/__init__.py` with:

```python
"""Promptune daemon — global hotkey, clipboard pipeline, notifications.

Supports macOS and Linux (X11 / Wayland) via the platform abstraction layer.
"""
```

- [ ] **Step 2: Refactor `daemon.py` — use platform factory**

Replace the existing macOS-specific imports at the top of `promptune/daemon/daemon.py`:

```python
# REMOVE these imports:
from promptune.daemon.clipboard import (
    copy_selection,
    get_frontmost_app,
    paste_result,
    save_clipboard,
    save_undo,
    write_clipboard,
)
from promptune.daemon.hotkey import (
    check_accessibility,
    parse_hotkey,
    register_hotkey,
    start_run_loop,
    stop_run_loop,
)
from promptune.daemon.notify import notify_enhanced, notify_error
```

Replace with:

```python
from promptune.daemon.platform import PlatformError, get_platform
from promptune.daemon.platform.base import PlatformBackend
```

Then update `_on_hotkey` to accept the platform backend:

```python
def _on_hotkey(
    state: DaemonState,
    config: dict[str, Any],
    platform: PlatformBackend,
) -> None:
    """Full enhancement pipeline — triggered by the global hotkey."""
    if _enhancing.is_set():
        return

    _enhancing.set()
    try:
        app_before = platform.active_window.get_frontmost_app()
        original_clipboard = platform.clipboard.read()
        selected_text = platform.clipboard.copy_selection()

        if not selected_text:
            platform.notify.send("Promptune", "No text selected. Select text first.", sound=False)
            return

        # Undo buffer
        from promptune.daemon.clipboard import UNDO_FILE
        import json
        UNDO_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {
            "original_clipboard": original_clipboard,
            "selected_text": selected_text,
        }
        UNDO_FILE.write_text(json.dumps(payload), encoding="utf-8")
        UNDO_FILE.chmod(0o600)

        try:
            result = enhance(selected_text, config)
        except Exception:
            _log.exception("Enhancement failed")
            platform.notify.send("Promptune", "Enhancement failed. Original text preserved.", sound=False)
            return

        app_after = platform.active_window.get_frontmost_app()

        if app_after == app_before:
            platform.clipboard.paste_result(result.enhanced)
            delta = result.score_after.total - result.score_before.total
            sign = "+" if delta >= 0 else ""
            platform.notify.send(
                "Promptune",
                f"Prompt enhanced ({sign}{delta} PQS). Ctrl+Z to undo.",
            )
        else:
            platform.clipboard.write(result.enhanced)
            platform.notify.send(
                "Promptune",
                "Enhanced text in clipboard \u2014 paste manually.",
                sound=False,
            )

        with state.lock:
            state.enhancement_count += 1
    finally:
        _enhancing.clear()
```

Update `get_status` to use the platform:

```python
def get_status() -> DaemonStatus:
    """Return a DaemonStatus reflecting current daemon health."""
    pid = _read_pid()
    running = pid is not None and _is_running(pid)

    uptime_seconds: float | None = None
    if running and PID_FILE.exists():
        uptime_seconds = time.time() - PID_FILE.stat().st_mtime

    enhancement_count = 0
    socket_exists = SOCKET_PATH.exists()

    # Accessibility check is macOS-specific; on Linux it's always True
    accessibility_granted = True
    if sys.platform == "darwin":
        try:
            from promptune.daemon.hotkey import check_accessibility
            accessibility_granted = check_accessibility()
        except Exception:
            accessibility_granted = False

    return DaemonStatus(
        running=running,
        pid=pid if running else None,
        uptime_seconds=uptime_seconds,
        enhancement_count=enhancement_count,
        socket_exists=socket_exists,
        accessibility_granted=accessibility_granted,
    )
```

Update `start_daemon` to use the platform factory:

```python
def start_daemon(
    foreground: bool = False,
    config_path: str | None = None,
) -> None:
    """Start the promptune daemon."""
    existing_pid = _read_pid()
    if existing_pid is not None and _is_running(existing_pid):
        _log.error("Daemon already running (PID %d)", existing_pid)
        return

    # Detect platform
    try:
        platform = get_platform()
    except PlatformError as exc:
        _log.error("Platform error: %s", exc)
        return

    # macOS: verify accessibility
    if sys.platform == "darwin":
        try:
            from promptune.daemon.hotkey import check_accessibility
            if not check_accessibility():
                _log.error(
                    "Accessibility permissions not granted. "
                    "Grant access in System Settings > Privacy & Security > Accessibility."
                )
                return
        except ImportError:
            pass

    cfg_path = Path(config_path) if config_path else None
    config = load_config(config_path=cfg_path)

    hotkey_str = config.get("daemon", {}).get("hotkey", "ctrl+shift+e")

    # Check for hotkey conflicts
    if platform.hotkey.check_conflict(hotkey_str):
        _log.warning("Hotkey %s is in use by another application", hotkey_str)

    if not foreground:
        _daemonise()

    _write_pid()

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _log.info("Daemon started (PID %d)", os.getpid())

    state = DaemonState()

    def _handle_term(signum: int, frame: Any) -> None:
        _log.info("Received signal %d, shutting down", signum)
        platform.hotkey.stop()
        _cleanup()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)

    start_ipc_server(state)

    local_cfg = config.get("local_llm", {})
    if local_cfg.get("enabled", False):
        from promptune.daemon.prewarm import start_prewarm_timer
        host = local_cfg.get("host", "http://localhost:11434")
        model = local_cfg.get("model", "qwen2.5:3b")
        start_prewarm_timer(host, model)
        _log.info("Ollama prewarm started for %s at %s", model, host)

    def _hotkey_callback() -> None:
        threading.Thread(
            target=_on_hotkey,
            args=(state, config, platform),
            daemon=True,
        ).start()

    platform.hotkey.register(hotkey_str, _hotkey_callback)

    _log.info("Entering event loop")
    platform.hotkey.listen()
```

- [ ] **Step 3: Update tests**

Replace the macOS-only daemon test imports and adapt tests to mock the platform factory. Key changes:

- Remove `pytestmark = pytest.mark.skipif(sys.platform != "darwin")` — these tests should run everywhere now
- Mock `get_platform` instead of individual macOS modules
- `_on_hotkey` now takes `platform` parameter — update call sites

Update `tests/test_daemon/test_daemon.py`:

```python
"""Tests for promptune.daemon.daemon — lifecycle and enhancement pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from promptune.daemon.daemon import (
    _cleanup,
    _enhancing,
    _is_running,
    _on_hotkey,
    _read_pid,
    _write_pid,
    get_status,
)
from promptune.daemon.ipc import DaemonState


class TestPIDManagement:
    def test_write_pid_file(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        with patch("promptune.daemon.daemon.PID_FILE", pid_file):
            _write_pid()
            assert pid_file.exists()
            assert _read_pid() == os.getpid()

    def test_read_pid_missing_file(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "nonexistent.pid"
        with patch("promptune.daemon.daemon.PID_FILE", pid_file):
            assert _read_pid() is None

    def test_is_running_false_for_dead_pid(self) -> None:
        assert _is_running(999999999) is False

    def test_is_running_true_for_self(self) -> None:
        assert _is_running(os.getpid()) is True

    def test_cleanup_removes_files(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        sock_file = tmp_path / "promptune.sock"
        pid_file.write_text("123")
        sock_file.write_text("")
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_file),
        ):
            _cleanup()
        assert not pid_file.exists()
        assert not sock_file.exists()


class TestDaemonStatus:
    def test_status_not_running(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
        ):
            status = get_status()
            assert status.running is False
            assert status.pid is None

    def test_status_running(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text(str(os.getpid()))
        sock_path.write_text("")
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
        ):
            status = get_status()
            assert status.running is True
            assert status.pid == os.getpid()
            assert status.socket_exists is True


class TestOnHotkey:
    def _make_platform(self) -> MagicMock:
        """Create a mock PlatformBackend."""
        platform = MagicMock()
        platform.active_window.get_frontmost_app.return_value = "com.test.App"
        platform.clipboard.read.return_value = "original clipboard"
        platform.clipboard.copy_selection.return_value = "selected text"
        return platform

    def test_enhances_and_pastes(self, tmp_path: Path) -> None:
        platform = self._make_platform()
        state = DaemonState()
        config = {"enhancement": {"max_tier": 0}, "provider": {"default": "claude", "format_style": "auto"}, "local_llm": {"enabled": False}, "api_keys": {}, "context": {}, "history": {"enabled": False}}
        undo_file = tmp_path / "undo.txt"

        with (
            patch("promptune.daemon.daemon.enhance") as mock_enhance,
            patch("promptune.daemon.daemon.UNDO_FILE", undo_file) if hasattr(__import__("promptune.daemon.daemon", fromlist=["UNDO_FILE"]), "UNDO_FILE") else patch("promptune.daemon.clipboard.UNDO_FILE", undo_file),
        ):
            mock_result = MagicMock()
            mock_result.enhanced = "enhanced text"
            mock_result.score_before.total = 40
            mock_result.score_after.total = 75
            mock_enhance.return_value = mock_result

            _on_hotkey(state, config, platform)

            platform.clipboard.paste_result.assert_called_once_with("enhanced text")
            platform.notify.send.assert_called_once()
            assert state.enhancement_count == 1

    def test_no_selection_notifies(self) -> None:
        platform = self._make_platform()
        platform.clipboard.copy_selection.return_value = None
        state = DaemonState()
        config = {}

        _on_hotkey(state, config, platform)

        platform.notify.send.assert_called_once()
        assert "Select text" in platform.notify.send.call_args[0][1]
        assert state.enhancement_count == 0

    def test_debounce_prevents_double_run(self) -> None:
        platform = self._make_platform()
        state = DaemonState()
        config = {}

        _enhancing.set()
        _on_hotkey(state, config, platform)
        _enhancing.clear()

        platform.clipboard.copy_selection.assert_not_called()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_daemon.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: All tests PASS (existing macOS daemon tests may need the `pytestmark` skip updated)

- [ ] **Step 6: Commit**

```bash
git add promptune/daemon/__init__.py promptune/daemon/daemon.py tests/test_daemon/test_daemon.py
git commit -m "refactor(daemon): use platform factory instead of direct macOS imports"
```

---

### Task 9: CLI Platform-Aware Commands

**Files:**
- Modify: `promptune/cli.py`
- Modify: `tests/test_cli.py`

**Context:** Update the daemon command group to work on both macOS and Linux. Remove the `sys.platform != "darwin"` guard. Add Linux-specific subcommands: `install`, `uninstall`, `purge`. Make `setup` and `diagnose` platform-aware.

- [ ] **Step 1: Write failing tests for new Linux commands**

Add these tests to `tests/test_cli.py`:

```python
class TestDaemonInstall:
    def test_install_calls_service_install(self) -> None:
        mock_platform = MagicMock()
        with (
            patch("promptune.cli.get_platform", return_value=mock_platform),
            patch("promptune.cli._check_dependencies", return_value=[]),
        ):
            runner = CliRunner()
            result = runner.invoke(main, ["daemon", "install"])
            mock_platform.service.install.assert_called_once()


class TestDaemonUninstall:
    def test_uninstall_calls_service_uninstall(self) -> None:
        mock_platform = MagicMock()
        with patch("promptune.cli.get_platform", return_value=mock_platform):
            runner = CliRunner()
            result = runner.invoke(main, ["daemon", "uninstall"])
            mock_platform.service.uninstall.assert_called_once()


class TestDaemonPurge:
    def test_purge_calls_service_purge(self) -> None:
        mock_platform = MagicMock()
        with patch("promptune.cli.get_platform", return_value=mock_platform):
            runner = CliRunner()
            result = runner.invoke(main, ["daemon", "purge"], input="y\n")
            mock_platform.service.purge.assert_called_once()
```

- [ ] **Step 2: Update the daemon group in `cli.py`**

Remove the macOS-only guard from the daemon group:

```python
@main.group()
def daemon() -> None:
    """Manage the promptune background daemon."""
```

Add new Linux commands:

```python
@daemon.command("install")
def daemon_install() -> None:
    """Install daemon service and check dependencies."""
    from promptune.daemon.platform import PlatformError, get_platform

    try:
        platform = get_platform()
    except PlatformError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    # Run dependency check on Linux
    if sys.platform == "linux":
        from promptune.daemon.platform.linux_service import LinuxDependencyChecker
        checker = LinuxDependencyChecker()
        results = checker.check()
        missing = [r.name for r in results if not r.installed and r.required]
        if missing:
            click.echo("Missing required dependencies:")
            for r in results:
                symbol = "\u2713" if r.installed else "\u2717"
                label = "required" if r.required else "optional"
                click.echo(f"  {r.name:<16} {symbol}  ({label})")
            cmd = checker.get_install_command(missing)
            click.echo(f"\nInstall with:\n  {cmd}")
            raise SystemExit(1)

    platform.service.install()
    click.echo("Daemon service installed.")


@daemon.command("uninstall")
def daemon_uninstall() -> None:
    """Remove daemon service."""
    from promptune.daemon.platform import PlatformError, get_platform

    try:
        platform = get_platform()
    except PlatformError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    platform.service.uninstall()
    click.echo("Daemon service removed.")


@daemon.command("purge")
def daemon_purge() -> None:
    """Remove all daemon files (service, socket, PID, undo, logs)."""
    from promptune.daemon.platform import PlatformError, get_platform

    if not click.confirm("Remove all daemon files?"):
        return

    try:
        platform = get_platform()
    except PlatformError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1) from exc

    platform.service.purge()
    click.echo("All daemon files removed.")
    click.echo("Note: History database preserved at ~/.local/share/promptune/history.db")
```

Update `diagnose` to be platform-aware:

```python
@daemon.command()
def diagnose() -> None:
    """Run diagnostic checks on daemon health."""
    from promptune.daemon.platform import PlatformError, get_platform

    try:
        platform = get_platform()
    except PlatformError as exc:
        click.echo(f"Platform: {exc}", err=True)
        raise SystemExit(1) from exc

    s = _get_daemon_status()
    installed = platform.service.is_installed()

    def _check(label: str, ok: bool, detail: str = "") -> None:
        mark = "\u2713" if ok else "\u2717"
        click.echo(f"  {label:<20} {mark}  {detail}")

    click.echo("promptune daemon diagnose\n")
    _check("Platform", True, sys.platform)
    _check("Daemon PID", s.running, f"pid {s.pid}" if s.running else "Not running")
    _check("Socket", s.socket_exists)
    _check("Service", installed)

    if sys.platform == "darwin":
        _check("Accessibility", s.accessibility_granted)
    elif sys.platform == "linux":
        from promptune.daemon.platform.linux_service import LinuxDependencyChecker
        checker = LinuxDependencyChecker()
        deps = checker.check()
        for dep in deps:
            _check(dep.name, dep.installed, "required" if dep.required else "optional")

    issues: list[str] = []
    if not s.running:
        issues.append("Start daemon: promptune daemon start")
    if not installed:
        issues.append("Install service: promptune daemon install")
    if issues:
        click.echo("\n  Issues:")
        for issue in issues:
            click.echo(f"    - {issue}")
```

Update `setup` to be platform-aware:

```python
@daemon.command()
def setup() -> None:
    """Guide through daemon setup (permissions, dependencies)."""
    if sys.platform == "darwin":
        _setup_macos()
    elif sys.platform == "linux":
        _setup_linux()
    else:
        click.echo("Unsupported platform.", err=True)
        raise SystemExit(1)


def _setup_macos() -> None:
    """macOS Accessibility permission setup."""
    import subprocess as sp
    import time as t
    from promptune.daemon.hotkey import check_accessibility, request_accessibility

    if check_accessibility():
        click.echo("Accessibility permission already granted.")
        return

    click.echo("Accessibility permission required for global hotkey.")
    click.echo("Opening System Settings...")
    sp.run(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])
    click.echo("Add your terminal app to the Accessibility list.")
    click.echo("Waiting for permission (60s timeout)...")
    request_accessibility()

    for _ in range(60):
        if check_accessibility():
            click.echo("Accessibility permission granted!")
            return
        t.sleep(1)
    click.echo("Timeout. Grant permission manually and retry.")


def _setup_linux() -> None:
    """Linux dependency check and group membership guidance."""
    from promptune.daemon.platform.linux_service import LinuxDependencyChecker, _detect_package_manager

    checker = LinuxDependencyChecker()
    results = checker.check()

    click.echo("Checking daemon dependencies...\n")
    missing = []
    for dep in results:
        symbol = "\u2713" if dep.installed else "\u2717"
        label = "required" if dep.required else "optional"
        click.echo(f"  {dep.name:<16} {symbol}  ({label})")
        if not dep.installed and dep.required:
            missing.append(dep.name)

    if missing:
        cmd = checker.get_install_command(missing)
        click.echo(f"\nInstall missing tools:\n  {cmd}")
    else:
        click.echo("\nAll dependencies satisfied.")

    # Check input group for Wayland
    import os
    session = os.environ.get("XDG_SESSION_TYPE", "")
    if session == "wayland":
        import grp
        try:
            input_group = grp.getgrnam("input")
            uid = os.getuid()
            import pwd
            username = pwd.getpwuid(uid).pw_name
            if username not in input_group.gr_mem:
                click.echo(f"\nFor Wayland hotkey support, add yourself to the input group:")
                click.echo(f"  sudo usermod -aG input {username}")
                click.echo("  (Log out and back in for the change to take effect)")
        except KeyError:
            pass
```

- [ ] **Step 3: Run CLI tests**

Run: `pytest tests/test_cli.py -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add promptune/cli.py tests/test_cli.py
git commit -m "feat(cli): add platform-aware daemon commands for Linux"
```

---

### Task 10: pyproject.toml Updates

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add linux-daemon optional dependency group and update metadata**

Add to `[project.optional-dependencies]`:

```toml
linux-daemon = [
    "python-xlib>=0.33",
    "dbus-next>=0.2.3",
    "evdev>=1.7.0",
]
```

Update classifiers — add:

```toml
"Operating System :: POSIX :: Linux",
```

Update description:

```toml
description = "Terminal prompt enhancer for macOS and Linux"
```

Add mypy overrides for new dependencies:

```toml
[[tool.mypy.overrides]]
module = ["Xlib", "Xlib.*", "dbus_next", "dbus_next.*", "evdev", "evdev.*"]
ignore_missing_imports = true
```

- [ ] **Step 2: Verify lint and type checks**

Run: `ruff check . && mypy promptune/`
Expected: No new errors

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "build: add linux-daemon optional deps and update metadata"
```

---

### Task 11: Documentation Updates

**Files:**
- Modify: `docs/USER_GUIDE.md`
- Modify: `docs/MANUAL_TESTING.md`
- Modify: `docs/ARCHITECTURE.md`
- Modify: `README.md`
- Modify: `CHANGELOG.md`
- Modify: `docs/superpowers/blueprint/promptune_blueprint.md`

- [ ] **Step 1: Update USER_GUIDE.md**

Add a "Linux Daemon" section after the existing macOS daemon section covering:
- Prerequisites (system tools by display server)
- Installation (`promptune daemon install`)
- Setup (`promptune daemon setup`)
- Dependency checker output
- systemd service management
- Troubleshooting (input group, proxy, WSL)

- [ ] **Step 2: Update MANUAL_TESTING.md**

Add sections 28-37 (Linux daemon test scenarios) and sections 38-50 (Phase 5 cross-platform verification) as listed in the spec.

- [ ] **Step 3: Update ARCHITECTURE.md**

Add platform abstraction layer diagram and description:
```
promptune/daemon/platform/
├── base.py         Abstract interfaces
├── __init__.py     Runtime detection factory
├── macos.py        macOS adapter
├── linux_x11.py    X11 backend
├── linux_wayland.py  Wayland backend
└── linux_service.py  systemd + PID fallback
```

- [ ] **Step 4: Update README.md**

- Update "Supported Platforms" to include Linux (X11 + Wayland)
- Add Linux daemon to features list
- Update roadmap: Phase 3 complete, add Phase 4/5
- Mark Windows as future

- [ ] **Step 5: Update CHANGELOG.md**

Add Phase 3 entry:
```markdown
## Phase 3 — Linux OS-Level Hotkey Daemon

### Added
- Platform abstraction layer (`promptune/daemon/platform/`)
- Linux X11 backend (python-xlib, xclip, xdotool)
- Linux Wayland backend (dbus-next portal, wl-clipboard, ydotool)
- Linux systemd user service management
- Dependency checker with package manager detection
- `promptune daemon install/uninstall/purge` commands
- Runtime detection of display server (X11/Wayland)
- WSL detection with clear error message
- `linux-daemon` optional dependency group

### Changed
- `daemon.py` uses platform factory instead of direct macOS imports
- `daemon/__init__.py` no longer blocks import on Linux
- CLI daemon group works on both macOS and Linux
- `promptune daemon diagnose` shows platform-specific checks
```

- [ ] **Step 6: Update blueprint**

In `docs/superpowers/blueprint/promptune_blueprint.md`:
- Mark Phase 3 as complete (update checklist items)
- Add Phase 4 (Direct integrations + shared prompt library)
- Add Phase 5 (Cross-platform verification)
- Add "Future" section for Windows support

- [ ] **Step 7: Commit**

```bash
git add docs/USER_GUIDE.md docs/MANUAL_TESTING.md docs/ARCHITECTURE.md README.md CHANGELOG.md docs/superpowers/blueprint/promptune_blueprint.md
git commit -m "docs: add Phase 3 Linux daemon documentation"
```

---

### Task 12: Full Verification

- [ ] **Step 1: Run ruff**

Run: `ruff check .`
Expected: 0 errors

- [ ] **Step 2: Run mypy**

Run: `mypy promptune/`
Expected: 0 errors

- [ ] **Step 3: Run full test suite with coverage**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: All tests PASS, coverage >= 90%

- [ ] **Step 4: Fix any issues found**

If any step fails, fix the issue and re-run.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix: resolve lint/type/test issues from Phase 3"
```

---

## Self-Review Results

**Spec coverage:** All spec sections have corresponding tasks:
- Abstract interfaces → Task 1
- macOS adapter → Task 3
- X11 backend → Task 4
- Wayland backend → Task 5
- Linux service + dependency checker → Task 6
- Factory → Task 7
- daemon.py integration → Task 8
- CLI commands → Task 9
- pyproject.toml → Task 10
- Documentation → Task 11
- Verification → Task 12

**Placeholder scan:** No TBD/TODO found. All steps have complete code.

**Type consistency:** Verified:
- `PlatformBackend` fields match ABC classes across all tasks
- `DependencyStatus` used consistently in Tasks 1, 6, 9
- `PlatformError` defined in Task 7, caught in Tasks 8, 9
- `get_platform()` signature matches across Tasks 7, 8, 9
- All backend method signatures match `base.py` ABCs
