# Phase 3: Linux OS-Level Hotkey Daemon — Design Spec

**Date:** 2026-03-29
**Status:** Draft
**Author:** kayumuzzaman

---

## Overview

Port the macOS OS-level hotkey daemon (Phase 2) to Linux, supporting both X11 and Wayland display servers. Introduces a platform abstraction layer so `daemon.py` orchestration is platform-agnostic. The daemon registers a global hotkey (`Ctrl+Shift+E`), captures the user's text selection, enhances it via the existing tier-based engine, and pastes the result back — identical behavior to macOS but using Linux-native tools.

**Target:** Ubuntu/GNOME first, runtime detection covers other distros/DEs.

**Not in scope:** Windows support (marked as future feature, no planned phase).

---

## Updated Phasing

| Phase | Content | Status |
|---|---|---|
| Phase 1 | Core engine, scoring, context, history, shell widgets, config wizard | Completed |
| Enhancement | Dedup, preferences, templates, Ollama auto-check | Completed |
| Phase 2 | macOS OS-level hotkey daemon | Completed |
| CI Pipeline | GitHub Actions CI | Completed |
| Distribution | LICENSE, install.sh, release workflow | Completed |
| **Phase 3** | **Linux OS-level hotkey daemon (this spec)** | **Designing** |
| Phase 4 | Direct integrations + shared prompt library | Planned |
| Phase 5 | Cross-platform verification (Linux CLI on all distros, Linux daemon X11/Wayland/GNOME/KDE, macOS regression) | Planned |
| Future | Windows support | Not planned |

---

## Architecture

### Platform Abstraction Layer

The Linux daemon reuses the existing orchestration layer (`daemon.py`, `ipc.py`, `prewarm.py`) and introduces a platform abstraction that selects the right backend at runtime.

```
promptune/daemon/
├── daemon.py              # Shared orchestration (uses platform factory)
├── ipc.py                 # Shared (Unix sockets — already portable)
├── prewarm.py             # Shared (HTTP to Ollama — already portable)
├── clipboard.py           # macOS-only (existing, to be wrapped)
├── hotkey.py              # macOS-only (existing, to be wrapped)
├── notify.py              # macOS-only (existing, to be wrapped)
├── launchagent.py         # macOS-only (existing, to be wrapped)
├── platform/
│   ├── __init__.py        # Runtime detection factory: get_platform() → PlatformBackend
│   ├── base.py            # Abstract interfaces
│   ├── macos.py           # Wraps existing macOS modules
│   ├── linux_x11.py       # X11 backend
│   ├── linux_wayland.py   # Wayland backend
│   └── linux_service.py   # systemd + direct process fallback
```

### Runtime Detection

The factory in `platform/__init__.py`:

1. `sys.platform == "darwin"` → load `macos.py`
2. `sys.platform == "linux"`:
   - Check `$XDG_SESSION_TYPE` → `wayland` loads `linux_wayland.py`, `x11` loads `linux_x11.py`
   - Fallback: check `$WAYLAND_DISPLAY` (set → Wayland), `$DISPLAY` (set → X11), neither → error
3. `$XDG_CURRENT_DESKTOP` detected for DE-specific behavior (GNOME vs KDE vs tiling WM)
4. WSL detected via `/proc/version` containing "microsoft" → block daemon, suggest CLI mode
5. Docker/container with no display → block daemon

---

## Abstract Interfaces (`platform/base.py`)

```python
class HotkeyBackend(ABC):
    def register(self, combo: str, callback: Callable) -> None: ...
    def check_conflict(self, combo: str) -> bool: ...
    def listen(self) -> None: ...       # blocking event loop (runs in thread)
    def stop(self) -> None: ...

class ClipboardBackend(ABC):
    def read(self) -> str | None: ...
    def write(self, text: str) -> None: ...
    def copy_selection(self) -> str | None: ...   # simulate copy + read
    def paste_result(self, text: str) -> None: ... # write + simulate paste

class NotifyBackend(ABC):
    def send(self, title: str, body: str, sound: bool = True) -> None: ...

class ServiceBackend(ABC):
    def install(self) -> None: ...
    def uninstall(self) -> None: ...
    def purge(self) -> None: ...        # remove all daemon files
    def is_installed(self) -> bool: ...

class ActiveWindowBackend(ABC):
    def get_frontmost_app(self) -> str: ...

class DependencyChecker(ABC):
    def check(self) -> list[DependencyStatus]: ...
    def get_install_command(self, missing: list[str]) -> str: ...
```

