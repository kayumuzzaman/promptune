"""Tests for promptune.daemon.daemon — lifecycle and enhancement pipeline."""

from __future__ import annotations

import contextlib
import logging
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from promptune.daemon.daemon import (
    _cleanup,
    _enhancing,
    _is_daemon_process,
    _is_python_executable,
    _is_running,
    _on_hotkey,
    _process_command,
    _process_name,
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

    def test_process_command_does_not_hide_unexpected_errors(self) -> None:
        with (
            patch(
                "promptune.daemon.daemon.subprocess.run",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            _process_command(12345)

    def test_process_name_does_not_hide_unexpected_errors(self) -> None:
        with (
            patch(
                "promptune.daemon.daemon.subprocess.run",
                side_effect=RuntimeError("boom"),
            ),
            pytest.raises(RuntimeError, match="boom"),
        ):
            _process_name(12345)

    def test_process_helpers_return_none_for_ps_failures(self) -> None:
        with patch(
            "promptune.daemon.daemon.subprocess.run",
            side_effect=subprocess.TimeoutExpired("ps", 2),
        ):
            assert _process_command(12345) is None
            assert _process_name(12345) is None

    def test_is_daemon_process_rejects_argument_text_match(self) -> None:
        """A reused PID is not ours just because argv mentions promptune daemon."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value="/usr/bin/python worker.py --note 'promptune daemon'",
            ),
        ):
            assert _is_daemon_process(12345) is False

    def test_is_daemon_process_accepts_promptune_daemon_start(self) -> None:
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="promptune",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value="/venv/bin/promptune daemon start --foreground",
            ),
        ):
            assert _is_daemon_process(12345) is True

    def test_is_daemon_process_accepts_space_in_path_console_script(
        self,
    ) -> None:
        """A daemon installed under a path with a space is still recognised.

        macOS paths routinely contain spaces ("Application Support", a user's
        full name). `ps -o command=` space-joins argv, so naive shlex/tokenise
        splits the path itself and false-negatives the real daemon — causing
        stop_daemon() to orphan it and start_daemon() to launch a duplicate.
        """
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="promptune",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/Users/Jane Doe/Library/Application Support/venv/bin/"
                    "promptune daemon start --foreground"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is True

    def test_is_daemon_process_accepts_space_in_path_module_form(self) -> None:
        """The `python -m promptune daemon start` form (plist/systemd) too."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="python",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/Users/Jane Doe/.venv/bin/python -m promptune daemon "
                    "start --foreground"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is True

    def test_is_daemon_process_accepts_capitalized_python_comm(self) -> None:
        """macOS framework builds can report Python with a capital P."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="Python",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/Library/Frameworks/Python.framework/Versions/3.14/bin/"
                    "python3 -m promptune daemon start --foreground"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is True

    def test_is_daemon_process_accepts_python_comm_console_script(
        self,
    ) -> None:
        """Shebang console scripts can report Python as the executable."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="python3.14",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/Users/Jane Doe/Library/Application Support/venv/bin/"
                    "promptune daemon start --foreground"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is True

    def test_is_daemon_process_accepts_python_interpreter_console_script(
        self,
    ) -> None:
        """Setuptools console scripts run as python /path/to/promptune."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="python3.12",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/opt/promptune/.venv/bin/python3.12 "
                    "/opt/promptune/.venv/bin/promptune daemon start "
                    "--foreground"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is True

    def test_is_daemon_process_accepts_python_console_script_space_path(
        self,
    ) -> None:
        """Python shebang wrappers can point at promptune under a spaced path."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="Python",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/Library/Frameworks/Python.framework/Versions/3.14/"
                    "Resources/Python.app/Contents/MacOS/Python "
                    "/Users/Jane Doe/Library/Application Support/venv/bin/"
                    "promptune daemon start --foreground"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is True

    def test_is_daemon_process_rejects_bare_arg_subsequence(self) -> None:
        """A process that merely passes `promptune daemon start` as plain
        arguments (not as the program / -m target) is not our daemon."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value="/usr/bin/grep promptune daemon start log.txt",
            ),
        ):
            assert _is_daemon_process(12345) is False

    def test_is_daemon_process_rejects_python_worker_slash_promptune_arg(
        self,
    ) -> None:
        """Python workers are not daemons just because an arg names promptune."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="python",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/usr/bin/python worker.py /tmp/promptune daemon start"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is False

    def test_is_daemon_process_rejects_capitalized_python_worker_arg(
        self,
    ) -> None:
        """Capitalized Python comm has the same false-positive boundary."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="Python",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/Library/Frameworks/Python.framework/Versions/3.14/"
                    "Resources/Python.app/Contents/MacOS/Python worker.py "
                    "/tmp/promptune daemon start"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is False

    def test_is_daemon_process_rejects_non_python_module_arg(self) -> None:
        """Only Python's `-m promptune daemon start` form is a daemon."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="some-tool",
                create=True,
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/usr/bin/some-tool --module -m promptune daemon start"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is False

    def test_is_daemon_process_rejects_slash_promptune_argument(self) -> None:
        """A non-daemon process can pass a path containing promptune words."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="grep",
                create=True,
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/usr/bin/grep /tmp/promptune daemon start log.txt"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is False

    def test_is_daemon_process_rejects_python_module_words_as_args(self) -> None:
        """Only the process executable can be Python for `-m promptune`."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="grep",
                create=True,
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/usr/bin/grep python -m promptune daemon start"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is False

    def test_is_daemon_process_rejects_python_worker_reused_pid_module_arg(
        self,
    ) -> None:
        """A Python worker that passes `-m promptune` is not the daemon."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="python3.13t",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/usr/bin/python3.13t worker.py -m promptune daemon start"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is False

    def test_is_daemon_process_rejects_spaced_python_worker_module_arg(
        self,
    ) -> None:
        """A spaced Python worker is not a daemon due to later module args."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="python",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/Users/Jane Doe/.venv/bin/python worker.py "
                    "/usr/bin/python -m promptune daemon start"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is False

    def test_is_daemon_process_accepts_free_threaded_python_comm(
        self,
    ) -> None:
        """Free-threaded/ABI-suffixed interpreters (python3.13t) count."""
        with (
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch(
                "promptune.daemon.daemon._process_name",
                return_value="python3.13t",
            ),
            patch(
                "promptune.daemon.daemon._process_command",
                return_value=(
                    "/opt/.venv/bin/python3.13t -m promptune daemon start "
                    "--foreground"
                ),
            ),
        ):
            assert _is_daemon_process(12345) is True

    def test_is_python_executable_accepts_abi_suffixes(self) -> None:
        """ABI suffixes (free-threaded t, debug d/dm) are recognised."""
        assert _is_python_executable("python3.13t")
        assert _is_python_executable("python3.13d")
        assert _is_python_executable("python3.13dm")
        assert _is_python_executable("python3.12")
        assert _is_python_executable("python")
        # A non-interpreter name merely starting with "python" is rejected.
        assert not _is_python_executable("pythonista")
        assert not _is_python_executable("python3.13foo")

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
            patch(
                "promptune.daemon.daemon._is_daemon_process",
                return_value=True,
            ),
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

        # Hold the guard: a concurrent hotkey event must skip the pipeline
        # rather than run a second, overlapping enhancement.
        acquired = _enhancing.acquire(blocking=False)
        assert acquired is True
        try:
            _on_hotkey(state, config, platform)
        finally:
            _enhancing.release()

        platform.clipboard.copy_selection.assert_not_called()
        # Guard is released again afterwards, so the next event can run.
        assert _enhancing.acquire(blocking=False) is True
        _enhancing.release()


# ---------------------------------------------------------------------------
# TestDebounce
# ---------------------------------------------------------------------------


class TestDebounce:
    def test_debounce_flag(self) -> None:
        assert _enhancing.locked() is False


# ---------------------------------------------------------------------------
# TestStartDaemon
# ---------------------------------------------------------------------------


class TestStartDaemon:
    def test_already_running_exits_early(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        pid_file.write_text(str(os.getpid()))
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            # A verified live promptune daemon must short-circuit start before
            # any platform detection. Without this mock, _is_daemon_process()
            # runs a real `ps` on the test's own PID, correctly reports "not a
            # daemon", and start_daemon() would fall through to a real
            # get_platform()/hotkey.listen() that blocks the suite forever.
            patch(
                "promptune.daemon.daemon._is_daemon_process",
                return_value=True,
            ),
            patch("promptune.daemon.daemon.get_platform") as mock_get_platform,
        ):
            start_daemon(foreground=True)

        # Early return: platform detection (and thus hotkey.listen) never runs.
        mock_get_platform.assert_not_called()

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

        assert not pid_file.exists()
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

    def test_normal_event_loop_exit_cleans_up_runtime_files_and_timer(
        self, tmp_path: Path
    ) -> None:
        """A foreground daemon whose listener returns still tears down state."""
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        log_file = tmp_path / "daemon.log"
        sock_path.write_text("")

        mock_platform = MagicMock()
        mock_platform.hotkey.check_conflict.return_value = False
        mock_platform.hotkey.listen.return_value = None
        mock_timer = MagicMock()

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
                "local_llm": {
                    "enabled": True,
                    "host": "http://localhost:11434",
                    "model": "qwen2.5:3b",
                },
            }),
            patch("promptune.daemon.daemon.start_ipc_server"),
            patch("promptune.daemon.daemon.signal.signal"),
            patch(
                "promptune.daemon.prewarm.start_prewarm_timer",
                return_value=mock_timer,
            ),
            patch("sys.platform", "linux"),
        ):
            start_daemon(foreground=True)

        mock_timer.cancel.assert_called_once()
        mock_platform.hotkey.stop.assert_called_once()
        assert not pid_file.exists()
        assert not sock_path.exists()


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

    def test_live_unrelated_pid_is_treated_as_stale(
        self, tmp_path: Path
    ) -> None:
        """PID reuse must not make stop_daemon signal an unrelated process."""
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text("12345")
        sock_path.write_text("")

        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
            patch("promptune.daemon.daemon._is_running", return_value=True),
            patch("promptune.daemon.daemon.os.kill") as mock_kill,
        ):
            stop_daemon()

        mock_kill.assert_not_called()
        assert not pid_file.exists()
        assert not sock_path.exists()

    def test_sends_sigterm(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text("12345")
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
            patch(
                "promptune.daemon.daemon._is_daemon_process",
                return_value=True,
            ),
            patch(
                "promptune.daemon.daemon._is_running",
                return_value=False,
            ),
            patch("promptune.daemon.daemon.os.kill") as mock_kill,
        ):
            stop_daemon()
        import signal

        mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_grace_loop_returns_when_process_dies(
        self, tmp_path: Path
    ) -> None:
        """Grace loop polls cheap _is_running and exits without SIGKILL."""
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text("12345")
        sock_path.write_text("")
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
            patch(
                "promptune.daemon.daemon._is_daemon_process",
                return_value=True,
            ),
            patch(
                "promptune.daemon.daemon._is_running",
                side_effect=[True, False],
            ),
            patch("promptune.daemon.daemon.os.kill") as mock_kill,
            patch("promptune.daemon.daemon.time.sleep"),
        ):
            stop_daemon()
        import signal

        # SIGTERM only — process died during grace, never escalated to SIGKILL.
        mock_kill.assert_called_once_with(12345, signal.SIGTERM)
        assert not pid_file.exists()
        assert not sock_path.exists()

    def test_sigterm_oserror_cleans_up(self, tmp_path: Path) -> None:
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text("12345")
        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
            patch(
                "promptune.daemon.daemon._is_daemon_process",
                return_value=True,
            ),
            patch(
                "promptune.daemon.daemon.os.kill",
                side_effect=OSError("no such process"),
            ),
        ):
            stop_daemon()

    def test_force_kill_after_timeout(self, tmp_path: Path) -> None:
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
                "promptune.daemon.daemon._is_daemon_process",
                return_value=True,
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

    def test_reused_pid_after_grace_timeout_skips_force_kill(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """If PID identity changes during grace, do not SIGKILL it."""
        pid_file = tmp_path / "daemon.pid"
        sock_path = tmp_path / "promptune.sock"
        pid_file.write_text("12345")
        sock_path.write_text("")
        caplog.set_level(logging.INFO, logger="promptune.daemon.daemon")

        with (
            patch("promptune.daemon.daemon.PID_FILE", pid_file),
            patch("promptune.daemon.daemon.SOCKET_PATH", sock_path),
            patch(
                "promptune.daemon.daemon._is_daemon_process",
                side_effect=[True, False],
            ),
            patch(
                "promptune.daemon.daemon._is_running",
                return_value=True,
            ),
            patch("promptune.daemon.daemon.os.kill") as mock_kill,
            patch("promptune.daemon.daemon.time.sleep"),
        ):
            stop_daemon()

        import signal as sig

        mock_kill.assert_called_once_with(12345, sig.SIGTERM)
        assert not pid_file.exists()
        assert not sock_path.exists()
        assert "stale" in caplog.text.lower()
        assert "reused" in caplog.text.lower()
        assert "force-killed" not in caplog.text.lower()


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
                "promptune.daemon.daemon._is_daemon_process",
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
        assert not pid_file.exists()

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
        mock_platform.hotkey.stop.reset_mock()

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
