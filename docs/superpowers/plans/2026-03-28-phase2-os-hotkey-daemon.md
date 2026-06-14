# Phase 2: OS-Level Hotkey Daemon — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a macOS background daemon to promptune that registers a global hotkey (Ctrl+Shift+E), captures selected text via clipboard, enhances it through the existing engine, and pastes the result back — working in any application.

**Architecture:** A `promptune/daemon/` package with 7 focused modules (hotkey, clipboard, notify, ipc, prewarm, launchagent, daemon) that compose into a background process managed via `promptune daemon` CLI subcommands. All macOS-specific code uses pyobjc directly. The daemon reuses the existing `engine.enhance()` pipeline.

**Tech Stack:** pyobjc-framework-Quartz (CGEventTap), pyobjc-framework-ApplicationServices (Accessibility), pyobjc-framework-Cocoa (NSWorkspace), Click (CLI), stdlib threading/socket/subprocess.

**Spec:** `docs/superpowers/specs/2026-03-28-phase2-os-hotkey-daemon-design.md`

---

## File Structure

### New Files

| File | Purpose |
|------|---------|
| `promptune/daemon/__init__.py` | Package init, platform guard, re-exports |
| `promptune/daemon/hotkey.py` | CGEventTap registration, hotkey parsing, accessibility checks |
| `promptune/daemon/clipboard.py` | Clipboard read/write via pbcopy/pbpaste, Cmd+C/V simulation, undo buffer |
| `promptune/daemon/ipc.py` | Unix socket server/client, CWD tracking, daemon state, status queries |
| `promptune/daemon/notify.py` | macOS notifications via osascript |
| `promptune/daemon/prewarm.py` | Ollama model pre-warm and periodic keep-alive |
| `promptune/daemon/launchagent.py` | LaunchAgent plist generation, install/uninstall |
| `promptune/daemon/daemon.py` | Main daemon loop — lifecycle, PID management, signal handlers, pipeline orchestration |
| `tests/test_daemon/__init__.py` | Test package init |
| `tests/test_daemon/test_hotkey.py` | Hotkey parsing, accessibility check mocking |
| `tests/test_daemon/test_clipboard.py` | Clipboard pipeline tests (mock subprocess/Quartz) |
| `tests/test_daemon/test_ipc.py` | IPC Unix socket communication tests |
| `tests/test_daemon/test_notify.py` | Notification tests (mock osascript) |
| `tests/test_daemon/test_prewarm.py` | Ollama pre-warm tests (mock httpx) |
| `tests/test_daemon/test_launchagent.py` | Plist generation and file management tests |
| `tests/test_daemon/test_daemon.py` | Daemon lifecycle tests |

### Modified Files

| File | Change |
|------|--------|
| `promptune/config.py` | Add `[daemon]` section to `DEFAULT_CONFIG` |
| `promptune/cli.py` | Add `daemon` command group with 8 subcommands |
| `promptune/shell.py` | Add IPC CWD reporting line to generated widgets |
| `pyproject.toml` | Add pyobjc dependencies with platform markers |
| `config.example.toml` | Add `[daemon]` section |
| `tests/test_config.py` | Test new daemon config defaults |
| `tests/test_cli.py` | Test daemon CLI subcommands |
| `tests/test_shell.py` | Test IPC reporting in generated widgets |

---

## Parallelism Note

**Tasks 1** is a prerequisite for all others (config section used everywhere).
**Tasks 2–7** are independent leaf modules — can be built in any order or in parallel.
**Task 8** integrates tasks 2–7 into the main daemon loop.
**Task 9** depends on task 8 (CLI exposes daemon).
**Task 10** depends on task 5 (shell widgets report CWD via IPC).
**Task 11** updates docs and config example.

---

## Task 1: Config Defaults for Daemon

**Files:**
- Modify: `promptune/config.py` (add daemon section to `DEFAULT_CONFIG`)
- Modify: `config.example.toml` (add `[daemon]` section)
- Modify: `tests/test_config.py` (test new defaults)

- [ ] **Step 1: Write the failing test**

In `tests/test_config.py`, add:

```python
def test_daemon_config_defaults():
    """Daemon config section has correct defaults."""
    from promptune.config import DEFAULT_CONFIG

    daemon = DEFAULT_CONFIG["daemon"]
    assert daemon["hotkey"] == "ctrl+shift+e"
    assert daemon["clipboard_settle_ms"] == 100
    assert daemon["notify"] is True
    assert daemon["notify_sound"] is True
    assert daemon["ollama_prewarm"] is True
    assert daemon["ollama_keepalive_minutes"] == 30
    assert daemon["log_level"] == "info"


def test_loaded_config_includes_daemon_defaults(tmp_path):
    """Loading a config file without [daemon] section fills in defaults."""
    config_file = tmp_path / "config.toml"
    config_file.write_text('[provider]\ndefault = "claude"\n')
    from promptune.config import load_config

    cfg = load_config(config_file, validate_keys=False)
    assert "daemon" in cfg
    assert cfg["daemon"]["hotkey"] == "ctrl+shift+e"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_daemon_config_defaults tests/test_config.py::test_loaded_config_includes_daemon_defaults -v`
Expected: FAIL with `KeyError: 'daemon'`

- [ ] **Step 3: Add daemon section to DEFAULT_CONFIG**

In `promptune/config.py`, add after the `"tui"` section in `DEFAULT_CONFIG`:

```python
    "daemon": {
        "hotkey": "ctrl+shift+e",
        "clipboard_settle_ms": 100,
        "notify": True,
        "notify_sound": True,
        "ollama_prewarm": True,
        "ollama_keepalive_minutes": 30,
        "log_level": "info",
    },
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: ALL PASS

- [ ] **Step 5: Update config.example.toml**

Append to `config.example.toml`:

```toml
[daemon]
hotkey = "ctrl+shift+e"              # Global hotkey (modifier+key format)
clipboard_settle_ms = 100            # Wait after Cmd+C before reading clipboard
notify = true                        # Show macOS notifications
notify_sound = true                  # Play sound with notifications
ollama_prewarm = true                # Pre-load Ollama model on daemon start
ollama_keepalive_minutes = 30        # Ollama keep_alive duration
log_level = "info"                   # debug | info | warning | error
```

- [ ] **Step 6: Commit**

```bash
git add promptune/config.py config.example.toml tests/test_config.py
git commit -m "feat(config): add [daemon] section with hotkey, notify, prewarm defaults"
```

---

## Task 2: Daemon Package Init with Platform Guard

**Files:**
- Create: `promptune/daemon/__init__.py`
- Create: `tests/test_daemon/__init__.py`

- [ ] **Step 1: Create test package init**

Create `tests/test_daemon/__init__.py`:

```python
```

- [ ] **Step 2: Create daemon package with platform guard**

Create `promptune/daemon/__init__.py`:

```python
"""Promptune macOS daemon — global hotkey, clipboard pipeline, notifications.

This package requires macOS. Importing on other platforms raises ImportError.
"""

from __future__ import annotations

import sys

if sys.platform != "darwin":
    raise ImportError(
        "promptune.daemon requires macOS. "
        "The daemon is not available on this platform."
    )
