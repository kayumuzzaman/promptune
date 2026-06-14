# Phase 2: OS-Level Hotkey Daemon (macOS) — Design Spec

**Date:** 2026-03-28
**Status:** Draft
**Scope:** macOS background daemon with global hotkey, clipboard pipeline, IPC, notifications

## Overview

Phase 2 extends promptune from terminal-only (CLI + TUI + shell widgets) to system-wide. A background daemon registers a global hotkey (Ctrl+Shift+E) that works in any macOS application — text editors, browsers, Slack, email, anything with a text field. The user selects text, presses the hotkey, and the prompt is enhanced in-place. No IDE plugins, no browser extensions, no app-specific integrations.

This is a personal tool for one macOS user. Design decisions favour simplicity and debuggability over robustness at scale. No multi-user concerns, no sandboxing, no notarisation.

**What ships:**
- `promptune daemon start|stop|restart|status|setup|diagnose`
- `promptune daemon install-login-item|uninstall-login-item`
- Global hotkey via CGEventTap (Ctrl+Shift+E, customisable)
- Clipboard pipeline: copy -> enhance -> paste
- IPC Unix socket for shell widget CWD reporting
- macOS notifications on completion
- Ollama model pre-warm on startup
- Silent mode (no TUI, Cmd+Z to undo)

**Out of scope:** Linux support (Phase 3), Windows support, menu bar icon, multi-hotkey profiles.

---

## Architecture

```
┌────────────────────────────────────────────────────┐
│                  promptune daemon                   │
│                  (background process)                │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  hotkey.py   │  │ clipboard.py │  │  notify.py │ │
│  │  CGEventTap  │  │  pbcopy/     │  │  osascript  │ │
│  │  listener    │  │  pbpaste     │  │  notif.     │ │
│  └──────┬───────┘  └──────┬───────┘  └─────┬──────┘ │
│         │                 │                │        │
│         v                 v                v        │
│  ┌─────────────────────────────────────────────────┐│
│  │              daemon.py (main loop)              ││
│  │  - Hotkey callback → clipboard pipeline         ││
│  │  - IPC socket listener                          ││
│  │  - Ollama pre-warm                              ││
│  │  - PID file management                          ││
│  └───────────────────┬─────────────────────────────┘│
│                      │                              │
│         ┌────────────┼────────────┐                 │
│         v            v            v                 │
│    engine.py    history.py   ipc.py                 │
│    (existing)   (existing)   (Unix socket)          │
│                                                     │
└────────────────────────────────────────────────────┘

External:
  Shell widget (zsh/bash/fish) ──IPC──> daemon (reports CWD)
  LaunchAgent plist ──launchd──> daemon auto-start
```

### Data Flow (hotkey press)

```
1. User selects text in any app
2. User presses Ctrl+Shift+E
3. CGEventTap fires callback in hotkey.py
4. daemon.py records frontmost app (via NSWorkspace)
5. clipboard.py saves current clipboard to undo buffer
6. clipboard.py simulates Cmd+C (CGEvent key event)
7. clipboard.py waits 100ms for clipboard to populate
8. clipboard.py reads clipboard via pbpaste
9. If empty or non-text → notify.py shows error, abort
10. engine.enhance(text, config) — reuses existing engine
11. clipboard.py writes result via pbcopy
12. clipboard.py checks frontmost app hasn't changed
    - Same app → simulate Cmd+V
    - Different app → notify "Enhanced text in clipboard"
13. notify.py shows "Prompt enhanced (+N PQS). Cmd+Z to undo."
14. history.py records the enhancement (decision="accept", silent mode)
```

---

## Daemon Lifecycle

### PID and Socket Paths

```python
PID_FILE = Path("~/.local/share/promptune/daemon.pid").expanduser()
SOCKET_PATH = Path("~/.local/share/promptune/promptune.sock").expanduser()
LOG_FILE = Path("~/.local/share/promptune/daemon.log").expanduser()
UNDO_FILE = Path("~/.local/share/promptune/undo.txt").expanduser()
```

### `promptune daemon start`

```python
def start_daemon(foreground: bool = False) -> None:
    """Start the daemon process.

    Args:
        foreground: If True, run in foreground (for debugging).
                    If False, fork and detach (daemonize).
    """
```