---

## Component Details

### 1. macOS Backend (`platform/macos.py`)

Wraps existing modules (`hotkey.py`, `clipboard.py`, `notify.py`, `launchagent.py`) behind the abstract interfaces. No behavior change — adapter pattern only.

### 2. X11 Backend (`platform/linux_x11.py`)

| Feature | Implementation |
|---|---|
| Hotkey registration | `python-xlib` `XGrabKey` + `XNextEvent` loop in dedicated thread |
| Conflict detection | Attempt `XGrabKey` — if `BadAccess` error, combo is taken |
| Clipboard read | `subprocess: xclip -selection clipboard -o` |
| Clipboard write | `subprocess: xclip -selection clipboard -i` (pipe text to stdin) |
| Copy simulation | `subprocess: xdotool key --clearmodifiers ctrl+c` |
| Paste simulation | `subprocess: xdotool key --clearmodifiers ctrl+v` |
| Active window | `python-xlib` read `_NET_ACTIVE_WINDOW` property, then `_NET_WM_PID` / `WM_CLASS` |
| Tiling WM (i3) | Detect via `$XDG_CURRENT_DESKTOP` or process check; use `i3-msg -t get_tree` for active window |

### 3. Wayland Backend (`platform/linux_wayland.py`)

| Feature | Implementation |
|---|---|
| Hotkey registration (primary) | `xdg-desktop-portal` GlobalShortcuts via DBus (`dbus-next` async lib) |
| Hotkey registration (fallback) | `evdev` listener on `/dev/input/` devices — requires `input` group membership |
| Conflict detection | Portal: registration fails gracefully. evdev: no conflict possible (passive listener) |
| Clipboard read | `subprocess: wl-paste --no-newline` |
| Clipboard write | `subprocess: wl-copy` (pipe text to stdin) |
| Copy simulation | `subprocess: ydotool key 29:1 46:1 46:0 29:0` (Ctrl+C keycodes) |
| Paste simulation | `subprocess: ydotool key 29:1 47:1 47:0 29:0` (Ctrl+V keycodes) |
| Active window (GNOME) | DBus `org.gnome.Shell.Eval` → `global.display.focus_window.get_wm_class()` |
| Active window (KDE) | DBus `org.kde.KWin` scripting interface |
| Active window (sway) | `swaymsg -t get_tree` → find focused node |
| Active window (fallback) | Return empty string — non-fatal |

**Portal GlobalShortcuts flow:**
1. Connect to `org.freedesktop.portal.GlobalShortcuts` via DBus
2. `CreateSession()` → session handle
3. `BindShortcuts()` with requested combo
4. User sees system permission prompt on first use
5. Listen for `Activated` signal on session
6. If portal unavailable → fall back to evdev with warning about `input` group

### 4. Linux Service Manager (`platform/linux_service.py`)

**Primary: systemd user service**

```ini
[Unit]
Description=Promptune Prompt Enhancement Daemon
After=graphical-session.target

[Service]
Type=simple
ExecStart=/path/to/promptune daemon start --foreground
Restart=on-failure
RestartSec=5
StartLimitBurst=3
MemoryMax=256M
Environment=DISPLAY=%I
EnvironmentFile=-%h/.config/promptune/daemon.env

[Install]
WantedBy=default.target
```

- `daemon.env` file (optional) for proxy settings: `HTTP_PROXY=...`, `HTTPS_PROXY=...`
- `install` → write service file to `~/.config/systemd/user/promptune.service`, run `systemctl --user daemon-reload && systemctl --user enable promptune`
- `uninstall` → `systemctl --user disable --now promptune`, remove service file
- `purge` → uninstall + remove socket, PID file, undo file, logs. Warn about history DB separately.