```

- [ ] **Step 3: Commit**

```bash
git add promptune/daemon/__init__.py tests/test_daemon/__init__.py
git commit -m "feat(daemon): add daemon package with macOS platform guard"
```

---

## Task 3: Hotkey Module — Parsing and Accessibility

**Files:**
- Create: `promptune/daemon/hotkey.py`
- Create: `tests/test_daemon/test_hotkey.py`

- [ ] **Step 1: Write failing tests for hotkey parsing**

Create `tests/test_daemon/test_hotkey.py`:

```python
"""Tests for daemon hotkey module — parsing, accessibility, registration."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


# Skip entire module on non-macOS
pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only daemon tests"
)


class TestParseHotkey:
    """Test hotkey string parsing into (keycode, modifier_mask)."""

    def test_parse_ctrl_shift_e(self):
        from promptune.daemon.hotkey import parse_hotkey

        keycode, mask = parse_hotkey("ctrl+shift+e")
        assert keycode == 14  # 'e' keycode on macOS

    def test_parse_ctrl_shift_e_modifiers(self):
        from promptune.daemon.hotkey import parse_hotkey, MODIFIER_MAP

        keycode, mask = parse_hotkey("ctrl+shift+e")
        expected_mask = MODIFIER_MAP["ctrl"] | MODIFIER_MAP["shift"]
        assert mask == expected_mask

    def test_parse_single_modifier(self):
        from promptune.daemon.hotkey import parse_hotkey

        keycode, mask = parse_hotkey("cmd+a")
        assert keycode == 0  # 'a' keycode

    def test_parse_unknown_key_raises(self):
        from promptune.daemon.hotkey import parse_hotkey

        with pytest.raises(ValueError, match="Unknown key"):
            parse_hotkey("ctrl+shift+?")

    def test_parse_unknown_modifier_raises(self):
        from promptune.daemon.hotkey import parse_hotkey

        with pytest.raises(ValueError, match="Unknown modifier"):
            parse_hotkey("super+e")

    def test_parse_case_insensitive(self):
        from promptune.daemon.hotkey import parse_hotkey

        keycode1, mask1 = parse_hotkey("Ctrl+Shift+E")
        keycode2, mask2 = parse_hotkey("ctrl+shift+e")
        assert keycode1 == keycode2
        assert mask1 == mask2

    def test_all_letter_keys_have_keycodes(self):
        from promptune.daemon.hotkey import KEYCODE_MAP

        for letter in "abcdefghijklmnopqrstuvwxyz":
            assert letter in KEYCODE_MAP, f"Missing keycode for '{letter}'"

    def test_space_key(self):
        from promptune.daemon.hotkey import parse_hotkey

        keycode, mask = parse_hotkey("ctrl+space")
        assert keycode == 49


class TestAccessibility:
    """Test accessibility permission checks (mocked)."""

    @patch("promptune.daemon.hotkey.ApplicationServices")
    def test_check_accessibility_granted(self, mock_as):
        mock_as.AXIsProcessTrustedWithOptions.return_value = True
        from promptune.daemon.hotkey import check_accessibility

        assert check_accessibility() is True
        mock_as.AXIsProcessTrustedWithOptions.assert_called_once()

    @patch("promptune.daemon.hotkey.ApplicationServices")
    def test_check_accessibility_denied(self, mock_as):
        mock_as.AXIsProcessTrustedWithOptions.return_value = False
        from promptune.daemon.hotkey import check_accessibility

        assert check_accessibility() is False

    @patch("promptune.daemon.hotkey.ApplicationServices")
    def test_request_accessibility_prompts(self, mock_as):
        mock_as.AXIsProcessTrustedWithOptions.return_value = False
        mock_as.kAXTrustedCheckOptionPrompt = "AXTrustedCheckOptionPrompt"
        from promptune.daemon.hotkey import request_accessibility

        request_accessibility()
        call_args = mock_as.AXIsProcessTrustedWithOptions.call_args[0][0]
        assert call_args["AXTrustedCheckOptionPrompt"] is True


class TestSecureInput:
    """Test secure input detection (mocked)."""

    @patch("promptune.daemon.hotkey.Quartz")
    def test_secure_input_active(self, mock_quartz):
        mock_quartz.CGSIsSecureEventInputSet.return_value = True
        from promptune.daemon.hotkey import is_secure_input_active

        assert is_secure_input_active() is True

    @patch("promptune.daemon.hotkey.Quartz")
    def test_secure_input_inactive(self, mock_quartz):
        mock_quartz.CGSIsSecureEventInputSet.return_value = False
        from promptune.daemon.hotkey import is_secure_input_active

        assert is_secure_input_active() is False


class TestRegisterHotkey:
    """Test hotkey registration (mocked CGEventTap)."""

    @patch("promptune.daemon.hotkey.Quartz")
    def test_register_raises_on_none_tap(self, mock_quartz):
        mock_quartz.CGEventTapCreate.return_value = None
        from promptune.daemon.hotkey import register_hotkey

        with pytest.raises(PermissionError, match="Accessibility"):
            register_hotkey(lambda: None)

    @patch("promptune.daemon.hotkey.Quartz")
    def test_register_success(self, mock_quartz):
        mock_tap = MagicMock()
        mock_quartz.CGEventTapCreate.return_value = mock_tap
        mock_source = MagicMock()
        mock_quartz.CFMachPortCreateRunLoopSource.return_value = mock_source
        mock_loop = MagicMock()
        mock_quartz.CFRunLoopGetCurrent.return_value = mock_loop

        from promptune.daemon.hotkey import register_hotkey

        result = register_hotkey(lambda: None)
        assert result == mock_tap
        mock_quartz.CGEventTapEnable.assert_called_once_with(mock_tap, True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_hotkey.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'promptune.daemon.hotkey'`

- [ ] **Step 3: Implement hotkey module**

Create `promptune/daemon/hotkey.py`:

```python
"""Global hotkey registration via CGEventTap (macOS).

Registers a system-wide keyboard shortcut that works in any application.
Requires Accessibility permission — CGEventTapCreate returns None without it.
"""

from __future__ import annotations

from typing import Callable

import ApplicationServices
import Quartz

# macOS keycode map (US keyboard layout)
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

# Default hotkey: Ctrl+Shift+E
DEFAULT_HOTKEY_KEYCODE = 14
CTRL_SHIFT_MASK = Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskShift


def parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    """Parse 'ctrl+shift+e' into (keycode, modifier_mask).

    Args:
        hotkey_str: Human-readable hotkey like 'ctrl+shift+e' or 'cmd+a'.

    Returns:
        Tuple of (macOS keycode, combined modifier mask).

    Raises:
        ValueError: If key or modifier is not recognised.
    """
    parts = hotkey_str.lower().split("+")
    key = parts[-1]
    modifiers = parts[:-1]

    keycode = KEYCODE_MAP.get(key)
    if keycode is None:
        raise ValueError(f"Unknown key: {key!r}")

    mask = 0
    for mod in modifiers:
        mod_flag = MODIFIER_MAP.get(mod)
        if mod_flag is None:
            raise ValueError(f"Unknown modifier: {mod!r}")
        mask |= mod_flag

    return keycode, mask


def _event_callback(
    proxy: int,
    event_type: int,
    event: Quartz.CGEventRef,
    callback: Callable[[], None],
    keycode: int,
    modifier_mask: int,
) -> Quartz.CGEventRef | None:
    """CGEventTap callback. Fires on key down matching hotkey."""
    if event_type == Quartz.kCGEventKeyDown:
        ev_keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )
        flags = Quartz.CGEventGetFlags(event)
        relevant_flags = flags & (
            Quartz.kCGEventFlagMaskControl
            | Quartz.kCGEventFlagMaskShift
            | Quartz.kCGEventFlagMaskAlternate
            | Quartz.kCGEventFlagMaskCommand
        )
        if ev_keycode == keycode and relevant_flags == modifier_mask:
            callback()
            return None  # Swallow the event
    return event


def check_accessibility() -> bool:
    """Check if Accessibility permission is granted (no prompt)."""
    return ApplicationServices.AXIsProcessTrustedWithOptions(
        {ApplicationServices.kAXTrustedCheckOptionPrompt: False}
    )


def request_accessibility() -> bool:
    """Prompt macOS to show Accessibility permission dialog."""
    return ApplicationServices.AXIsProcessTrustedWithOptions(
        {ApplicationServices.kAXTrustedCheckOptionPrompt: True}
    )


def is_secure_input_active() -> bool:
    """Check if macOS secure input is active (password field focused)."""
    return Quartz.CGSIsSecureEventInputSet()


def register_hotkey(
    callback: Callable[[], None],
    keycode: int = DEFAULT_HOTKEY_KEYCODE,
    modifier_mask: int = CTRL_SHIFT_MASK,
) -> Quartz.CFMachPortRef:
    """Register global hotkey tap. Returns the tap for cleanup.

    Raises:
        PermissionError: If Accessibility permission is not granted.
    """
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionDefault,
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
        lambda proxy, etype, event, _: _event_callback(
            proxy, etype, event, callback, keycode, modifier_mask
        ),
        None,
    )
    if tap is None:
        raise PermissionError(
            "Failed to create event tap. Grant Accessibility permission: "
            "promptune daemon setup"
        )

    source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    loop = Quartz.CFRunLoopGetCurrent()
    Quartz.CFRunLoopAddSource(loop, source, Quartz.kCFRunLoopCommonModes)
    Quartz.CGEventTapEnable(tap, True)
    return tap


def start_run_loop() -> None:
    """Enter the CFRunLoop. Blocks until stopped."""
    Quartz.CFRunLoopRun()


def stop_run_loop() -> None:
    """Stop the CFRunLoop from a signal handler or another thread."""
    Quartz.CFRunLoopStop(Quartz.CFRunLoopGetMain())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_hotkey.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/hotkey.py tests/test_daemon/test_hotkey.py
git commit -m "feat(daemon): add hotkey module with CGEventTap, parsing, accessibility"
```

---

## Task 4: Clipboard Module

**Files:**
- Create: `promptune/daemon/clipboard.py`
- Create: `tests/test_daemon/test_clipboard.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_daemon/test_clipboard.py`:

```python
"""Tests for daemon clipboard module — read/write, simulation, undo."""

from __future__ import annotations

import json
import sys
from unittest.mock import MagicMock, call, patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only daemon tests"
)


class TestSaveClipboard:
    """Test reading clipboard via pbpaste."""

    @patch("promptune.daemon.clipboard.subprocess")
    def test_read_text(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(
            returncode=0, stdout="hello world"
        )
        from promptune.daemon.clipboard import save_clipboard

        result = save_clipboard()
        assert result == "hello world"
        mock_subprocess.run.assert_called_once_with(
            ["pbpaste"], capture_output=True, text=True, timeout=2
        )

    @patch("promptune.daemon.clipboard.subprocess")
    def test_read_failure_returns_none(self, mock_subprocess):
        mock_subprocess.run.return_value = MagicMock(returncode=1, stdout="")
        from promptune.daemon.clipboard import save_clipboard

        assert save_clipboard() is None


class TestWriteClipboard:
    """Test writing clipboard via pbcopy."""

    @patch("promptune.daemon.clipboard.subprocess")
    def test_write_text(self, mock_subprocess):
        from promptune.daemon.clipboard import write_clipboard

        write_clipboard("enhanced text")
        mock_subprocess.run.assert_called_once_with(
            ["pbcopy"], input="enhanced text", text=True, timeout=2, check=True
        )


class TestSimulateKeys:
    """Test Cmd+C and Cmd+V simulation (mocked Quartz)."""

    @patch("promptune.daemon.clipboard.Quartz")
    def test_simulate_cmd_c(self, mock_quartz):
        from promptune.daemon.clipboard import simulate_cmd_c

        simulate_cmd_c()
        # Should create key down and key up events
        assert mock_quartz.CGEventCreateKeyboardEvent.call_count == 2
        # Keycode 8 = 'c'
        calls = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
        assert calls[0][0][1] == 8  # keycode for 'c'
        assert calls[0][0][2] is True  # key down
        assert calls[1][0][1] == 8
        assert calls[1][0][2] is False  # key up

    @patch("promptune.daemon.clipboard.Quartz")
    def test_simulate_cmd_v(self, mock_quartz):
        from promptune.daemon.clipboard import simulate_cmd_v

        simulate_cmd_v()
        calls = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
        assert calls[0][0][1] == 9  # keycode for 'v'


class TestGetFrontmostApp:
    """Test frontmost app detection (mocked NSWorkspace)."""

    @patch("promptune.daemon.clipboard.NSWorkspace")
    def test_get_frontmost_app(self, mock_ns):
        mock_app = MagicMock()
        mock_app.bundleIdentifier.return_value = "com.apple.Safari"
        mock_ns.sharedWorkspace.return_value.frontmostApplication.return_value = mock_app

        from promptune.daemon.clipboard import get_frontmost_app

        assert get_frontmost_app() == "com.apple.Safari"

    @patch("promptune.daemon.clipboard.NSWorkspace")
    def test_get_frontmost_app_no_bundle(self, mock_ns):
        mock_app = MagicMock()
        mock_app.bundleIdentifier.return_value = None
        mock_ns.sharedWorkspace.return_value.frontmostApplication.return_value = mock_app

        from promptune.daemon.clipboard import get_frontmost_app

        assert get_frontmost_app() == ""


class TestCopySelection:
    """Test the copy_selection pipeline."""

    @patch("promptune.daemon.clipboard.time")
    @patch("promptune.daemon.clipboard.save_clipboard")
    @patch("promptune.daemon.clipboard.simulate_cmd_c")
    def test_copy_selection_success(self, mock_cmd_c, mock_save, mock_time):
        mock_save.return_value = "selected text"
        from promptune.daemon.clipboard import copy_selection, CLIPBOARD_SETTLE_MS

        result = copy_selection()
        assert result == "selected text"
        mock_cmd_c.assert_called_once()
        mock_time.sleep.assert_called_once_with(CLIPBOARD_SETTLE_MS / 1000)


class TestUndoBuffer:
    """Test undo file save."""

    def test_save_undo(self, tmp_path):
        from promptune.daemon.clipboard import save_undo

        undo_file = tmp_path / "undo.txt"
        with patch("promptune.daemon.clipboard.UNDO_FILE", undo_file):
            save_undo("old clipboard", "selected text")

        data = json.loads(undo_file.read_text())
        assert data["original_clipboard"] == "old clipboard"
        assert data["selected_text"] == "selected text"
        assert "timestamp" in data

    def test_save_undo_none_clipboard(self, tmp_path):
        from promptune.daemon.clipboard import save_undo

        undo_file = tmp_path / "undo.txt"
        with patch("promptune.daemon.clipboard.UNDO_FILE", undo_file):
            save_undo(None, "selected text")

        data = json.loads(undo_file.read_text())
        assert data["original_clipboard"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_clipboard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'promptune.daemon.clipboard'`

- [ ] **Step 3: Implement clipboard module**

Create `promptune/daemon/clipboard.py`:

```python
"""Clipboard pipeline — read, write, simulate Cmd+C/V, undo buffer.