Steps:
1. Check if already running (read PID file, check `os.kill(pid, 0)`)
2. If already running, print PID and exit
3. Verify Accessibility permission (see Section: Global Hotkey)
4. Create data directory if needed
5. If not foreground: `os.fork()` + `os.setsid()` + redirect stdout/stderr to log file
6. Write PID to `daemon.pid`
7. Start Ollama pre-warm (background thread)
8. Start IPC socket listener (background thread)
9. Register global hotkey via CGEventTap
10. Enter CFRunLoop (blocks — this is the main loop)

### `promptune daemon stop`

1. Read PID from `daemon.pid`
2. Send `SIGTERM` to process
3. Wait up to 3 seconds for process to exit
4. If still running, send `SIGKILL`
5. Remove PID file and socket file

### `promptune daemon restart`

Stop then start. Simple.

### `promptune daemon status`

```python
@dataclass
class DaemonStatus:
    running: bool
    pid: int | None
    uptime_seconds: float | None
    enhancement_count: int
    last_enhancement_ago: str | None  # "2m ago"
    socket_exists: bool
    accessibility_granted: bool
```

Read PID file, check process alive, stat the PID file for uptime (ctime), query IPC socket for stats.

### `promptune daemon setup`

Interactive walkthrough:
1. Check macOS version (Monterey 12+ required)
2. Check if Accessibility permission is granted
3. If not: open System Settings to the right pane via `open "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"`
4. Print step-by-step instructions: "Add Terminal.app (or iTerm/Alacritty) to the Accessibility list"
5. Poll for permission grant (1-second interval, 60-second timeout)
6. Confirm success or print manual steps

### `promptune daemon diagnose`

```
promptune daemon diagnose

  Daemon PID     ✓  Running (pid 4821, uptime 2h14m)
  Socket         ✓  ~/.local/share/promptune/promptune.sock
  Accessibility  ✓  Granted
  Hotkey         ✓  Ctrl+Shift+E registered
  Ollama         ✓  Model qwen2.5:3b loaded (warm)
  LaunchAgent    ✗  Not installed
  Log file       ✓  ~/.local/share/promptune/daemon.log (12KB)

  Issues:
    - Install LaunchAgent for auto-start: promptune daemon install-login-item
```

---

## Global Hotkey

### Implementation: CGEventTap via pyobjc

Use `Quartz.CGEventTapCreate` directly via pyobjc. This is more reliable than pynput for macOS — pynput wraps CGEventTap anyway, and the extra abstraction layer adds failure modes without adding value for a macOS-only tool.

```python
# hotkey.py

from __future__ import annotations

import Quartz
from typing import Callable


# Modifier masks for Ctrl+Shift
CTRL_SHIFT_MASK = Quartz.kCGEventFlagMaskControl | Quartz.kCGEventFlagMaskShift

# Default hotkey: 'e' keycode = 14
DEFAULT_HOTKEY_KEYCODE = 14


def _event_callback(
    proxy: int,
    event_type: int,
    event: Quartz.CGEventRef,
    callback: Callable[[], None],
) -> Quartz.CGEventRef | None:
    """CGEventTap callback. Fires on key down matching hotkey."""
    if event_type == Quartz.kCGEventKeyDown:
        keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )
        flags = Quartz.CGEventGetFlags(event)
        # Mask out caps lock and other irrelevant flags
        relevant_flags = flags & (
            Quartz.kCGEventFlagMaskControl
            | Quartz.kCGEventFlagMaskShift
            | Quartz.kCGEventFlagMaskAlternate
            | Quartz.kCGEventFlagMaskCommand
        )
        if keycode == DEFAULT_HOTKEY_KEYCODE and relevant_flags == CTRL_SHIFT_MASK:
            callback()
            return None  # Swallow the event
    return event


def check_accessibility() -> bool:
    """Check if Accessibility permission is granted."""
    import ApplicationServices
    return ApplicationServices.AXIsProcessTrustedWithOptions(
        {ApplicationServices.kAXTrustedCheckOptionPrompt: False}
    )


def request_accessibility() -> bool:
    """Prompt macOS to show Accessibility permission dialog."""
    import ApplicationServices
    return ApplicationServices.AXIsProcessTrustedWithOptions(
        {ApplicationServices.kAXTrustedCheckOptionPrompt: True}
    )


def register_hotkey(callback: Callable[[], None]) -> Quartz.CFMachPortRef:
    """Register global hotkey tap. Returns the tap for cleanup."""
    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionDefault,  # active tap (can swallow events)
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown),
        lambda proxy, etype, event, _: _event_callback(proxy, etype, event, callback),
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

### Hotkey Customisation

Config key maps a human-readable string to a macOS keycode:

```python
# Key name to macOS keycode mapping (US keyboard layout)
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