**Fallback: direct process management**

- `promptune daemon start` → fork, write PID to `~/.local/share/promptune/promptune.pid`
- `promptune daemon start --foreground` → run in foreground (useful for debugging, systemd, containers)
- `promptune daemon stop` → read PID file, send `SIGTERM`
- Stale PID detection: check `/proc/<pid>/` existence before trusting PID file

### 5. Dependency Checker

Detects package manager (`apt`, `dnf`, `pacman`, `zypper`) and checks for required system tools.

**Required tools by backend:**

| Tool | X11 | Wayland | Purpose |
|---|---|---|---|
| `xclip` | Required | Not needed | Clipboard |
| `xdotool` | Required | Not needed | Key simulation |
| `wl-clipboard` (`wl-paste`, `wl-copy`) | Not needed | Required | Clipboard |
| `ydotool` | Not needed | Required | Key simulation |
| `notify-send` | Optional | Optional | Notifications |

**Python dependencies (pip-installed automatically):**

| Package | X11 | Wayland | Purpose |
|---|---|---|---|
| `python-xlib` | Required | Not needed | Hotkey registration, active window |
| `dbus-next` | Not needed | Required | Portal GlobalShortcuts |
| `evdev` | Not needed | Fallback | evdev hotkey listener (requires `input` group, same as ydotool) |

**Output example:**
```
$ promptune daemon install

Checking system dependencies...
  Platform: Linux
  Display server: Wayland (GNOME 46)
  Package manager: apt

  wl-clipboard    ✓ installed
  ydotool         ✗ missing
  notify-send     ✓ installed

Missing required tools. Run:
  sudo apt install ydotool
  sudo usermod -aG input $USER
  (Log out and back in for group change to take effect)
```

### 6. Daemon Orchestration Changes (`daemon.py`)

Replace direct imports of macOS modules with platform factory:

```python
from promptune.daemon.platform import get_platform

platform = get_platform()
hotkey = platform.hotkey
clipboard = platform.clipboard
notify = platform.notify
service = platform.service
active_window = platform.active_window
```

The enhance pipeline is identical across platforms:

```
Hotkey fires callback
  → clipboard.copy_selection()
  → active_window.get_frontmost_app()
  → engine.enhance(text, config)
  → clipboard.paste_result(enhanced)
  → notify.send("Prompt enhanced")
  → save_undo(original, selected)
```

---

## Hotkey Conflict Resolution

Default hotkey: `Ctrl+Shift+E` (same as macOS).

**Conflict detection at daemon start:**
1. Attempt to register the configured hotkey
2. If conflict detected (XGrabKey `BadAccess`, portal rejection, or known input method binding):
   - Check common input method configs: ibus (`dconf read /desktop/ibus/...`), fcitx5 config files
   - Log which application/system holds the binding (if detectable)
   - Print: "Hotkey Ctrl+Shift+E is in use by [source]. Choose an alternative:"
   - Suggest alternatives: `Ctrl+Shift+P`, `Ctrl+Shift+;`, `Super+E`
   - Accept user input for custom combo
   - Save chosen combo to `config.toml` `[daemon] hotkey` field

**Runtime hotkey change:**
- User edits `config.toml` hotkey field
- `promptune daemon restart` or send `SIGHUP` to daemon PID → daemon re-reads config, re-registers hotkey

---

## CLI Changes

New Linux-specific subcommands under `promptune daemon`:

| Command | Linux behavior |
|---|---|
| `daemon install` | Check dependencies, create systemd service (or warn if no systemd) |
| `daemon uninstall` | Remove systemd service |
| `daemon purge` | Remove all daemon files (service, socket, PID, undo, logs) |
| `daemon start` | Start via systemd or direct process |
| `daemon start --foreground` | Run daemon in foreground |
| `daemon stop` | Stop via systemd or SIGTERM to PID |
| `daemon status` | Query systemd or check PID file |
| `daemon restart` | Stop + start |
| `daemon diagnose` | Check: display server, tools, permissions, socket, service, group membership |
| `daemon setup` | Walk through dependency installation and permissions |