Uses pbcopy/pbpaste for clipboard and CGEvent for key simulation.
"""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

import Quartz
from AppKit import NSWorkspace

UNDO_FILE = Path("~/.local/share/promptune/undo.txt").expanduser()
CLIPBOARD_SETTLE_MS = 100  # Time for clipboard to populate after Cmd+C


def save_clipboard() -> str | None:
    """Read current clipboard text. Returns None if not text."""
    result = subprocess.run(
        ["pbpaste"], capture_output=True, text=True, timeout=2
    )
    if result.returncode != 0:
        return None
    return result.stdout


def write_clipboard(text: str) -> None:
    """Write text to clipboard via pbcopy."""
    subprocess.run(
        ["pbcopy"], input=text, text=True, timeout=2, check=True
    )


def _simulate_key_combo(keycode: int, modifier: int) -> None:
    """Simulate a modifier+key press and release."""
    source = Quartz.CGEventSourceCreate(
        Quartz.kCGEventSourceStateCombinedSessionState
    )
    key_down = Quartz.CGEventCreateKeyboardEvent(source, keycode, True)
    Quartz.CGEventSetFlags(key_down, modifier)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_down)

    key_up = Quartz.CGEventCreateKeyboardEvent(source, keycode, False)
    Quartz.CGEventSetFlags(key_up, modifier)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_up)


def simulate_cmd_c() -> None:
    """Simulate Cmd+C via CGEvent."""
    _simulate_key_combo(keycode=8, modifier=Quartz.kCGEventFlagMaskCommand)


def simulate_cmd_v() -> None:
    """Simulate Cmd+V via CGEvent."""
    _simulate_key_combo(keycode=9, modifier=Quartz.kCGEventFlagMaskCommand)


def get_frontmost_app() -> str:
    """Get bundle ID of the frontmost application."""
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() or ""


def copy_selection() -> str | None:
    """Simulate Cmd+C and read the resulting clipboard text.

    Returns None if clipboard is empty or non-text after copy.
    """
    simulate_cmd_c()
    time.sleep(CLIPBOARD_SETTLE_MS / 1000)
    return save_clipboard()


def paste_result(text: str) -> None:
    """Write text to clipboard and simulate Cmd+V."""
    write_clipboard(text)
    time.sleep(0.05)
    simulate_cmd_v()


def save_undo(original_clipboard: str | None, selected_text: str) -> None:
    """Save originals for undo recovery."""
    data = {
        "original_clipboard": original_clipboard,
        "selected_text": selected_text,
        "timestamp": time.time(),
    }
    UNDO_FILE.parent.mkdir(parents=True, exist_ok=True)
    UNDO_FILE.write_text(json.dumps(data))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_clipboard.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/clipboard.py tests/test_daemon/test_clipboard.py
git commit -m "feat(daemon): add clipboard module with pbcopy/pbpaste, Cmd+C/V sim, undo"
```

---

## Task 5: Notify Module

**Files:**
- Create: `promptune/daemon/notify.py`
- Create: `tests/test_daemon/test_notify.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_daemon/test_notify.py`:

```python
"""Tests for daemon notification module."""

from __future__ import annotations

import sys
from unittest.mock import patch, call

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only daemon tests"
)


class TestNotify:
    """Test osascript notification dispatch."""

    @patch("promptune.daemon.notify.subprocess")
    def test_notify_with_sound(self, mock_subprocess):
        from promptune.daemon.notify import notify

        notify("Title", "Message", sound=True)
        args = mock_subprocess.run.call_args
        cmd = args[0][0]
        assert cmd[0] == "osascript"
        script = cmd[2]
        assert "Title" in script
        assert "Message" in script
        assert 'sound name "Tink"' in script

    @patch("promptune.daemon.notify.subprocess")
    def test_notify_without_sound(self, mock_subprocess):
        from promptune.daemon.notify import notify

        notify("Title", "Message", sound=False)
        script = mock_subprocess.run.call_args[0][0][2]
        assert "sound name" not in script

    @patch("promptune.daemon.notify.subprocess")
    def test_notify_escapes_quotes(self, mock_subprocess):
        from promptune.daemon.notify import notify

        notify('Say "hello"', 'It\'s a "test"')
        script = mock_subprocess.run.call_args[0][0][2]
        assert r"\"hello\"" in script


class TestNotifyEnhanced:
    """Test enhancement success notification."""

    @patch("promptune.daemon.notify.notify")
    def test_positive_delta(self, mock_notify):
        from promptune.daemon.notify import notify_enhanced

        notify_enhanced(score_before=50, score_after=62)
        mock_notify.assert_called_once()
        msg = mock_notify.call_args[1]["message"]
        assert "+12 PQS" in msg
        assert "Cmd+Z" in msg

    @patch("promptune.daemon.notify.notify")
    def test_negative_delta(self, mock_notify):
        from promptune.daemon.notify import notify_enhanced

        notify_enhanced(score_before=70, score_after=65)
        msg = mock_notify.call_args[1]["message"]
        assert "-5 PQS" in msg

    @patch("promptune.daemon.notify.notify")
    def test_zero_delta(self, mock_notify):
        from promptune.daemon.notify import notify_enhanced

        notify_enhanced(score_before=50, score_after=50)
        msg = mock_notify.call_args[1]["message"]
        assert "+0 PQS" in msg


class TestNotifyError:
    """Test error notification."""

    @patch("promptune.daemon.notify.notify")
    def test_error_no_sound(self, mock_notify):
        from promptune.daemon.notify import notify_error

        notify_error("No text selected.")
        mock_notify.assert_called_once_with(
            title="Promptune", message="No text selected.", sound=False
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_notify.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement notify module**

Create `promptune/daemon/notify.py`:

```python
"""macOS notifications via osascript."""

from __future__ import annotations

import subprocess


def _escape(text: str) -> str:
    """Escape double quotes for AppleScript strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def notify(
    title: str,
    message: str,
    sound: bool = True,
) -> None:
    """Show a macOS notification via osascript."""
    sound_line = 'sound name "Tink"' if sound else ""
    script = (
        f'display notification "{_escape(message)}" '
        f'with title "{_escape(title)}" {sound_line}'
    )
    subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        timeout=5,
    )