def parse_hotkey(hotkey_str: str) -> tuple[int, int]:
    """Parse 'ctrl+shift+e' into (keycode, modifier_mask)."""
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
```

### Accessibility Permission

CGEventTap requires Accessibility permission. Without it, `CGEventTapCreate` returns `None`. The daemon must:

1. On startup: call `check_accessibility()`. If denied, print clear error and exit with code 1.
2. `promptune daemon setup`: call `request_accessibility()` which triggers the macOS permission dialog, then poll `check_accessibility()` until granted or timeout.
3. `promptune daemon diagnose`: report permission status.

### Secure Input Detection

macOS enables "secure input" mode for password fields (`SecureEventInput`). When active, CGEventTap receives no events. Detect this and skip gracefully:

```python
def is_secure_input_active() -> bool:
    """Check if macOS secure input is active (password field focused)."""
    return Quartz.CGSIsSecureEventInputSet()
```

If secure input is detected when the hotkey fires (which it won't — the tap is silenced), the daemon does nothing. More importantly, if `pbpaste` returns empty after Cmd+C simulation and secure input was recently active, the daemon should not show an error — just silently skip.

---

## Clipboard Pipeline

### Module: `clipboard.py`

```python
from __future__ import annotations

import subprocess
import time

import Quartz


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


def simulate_cmd_c() -> None:
    """Simulate Cmd+C via CGEvent."""
    _simulate_key_combo(keycode=8, modifier=Quartz.kCGEventFlagMaskCommand)


def simulate_cmd_v() -> None:
    """Simulate Cmd+V via CGEvent."""
    _simulate_key_combo(keycode=9, modifier=Quartz.kCGEventFlagMaskCommand)


def _simulate_key_combo(keycode: int, modifier: int) -> None:
    """Simulate a modifier+key press and release."""
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateCombinedSessionState)

    key_down = Quartz.CGEventCreateKeyboardEvent(source, keycode, True)
    Quartz.CGEventSetFlags(key_down, modifier)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_down)

    key_up = Quartz.CGEventCreateKeyboardEvent(source, keycode, False)
    Quartz.CGEventSetFlags(key_up, modifier)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, key_up)


def get_frontmost_app() -> str:
    """Get bundle ID of the frontmost application."""
    from AppKit import NSWorkspace
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() or ""


CLIPBOARD_SETTLE_MS = 100  # Time for clipboard to populate after Cmd+C


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
    time.sleep(0.05)  # Brief settle
    simulate_cmd_v()
```

### Undo Buffer

Before enhancing, save the original clipboard and the original selected text to `UNDO_FILE`:

```python
def save_undo(original_clipboard: str | None, selected_text: str) -> None:
    """Save originals for undo recovery."""
    import json
    data = {
        "original_clipboard": original_clipboard,
        "selected_text": selected_text,
        "timestamp": time.time(),
    }
    UNDO_FILE.write_text(json.dumps(data))
```

The user's native Cmd+Z in the target app handles undo for the paste operation. The `UNDO_FILE` is a backup if Cmd+Z doesn't work (e.g., app doesn't support undo). A future `promptune daemon undo` command could restore from this file.

---

## IPC — Unix Socket

### Purpose

The shell widget (zsh/bash/fish) reports its CWD to the daemon on each invocation. This gives the daemon context about the user's current project even when the hotkey is pressed in a non-terminal app.

### Module: `ipc.py`

```python
from __future__ import annotations