Existing macOS commands (`install-login-item`, `uninstall-login-item`) remain macOS-only. Platform detection in CLI routes to the correct subcommand set.

`promptune doctor` updated to detect platform and check Linux-specific deps.

---

## Config Changes

No new config keys needed. Existing `[daemon]` section is platform-agnostic:

```toml
[daemon]
hotkey = "ctrl+shift+e"
clipboard_settle_ms = 100
notify = true
notify_sound = true            # ignored on Linux (notify-send doesn't support sound control)
ollama_prewarm = true
ollama_keepalive_minutes = 30
log_level = "info"
```

New optional file for systemd proxy passthrough:

```
~/.config/promptune/daemon.env    # HTTP_PROXY, HTTPS_PROXY, NO_PROXY
```

---

## Edge Cases (99 total)

### Hotkey Registration (11 cases)

| Edge case | Handling |
|---|---|
| `Ctrl+Shift+E` taken by GNOME emoji picker (older versions) | Conflict detection warns user, prompts for alternative |
| `Ctrl+Shift+E` taken by IDE (VS Code, JetBrains) | Detect conflict, suggest alternatives, accept user input |
| User changes hotkey in config while daemon is running | `SIGHUP` or restart re-registers with new combo |
| XGrabKey fails (another app holds exclusive grab) | Clear error: "Hotkey grabbed by another application" |
| Portal GlobalShortcuts permission denied by user | Fall back to evdev, explain why |
| Portal DBus service not running | Fall back to evdev with warning |
| evdev `/dev/input/` permission denied | "Add yourself to input group: `sudo usermod -aG input $USER`" |
| Multiple keyboards connected | evdev listener scans all input devices |
| Bluetooth keyboard reconnect | Monitor udev events for input device changes |
| Hotkey pressed during screen lock | No-op — display server blocks input events |
| Hotkey pressed during login screen (GDM/SDDM) | Daemon not running (user service starts after login) |

### Clipboard (10 cases)

| Edge case | Handling |
|---|---|
| Empty selection (nothing highlighted) | `copy_selection()` returns None → notify "Select text first" |
| Selection is image/binary, not text | clipboard tool returns empty for `text/plain` → notify "Select text first" |
| xclip/wl-paste not installed | Daemon refuses to start, prints install command |
| Clipboard manager (CopyQ, GPaste) intercepts | Works — we use standard clipboard tools |
| Large selection (>10K chars) | Warn "Large selection — enhancement may be slow", proceed |
| Selection contains null bytes | Strip null bytes before passing to engine |
| wl-copy fails in some Wayland compositors | Catch subprocess error, notify "Clipboard write failed" |
| X11 clipboard vs primary selection | Always use `-selection clipboard`, never primary |
| Clipboard content changes between copy and read | Configurable settle delay (`clipboard_settle_ms`) |
| Electron apps using custom clipboard | Standard clipboard tools still work — Electron uses system clipboard |

### Key Simulation (9 cases)

| Edge case | Handling |
|---|---|
| xdotool `Ctrl+C` triggers terminal SIGINT | Detect terminal emulator as active window → skip sim, notify "Use CLI mode" |
| ydotool requires `input` group | Check group membership at startup, warn with fix command |
| Key simulation arrives before clipboard settles | Configurable settle delay |
| Focused app changes between copy and paste | Detect app change → clipboard-only, notify |
| App ignores simulated key events (Wayland-native) | Clipboard-only fallback with notification |
| xdotool not found on Wayland session | Expected — use ydotool, no error |
| ydotool not found on X11 session | Expected — use xdotool, no error |
| Key simulation during compositor transition | Small settle delay |
| Simulated paste corrupts multi-byte Unicode | Always use clipboard paste (Ctrl+V sim), never `xdotool type` |

### Active Window Detection (7 cases)