def notify_enhanced(score_before: int, score_after: int) -> None:
    """Notify user of successful enhancement."""
    delta = score_after - score_before
    sign = "+" if delta >= 0 else ""
    notify(
        title="Promptune",
        message=f"Prompt enhanced ({sign}{delta} PQS). Cmd+Z to undo.",
    )


def notify_error(message: str) -> None:
    """Notify user of an error during enhancement."""
    notify(
        title="Promptune",
        message=message,
        sound=False,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_notify.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/notify.py tests/test_daemon/test_notify.py
git commit -m "feat(daemon): add notify module with osascript notifications"
```

---

## Task 6: IPC Module — Unix Socket Server/Client

**Files:**
- Create: `promptune/daemon/ipc.py`
- Create: `tests/test_daemon/test_ipc.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_daemon/test_ipc.py`:

```python
"""Tests for daemon IPC module — Unix socket server/client."""

from __future__ import annotations

import json
import socket
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only daemon tests"
)


class TestDaemonState:
    """Test shared mutable state dataclass."""

    def test_initial_state(self):
        from promptune.daemon.ipc import DaemonState

        state = DaemonState()
        assert state.last_cwd == ""
        assert state.last_project_root == ""
        assert state.enhancement_count == 0

    def test_state_update_thread_safe(self):
        from promptune.daemon.ipc import DaemonState

        state = DaemonState()
        with state.lock:
            state.last_cwd = "/tmp/test"
            state.enhancement_count = 5
        assert state.last_cwd == "/tmp/test"
        assert state.enhancement_count == 5


class TestIPCServer:
    """Test Unix socket server and client communication."""

    def test_report_cwd(self, tmp_path):
        """Client reports CWD, server updates state."""
        from promptune.daemon.ipc import DaemonState, start_ipc_server, send_ipc_message

        sock_path = tmp_path / "test.sock"
        state = DaemonState()

        with patch("promptune.daemon.ipc.SOCKET_PATH", sock_path):
            thread = start_ipc_server(state)
            time.sleep(0.2)  # Let server start

            send_ipc_message({"action": "report_cwd", "cwd": "/tmp/proj", "project_root": "/tmp/proj"})
            time.sleep(0.1)  # Let message process

            with state.lock:
                assert state.last_cwd == "/tmp/proj"
                assert state.last_project_root == "/tmp/proj"

    def test_status_query(self, tmp_path):
        """Client queries status, server responds."""
        from promptune.daemon.ipc import DaemonState, start_ipc_server, send_ipc_message

        sock_path = tmp_path / "test.sock"
        state = DaemonState()
        state.enhancement_count = 42
        state.last_cwd = "/home/user/project"

        with patch("promptune.daemon.ipc.SOCKET_PATH", sock_path):
            thread = start_ipc_server(state)
            time.sleep(0.2)

            response = send_ipc_message({"action": "status"})
            assert response is not None
            assert response["running"] is True
            assert response["enhancement_count"] == 42
            assert response["last_cwd"] == "/home/user/project"

    def test_send_to_nonexistent_socket(self, tmp_path):
        """Sending to nonexistent socket returns None."""
        from promptune.daemon.ipc import send_ipc_message

        sock_path = tmp_path / "nonexistent.sock"
        with patch("promptune.daemon.ipc.SOCKET_PATH", sock_path):
            result = send_ipc_message({"action": "status"})
            assert result is None

    def test_stale_socket_removed(self, tmp_path):
        """Server removes stale socket file before binding."""
        from promptune.daemon.ipc import DaemonState, start_ipc_server

        sock_path = tmp_path / "stale.sock"
        sock_path.write_text("stale")  # Create stale file

        state = DaemonState()
        with patch("promptune.daemon.ipc.SOCKET_PATH", sock_path):
            thread = start_ipc_server(state)
            time.sleep(0.2)
            assert sock_path.exists()  # New socket created
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_ipc.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement IPC module**

Create `promptune/daemon/ipc.py`:

```python
"""IPC via Unix domain socket — CWD tracking, status queries.

The daemon listens on a Unix socket. Shell widgets report their CWD,
and CLI commands query daemon status.
"""

from __future__ import annotations

import json
import socket
import threading
from dataclasses import dataclass, field
from pathlib import Path

SOCKET_PATH = Path("~/.local/share/promptune/promptune.sock").expanduser()


@dataclass
class DaemonState:
    """Shared mutable state for the daemon."""

    last_cwd: str = ""
    last_project_root: str = ""
    enhancement_count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


def start_ipc_server(state: DaemonState) -> threading.Thread:
    """Start the IPC socket listener in a background thread."""

    def _serve() -> None:
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(str(SOCKET_PATH))
        server.listen(5)
        server.settimeout(1.0)

        while True:
            try:
                conn, _ = server.accept()
                data = conn.recv(4096).decode("utf-8")
                _handle_message(data, state, conn)
                conn.close()
            except socket.timeout:
                continue
            except OSError:
                break

    thread = threading.Thread(target=_serve, daemon=True, name="ipc-server")
    thread.start()
    return thread


def _handle_message(
    data: str, state: DaemonState, conn: socket.socket
) -> None:
    """Handle an IPC message from a client."""
    try:
        msg = json.loads(data)
    except json.JSONDecodeError:
        return

    action = msg.get("action")

    if action == "report_cwd":
        with state.lock:
            state.last_cwd = msg.get("cwd", "")
            state.last_project_root = msg.get("project_root", "")

    elif action == "status":
        with state.lock:
            response = json.dumps({
                "running": True,
                "enhancement_count": state.enhancement_count,
                "last_cwd": state.last_cwd,
            })
        conn.sendall(response.encode("utf-8"))


def send_ipc_message(msg: dict) -> dict | None:
    """Send a message to the daemon via IPC socket. Returns response or None."""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(str(SOCKET_PATH))
        sock.sendall(json.dumps(msg).encode("utf-8"))
        sock.settimeout(2.0)
        try:
            data = sock.recv(4096).decode("utf-8")
            return json.loads(data)
        except (socket.timeout, json.JSONDecodeError):
            return None
        finally:
            sock.close()
    except (ConnectionRefusedError, FileNotFoundError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_ipc.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/ipc.py tests/test_daemon/test_ipc.py
git commit -m "feat(daemon): add IPC module with Unix socket server/client"
```

---

## Task 7: Prewarm Module — Ollama Model Loading

**Files:**
- Create: `promptune/daemon/prewarm.py`
- Create: `tests/test_daemon/test_prewarm.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_daemon/test_prewarm.py`:

```python
"""Tests for Ollama pre-warm module."""

from __future__ import annotations

import logging
import sys
import threading
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only daemon tests"
)


class TestPrewarmOllama:
    """Test Ollama model pre-warm."""

    @patch("promptune.daemon.prewarm.httpx")
    def test_prewarm_success(self, mock_httpx):
        mock_resp = MagicMock(status_code=200)
        mock_httpx.post.return_value = mock_resp

        from promptune.daemon.prewarm import prewarm_ollama

        prewarm_ollama("http://localhost:11434", "qwen2.5:3b")
        mock_httpx.post.assert_called_once()
        call_kwargs = mock_httpx.post.call_args
        assert "qwen2.5:3b" in str(call_kwargs)

    @patch("promptune.daemon.prewarm.httpx")
    def test_prewarm_http_error(self, mock_httpx, caplog):
        mock_resp = MagicMock(status_code=500)
        mock_httpx.post.return_value = mock_resp

        from promptune.daemon.prewarm import prewarm_ollama

        with caplog.at_level(logging.WARNING):
            prewarm_ollama("http://localhost:11434", "qwen2.5:3b")
        # Should not raise

    @patch("promptune.daemon.prewarm.httpx")
    def test_prewarm_connection_error(self, mock_httpx, caplog):
        mock_httpx.post.side_effect = ConnectionError("refused")

        from promptune.daemon.prewarm import prewarm_ollama

        with caplog.at_level(logging.WARNING):
            prewarm_ollama("http://localhost:11434", "qwen2.5:3b")
        # Should not raise


class TestStartPrewarmTimer:
    """Test periodic keep-alive timer."""

    @patch("promptune.daemon.prewarm.prewarm_ollama")
    def test_start_timer_calls_prewarm(self, mock_prewarm):
        from promptune.daemon.prewarm import start_prewarm_timer

        timer = start_prewarm_timer("http://localhost:11434", "qwen2.5:3b", interval_minutes=0)
        # Give it a moment to fire
        import time
        time.sleep(0.2)
        mock_prewarm.assert_called()
        timer.cancel()

    @patch("promptune.daemon.prewarm.prewarm_ollama")
    def test_timer_is_daemon_thread(self, mock_prewarm):
        from promptune.daemon.prewarm import start_prewarm_timer

        timer = start_prewarm_timer("http://localhost:11434", "qwen2.5:3b", interval_minutes=25)
        assert timer.daemon is True
        timer.cancel()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_prewarm.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement prewarm module**

Create `promptune/daemon/prewarm.py`:

```python
"""Ollama model pre-warm and periodic keep-alive.

Loads the configured local LLM into memory on daemon startup
so Tier 1 enhancements have no cold-start delay.
"""

