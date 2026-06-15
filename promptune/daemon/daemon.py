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
import signal
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

_enhancing = threading.Event()

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


# ---------------------------------------------------------------------------
# Enhancement pipeline (hotkey callback)
# ---------------------------------------------------------------------------


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

        # copy_selection raises when the copy tool is missing/broken, and
        # returns None/empty only for a genuinely empty selection. Keep these
        # distinct so we don't tell the user "no text selected" when the real
        # problem is a missing xdotool/ydotool.
        try:
            selected_text = platform.clipboard.copy_selection()
        except Exception:
            _log.exception("Copy tool failed")
            platform.notify.send(
                "Promptune",
                "Couldn't read selection — copy tool (xdotool/ydotool) "
                "missing or broken.",
                sound=False,
            )
            return

        if not selected_text:
            platform.notify.send(
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
            platform.notify.send(
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
            if app_after == app_before:
                injected = platform.clipboard.paste_result(result.enhanced)
                if injected:
                    delta = result.score_after.total - result.score_before.total
                    sign = "+" if delta >= 0 else ""
                    platform.notify.send(
                        "Promptune",
                        f"Prompt enhanced ({sign}{delta} PQS). Ctrl+Z to undo.",
                    )
                else:
                    # Write succeeded but the paste keystroke didn't inject \u2014
                    # the text is on the clipboard, so tell the user to paste.
                    platform.notify.send(
                        "Promptune",
                        "Enhanced text on clipboard \u2014 paste manually "
                        "(Ctrl+V).",
                        sound=False,
                    )
            else:
                platform.clipboard.write(result.enhanced)
                platform.notify.send(
                    "Promptune",
                    "Enhanced text in clipboard \u2014 paste manually.",
                    sound=False,
                )
        except Exception:
            _log.exception("Failed to deliver enhanced text")
            platform.notify.send(
                "Promptune",
                "Enhancement ready but clipboard/paste failed \u2014 check "
                "clipboard tools (xclip/wl-clipboard) are installed.",
                sound=False,
            )
            return

        with state.lock:
            state.enhancement_count += 1
    finally:
        _enhancing.clear()


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
                    "Accessibility permissions not granted. Grant access "
                    "in System Settings > Privacy & Security > Accessibility."
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

    def _handle_term(signum: int, frame: Any) -> None:
        _log.info("Received signal %d, shutting down", signum)
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


def stop_daemon() -> None:
    """Stop a running daemon by sending SIGTERM, then SIGKILL if needed."""
    pid = _read_pid()
    if pid is None:
        _log.info("No PID file found; daemon not running")
        return

    if not _is_running(pid):
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

    with contextlib.suppress(OSError):
        os.kill(pid, signal.SIGKILL)

    _cleanup()
    _log.info("Daemon (PID %d) force-killed", pid)