| Edge case | Handling |
|---|---|
| GNOME Shell DBus not responding | Timeout after 500ms, proceed without app context |
| KDE Plasma (different DBus interface) | Detect desktop, use `org.kde.KWin` |
| Tiling WM (i3, sway) — no DBus | i3: `i3-msg -t get_tree`; sway: `swaymsg -t get_tree` |
| No window focused (desktop shown) | Return empty string — non-fatal |
| Wayland compositor doesn't expose active window | Proceed without — non-fatal |
| Multiple monitors with focus-follows-mouse | Compositor reports correct focused window |
| Full-screen app | Enhancement triggers — user pressed hotkey intentionally |

### Notifications (5 cases)

| Edge case | Handling |
|---|---|
| `notify-send` not installed | Non-fatal — skip notifications, log warning at startup |
| Notification daemon not running | `notify-send` fails silently — non-fatal |
| Do Not Disturb active | OS suppresses — enhancement still works |
| `notify = false` in config | Skip notification entirely |
| Very long enhanced text in notification | Truncate body to 100 chars + "..." |

### Service Management (9 cases)

| Edge case | Handling |
|---|---|
| systemd not available (Void, Artix, Docker) | Fall back to direct PID-file process management |
| Service file already exists (upgrade) | Overwrite with warning |
| Daemon crashes in loop | systemd `Restart=on-failure`, `RestartSec=5`, `StartLimitBurst=3` |
| Stale PID file (process dead) | Check `/proc/<pid>/` — if missing, remove stale file, start |
| Two daemon instances started | PID file lock prevents second instance |
| `daemon start` run as root | Warn: "Run as your user, not root" |
| `$XDG_RUNTIME_DIR` not set | Fall back to `/tmp/promptune-$UID/` |
| Stale socket file | Remove and start fresh |
| SSH session, SSH disconnects | systemd persists if `loginctl enable-linger` — warn at install |

### Platform Detection (7 cases)

| Edge case | Handling |
|---|---|
| `$XDG_SESSION_TYPE` not set | Check `$WAYLAND_DISPLAY` → Wayland, `$DISPLAY` → X11, neither → error |
| XWayland app on Wayland session | Use Wayland backend — XWayland clipboard routes through compositor |
| WSL (Windows Subsystem for Linux) | Detect via `/proc/version` → block daemon, suggest CLI mode |
| Docker/container with no display | Detect missing display env vars → block daemon |
| Remote desktop (VNC, RDP) | X11 backend via `$DISPLAY` |
| Switching X11/Wayland between logins | Detection at daemon start — restart daemon after switching |
| ChromeOS/Crostini | X11 via Sommelier — X11 backend works |

### Security (5 cases)

| Edge case | Handling |
|---|---|
| evdev listener reads all keystrokes | Only capture registered hotkey combo, discard all other events immediately — never buffer or log |
| Clipboard contains passwords | Same as macOS — enhance and replace. Config option `skip_apps` to block enhancement in password managers |
| Undo file stores plaintext | `0o600` permissions, overwritten each time, one entry deep |
| IPC socket accessible to others | `0o700` on socket directory and file |
| systemd service file readable | No secrets in service file — API keys in config.toml (`0o600`) |

### Input Methods & Encoding (4 cases)

| Edge case | Handling |
|---|---|
| CJK input method (ibus, fcitx5) conflicts | Conflict detection checks ibus/fcitx5 bindings, not just WM |
| Right-to-left text (Arabic, Hebrew) | Preserve original text direction markers |
| Emoji/Unicode in selection | Use clipboard paste, never `xdotool type` |
| Non-UTF-8 locale (`LANG=C`) | Force UTF-8 decode with fallback, warn if locale not UTF-8 |

### Multi-User & Shared Systems (3 cases)

| Edge case | Handling |
|---|---|
| Multiple users on shared machine | Socket path user-scoped via `~/` — no collision |
| Switching GNOME/KDE between logins | Backend detected at each daemon start |
| Multiple graphical sessions (VT switching) | Daemon only works in the session it started in — document this |

### Network & Proxy (3 cases)

| Edge case | Handling |
|---|---|
| Corporate proxy env vars | `httpx` respects proxy env vars, but systemd needs explicit config |
| systemd doesn't inherit `$HTTP_PROXY` | Service file uses `EnvironmentFile=~/.config/promptune/daemon.env` |
| Ollama on remote host | Already supported via `host` config field |