from __future__ import annotations

import logging
import threading

import httpx

logger = logging.getLogger("promptune.daemon.prewarm")


def prewarm_ollama(host: str, model: str, keepalive: str = "30m") -> None:
    """Send a minimal request to load the model into memory.

    Failure is logged but never fatal.
    """
    try:
        resp = httpx.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": keepalive},
            timeout=60.0,
        )
        if resp.status_code == 200:
            logger.info("Ollama pre-warm: model %s loaded", model)
        else:
            logger.warning("Ollama pre-warm: HTTP %d", resp.status_code)
    except Exception as e:
        logger.warning("Ollama pre-warm: %s", e)


class _RepeatingTimer(threading.Timer):
    """Timer that re-arms itself after each run."""

    daemon = True

    def run(self) -> None:
        while not self.finished.wait(self.interval):
            self.function(*self.args, **self.kwargs)


def start_prewarm_timer(
    host: str, model: str, interval_minutes: int = 25
) -> threading.Timer:
    """Start a periodic timer that re-warms Ollama model.

    Returns the timer for cancellation.
    """
    interval_seconds = max(interval_minutes * 60, 0.01)  # floor for testing
    timer = _RepeatingTimer(interval_seconds, prewarm_ollama, args=[host, model])
    timer.daemon = True
    timer.start()
    return timer
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_prewarm.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/prewarm.py tests/test_daemon/test_prewarm.py
git commit -m "feat(daemon): add prewarm module with Ollama keep-alive timer"
```

---

## Task 8: LaunchAgent Module

**Files:**
- Create: `promptune/daemon/launchagent.py`
- Create: `tests/test_daemon/test_launchagent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_daemon/test_launchagent.py`:

```python
"""Tests for LaunchAgent plist generation and management."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only daemon tests"
)


class TestGeneratePlist:
    """Test LaunchAgent plist content generation."""

    def test_plist_contains_label(self):
        from promptune.daemon.launchagent import generate_plist

        plist = generate_plist()
        assert "dev.promptune.daemon" in plist

    def test_plist_contains_promptune_command(self):
        from promptune.daemon.launchagent import generate_plist

        plist = generate_plist()
        assert "promptune" in plist
        assert "daemon" in plist
        assert "start" in plist
        assert "--foreground" in plist

    def test_plist_run_at_load(self):
        from promptune.daemon.launchagent import generate_plist

        plist = generate_plist()
        assert "<key>RunAtLoad</key>" in plist

    def test_plist_keep_alive(self):
        from promptune.daemon.launchagent import generate_plist

        plist = generate_plist()
        assert "<key>KeepAlive</key>" in plist

    def test_plist_is_valid_xml(self):
        import xml.etree.ElementTree as ET
        from promptune.daemon.launchagent import generate_plist

        plist = generate_plist()
        # Should not raise
        ET.fromstring(plist)


class TestInstallUninstall:
    """Test install and uninstall operations."""

    def test_install_writes_plist(self, tmp_path):
        from promptune.daemon.launchagent import install_login_item

        plist_path = tmp_path / "dev.promptune.daemon.plist"
        with patch("promptune.daemon.launchagent.PLIST_PATH", plist_path):
            with patch("promptune.daemon.launchagent.subprocess") as mock_sub:
                install_login_item()

        assert plist_path.exists()
        content = plist_path.read_text()
        assert "dev.promptune.daemon" in content

    def test_uninstall_removes_plist(self, tmp_path):
        from promptune.daemon.launchagent import uninstall_login_item

        plist_path = tmp_path / "dev.promptune.daemon.plist"
        plist_path.write_text("<plist>test</plist>")

        with patch("promptune.daemon.launchagent.PLIST_PATH", plist_path):
            with patch("promptune.daemon.launchagent.subprocess") as mock_sub:
                uninstall_login_item()

        assert not plist_path.exists()
        mock_sub.run.assert_called_once()  # launchctl unload

    def test_uninstall_nonexistent_noop(self, tmp_path):
        from promptune.daemon.launchagent import uninstall_login_item

        plist_path = tmp_path / "nonexistent.plist"
        with patch("promptune.daemon.launchagent.PLIST_PATH", plist_path):
            with patch("promptune.daemon.launchagent.subprocess"):
                uninstall_login_item()  # Should not raise


class TestIsInstalled:
    """Test installation status check."""

    def test_installed_when_file_exists(self, tmp_path):
        from promptune.daemon.launchagent import is_installed

        plist_path = tmp_path / "dev.promptune.daemon.plist"
        plist_path.write_text("<plist/>")
        with patch("promptune.daemon.launchagent.PLIST_PATH", plist_path):
            assert is_installed() is True

    def test_not_installed_when_no_file(self, tmp_path):
        from promptune.daemon.launchagent import is_installed

        plist_path = tmp_path / "nonexistent.plist"
        with patch("promptune.daemon.launchagent.PLIST_PATH", plist_path):
            assert is_installed() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_launchagent.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement launchagent module**

Create `promptune/daemon/launchagent.py`:

```python
"""LaunchAgent plist management — auto-start daemon on login.

Generates, installs, and uninstalls the launchd plist at
~/Library/LaunchAgents/dev.promptune.daemon.plist.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PLIST_PATH = Path("~/Library/LaunchAgents/dev.promptune.daemon.plist").expanduser()
LOG_FILE = Path("~/.local/share/promptune/daemon.log").expanduser()
LABEL = "dev.promptune.daemon"


def generate_plist() -> str:
    """Generate LaunchAgent plist XML content."""
    python = sys.executable
    log = str(LOG_FILE)
    return f"""\
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python}</string>
        <string>-m</string>
        <string>promptune</string>
        <string>daemon</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>"""


def install_login_item() -> None:
    """Write plist and load via launchctl."""
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(generate_plist())
    subprocess.run(
        ["launchctl", "load", str(PLIST_PATH)],
        capture_output=True,
    )


def uninstall_login_item() -> None:
    """Unload and remove plist."""
    if PLIST_PATH.exists():
        subprocess.run(
            ["launchctl", "unload", str(PLIST_PATH)],
            capture_output=True,
        )
        PLIST_PATH.unlink()


def is_installed() -> bool:
    """Check if the LaunchAgent plist exists."""
    return PLIST_PATH.exists()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_launchagent.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/launchagent.py tests/test_daemon/test_launchagent.py
git commit -m "feat(daemon): add launchagent module with plist install/uninstall"
```

---

## Task 9: Main Daemon Module — Lifecycle and Pipeline

**Files:**
- Create: `promptune/daemon/daemon.py`
- Create: `tests/test_daemon/test_daemon.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_daemon/test_daemon.py`:

```python
"""Tests for main daemon module — lifecycle, PID management, pipeline."""

from __future__ import annotations

import json
import os
import signal
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only daemon tests"
)


class TestPIDManagement:
    """Test PID file creation and stale PID detection."""

    def test_write_pid_file(self, tmp_path):
        from promptune.daemon.daemon import _write_pid, _read_pid

        pid_file = tmp_path / "daemon.pid"
        with patch("promptune.daemon.daemon.PID_FILE", pid_file):
            _write_pid()
            assert _read_pid() == os.getpid()

    def test_read_pid_missing_file(self, tmp_path):
        from promptune.daemon.daemon import _read_pid

        pid_file = tmp_path / "nonexistent.pid"
        with patch("promptune.daemon.daemon.PID_FILE", pid_file):
            assert _read_pid() is None

    def test_is_running_false_for_dead_pid(self, tmp_path):
        from promptune.daemon.daemon import _is_running

        assert _is_running(999999999) is False

    def test_is_running_true_for_self(self):
        from promptune.daemon.daemon import _is_running

        assert _is_running(os.getpid()) is True

    def test_cleanup_removes_files(self, tmp_path):
        from promptune.daemon.daemon import _cleanup

        pid_file = tmp_path / "daemon.pid"
        sock_file = tmp_path / "daemon.sock"
        pid_file.write_text(str(os.getpid()))
        sock_file.write_text("sock")

        with patch("promptune.daemon.daemon.PID_FILE", pid_file), \
             patch("promptune.daemon.daemon.SOCKET_PATH", sock_file):
            _cleanup()

        assert not pid_file.exists()
        assert not sock_file.exists()