import json
import os
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
        server.settimeout(1.0)  # Allow periodic shutdown checks

        while True:
            try:
                conn, _ = server.accept()
                data = conn.recv(4096).decode("utf-8")
                _handle_message(data, state, conn)
                conn.close()
            except socket.timeout:
                continue
            except OSError:
                break  # Socket was closed

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
        # Wait briefly for response
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

### Shell Widget Integration

The existing shell widgets (`shell.py`) need a one-line addition: after calling `promptune enhance`, report CWD to the daemon socket. This happens in the background and never blocks the widget.

Updated zsh widget excerpt:

```bash
_promptune_enhance() {
    local original="$BUFFER"
    if [[ -z "$original" ]]; then return; fi
    local enhanced
    enhanced=$(promptune enhance --no-tui "$original" 2>/dev/null)
    if [[ $? -eq 0 && -n "$enhanced" ]]; then
        BUFFER="$enhanced"
        CURSOR=${#BUFFER}
    fi
    # Report CWD to daemon (non-blocking, best-effort)
    echo "{\"action\":\"report_cwd\",\"cwd\":\"$PWD\",\"project_root\":\"$(git rev-parse --show-toplevel 2>/dev/null)\"}" | \
        socat - UNIX-CONNECT:~/.local/share/promptune/promptune.sock 2>/dev/null &
    zle redisplay
}
```

Note: `socat` is used as a lightweight Unix socket client. If not available, a Python one-liner fallback via `promptune daemon report-cwd` command can be used. This is a best-effort enhancement — failure is silently ignored.

---

## Silent Mode

The daemon always operates in silent mode. There is no TUI, no interactive prompt, no accept/reject/edit flow. The pipeline is:

1. Copy selected text
2. Enhance via `engine.enhance()`
3. Paste result back
4. Show macOS notification with score delta

The user undoes with Cmd+Z in the target app. This is the standard macOS undo model — no promptune-specific undo mechanism needed for the common case.

All daemon enhancements are recorded in history with `decision="accept"` since there is no reject/edit flow. A future iteration could add a notification action button for reject.

---

## macOS Notifications

### Module: `notify.py`

Use `osascript` for notifications — no additional dependencies, works on all macOS versions.

```python
from __future__ import annotations

import subprocess


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


def _escape(text: str) -> str:
    """Escape double quotes for AppleScript strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


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

### Notification Scenarios

| Scenario | Notification |
|----------|-------------|
| Success | "Prompt enhanced (+12 PQS). Cmd+Z to undo." |
| Empty clipboard after Cmd+C | "No text selected. Select text first." |
| Non-text clipboard | "Clipboard contains non-text content." |
| App focus changed | "Enhanced text in clipboard -- paste manually." |
| Engine error | "Enhancement failed. Original text preserved." |
| Secure input active | No notification (silent skip) |

---

## Ollama Pre-Warm

On daemon startup, load the configured local LLM model so Tier 1 enhancements have no cold-start delay.

```python
def prewarm_ollama(host: str, model: str) -> None:
    """Send a minimal request to load the model into memory.

    Runs in a background thread. Failure is logged but never fatal.
    """
    import httpx

    try:
        # Ollama's /api/generate with empty prompt loads the model
        resp = httpx.post(
            f"{host}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": "30m"},
            timeout=60.0,
        )
        if resp.status_code == 200:
            _log("Ollama pre-warm: model loaded")
        else:
            _log(f"Ollama pre-warm: HTTP {resp.status_code}")
    except Exception as e:
        _log(f"Ollama pre-warm: {e}")
```

The `keep_alive: "30m"` parameter tells Ollama to keep the model loaded for 30 minutes without requests. The daemon re-warms every 25 minutes via a timer thread.

---

## Config Additions

New `[daemon]` section in `config.toml`:

```toml
[daemon]
hotkey = "ctrl+shift+e"             # Global hotkey (modifier+key format)
clipboard_settle_ms = 100           # Wait after Cmd+C before reading clipboard
notify = true                       # Show macOS notifications
notify_sound = true                 # Play sound with notifications
ollama_prewarm = true               # Pre-load Ollama model on daemon start
ollama_keepalive_minutes = 30       # Ollama keep_alive duration
log_level = "info"                  # debug | info | warning | error
```

### Config Defaults (addition to `config.py`)

```python
# Added to DEFAULT_CONFIG
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