### Uninstall & Cleanup (3 cases)

| Edge case | Handling |
|---|---|
| User uninstalls via pip without stopping daemon | Document: run `daemon uninstall-service` first |
| Need full cleanup | `promptune daemon purge` removes service, socket, PID, undo, logs |
| Config deleted while daemon running | Catch ConfigError, notify user, don't crash |

### First-Time Experience (4 cases)

| Edge case | Handling |
|---|---|
| `daemon start` without `install` | Auto-run dependency check if first time |
| User doesn't know about `input` group for ydotool | Catch at install and at runtime (first paste failure) |
| `usermod -aG input` applied but not logged out | Detect: check `groups` output vs `/etc/group`, say "Log out and back in" |
| Minimal distro (no DE tools) | Show capability summary at install: "hotkey ✓, clipboard ✓, notifications ✗" |

### Long-Running Stability (5 cases)

| Edge case | Handling |
|---|---|
| Memory leak over weeks | systemd `MemoryMax=256M` safety net |
| DBus connection drops after suspend/resume | Monitor DBus, reconnect on `PrepareForSleep` signal |
| X11 display connection reset (GPU crash) | Catch connection error, reconnect with backoff |
| Ollama prewarm timer drift after suspend | `_RepeatingTimer` checks if interval actually elapsed |
| Log file grows unbounded | `RotatingFileHandler`, 5MB max, 3 backups |

### Desktop Environment Quirks (5 cases)

| Edge case | Handling |
|---|---|
| GNOME 46+ removed some DBus interfaces | Use `org.gnome.Shell.Extensions` eval fallback |
| KDE Plasma 6 portal changes | Version-check portal interface, test specifically |
| Pop!_OS modified GNOME (COSMIC) | Detect `pop:GNOME` in `$XDG_CURRENT_DESKTOP`, treat as GNOME |
| Ubuntu patched GNOME custom shortcuts | Conflict detection covers this |
| Tiling WM — no portal, no Shell DBus | Detect WM, use `i3-msg`/`swaymsg` for active window |

### Accessibility (3 cases)

| Edge case | Handling |
|---|---|
| Screen reader active (Orca) | Detect via DBus, add extra settle delay for key simulation |
| On-screen keyboard | Works — hotkey registered at lower level |
| Assistive tech grabbing keys | Same conflict detection as other apps |

---

## Testing Strategy

All platform backends get dedicated test files with mocked subprocess calls and DBus interactions. No real X11/Wayland/DBus calls in unit tests.