class TestDaemonStatus:
    """Test daemon status dataclass and query."""

    def test_status_not_running(self, tmp_path):
        from promptune.daemon.daemon import get_status

        pid_file = tmp_path / "daemon.pid"
        sock_file = tmp_path / "daemon.sock"

        with patch("promptune.daemon.daemon.PID_FILE", pid_file), \
             patch("promptune.daemon.daemon.SOCKET_PATH", sock_file), \
             patch("promptune.daemon.daemon.check_accessibility", return_value=False):
            status = get_status()

        assert status.running is False
        assert status.pid is None

    def test_status_stale_pid(self, tmp_path):
        from promptune.daemon.daemon import get_status

        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text("999999999")
        sock_file = tmp_path / "daemon.sock"

        with patch("promptune.daemon.daemon.PID_FILE", pid_file), \
             patch("promptune.daemon.daemon.SOCKET_PATH", sock_file), \
             patch("promptune.daemon.daemon.check_accessibility", return_value=True):
            status = get_status()

        assert status.running is False


class TestEnhancePipeline:
    """Test the hotkey-triggered enhancement pipeline."""

    @patch("promptune.daemon.daemon.notify_enhanced")
    @patch("promptune.daemon.daemon.notify_error")
    @patch("promptune.daemon.daemon.get_frontmost_app")
    @patch("promptune.daemon.daemon.paste_result")
    @patch("promptune.daemon.daemon.save_undo")
    @patch("promptune.daemon.daemon.save_clipboard")
    @patch("promptune.daemon.daemon.copy_selection")
    @patch("promptune.daemon.daemon.enhance")
    def test_successful_pipeline(
        self,
        mock_enhance,
        mock_copy,
        mock_save_clip,
        mock_save_undo,
        mock_paste,
        mock_frontmost,
        mock_notify_err,
        mock_notify_ok,
    ):
        from promptune.daemon.daemon import _on_hotkey
        from promptune.daemon.ipc import DaemonState

        mock_save_clip.return_value = "old clipboard"
        mock_copy.return_value = "original prompt"
        mock_frontmost.side_effect = ["com.apple.Safari", "com.apple.Safari"]
        mock_result = MagicMock()
        mock_result.enhanced = "enhanced prompt"
        mock_result.score_before = MagicMock(total=40)
        mock_result.score_after = MagicMock(total=65)
        mock_enhance.return_value = mock_result

        state = DaemonState()
        config = {"enhancement": {"max_tier": 2}}
        _on_hotkey(state, config)

        mock_save_undo.assert_called_once_with("old clipboard", "original prompt")
        mock_paste.assert_called_once_with("enhanced prompt")
        mock_notify_ok.assert_called_once_with(score_before=40, score_after=65)

    @patch("promptune.daemon.daemon.notify_error")
    @patch("promptune.daemon.daemon.save_clipboard")
    @patch("promptune.daemon.daemon.copy_selection")
    def test_empty_selection_notifies_error(
        self, mock_copy, mock_save_clip, mock_notify_err
    ):
        from promptune.daemon.daemon import _on_hotkey
        from promptune.daemon.ipc import DaemonState

        mock_save_clip.return_value = ""
        mock_copy.return_value = None

        state = DaemonState()
        config = {"enhancement": {"max_tier": 2}}
        _on_hotkey(state, config)

        mock_notify_err.assert_called_once_with("No text selected. Select text first.")

    @patch("promptune.daemon.daemon.notify_enhanced")
    @patch("promptune.daemon.daemon.notify_error")
    @patch("promptune.daemon.daemon.get_frontmost_app")
    @patch("promptune.daemon.daemon.write_clipboard")
    @patch("promptune.daemon.daemon.save_undo")
    @patch("promptune.daemon.daemon.save_clipboard")
    @patch("promptune.daemon.daemon.copy_selection")
    @patch("promptune.daemon.daemon.enhance")
    def test_app_focus_changed_skips_paste(
        self,
        mock_enhance,
        mock_copy,
        mock_save_clip,
        mock_save_undo,
        mock_write_clip,
        mock_frontmost,
        mock_notify_err,
        mock_notify_ok,
    ):
        from promptune.daemon.daemon import _on_hotkey
        from promptune.daemon.ipc import DaemonState

        mock_save_clip.return_value = ""
        mock_copy.return_value = "text"
        # App changes between start and end
        mock_frontmost.side_effect = ["com.apple.Safari", "com.apple.Terminal"]
        mock_result = MagicMock()
        mock_result.enhanced = "enhanced"
        mock_result.score_before = MagicMock(total=50)
        mock_result.score_after = MagicMock(total=70)
        mock_enhance.return_value = mock_result

        state = DaemonState()
        config = {"enhancement": {"max_tier": 2}}
        _on_hotkey(state, config)

        # Should write to clipboard but NOT simulate paste
        mock_write_clip.assert_called_once_with("enhanced")
        mock_notify_ok.assert_not_called()

    @patch("promptune.daemon.daemon.notify_error")
    @patch("promptune.daemon.daemon.get_frontmost_app")
    @patch("promptune.daemon.daemon.save_undo")
    @patch("promptune.daemon.daemon.save_clipboard")
    @patch("promptune.daemon.daemon.copy_selection")
    @patch("promptune.daemon.daemon.enhance")
    def test_engine_error_notifies(
        self,
        mock_enhance,
        mock_copy,
        mock_save_clip,
        mock_save_undo,
        mock_frontmost,
        mock_notify_err,
    ):
        from promptune.daemon.daemon import _on_hotkey
        from promptune.daemon.ipc import DaemonState

        mock_save_clip.return_value = ""
        mock_copy.return_value = "text"
        mock_frontmost.return_value = "com.apple.Safari"
        mock_enhance.side_effect = Exception("LLM timeout")

        state = DaemonState()
        config = {"enhancement": {"max_tier": 2}}
        _on_hotkey(state, config)

        mock_notify_err.assert_called_once_with(
            "Enhancement failed. Original text preserved."
        )


class TestDebounce:
    """Test that concurrent hotkey presses are debounced."""

    def test_debounce_flag(self):
        from promptune.daemon.daemon import _enhancing

        assert _enhancing.is_set() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_daemon/test_daemon.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement daemon module**

Create `promptune/daemon/daemon.py`:

```python
"""Main daemon loop — lifecycle, PID management, enhancement pipeline.

Orchestrates hotkey registration, clipboard pipeline, IPC, notifications,
and Ollama pre-warm into a background process.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from promptune.config import load_config
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
from promptune.daemon.ipc import DaemonState, start_ipc_server
from promptune.daemon.notify import notify_enhanced, notify_error
from promptune.engine import enhance

logger = logging.getLogger("promptune.daemon")

PID_FILE = Path("~/.local/share/promptune/daemon.pid").expanduser()
SOCKET_PATH = Path("~/.local/share/promptune/promptune.sock").expanduser()
LOG_FILE = Path("~/.local/share/promptune/daemon.log").expanduser()

# Debounce flag — prevents concurrent enhancements
_enhancing = threading.Event()


@dataclass
class DaemonStatus:
    """Snapshot of daemon state for status display."""

    running: bool
    pid: int | None
    uptime_seconds: float | None
    enhancement_count: int
    socket_exists: bool
    accessibility_granted: bool


def _write_pid() -> None:
    """Write current PID to file."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))


def _read_pid() -> int | None:
    """Read PID from file. Returns None if missing or invalid."""
    try:
        return int(PID_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def _is_running(pid: int) -> bool:
    """Check if a process with the given PID is alive."""
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _cleanup() -> None:
    """Remove PID file and socket file."""
    for path in (PID_FILE, SOCKET_PATH):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def get_status() -> DaemonStatus:
    """Get current daemon status."""
    pid = _read_pid()
    running = pid is not None and _is_running(pid)
    uptime = None
    enhancement_count = 0

    if running and PID_FILE.exists():
        uptime = time.time() - PID_FILE.stat().st_ctime

    return DaemonStatus(
        running=running,
        pid=pid if running else None,
        uptime_seconds=uptime,
        enhancement_count=enhancement_count,
        socket_exists=SOCKET_PATH.exists(),
        accessibility_granted=check_accessibility(),
    )


def _on_hotkey(state: DaemonState, config: dict[str, Any]) -> None:
    """Handle a hotkey press — the full enhancement pipeline."""
    if _enhancing.is_set():
        return  # Debounce
    _enhancing.set()

    try:
        # 1. Record frontmost app
        app_before = get_frontmost_app()

        # 2. Save current clipboard for undo
        original_clipboard = save_clipboard()

        # 3. Copy selection
        selected_text = copy_selection()
        if not selected_text:
            notify_error("No text selected. Select text first.")
            return

        # 4. Save undo buffer
        save_undo(original_clipboard, selected_text)

        # 5. Enhance via engine
        try:
            result = enhance(selected_text, config)
        except Exception:
            logger.exception("Enhancement failed")
            notify_error("Enhancement failed. Original text preserved.")
            return

        # 6. Check if app focus changed
        app_after = get_frontmost_app()
        if app_before == app_after:
            paste_result(result.enhanced)
            notify_enhanced(
                score_before=result.score_before.total,
                score_after=result.score_after.total,
            )
        else:
            write_clipboard(result.enhanced)
            notify_error("Enhanced text in clipboard — paste manually.")

        # 7. Update state
        with state.lock:
            state.enhancement_count += 1

    finally:
        _enhancing.clear()


def start_daemon(foreground: bool = False, config_path: Path | None = None) -> None:
    """Start the daemon process.

    Args:
        foreground: If True, run in foreground (for debugging / launchd).
        config_path: Override config file path.
    """
    # Check if already running
    pid = _read_pid()
    if pid is not None and _is_running(pid):
        print(f"Daemon already running (pid {pid})")
        sys.exit(0)

    # Remove stale PID
    if pid is not None:
        _cleanup()

    # Verify accessibility
    if not check_accessibility():
        print(
            "Error: Accessibility permission not granted.\n"
            "Run: promptune daemon setup"
        )
        sys.exit(1)

    # Load config
    config = load_config(config_path, validate_keys=False)
    daemon_config = config.get("daemon", {})

    # Parse hotkey
    hotkey_str = daemon_config.get("hotkey", "ctrl+shift+e")
    keycode, modifier_mask = parse_hotkey(hotkey_str)

    # Create data dir
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Daemonise if not foreground
    if not foreground:
        _daemonise()

    # Write PID
    _write_pid()

    # Setup logging
    logging.basicConfig(
        filename=str(LOG_FILE),
        level=getattr(logging, daemon_config.get("log_level", "info").upper()),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logger.info("Daemon starting (pid %d)", os.getpid())

    # Signal handlers
    state = DaemonState()

    def _handle_term(signum: int, frame: Any) -> None:
        logger.info("Received signal %d, shutting down", signum)
        _cleanup()
        stop_run_loop()

    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)

    # Start IPC server
    start_ipc_server(state)

    # Start Ollama pre-warm
    if daemon_config.get("ollama_prewarm", True):
        from promptune.daemon.prewarm import prewarm_ollama, start_prewarm_timer

        llm_config = config.get("local_llm", {})
        host = llm_config.get("host", "http://localhost:11434")
        model = llm_config.get("model", "qwen2.5:3b")
        keepalive_min = daemon_config.get("ollama_keepalive_minutes", 30)

        # Initial pre-warm in background thread
        threading.Thread(
            target=prewarm_ollama, args=(host, model), daemon=True
        ).start()
        start_prewarm_timer(host, model, interval_minutes=keepalive_min - 5)

    # Register hotkey
    def _hotkey_callback() -> None:
        threading.Thread(
            target=_on_hotkey, args=(state, config), daemon=True
        ).start()

    register_hotkey(_hotkey_callback, keycode, modifier_mask)
    logger.info("Hotkey registered: %s", hotkey_str)

    # Enter run loop (blocks)
    start_run_loop()
    logger.info("Daemon stopped")


def stop_daemon() -> None:
    """Stop the running daemon."""
    pid = _read_pid()
    if pid is None:
        print("Daemon not running (no PID file)")
        return

    if not _is_running(pid):
        print("Daemon not running (stale PID file)")
        _cleanup()
        return

    os.kill(pid, signal.SIGTERM)

    # Wait up to 3 seconds
    for _ in range(30):
        if not _is_running(pid):
            break
        time.sleep(0.1)
    else:
        os.kill(pid, signal.SIGKILL)

    _cleanup()
    print("Daemon stopped")


def _daemonise() -> None:
    """Fork and detach from terminal (classic Unix daemon pattern)."""
    pid = os.fork()
    if pid > 0:
        sys.exit(0)  # Parent exits

    os.setsid()

    # Redirect stdio to log
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    devnull = os.open(os.devnull, os.O_RDWR)
    log_fd = os.open(str(LOG_FILE), os.O_WRONLY | os.O_CREAT | os.O_APPEND)
    os.dup2(devnull, 0)
    os.dup2(log_fd, 1)
    os.dup2(log_fd, 2)
    os.close(devnull)
    os.close(log_fd)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_daemon/test_daemon.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/daemon/daemon.py tests/test_daemon/test_daemon.py
git commit -m "feat(daemon): add main daemon module with lifecycle, PID, pipeline"
```

---

## Task 10: CLI — Daemon Command Group

**Files:**
- Modify: `promptune/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_cli.py`:

```python
class TestDaemonCommands:
    """Test daemon CLI subcommands."""

    def test_daemon_group_exists(self, runner):
        result = runner.invoke(main, ["daemon", "--help"])
        assert result.exit_code == 0
        assert "start" in result.output
        assert "stop" in result.output
        assert "status" in result.output

    def test_daemon_start_help(self, runner):
        result = runner.invoke(main, ["daemon", "start", "--help"])
        assert result.exit_code == 0
        assert "--foreground" in result.output

    def test_daemon_status(self, runner, mocker):
        mock_status = mocker.MagicMock(
            running=False,
            pid=None,
            uptime_seconds=None,
            enhancement_count=0,
            socket_exists=False,
            accessibility_granted=True,
        )
        mocker.patch(
            "promptune.cli.get_daemon_status",
            return_value=mock_status,
        )
        result = runner.invoke(main, ["daemon", "status"])
        assert result.exit_code == 0
        assert "not running" in result.output.lower() or "Not running" in result.output

    def test_daemon_setup_command_exists(self, runner):
        result = runner.invoke(main, ["daemon", "setup", "--help"])
        assert result.exit_code == 0

    def test_daemon_diagnose_command_exists(self, runner):
        result = runner.invoke(main, ["daemon", "diagnose", "--help"])
        assert result.exit_code == 0

    def test_daemon_install_login_item_exists(self, runner):
        result = runner.invoke(main, ["daemon", "install-login-item", "--help"])
        assert result.exit_code == 0

    def test_daemon_uninstall_login_item_exists(self, runner):
        result = runner.invoke(main, ["daemon", "uninstall-login-item", "--help"])
        assert result.exit_code == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli.py::TestDaemonCommands -v`
Expected: FAIL with `"No such command 'daemon'"`

- [ ] **Step 3: Add daemon command group to CLI**

In `promptune/cli.py`, add the import at the top (lazy, inside functions to avoid import on non-macOS):

```python
# Near other imports, add:
import sys
```

Then add the daemon command group after the existing commands:

```python
@main.group()
def daemon():
    """Manage the promptune background daemon (macOS)."""
    if sys.platform != "darwin":
        click.echo("Error: daemon is only available on macOS.", err=True)
        raise SystemExit(1)


@daemon.command()
@click.option("--foreground", is_flag=True, help="Run in foreground (debug mode)")
def start(foreground):
    """Start the background daemon."""
    from promptune.daemon.daemon import start_daemon

    start_daemon(foreground=foreground)


@daemon.command()
def stop():
    """Stop the running daemon."""
    from promptune.daemon.daemon import stop_daemon

    stop_daemon()


@daemon.command()
def restart():
    """Restart the daemon."""
    from promptune.daemon.daemon import stop_daemon, start_daemon

    stop_daemon()
    start_daemon()


@daemon.command()
def status():
    """Show daemon status."""
    from promptune.daemon.daemon import get_status as get_daemon_status

    s = get_daemon_status()
    if s.running:
        uptime = ""
        if s.uptime_seconds is not None:
            mins = int(s.uptime_seconds // 60)
            hours = mins // 60
            mins = mins % 60
            uptime = f" (uptime {hours}h{mins:02d}m)"
        click.echo(f"Daemon running (pid {s.pid}){uptime}")
        click.echo(f"  Enhancements: {s.enhancement_count}")
        click.echo(f"  Socket: {'exists' if s.socket_exists else 'missing'}")
    else:
        click.echo("Daemon not running")
    click.echo(f"  Accessibility: {'granted' if s.accessibility_granted else 'denied'}")


# Make get_daemon_status importable for test mocking
def get_daemon_status():
    """Wrapper for test mocking."""
    from promptune.daemon.daemon import get_status
    return get_status()


# Re-implement status to use the wrapper
@daemon.command("status")
def status():
    """Show daemon status."""
    s = get_daemon_status()
    if s.running:
        uptime = ""
        if s.uptime_seconds is not None:
            mins = int(s.uptime_seconds // 60)
            hours = mins // 60
            mins = mins % 60
            uptime = f" (uptime {hours}h{mins:02d}m)"
        click.echo(f"Daemon running (pid {s.pid}){uptime}")
        click.echo(f"  Enhancements: {s.enhancement_count}")
        click.echo(f"  Socket: {'exists' if s.socket_exists else 'missing'}")
    else:
        click.echo("Daemon not running")
    click.echo(f"  Accessibility: {'granted' if s.accessibility_granted else 'denied'}")


@daemon.command()
def setup():
    """Guide through Accessibility permission setup."""
    from promptune.daemon.hotkey import check_accessibility, request_accessibility

    if check_accessibility():
        click.echo("Accessibility permission already granted.")
        return

    click.echo("Accessibility permission required for global hotkey.")
    click.echo("Opening System Settings...")

    import subprocess
    subprocess.run([
        "open",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    ])

    click.echo("Add your terminal app to the Accessibility list.")
    click.echo("Waiting for permission (60s timeout)...")

    request_accessibility()

    import time
    for i in range(60):
        if check_accessibility():
            click.echo("Accessibility permission granted!")
            return
        time.sleep(1)

    click.echo("Timeout. Grant permission manually and retry.")


@daemon.command()
def diagnose():
    """Run diagnostic checks on daemon health."""
    s = get_daemon_status()

    def _check(label, ok, detail=""):
        mark = "✓" if ok else "✗"
        line = f"  {label:<20} {mark}  {detail}"
        click.echo(line)

    click.echo("promptune daemon diagnose\n")
    _check("Daemon PID", s.running, f"pid {s.pid}" if s.running else "Not running")
    _check("Socket", s.socket_exists)
    _check("Accessibility", s.accessibility_granted)

    from promptune.daemon.launchagent import is_installed
    _check("LaunchAgent", is_installed())

    if not s.running:
        click.echo("\n  Issues:")
        click.echo("    - Start daemon: promptune daemon start")
    if not is_installed():
        click.echo("    - Install LaunchAgent: promptune daemon install-login-item")


@daemon.command("install-login-item")
def install_login_item():
    """Install LaunchAgent for auto-start on login."""
    from promptune.daemon.launchagent import install_login_item as _install

    _install()
    click.echo("LaunchAgent installed. Daemon will start on login.")


@daemon.command("uninstall-login-item")
def uninstall_login_item():
    """Remove LaunchAgent (disable auto-start)."""
    from promptune.daemon.launchagent import uninstall_login_item as _uninstall

    _uninstall()
    click.echo("LaunchAgent removed.")
```