---

## Edge Cases

| Case | Behaviour |
|------|-----------|
| Accessibility denied | `CGEventTapCreate` returns None. Daemon prints error, exits with code 1. `promptune daemon setup` guides user. |
| Secure input (password field) | CGEventTap is silenced by macOS. Hotkey simply doesn't fire. No action needed. |
| Empty clipboard after Cmd+C | Notify "No text selected." Do not proceed. |
| Non-text clipboard (image, file) | `pbpaste` returns empty for non-text. Same handling as empty clipboard. |
| App focus changes during enhancement | Compare frontmost app before and after. If different, skip Cmd+V, notify "Enhanced text in clipboard." |
| Hotkey pressed during enhancement | Debounce — ignore hotkey if an enhancement is already in progress. Use a threading `Event` flag. |
| Socket file exists but daemon dead | `promptune daemon start` removes stale socket before binding. |
| PID file exists but process dead | `promptune daemon start` checks `os.kill(pid, 0)`. If process dead, removes stale PID file and starts. |
| Ollama not running | Pre-warm fails silently. Tier 1 fails at enhancement time, falls back to Tier 0 or Tier 2. |
| Very long prompt (>10K chars) | Engine handles this already. Clipboard has no practical size limit. |
| Enhancement takes >10s | Engine timeout applies. On timeout, notify "Enhancement timed out. Original preserved." |
| Daemon crash | LaunchAgent with KeepAlive restarts it automatically. |
| Multiple daemon instances | PID file prevents double-start. Second `promptune daemon start` prints "Already running." |
| macOS sleep/wake | CGEventTap survives sleep. Ollama model may be unloaded — re-warm on wake via `NSWorkspace` notification. |

---

## LaunchAgent

### `promptune daemon install-login-item`

Creates `~/Library/LaunchAgents/dev.promptune.daemon.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>dev.promptune.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
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
    <string>{LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>{LOG_FILE}</string>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
```

`--foreground` is used because launchd manages the process lifecycle — no need for the daemon to fork.

### `promptune daemon uninstall-login-item`

1. `launchctl unload ~/Library/LaunchAgents/dev.promptune.daemon.plist`
2. Remove the plist file

---

## New Files

| File | Purpose |
|------|---------|
| `promptune/daemon/__init__.py` | Package init, re-exports |
| `promptune/daemon/daemon.py` | Main daemon loop — lifecycle, signal handlers, orchestration |
| `promptune/daemon/hotkey.py` | CGEventTap registration, hotkey parsing, accessibility checks |
| `promptune/daemon/clipboard.py` | Clipboard read/write, Cmd+C/V simulation, undo buffer |
| `promptune/daemon/ipc.py` | Unix socket server/client, CWD tracking, status queries |
| `promptune/daemon/notify.py` | macOS notifications via osascript |
| `promptune/daemon/prewarm.py` | Ollama model pre-warm and keep-alive timer |
| `promptune/daemon/launchagent.py` | LaunchAgent plist generation, install/uninstall |
| `tests/test_daemon/__init__.py` | Test package init |
| `tests/test_daemon/test_daemon.py` | Daemon lifecycle tests |
| `tests/test_daemon/test_hotkey.py` | Hotkey parsing, accessibility check mocking |
| `tests/test_daemon/test_clipboard.py` | Clipboard pipeline tests (mock subprocess) |
| `tests/test_daemon/test_ipc.py` | IPC socket communication tests |
| `tests/test_daemon/test_notify.py` | Notification tests (mock osascript) |
| `tests/test_daemon/test_prewarm.py` | Ollama pre-warm tests (mock httpx) |
| `tests/test_daemon/test_launchagent.py` | Plist generation and file management tests |

---

## Modified Files