| Component | Test approach |
|---|---|
| `platform/__init__.py` | Mock env vars, assert correct backend loaded |
| `platform/base.py` | Verify ABC enforcement (can't instantiate) |
| `platform/macos.py` | Same mocks as existing daemon tests — adapter only |
| `platform/linux_x11.py` | Mock `subprocess.run` for xclip/xdotool, mock `python-xlib` |
| `platform/linux_wayland.py` | Mock `subprocess.run` for wl-paste/wl-copy/ydotool, mock `dbus-next` |
| `platform/linux_service.py` | Mock `subprocess.run` for systemctl, mock file writes |
| Dependency checker | Mock `shutil.which`, assert correct install commands per package manager |
| Conflict detection | Mock XGrabKey error / portal rejection, verify fallback and user prompt |
| `daemon.py` integration | Mock entire platform backend, test orchestration pipeline |

Coverage target: >= 90% for all new files.

---

## New Files

| File | Purpose |
|---|---|
| `promptune/daemon/platform/__init__.py` | Runtime detection factory |
| `promptune/daemon/platform/base.py` | Abstract backend interfaces |
| `promptune/daemon/platform/macos.py` | macOS backend adapter |
| `promptune/daemon/platform/linux_x11.py` | X11 backend |
| `promptune/daemon/platform/linux_wayland.py` | Wayland backend |
| `promptune/daemon/platform/linux_service.py` | systemd + direct process management |
| `tests/test_daemon/test_platform/__init__.py` | Test package |
| `tests/test_daemon/test_platform/test_init.py` | Factory detection tests |
| `tests/test_daemon/test_platform/test_base.py` | ABC enforcement tests |
| `tests/test_daemon/test_platform/test_macos.py` | macOS adapter tests |
| `tests/test_daemon/test_platform/test_linux_x11.py` | X11 backend tests |
| `tests/test_daemon/test_platform/test_linux_wayland.py` | Wayland backend tests |
| `tests/test_daemon/test_platform/test_linux_service.py` | Service management tests |

## Modified Files

| File | Changes |
|---|---|
| `promptune/daemon/daemon.py` | Replace direct macOS imports with `get_platform()` factory |
| `promptune/cli.py` | Add Linux daemon subcommands (`install`, `uninstall`, `purge`, `setup`), platform-aware routing |
| `promptune/config.py` | No schema changes — validate `daemon.env` path if present |
| `pyproject.toml` | Add optional deps: `python-xlib`, `dbus-next`, `evdev` (extras group `[linux-daemon]`) |
| `docs/USER_GUIDE.md` | Linux daemon section (setup, permissions, troubleshooting) |
| `docs/MANUAL_TESTING.md` | Linux daemon test scenarios + Phase 5 cross-platform verification checklist |
| `docs/ARCHITECTURE.md` | Platform abstraction layer diagram |
| `README.md` | Update platform support, add Linux daemon to features |
| `CHANGELOG.md` | Phase 3 entry |
| `docs/superpowers/blueprint/promptune_blueprint.md` | Update phase statuses, add Phase 4/5, mark Windows as future |

---

## Python Dependencies

Added as optional extras in `pyproject.toml`:

```toml
[project.optional-dependencies]
linux-daemon = [
    "python-xlib>=0.33",
    "dbus-next>=0.2.3",
    "evdev>=1.7.0",
]
```

Install: `pip install promptune[linux-daemon]` or `pipx install promptune[linux-daemon]`

System tools installed by user via their package manager (check-and-warn strategy).

---

## Manual Testing Additions (for MANUAL_TESTING.md)

### Phase 3: Linux Daemon

- **28. Linux daemon lifecycle** — install, start, status, stop, restart, uninstall, purge on systemd and non-systemd systems
- **29. Linux X11 hotkey + pipeline** — register hotkey, select text, Ctrl+Shift+E, verify enhance + paste on X11 session
- **30. Linux Wayland hotkey + pipeline** — same flow on Wayland session (portal path and evdev fallback)
- **31. Linux clipboard edge cases** — empty selection, binary content, large text, null bytes
- **32. Linux dependency checker** — verify correct tool detection and install commands for apt/dnf/pacman/zypper
- **33. Linux conflict detection** — test with ibus/fcitx5 active, test with IDE holding the hotkey
- **34. Linux notifications** — with and without notify-send, with Do Not Disturb
- **35. Linux active window** — GNOME, KDE, i3, sway, no-DE
- **36. Linux suspend/resume** — verify daemon recovers DBus/X11 connections after laptop wake
- **37. Linux proxy passthrough** — verify cloud tier works with HTTP_PROXY in daemon.env

### Phase 5: Cross-Platform Verification

- **38. Linux CLI on Ubuntu 22.04/24.04** — all Phase 1 commands, shell widgets, Ollama
- **39. Linux CLI on Fedora 40+** — same verification
- **40. Linux CLI on Arch Linux** — same verification
- **41. Fish shell widget on Linux** — verify Ctrl+E works
- **42. Linux daemon on GNOME X11** — full pipeline
- **43. Linux daemon on GNOME Wayland** — full pipeline
- **44. Linux daemon on KDE X11** — full pipeline
- **45. Linux daemon on KDE Wayland** — full pipeline
- **46. Linux daemon on i3 (X11)** — full pipeline
- **47. Linux daemon on sway (Wayland)** — full pipeline
- **48. macOS regression** — verify all Phase 2 features still work after platform abstraction
- **49. WSL detection** — verify daemon blocks with clear message
- **50. Docker/container** — verify daemon blocks with clear message