**Important:** The above has a duplicate `status` command. The correct implementation removes the first `status` and keeps only the version using `get_daemon_status()`. The `sys` import is already present at the top of `cli.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli.py::TestDaemonCommands -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add promptune/cli.py tests/test_cli.py
git commit -m "feat(cli): add daemon command group with start/stop/status/setup/diagnose"
```

---

## Task 11: Shell Widget IPC Reporting

**Files:**
- Modify: `promptune/shell.py`
- Modify: `tests/test_shell.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_shell.py`:

```python
class TestIPCReporting:
    """Test that shell widgets include daemon IPC CWD reporting."""

    def test_zsh_widget_includes_ipc(self):
        from promptune.shell import _generate_zsh_widget

        script = _generate_zsh_widget("'^E'")
        assert "promptune.sock" in script or "report_cwd" in script

    def test_bash_widget_includes_ipc(self):
        from promptune.shell import _generate_bash_widget

        script = _generate_bash_widget('"\\C-e"')
        assert "promptune.sock" in script or "report_cwd" in script

    def test_fish_widget_includes_ipc(self):
        from promptune.shell import _generate_fish_widget

        script = _generate_fish_widget("\\ce")
        assert "promptune.sock" in script or "report_cwd" in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_shell.py::TestIPCReporting -v`
Expected: FAIL (assertion — widgets don't have IPC lines yet)

- [ ] **Step 3: Update shell widget generators**

In `promptune/shell.py`, update `_generate_zsh_widget` to add IPC reporting after `zle redisplay`:

Replace the function body so the widget function includes:
```bash
    # Report CWD to daemon (non-blocking, best-effort)
    echo '{{"action":"report_cwd","cwd":"'$PWD'","project_root":"'$(git rev-parse --show-toplevel 2>/dev/null)'"}}' | \
        socat - UNIX-CONNECT:~/.local/share/promptune/promptune.sock 2>/dev/null &
```

Insert this line in each widget:
- **zsh**: Before `zle redisplay`
- **bash**: At the end of the function body
- **fish**: Before the final `end`

Updated `_generate_zsh_widget`:
```python
def _generate_zsh_widget(key: str) -> str:
    """Generate zsh ZLE widget script with parameterized key."""
    return f"""\
# Promptune Zsh Widget
# Add to .zshrc: eval "$(promptune shell-init)"

_promptune_enhance() {{
    local original="$BUFFER"
    if [[ -z "$original" ]]; then
        return
    fi
    local enhanced
    enhanced=$(promptune enhance --no-tui "$original" 2>/dev/null)
    if [[ $? -eq 0 && -n "$enhanced" ]]; then
        BUFFER="$enhanced"
        CURSOR=${{#BUFFER}}
    fi
    # Report CWD to daemon (non-blocking, best-effort)
    echo '{{"action":"report_cwd","cwd":"'$PWD'","project_root":"'$(git rev-parse --show-toplevel 2>/dev/null)'"}}' | \\
        socat - UNIX-CONNECT:~/.local/share/promptune/promptune.sock 2>/dev/null &
    zle redisplay
}}

zle -N _promptune_enhance
bindkey {key} _promptune_enhance
"""
```

Updated `_generate_bash_widget`:
```python
def _generate_bash_widget(key: str) -> str:
    """Generate bash readline widget script with parameterized key."""
    return f"""\
# Promptune Bash Widget
# Add to .bashrc: eval "$(promptune shell-init)"

_promptune_enhance() {{
    if [[ -z "$READLINE_LINE" ]]; then
        return
    fi
    local enhanced
    enhanced=$(promptune enhance --no-tui "$READLINE_LINE" 2>/dev/null)
    if [[ $? -eq 0 && -n "$enhanced" ]]; then
        READLINE_LINE="$enhanced"
        READLINE_POINT=${{#READLINE_LINE}}
    fi
    # Report CWD to daemon (non-blocking, best-effort)
    echo '{{"action":"report_cwd","cwd":"'$PWD'","project_root":"'$(git rev-parse --show-toplevel 2>/dev/null)'"}}' | \\
        socat - UNIX-CONNECT:~/.local/share/promptune/promptune.sock 2>/dev/null &
}}
bind -x '{key}: _promptune_enhance'
"""
```

Updated `_generate_fish_widget`:
```python
def _generate_fish_widget(key: str) -> str:
    """Generate fish shell widget script with parameterized key."""
    return f"""\
# Promptune Fish Widget
# Add to config.fish: promptune shell-init | source

function _promptune_enhance
    set -l original (commandline)
    if test -z "$original"
        return
    end
    set -l enhanced (promptune enhance --no-tui "$original" 2>/dev/null)
    if test $status -eq 0 -a -n "$enhanced"
        commandline -r "$enhanced"
    end
    # Report CWD to daemon (non-blocking, best-effort)
    echo '{{"action":"report_cwd","cwd":"'(pwd)'","project_root":"'(git rev-parse --show-toplevel 2>/dev/null)'"}}' | \\
        socat - UNIX-CONNECT:~/.local/share/promptune/promptune.sock 2>/dev/null &
end
bind {key} _promptune_enhance
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_shell.py -v`
Expected: ALL PASS (including existing tests — verify no regressions)

- [ ] **Step 5: Commit**

```bash
git add promptune/shell.py tests/test_shell.py
git commit -m "feat(shell): add IPC CWD reporting to shell widgets"
```

---

## Task 12: Dependencies and Documentation

**Files:**
- Modify: `pyproject.toml`
- Modify: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Update pyproject.toml dependencies**

Add to the `dependencies` list in `pyproject.toml`:

```toml
    "pyobjc-framework-Quartz>=10.0; sys_platform == 'darwin'",
    "pyobjc-framework-ApplicationServices>=10.0; sys_platform == 'darwin'",
    "pyobjc-framework-Cocoa>=10.0; sys_platform == 'darwin'",
```

Also add mypy override for pyobjc:

```toml
[[tool.mypy.overrides]]
module = ["Quartz", "ApplicationServices", "AppKit"]
ignore_missing_imports = true
```

- [ ] **Step 2: Update ARCHITECTURE.md**

Add a "Daemon Layer" section to `docs/ARCHITECTURE.md` describing the daemon architecture, module responsibilities, and data flow. Reference the spec for full details.

- [ ] **Step 3: Run full test suite**

Run: `pytest --cov=promptune --cov-report=term-missing -v`
Expected: ALL PASS, coverage ≥ 90%

- [ ] **Step 4: Run linter and type checker**

Run: `ruff check . && mypy promptune/`
Expected: No errors

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml docs/ARCHITECTURE.md
git commit -m "feat(daemon): add pyobjc deps, update architecture docs"
```

---

## Summary

| Task | Module | Parallelisable | Depends on |
|------|--------|---------------|------------|
| 1 | Config defaults | No (prerequisite) | — |
| 2 | Package init | Yes | Task 1 |
| 3 | Hotkey | Yes | Task 1, 2 |
| 4 | Clipboard | Yes | Task 1, 2 |
| 5 | Notify | Yes | Task 1, 2 |
| 6 | IPC | Yes | Task 1, 2 |
| 7 | Prewarm | Yes | Task 1, 2 |
| 8 | LaunchAgent | Yes | Task 1, 2 |
| 9 | Main daemon | No | Tasks 3-8 |
| 10 | CLI commands | No | Task 9 |
| 11 | Shell IPC | No | Task 6 |
| 12 | Deps & docs | No | All above |