| File | Change |
|------|--------|
| `promptune/cli.py` | Add `daemon` command group with `start`, `stop`, `restart`, `status`, `setup`, `diagnose`, `install-login-item`, `uninstall-login-item` subcommands |
| `promptune/config.py` | Add `[daemon]` section to `DEFAULT_CONFIG` with hotkey, notify, prewarm keys |
| `promptune/shell.py` | Add IPC CWD reporting line to generated shell widgets (zsh, bash, fish) |
| `config.example.toml` | Add `[daemon]` section with documented keys |
| `tests/test_cli.py` | Test daemon CLI subcommands (argument parsing, help text) |
| `tests/test_config.py` | Test new daemon config defaults and validation |
| `tests/test_shell.py` | Test that generated widgets include IPC reporting line |
| `pyproject.toml` | Add `pyobjc-framework-Quartz` and `pyobjc-framework-ApplicationServices` to dependencies |
| `docs/ARCHITECTURE.md` | Add daemon layer to architecture diagram |

---

## Dependencies

### New (required)

| Package | Purpose | Size |
|---------|---------|------|
| `pyobjc-framework-Quartz` | CGEventTap, CGEvent key simulation, CFRunLoop | ~2MB |
| `pyobjc-framework-ApplicationServices` | Accessibility permission checks (AXIsProcessTrusted) | ~1MB |
| `pyobjc-framework-Cocoa` | NSWorkspace (frontmost app detection), wake notifications | ~3MB (often already installed as pyobjc-core dep) |

### Already present

| Package | Used for |
|---------|----------|
| `httpx` | Ollama pre-warm HTTP requests |
| `click` | Daemon CLI subcommands |

### Considered and rejected

| Package | Reason |
|---------|--------|
| `pynput` | Wraps CGEventTap with extra abstraction. Direct pyobjc is more reliable and debuggable for a macOS-only tool. |
| `rumps` | Menu bar framework. Out of scope — no menu bar icon in Phase 2. |
| `py2app` | App bundling. Not needed for personal tool installed via pip. |

### pyproject.toml changes

```toml
dependencies = [
    # ... existing ...
    "pyobjc-framework-Quartz>=10.0; sys_platform == 'darwin'",
    "pyobjc-framework-ApplicationServices>=10.0; sys_platform == 'darwin'",
    "pyobjc-framework-Cocoa>=10.0; sys_platform == 'darwin'",
]
```

Platform markers ensure these are only installed on macOS. Non-macOS installs skip them — the daemon module raises `ImportError` with a clear message if imported on Linux.

---

## Build Order

| Step | Module | Depends on | Key deliverable |
|------|--------|-----------|-----------------|
| 1 | `config.py` updates | Nothing | `[daemon]` section in defaults, validation |
| 2 | `daemon/hotkey.py` | pyobjc | CGEventTap, hotkey parsing, accessibility checks |
| 3 | `daemon/clipboard.py` | pyobjc | Cmd+C/V simulation, pbcopy/pbpaste, undo buffer |
| 4 | `daemon/notify.py` | Nothing | osascript notifications |
| 5 | `daemon/ipc.py` | Nothing | Unix socket server/client, state tracking |
| 6 | `daemon/prewarm.py` | httpx | Ollama pre-warm and keep-alive timer |
| 7 | `daemon/launchagent.py` | Nothing | Plist generation, install/uninstall |
| 8 | `daemon/daemon.py` | Steps 2-7 | Main loop, lifecycle, signal handlers, pipeline orchestration |
| 9 | `cli.py` updates | Step 8 | `daemon` command group with all subcommands |
| 10 | `shell.py` updates | Step 5 | IPC CWD reporting in widget scripts |

Each step follows TDD (RED-GREEN-REFACTOR). Steps 2-7 are independent leaf modules and can be built in any order. Step 8 integrates them. Step 9 exposes them via CLI.

---

## Development Approach

- **TDD** — tests first, mock pyobjc/subprocess at boundaries
- **macOS-only** — no cross-platform abstractions. Direct pyobjc calls. Guard all daemon imports with `sys.platform == "darwin"` checks.
- **Daemon tests** — all tests mock `CGEventTapCreate`, `subprocess.run`, `socket`. No real event taps or clipboard access in CI.
- **Manual testing** — hotkey registration and clipboard pipeline require manual verification on real macOS. Document a manual test checklist.
- **Logging** — all daemon modules log to `daemon.log` via stdlib `logging`. Debug level for development, info for production.
