"""Tests for promptune.daemon.daemon — lifecycle and enhancement pipeline."""

from __future__ import annotations

import contextlib
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
    start_daemon,
    stop_daemon,
)
from promptune.daemon.ipc import DaemonState

# ---------------------------------------------------------------------------
# TestPIDManagement
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TestDaemonStatus
# ---------------------------------------------------------------------------


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
        assert status.uptime_seconds is None

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


# ---------------------------------------------------------------------------
# TestOnHotkey
# ---------------------------------------------------------------------------


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
        config = {
            "enhancement": {"max_tier": 0},
            "provider": {"default": "claude", "format_style": "auto"},
            "local_llm": {"enabled": False},
            "api_keys": {},
            "context": {},
            "history": {"enabled": False},
        }
        undo_file = tmp_path / "undo.txt"

        with (
            patch("promptune.daemon.daemon.enhance") as mock_enhance,
            patch("promptune.daemon.daemon.UNDO_FILE", undo_file),
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

    def test_restores_original_clipboard_after_paste(
        self, tmp_path: Path
    ) -> None:
        """A successful paste must restore the user's prior clipboard."""
        platform = self._make_platform()
        state = DaemonState()
        config = {
            "enhancement": {"max_tier": 0},
            "provider": {"default": "claude", "format_style": "auto"},
            "local_llm": {"enabled": False},
            "api_keys": {},
            "context": {},
            "history": {"enabled": False},
            "daemon": {"clipboard_settle_ms": 0},
        }
        undo_file = tmp_path / "undo.txt"

        with (
            patch("promptune.daemon.daemon.enhance") as mock_enhance,
            patch("promptune.daemon.daemon.UNDO_FILE", undo_file),
        ):
            mock_result = MagicMock()
            mock_result.enhanced = "enhanced text"
            mock_result.score_before.total = 40
            mock_result.score_after.total = 75
            mock_enhance.return_value = mock_result

            _on_hotkey(state, config, platform)

            platform.clipboard.paste_result.assert_called_once_with(
                "enhanced text"
            )
            # Original clipboard restored after the paste, not clobbered.
            platform.clipboard.write.assert_called_once_with(
                "original clipboard"
            )

    def test_no_selection_notifies(self) -> None:
        platform = self._make_platform()
        platform.clipboard.copy_selection.return_value = None
        state = DaemonState()
        config = {}

        _on_hotkey(state, config, platform)

        platform.notify.send.assert_called_once()
        assert "Select text" in platform.notify.send.call_args[0][1]
        assert state.enhancement_count == 0

    def test_app_focus_changed_skips_paste(self, tmp_path: Path) -> None:
        platform = self._make_platform()
        platform.active_window.get_frontmost_app.side_effect = [
            "com.apple.Safari",
            "com.apple.Terminal",
        ]
        state = DaemonState()
        config = {
            "enhancement": {"max_tier": 0},
            "provider": {"default": "claude", "format_style": "auto"},
            "local_llm": {"enabled": False},
            "api_keys": {},
            "context": {},
            "history": {"enabled": False},
        }
        undo_file = tmp_path / "undo.txt"

        with (
            patch("promptune.daemon.daemon.enhance") as mock_enhance,
            patch("promptune.daemon.daemon.UNDO_FILE", undo_file),
        ):
            mock_result = MagicMock()
            mock_result.enhanced = "enhanced text"
            mock_result.score_before.total = 40
            mock_result.score_after.total = 75
            mock_enhance.return_value = mock_result

            _on_hotkey(state, config, platform)

            platform.clipboard.write.assert_called_once_with("enhanced text")
            platform.clipboard.paste_result.assert_not_called()
            assert "clipboard" in platform.notify.send.call_args[0][1].lower()

    def test_clipboard_delivery_failure_notifies(self, tmp_path: Path) -> None:
        platform = self._make_platform()
        platform.clipboard.paste_result.side_effect = RuntimeError(
            "wl-copy not found"
        )
        state = DaemonState()
        config = {
            "enhancement": {"max_tier": 0},
            "provider": {"default": "claude", "format_style": "auto"},
            "local_llm": {"enabled": False},
            "api_keys": {},
            "context": {},
            "history": {"enabled": False},
        }
        undo_file = tmp_path / "undo.txt"

        with (
            patch("promptune.daemon.daemon.enhance") as mock_enhance,
            patch("promptune.daemon.daemon.UNDO_FILE", undo_file),
        ):
            mock_result = MagicMock()
            mock_result.enhanced = "enhanced text"
            mock_result.score_before.total = 40
            mock_result.score_after.total = 75
            mock_enhance.return_value = mock_result

            # Must not raise even though paste_result blows up
            _on_hotkey(state, config, platform)

        platform.notify.send.assert_called_once()
        msg = platform.notify.send.call_args[0][1].lower()
        assert "fail" in msg or "manual" in msg
        assert state.enhancement_count == 0

    def test_paste_injection_failure_notifies_manual(
        self, tmp_path: Path
    ) -> None:
        platform = self._make_platform()
        # Write succeeded (text on clipboard) but the paste keystroke didn't
        # inject -> backend returns False.
        platform.clipboard.paste_result.return_value = False
        state = DaemonState()
        config = {
            "enhancement": {"max_tier": 0},
            "provider": {"default": "claude", "format_style": "auto"},
            "local_llm": {"enabled": False},
            "api_keys": {},
            "context": {},
            "history": {"enabled": False},
        }
        undo_file = tmp_path / "undo.txt"

        with (
            patch("promptune.daemon.daemon.enhance") as mock_enhance,
            patch("promptune.daemon.daemon.UNDO_FILE", undo_file),
        ):
            mock_result = MagicMock()
            mock_result.enhanced = "enhanced text"
            mock_result.score_before.total = 40
            mock_result.score_after.total = 75
            mock_enhance.return_value = mock_result

            _on_hotkey(state, config, platform)

        msg = platform.notify.send.call_args[0][1].lower()
        assert "paste" in msg and "manual" in msg
        # Enhancement happened and text is on the clipboard, so it counts.
        assert state.enhancement_count == 1

    def test_copy_tool_failure_notifies(self) -> None:
        platform = self._make_platform()
        platform.clipboard.copy_selection.side_effect = RuntimeError(
            "xdotool not found"
        )
        state = DaemonState()
        config: dict = {}

        # Must not raise even though copy_selection blows up.
        _on_hotkey(state, config, platform)

        platform.notify.send.assert_called_once()
        msg = platform.notify.send.call_args[0][1].lower()
        assert "copy" in msg or "tool" in msg
        assert state.enhancement_count == 0

    def test_unknown_focus_uses_manual_paste(self, tmp_path: Path) -> None:
        """When active-window detection is unavailable both ids are "".

        That must NOT be treated as "same window" — auto-pasting into an
        unknown focus risks injecting the prompt into the wrong app. Fall
        back to the clipboard-only path instead.
        """
        platform = self._make_platform()
        platform.active_window.get_frontmost_app.return_value = ""
        state = DaemonState()
        config = {
            "enhancement": {"max_tier": 0},
            "provider": {"default": "claude", "format_style": "auto"},
            "local_llm": {"enabled": False},
            "api_keys": {},
            "context": {},
            "history": {"enabled": False},
        }
        undo_file = tmp_path / "undo.txt"

        with (
            patch("promptune.daemon.daemon.enhance") as mock_enhance,
            patch("promptune.daemon.daemon.UNDO_FILE", undo_file),
        ):
            mock_result = MagicMock()
            mock_result.enhanced = "enhanced text"
            mock_result.score_before.total = 40
            mock_result.score_after.total = 75
            mock_enhance.return_value = mock_result

            _on_hotkey(state, config, platform)

            platform.clipboard.write.assert_called_once_with("enhanced text")
            platform.clipboard.paste_result.assert_not_called()
            assert "clipboard" in platform.notify.send.call_args[0][1].lower()

    def test_engine_error_notifies(self, tmp_path: Path) -> None:
        platform = self._make_platform()
        state = DaemonState()
        config = {}
        undo_file = tmp_path / "undo.txt"

        with (
            patch(
                "promptune.daemon.daemon.enhance",
                side_effect=RuntimeError("LLM timeout"),
            ),
            patch("promptune.daemon.daemon.UNDO_FILE", undo_file),
        ):
            _on_hotkey(state, config, platform)

            platform.notify.send.assert_called_once()
            assert "failed" in platform.notify.send.call_args[0][1].lower()
            platform.clipboard.paste_result.assert_not_called()

    def test_debounce_prevents_double_run(self) -> None:
        platform = self._make_platform()
        state = DaemonState()
        config = {}

        _enhancing.set()
        _on_hotkey(state, config, platform)
        _enhancing.clear()

        platform.clipboard.copy_selection.assert_not_called()


# ---------------------------------------------------------------------------
# TestDebounce
# ---------------------------------------------------------------------------


class TestDebounce:
    def test_debounce_flag(self) -> None:
        assert _enhancing.is_set() is False


# ---------------------------------------------------------------------------
# TestStartDaemon
# ---------------------------------------------------------------------------


class TestStartDaemon:
    def test_already_running_exits_early(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text(str(os.getpid()))
        with patch("promptune.daemon.daemon.PID_FILE", pid_file):
            start_daemon(foreground=True)
            # Should log error and return without calling get_platform

    def test_platform_error_exits_early(self, tmp_path: Path) -> None:
        from promptune.daemon.platform import PlatformError

        pid_file = tmp_path / "daemon.pid"
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch(
                "promptune.daemon.daemon.get_platform",
                side_effect=PlatformError("unsupported"),
            ),
        ):
            start_daemon(foreground=True)

    def test_foreground_start_runs_event_loop(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        log_file = tmp_path / "daemon.log"

        mock_platform = MagicMock()
        mock_platform.hotkey.check_conflict.return_value = False
        mock_platform.hotkey.listen.return_value = None

        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
            patch("promptune.daemon.daemon.LOG_FILE", log_file),
            patch(
                "promptune.daemon.daemon.get_platform",
                return_value=mock_platform,
            ),
            patch("promptune.daemon.daemon.load_config", return_value={
                "daemon": {"hotkey": "ctrl+shift+e"},
                "local_llm": {"enabled": False},
            }),
            patch("promptune.daemon.daemon.start_ipc_server"),
            patch("promptune.daemon.daemon.signal.signal"),
            patch("sys.platform", "linux"),
        ):
            start_daemon(foreground=True)

        assert pid_file.exists()
        mock_platform.hotkey.register.assert_called_once()
        mock_platform.hotkey.listen.assert_called_once()

    def test_hotkey_conflict_warns(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        log_file = tmp_path / "daemon.log"

        mock_platform = MagicMock()
        mock_platform.hotkey.check_conflict.return_value = True
        mock_platform.hotkey.listen.return_value = None

        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.LOG_FILE", log_file),
            patch(
                "promptune.daemon.daemon.get_platform",
                return_value=mock_platform,
            ),
            patch("promptune.daemon.daemon.load_config", return_value={
                "daemon": {"hotkey": "ctrl+shift+e"},
                "local_llm": {"enabled": False},
            }),
            patch("promptune.daemon.daemon.start_ipc_server"),
            patch("promptune.daemon.daemon.signal.signal"),
            patch("sys.platform", "linux"),
        ):
            start_daemon(foreground=True)

        mock_platform.hotkey.check_conflict.assert_called_once()

    def test_prewarm_started_when_local_enabled(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        log_file = tmp_path / "daemon.log"

        mock_platform = MagicMock()
        mock_platform.hotkey.check_conflict.return_value = False
        mock_platform.hotkey.listen.return_value = None

        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.LOG_FILE", log_file),
            patch(
                "promptune.daemon.daemon.get_platform",
                return_value=mock_platform,
            ),
            patch("promptune.daemon.daemon.load_config", return_value={
                "daemon": {"hotkey": "ctrl+shift+e"},
                "local_llm": {
                    "enabled": True,
                    "host": "http://localhost:11434",
                    "model": "qwen2.5:3b",
                },
            }),
            patch("promptune.daemon.daemon.start_ipc_server"),
            patch("promptune.daemon.daemon.signal.signal"),
            patch(
                "promptune.daemon.prewarm.start_prewarm_timer"
            ) as mock_prewarm,
            patch("sys.platform", "linux"),
        ):
            start_daemon(foreground=True)

        mock_prewarm.assert_called_once()


# ---------------------------------------------------------------------------
# TestStopDaemon
# ---------------------------------------------------------------------------


class TestStopDaemon:
    def test_no_pid_file(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        with patch("promptune.daemon.daemon.PID_FILE", pid_file):
            stop_daemon()  # should not raise

    def test_stale_pid_cleans_up(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text("999999999")
        sock_path.write_text("")
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
        ):
            stop_daemon()
        assert not pid_file.exists()
        assert not sock_path.exists()

    def test_sends_sigterm(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text("12345")
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
            patch("promptune.daemon.daemon._is_running", side_effect=[True, False]),
            patch("promptune.daemon.daemon.os.kill") as mock_kill,
        ):
            stop_daemon()
        import signal

        mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_sigterm_oserror_cleans_up(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text("12345")
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon.os.kill",
                side_effect=OSError("no such process"),
            ),
        ):
            stop_daemon()

    def test_force_kill_after_timeout(
        self, tmp_path: Path
    ) -> None:
        """Lines 359-365: SIGTERM fails, falls through to SIGKILL."""
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text("12345")
        sock_path.write_text("")

        with (
            patch(
                "promptune.daemon.daemon.PID_FILE", pid_file
            ),
            patch(
                "promptune.daemon.daemon.SOCKET_PATH",
                sock_path,
            ),
            patch(
                "promptune.daemon.daemon._is_running",
                return_value=True,
            ),
            patch(
                "promptune.daemon.daemon.os.kill"
            ) as mock_kill,
            patch(
                "promptune.daemon.daemon.time.sleep"
            ),
        ):
            stop_daemon()

        import signal as sig

        calls = mock_kill.call_args_list
        assert calls[0] == (
            (12345, sig.SIGTERM),
        )
        assert calls[-1] == (
            (12345, sig.SIGKILL),
        )
        assert not pid_file.exists()


# -------------------------------------------------------------------
# TestDaemonise
# -------------------------------------------------------------------


class TestDaemonise:
    def test_daemonise_double_fork(self) -> None:
        """Lines 216-230: double-fork daemonisation."""
        from promptune.daemon.daemon import _daemonise

        with (
            patch(
                "promptune.daemon.daemon.os.fork",
                side_effect=[0, 0],
            ),
            patch("promptune.daemon.daemon.os.setsid"),
            patch(
                "promptune.daemon.daemon.os.open",
                return_value=3,
            ),
            patch("promptune.daemon.daemon.os.dup2"),
            patch("promptune.daemon.daemon.os.close"),
        ):
            _daemonise()

    def test_daemonise_first_fork_parent(self) -> None:
        """Lines 216-218: first fork returns child PID."""
        from promptune.daemon.daemon import _daemonise

        with (
            patch(
                "promptune.daemon.daemon.os.fork",
                return_value=42,
            ),
            patch(
                "promptune.daemon.daemon.sys.exit"
            ) as mock_exit,
        ):
            mock_exit.side_effect = SystemExit(0)
            with contextlib.suppress(SystemExit):
                _daemonise()
            mock_exit.assert_called_once_with(0)

    def test_daemonise_second_fork_parent(self) -> None:
        """Lines 222-224: second fork returns child PID."""
        from promptune.daemon.daemon import _daemonise

        with (
            patch(
                "promptune.daemon.daemon.os.fork",
                side_effect=[0, 42],
            ),
            patch("promptune.daemon.daemon.os.setsid"),
            patch(
                "promptune.daemon.daemon.sys.exit"
            ) as mock_exit,
        ):
            mock_exit.side_effect = SystemExit(0)
            with contextlib.suppress(SystemExit):
                _daemonise()
            mock_exit.assert_called_once_with(0)


# -------------------------------------------------------------------
# TestWritePidPermissionError
# -------------------------------------------------------------------


class TestWritePidPermissionError:
    def test_write_pid_permission_error(self) -> None:
        """Lines 126-127: check_accessibility raises."""
        with (
            patch(
                "promptune.daemon.daemon._read_pid",
                return_value=os.getpid(),
            ),
            patch(
                "promptune.daemon.daemon._is_running",
                return_value=True,
            ),
            patch(
                "promptune.daemon.daemon.SOCKET_PATH",
                MagicMock(exists=MagicMock(return_value=False)),
            ),
            patch(
                "sys.platform", "darwin"
            ),
            patch(
                "promptune.daemon.daemon.check_accessibility",
                side_effect=RuntimeError("boom"),
                create=True,
            ),
        ):
            # We need to patch the import inside get_status
            import types

            fake_hotkey = types.ModuleType("hotkey")
            fake_hotkey.check_accessibility = (  # type: ignore[attr-defined]
                MagicMock(side_effect=RuntimeError("boom"))
            )
            with patch.dict(
                "sys.modules",
                {
                    "promptune.daemon.hotkey": fake_hotkey,
                },
            ):
                status = get_status()
            assert status.accessibility_granted is False


# -------------------------------------------------------------------
# TestStartDaemonAccessibility
# -------------------------------------------------------------------


class TestStartDaemonAccessibility:
    def test_accessibility_denied_exits(
        self, tmp_path: Path
    ) -> None:
        """Lines 257-267: macOS accessibility denied."""
        import types

        pid_file = tmp_path / "daemon.pid"
        mock_platform = MagicMock()

        fake_hotkey = types.ModuleType("hotkey")
        fake_hotkey.check_accessibility = (  # type: ignore[attr-defined]
            MagicMock(return_value=False)
        )

        with (
            patch(
                "promptune.daemon.daemon.PID_FILE",
                pid_file,
            ),
            patch(
                "promptune.daemon.daemon.get_platform",
                return_value=mock_platform,
            ),
            patch("sys.platform", "darwin"),
            patch.dict(
                "sys.modules",
                {
                    "promptune.daemon.hotkey": fake_hotkey,
                },
            ),
        ):
            start_daemon(foreground=True)

        # Should return early — no PID file written
        assert not pid_file.exists()

    def test_accessibility_import_error(
        self, tmp_path: Path
    ) -> None:
        """Lines 266-267: ImportError on hotkey import."""
        pid_file = tmp_path / "daemon.pid"
        log_file = tmp_path / "daemon.log"
        mock_platform = MagicMock()
        mock_platform.hotkey.check_conflict.return_value = False
        mock_platform.hotkey.listen.return_value = None

        def raise_import(name, *a, **kw):
            if "hotkey" in name:
                raise ImportError("no hotkey")
            return orig_import(name, *a, **kw)

        import builtins

        orig_import = builtins.__import__

        with (
            patch(
                "promptune.daemon.daemon.PID_FILE",
                pid_file,
            ),
            patch(
                "promptune.daemon.daemon.LOG_FILE",
                log_file,
            ),
            patch(
                "promptune.daemon.daemon.get_platform",
                return_value=mock_platform,
            ),
            patch(
                "promptune.daemon.daemon.load_config",
                return_value={
                    "daemon": {"hotkey": "ctrl+shift+e"},
                    "local_llm": {"enabled": False},
                },
            ),
            patch(
                "promptune.daemon.daemon.start_ipc_server"
            ),
            patch(
                "promptune.daemon.daemon.signal.signal"
            ),
            patch("sys.platform", "darwin"),
            patch(
                "builtins.__import__",
                side_effect=raise_import,
            ),
        ):
            start_daemon(foreground=True)

        # Should proceed despite ImportError
        assert pid_file.exists()

    def test_background_calls_daemonise(
        self, tmp_path: Path
    ) -> None:
        """Line 279: foreground=False calls _daemonise."""
        pid_file = tmp_path / "daemon.pid"
        log_file = tmp_path / "daemon.log"
        mock_platform = MagicMock()
        mock_platform.hotkey.check_conflict.return_value = False
        mock_platform.hotkey.listen.return_value = None

        with (
            patch(
                "promptune.daemon.daemon.PID_FILE",
                pid_file,
            ),
            patch(
                "promptune.daemon.daemon.LOG_FILE",
                log_file,
            ),
            patch(
                "promptune.daemon.daemon.get_platform",
                return_value=mock_platform,
            ),
            patch(
                "promptune.daemon.daemon.load_config",
                return_value={
                    "daemon": {"hotkey": "ctrl+shift+e"},
                    "local_llm": {"enabled": False},
                },
            ),
            patch(
                "promptune.daemon.daemon.start_ipc_server"
            ),
            patch(
                "promptune.daemon.daemon.signal.signal"
            ),
            patch("sys.platform", "linux"),
            patch(
                "promptune.daemon.daemon._daemonise"
            ) as mock_daemonise,
        ):
            start_daemon(foreground=False)

        mock_daemonise.assert_called_once()


# -------------------------------------------------------------------
# TestSignalHandler
# -------------------------------------------------------------------


class TestSignalHandler:
    def test_handle_term_cleans_up(
        self, tmp_path: Path
    ) -> None:
        """Lines 299-302: _handle_term signal handler."""
        pid_file = tmp_path / "daemon.pid"
        log_file = tmp_path / "daemon.log"
        mock_platform = MagicMock()
        mock_platform.hotkey.check_conflict.return_value = (
            False
        )

        captured_handler = {}

        def capture_signal(signum, handler):
            captured_handler[signum] = handler

        with (
            patch(
                "promptune.daemon.daemon.PID_FILE",
                pid_file,
            ),
            patch(
                "promptune.daemon.daemon.LOG_FILE",
                log_file,
            ),
            patch(
                "promptune.daemon.daemon.SOCKET_PATH",
                tmp_path / "promptune.sock",
            ),
            patch(
                "promptune.daemon.daemon.get_platform",
                return_value=mock_platform,
            ),
            patch(
                "promptune.daemon.daemon.load_config",
                return_value={
                    "daemon": {"hotkey": "ctrl+shift+e"},
                    "local_llm": {"enabled": False},
                },
            ),
            patch(
                "promptune.daemon.daemon.start_ipc_server"
            ),
            patch(
                "promptune.daemon.daemon.signal.signal",
                side_effect=capture_signal,
            ),
            patch("sys.platform", "linux"),
        ):
            # listen() will block, so raise to break out
            mock_platform.hotkey.listen.side_effect = (
                KeyboardInterrupt
            )
            with contextlib.suppress(KeyboardInterrupt):
                start_daemon(foreground=True)

        import signal as sig

        handler = captured_handler.get(sig.SIGTERM)
        assert handler is not None

        # Call the handler — it calls sys.exit(0)
        with pytest.raises(SystemExit):
            handler(sig.SIGTERM, None)

        mock_platform.hotkey.stop.assert_called_once()


# -------------------------------------------------------------------
# TestOnHotkeyEmptyEnhancement
# -------------------------------------------------------------------


class TestOnHotkeyEmptyEnhancement:
    def test_empty_enhanced_text(
        self, tmp_path: Path
    ) -> None:
        """Lines 299-302 area: enhance returns empty."""
        platform = MagicMock()
        platform.active_window.get_frontmost_app.return_value = (
            "com.test.App"
        )
        platform.clipboard.read.return_value = "orig"
        platform.clipboard.copy_selection.return_value = (
            "text"
        )

        state = DaemonState()
        config = {}
        undo_file = tmp_path / "undo.txt"

        with (
            patch(
                "promptune.daemon.daemon.enhance"
            ) as mock_enh,
            patch(
                "promptune.daemon.daemon.UNDO_FILE",
                undo_file,
            ),
        ):
            mock_result = MagicMock()
            mock_result.enhanced = ""
            mock_result.score_before.total = 40
            mock_result.score_after.total = 40
            mock_enh.return_value = mock_result

            _on_hotkey(state, config, platform)

            # Even with empty result, it still pastes
            platform.clipboard.paste_result.assert_called_once_with(
                ""
            )
