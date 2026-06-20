"""Main daemon module — lifecycle management and enhancement pipeline.

Orchestrates hotkey, clipboard, notify, IPC, and prewarm modules into a
background process that listens for a global hotkey and enhances the
currently selected text.  Uses the platform abstraction layer for
cross-platform support (macOS, Linux X11, Linux Wayland).
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from promptune.config import load_config
from promptune.daemon.ipc import DaemonState, start_ipc_server
from promptune.daemon.platform import PlatformError, get_platform
from promptune.daemon.platform.base import PlatformBackend
from promptune.engine import enhance

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

PID_FILE = Path("~/.local/share/promptune/daemon.pid").expanduser()
SOCKET_PATH = Path("~/.local/share/promptune/promptune.sock").expanduser()
LOG_FILE = Path("~/.local/share/promptune/daemon.log").expanduser()
UNDO_FILE = Path("~/.local/share/promptune/undo.txt").expanduser()

# ---------------------------------------------------------------------------
# Debounce
# ---------------------------------------------------------------------------

# Guards the enhancement pipeline so overlapping hotkey events (e.g. OS key
# autorepeat while the combo is held) can't run _on_hotkey concurrently. A Lock
# gives an atomic test-and-set; a bare Event has a check-then-set race.
_enhancing = threading.Lock()

# ---------------------------------------------------------------------------
# Logger
# ---------------------------------------------------------------------------

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# DaemonStatus
# ---------------------------------------------------------------------------


@dataclass
class DaemonStatus:
    """Snapshot of daemon health for CLI status display."""

    running: bool
    pid: int | None
    uptime_seconds: float | None
    enhancement_count: int
    socket_exists: bool
    accessibility_granted: bool


# ---------------------------------------------------------------------------
# PID management
# ---------------------------------------------------------------------------


def _write_pid() -> None:
    """Write the current process PID to *PID_FILE*. Create parent dirs."""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()), encoding="utf-8")


def _read_pid() -> int | None:
    """Read the PID from *PID_FILE*. Returns ``None`` if missing or invalid."""
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def _is_running(pid: int) -> bool:
    """Check whether a process with *pid* is alive via ``os.kill(pid, 0)``."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _process_command(pid: int) -> str | None:
    """Return the process command line for *pid*, if it can be verified."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _process_name(pid: int) -> str | None:
    """Return the executable basename for *pid*, if it can be verified."""
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    name = result.stdout.strip()
    return os.path.basename(name) if name else None


# Matches the daemon launch forms in `ps -o command=` output. `ps` space-joins
# argv with no quoting, so an interpreter/script path containing a space (common
# on macOS: "/Users/Jane Doe/...", "Library/Application Support/...") cannot be
# tokenised back into argv. The executable name from `ps -o comm=` supplies the
# missing identity boundary: console-script form needs comm=promptune, module
# form needs comm=python*, and args must still end with `daemon start`. For
# Python shebang wrappers, accept the unambiguous no-space script path form
# (`python /.../promptune daemon start`) and the common spaced venv path form
# (`python /.../venv/bin/promptune daemon start`), not arbitrary worker args.
_PROMPTUNE_DAEMON_ARGS_RE = re.compile(
    r"(?:^|/)promptune\s+daemon\s+start(?:\s|$)"
)
_PYTHON_EXECUTABLE_PATTERN = r"python(?:\d+(?:\.\d+)?(?:dm|d|t)?)?"
_PYTHON_MODULE_EXECUTABLE_RE = re.compile(
    rf"^(?:{_PYTHON_EXECUTABLE_PATTERN}|.*?/{_PYTHON_EXECUTABLE_PATTERN})"
    r"(?=\s)",
    re.IGNORECASE,
)
_PYTHON_MODULE_DAEMON_ARGS_RE = re.compile(
    r"\s+-m\s+promptune\s+daemon\s+start(?:\s|$)",
    re.IGNORECASE,
)
_PYTHON_COMMAND_RE = re.compile(
    rf"^(?:\S*/)?{_PYTHON_EXECUTABLE_PATTERN}(?:\s|$)", re.IGNORECASE
)
_PYTHON_CONSOLE_SCRIPT_RE = re.compile(
    rf"^(?:\S*/)?{_PYTHON_EXECUTABLE_PATTERN}\s+"
    r"(?:\S*/)?promptune\s+daemon\s+start(?:\s|$)",
    re.IGNORECASE,
)
_PYTHON_SPACED_CONSOLE_SCRIPT_RE = re.compile(
    rf"^/.+/{_PYTHON_EXECUTABLE_PATTERN}\s+"
    r"/.+/(?:bin|Scripts)/promptune\s+daemon\s+start(?:\s|$)",
    re.IGNORECASE,
)
_PYTHON_SCRIPT_ARG_RE = re.compile(
    rf"^(?:\S*/)?{_PYTHON_EXECUTABLE_PATTERN}\s+\S+\.pyw?(?:\s|$)",
    re.IGNORECASE,
)


def _is_python_executable(name: str) -> bool:
    return re.fullmatch(_PYTHON_EXECUTABLE_PATTERN, name.lower()) is not None


def _is_python_module_command(command: str) -> bool:
    match = _PYTHON_MODULE_EXECUTABLE_RE.match(command)
    if match is None:
        return False
    return _PYTHON_MODULE_DAEMON_ARGS_RE.match(command, match.end()) is not None


def _is_console_script_command(command: str) -> bool:
    if _PYTHON_COMMAND_RE.search(command):
        return False
    return _PROMPTUNE_DAEMON_ARGS_RE.search(command) is not None


def _is_python_console_script_command(command: str) -> bool:
    if _PYTHON_CONSOLE_SCRIPT_RE.search(command):
        return True
    if _PYTHON_SCRIPT_ARG_RE.search(command):
        return False
    return _PYTHON_SPACED_CONSOLE_SCRIPT_RE.search(command) is not None


def _is_daemon_process(pid: int) -> bool:
    """Return True only when *pid* is a live promptune daemon process."""
    if not _is_running(pid):
        return False
    command = _process_command(pid)
    process_name = _process_name(pid)
    if command is None or process_name is None:
        return False
    process_name_norm = process_name.lower()
    if process_name_norm == "promptune":
        return _is_console_script_command(command)
    if _is_python_executable(process_name_norm):
        return (
            _is_python_module_command(command)
            or _is_console_script_command(command)
            or _is_python_console_script_command(command)
        )
    return False


def _cleanup() -> None:
    """Remove *PID_FILE* and *SOCKET_PATH*, ignoring missing files."""
    for path in (PID_FILE, SOCKET_PATH):
        with contextlib.suppress(FileNotFoundError):
            path.unlink()


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def get_status() -> DaemonStatus:
    """Return a :class:`DaemonStatus` reflecting current daemon health."""
    pid = _read_pid()
    running = pid is not None and _is_daemon_process(pid)

    uptime_seconds: float | None = None
    if running and PID_FILE.exists():
        uptime_seconds = time.time() - PID_FILE.stat().st_mtime

    socket_exists = SOCKET_PATH.exists()

    enhancement_count = 0
    if running and socket_exists:
        from promptune.daemon.ipc import send_ipc_message

        resp = send_ipc_message({"action": "status"})
        if isinstance(resp, dict):
            enhancement_count = resp.get("enhancement_count", 0)

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


# ---------------------------------------------------------------------------
# Enhancement pipeline (hotkey callback)
# ---------------------------------------------------------------------------


def _on_hotkey(
    state: DaemonState,
    config: dict[str, Any],
    platform: PlatformBackend,
) -> None:
    """Full enhancement pipeline — triggered by the global hotkey."""
    if not _enhancing.acquire(blocking=False):
        return

    daemon_cfg = config.get("daemon", {})
    notify_enabled = daemon_cfg.get("notify", True)
    notify_sound = daemon_cfg.get("notify_sound", True)

    def _notify(title: str, body: str, sound: bool = True) -> None:
        if not notify_enabled:
            return
        platform.notify.send(title, body, sound=sound and notify_sound)

    try:
        app_before = platform.active_window.get_frontmost_app()
        original_clipboard = platform.clipboard.read()

        # copy_selection raises when the copy tool is missing/broken, and
        # returns None/empty only for a genuinely empty selection. Keep these
        # distinct so we don't tell the user "no text selected" when the real
        # problem is a missing xdotool/ydotool.
        try:
            selected_text = platform.clipboard.copy_selection()
        except Exception:
            _log.exception("Copy tool failed")
            _notify(
                "Promptune",
                "Couldn't read selection — copy tool (xdotool/ydotool) "
                "missing or broken.",
                sound=False,
            )
            return

        # copy_selection() clears the clipboard before the copy keystroke, so
        # a falsy result means nothing was actually selected (the backend has
        # already restored the prior clipboard); a stale value can no longer
        # masquerade as a selection here.
        if not selected_text:
            _notify(
                "Promptune", "No text selected. Select text first.", sound=False
            )
            return

        # Undo buffer
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
            _notify(
                "Promptune",
                "Enhancement failed. Original text preserved.",
                sound=False,
            )
            return

        app_after = platform.active_window.get_frontmost_app()

        # Clipboard delivery can fail when system tools are missing
        # (xclip/xdotool, wl-clipboard/ydotool). Backends signal this by
        # raising; catch it here so the hotkey thread never dies silently
        # and the user always gets feedback.
        try:
            # Only auto-paste when the focused window is known AND unchanged.
            # Linux active-window detection often degrades to "" (locked-down
            # GNOME Shell.Eval, unsupported desktops); treating "" == "" as
            # "same window" would inject the prompt into whatever is focused
            # now — possibly the wrong app. Unknown focus -> clipboard only.
            if app_before and app_after and app_after == app_before:
                injected = platform.clipboard.paste_result(result.enhanced)
                if injected:
                    delta = result.score_after.total - result.score_before.total
                    sign = "+" if delta >= 0 else ""
                    _notify(
                        "Promptune",
                        f"Prompt enhanced ({sign}{delta} PQS). Ctrl+Z to undo.",
                    )
                    # Restore the user's pre-hotkey clipboard now that the
                    # enhanced text has been pasted, so enhancement doesn't
                    # silently clobber it. Wait one settle interval first so
                    # the paste keystroke consumes the enhanced text before we
                    # overwrite the clipboard. (Only text clipboards can be
                    # restored; an image/empty clipboard reads as None.)
                    if original_clipboard is not None:
                        settle_s = (
                            daemon_cfg.get("clipboard_settle_ms", 100)
                            / 1000.0
                        )
                        time.sleep(settle_s)
                        platform.clipboard.write(original_clipboard)
                else:
                    # Write succeeded but the paste keystroke didn't inject \u2014
                    # the text is on the clipboard, so tell the user to paste.
                    _notify(
                        "Promptune",
                        "Enhanced text on clipboard \u2014 paste manually "
                        "(Ctrl+V).",
                        sound=False,
                    )
            else:
                platform.clipboard.write(result.enhanced)
                _notify(
                    "Promptune",
                    "Enhanced text in clipboard \u2014 paste manually.",
                    sound=False,
                )
        except Exception:
            _log.exception("Failed to deliver enhanced text")
            _notify(
                "Promptune",
                "Enhancement ready but clipboard/paste failed \u2014 check "
                "clipboard tools (xclip/wl-clipboard) are installed.",
                sound=False,
            )
            return

        with state.lock:
            state.enhancement_count += 1
    finally:
        _enhancing.release()


# ---------------------------------------------------------------------------
# Daemonise
# ---------------------------------------------------------------------------


def _daemonise() -> None:
    """Classic Unix double-fork daemonisation with setsid and stdio redirect."""
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    os.setsid()

    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    devnull = os.open(os.devnull, os.O_RDWR)
    os.dup2(devnull, 0)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)


# ---------------------------------------------------------------------------
# Start / Stop
# ---------------------------------------------------------------------------


def start_daemon(
    foreground: bool = False,
    config_path: str | None = None,
) -> bool:
    """Start the promptune daemon."""
    existing_pid = _read_pid()
    if existing_pid is not None and _is_daemon_process(existing_pid):
        _log.error("Daemon already running (PID %d)", existing_pid)
        return True

    cfg_path = Path(config_path) if config_path else None
    config = load_config(config_path=cfg_path)
    settle_ms = config.get("daemon", {}).get("clipboard_settle_ms", 100)

    # Detect platform
    try:
        platform = get_platform(settle_ms=settle_ms)
    except PlatformError as exc:
        _log.error("Platform error: %s", exc)
        return False

    # macOS: verify accessibility
    if sys.platform == "darwin":
        try:
            from promptune.daemon.hotkey import check_accessibility

            if not check_accessibility():
                _log.error(
                    "Accessibility permissions not granted. Grant access "
                    "in System Settings > Privacy & Security > Accessibility."
                )
                return False
        except ImportError:
            pass

    hotkey_str = config.get("daemon", {}).get("hotkey", "ctrl+shift+e")

    # Check for hotkey conflicts
    if platform.hotkey.check_conflict(hotkey_str):
        _log.warning("Hotkey %s is in use by another application", hotkey_str)

    if not foreground:
        _daemonise()

    _write_pid()

    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    # TODO(linux-ci): Replace basicConfig with RotatingFileHandler to prevent
    # unbounded log growth on long-running Linux daemons. On Linux, also add a
    # SIGHUP handler that calls handler.doRollover() for logrotate compatibility:
    #   signal.signal(signal.SIGHUP, lambda s, f: handler.doRollover())
    # Integration test on Linux: send SIGHUP and assert the log file rotates.
    logging.basicConfig(
        filename=str(LOG_FILE),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _log.info("Daemon started (PID %d)", os.getpid())

    state = DaemonState()
    prewarm_timer: Any = None

    def _handle_term(signum: int, frame: Any) -> None:
        _log.info("Received signal %d, shutting down", signum)
        if prewarm_timer is not None:
            prewarm_timer.cancel()
        platform.hotkey.stop()
        _cleanup()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_term)
    signal.signal(signal.SIGINT, _handle_term)
    # TODO(linux-ci): Register a SIGHUP handler for config reload on Linux.
    # On macOS, SIGHUP is not conventionally used by daemons (LaunchAgent
    # restarts the process). On Linux systemd services, SIGHUP is the standard
    # signal for graceful config reload without full restart.
    # Integration test: send SIGHUP to running daemon, assert config reloads.

    try:
        start_ipc_server(state)

        daemon_cfg = config.get("daemon", {})
        local_cfg = config.get("local_llm", {})
        if local_cfg.get("enabled", False) and daemon_cfg.get(
            "ollama_prewarm", True
        ):
            from promptune.daemon.prewarm import start_prewarm_timer

            host = local_cfg.get("host", "http://localhost:11434")
            model = local_cfg.get("model", "qwen2.5:3b")
            keepalive_minutes = daemon_cfg.get("ollama_keepalive_minutes", 30)
            # Ping before the keep-alive lapses: the repeating timer waits the
            # interval *after* each ping, so an equal interval lets scheduling
            # drift unload the model. Stay a margin under the keep-alive.
            interval_minutes = max(1, int(keepalive_minutes) - 5)
            prewarm_timer = start_prewarm_timer(
                host,
                model,
                interval_minutes=interval_minutes,
                keepalive=f"{int(keepalive_minutes)}m",
            )
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
        return True
    except Exception:
        _log.exception("Daemon startup failed; cleaning up")
        raise
    finally:
        if prewarm_timer is not None:
            prewarm_timer.cancel()
        with contextlib.suppress(Exception):
            platform.hotkey.stop()
        _cleanup()


def stop_daemon() -> None:
    """Stop a running daemon by sending SIGTERM, then SIGKILL if needed."""
    pid = _read_pid()
    if pid is None:
        _log.info("No PID file found; daemon not running")
        return

    if not _is_daemon_process(pid):
        _log.info("PID %d not running; cleaning up stale files", pid)
        _cleanup()
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        _cleanup()
        return

    for _ in range(30):
        if not _is_running(pid):
            _cleanup()
            _log.info("Daemon (PID %d) stopped gracefully", pid)
            return
        time.sleep(0.1)

    if _is_daemon_process(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            _cleanup()
            _log.info("PID %d exited before force kill; cleaning up stale files", pid)
            return
        _cleanup()
        _log.info("Daemon (PID %d) force-killed", pid)
        return

    _cleanup()
    _log.info("PID %d stale or reused before force kill; cleaning up files", pid)
