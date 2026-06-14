"""Tests for promptune.daemon.clipboard — macOS clipboard utilities."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

if sys.platform != "darwin":
    pytest.skip("macOS-only", allow_module_level=True)

# ---------------------------------------------------------------------------
# We patch at the module level so that imports inside clipboard.py resolve to
# our mocks before any real system calls are attempted. The skip above aborts
# collection on non-macOS *before* this import runs (skipif would not).
# ---------------------------------------------------------------------------

from promptune.daemon import clipboard  # noqa: E402  (import after skip guard)

# ---------------------------------------------------------------------------
# TestSaveClipboard
# ---------------------------------------------------------------------------


class TestSaveClipboard:
    def test_read_text_success(self) -> None:
        """save_clipboard returns stdout when pbpaste succeeds."""
        mock_result = MagicMock()
        mock_result.stdout = "hello world"

        with patch("promptune.daemon.clipboard.subprocess") as mock_sub:
            mock_sub.run.return_value = mock_result
            result = clipboard.save_clipboard()

        assert result == "hello world"
        mock_sub.run.assert_called_once_with(
            ["pbpaste"],
            capture_output=True,
            text=True,
            check=True,
        )

    def test_failure_returns_none(self) -> None:
        """save_clipboard returns None when pbpaste raises an exception."""
        with patch("promptune.daemon.clipboard.subprocess") as mock_sub:
            mock_sub.run.side_effect = Exception("pbpaste not found")
            result = clipboard.save_clipboard()

        assert result is None


# ---------------------------------------------------------------------------
# TestWriteClipboard
# ---------------------------------------------------------------------------


class TestWriteClipboard:
    def test_write_text_calls_pbcopy(self) -> None:
        """write_clipboard passes text to pbcopy via stdin."""
        with patch("promptune.daemon.clipboard.subprocess") as mock_sub:
            clipboard.write_clipboard("my text")

        mock_sub.run.assert_called_once_with(
            ["pbcopy"],
            input="my text",
            text=True,
            check=True,
        )

    def test_write_empty_string(self) -> None:
        """write_clipboard accepts an empty string."""
        with patch("promptune.daemon.clipboard.subprocess") as mock_sub:
            clipboard.write_clipboard("")

        mock_sub.run.assert_called_once_with(
            ["pbcopy"],
            input="",
            text=True,
            check=True,
        )


# ---------------------------------------------------------------------------
# TestSimulateKeys
# ---------------------------------------------------------------------------


class TestSimulateKeys:
    def _make_quartz_mock(self) -> MagicMock:
        mock_quartz = MagicMock()
        mock_quartz.kCGEventSourceStateHIDSystemState = 1
        mock_quartz.kCGEventFlagMaskCommand = 0x100000
        mock_quartz.kCGHIDEventTap = 0
        mock_quartz.CGEventSourceCreate.return_value = MagicMock()
        mock_quartz.CGEventCreateKeyboardEvent.return_value = MagicMock()
        return mock_quartz

    def test_cmd_c_uses_keycode_8(self) -> None:
        """simulate_cmd_c creates key events with keycode 8."""
        mock_quartz = self._make_quartz_mock()

        with patch("promptune.daemon.clipboard.Quartz", mock_quartz):
            clipboard.simulate_cmd_c()

        calls = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
        keycodes = [c[0][1] for c in calls]
        assert all(k == 8 for k in keycodes), f"Expected keycode 8, got {keycodes}"

    def test_cmd_v_uses_keycode_9(self) -> None:
        """simulate_cmd_v creates key events with keycode 9."""
        mock_quartz = self._make_quartz_mock()

        with patch("promptune.daemon.clipboard.Quartz", mock_quartz):
            clipboard.simulate_cmd_v()

        calls = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
        keycodes = [c[0][1] for c in calls]
        assert all(k == 9 for k in keycodes), f"Expected keycode 9, got {keycodes}"

    def test_cmd_c_sets_command_modifier(self) -> None:
        """simulate_cmd_c applies kCGEventFlagMaskCommand to both events."""
        mock_quartz = self._make_quartz_mock()

        with patch("promptune.daemon.clipboard.Quartz", mock_quartz):
            clipboard.simulate_cmd_c()

        set_flags_calls = mock_quartz.CGEventSetFlags.call_args_list
        assert len(set_flags_calls) == 2
        for c in set_flags_calls:
            assert c[0][1] == mock_quartz.kCGEventFlagMaskCommand

    def test_cmd_c_posts_key_down_and_up(self) -> None:
        """simulate_cmd_c posts exactly two events (down + up)."""
        mock_quartz = self._make_quartz_mock()

        with patch("promptune.daemon.clipboard.Quartz", mock_quartz):
            clipboard.simulate_cmd_c()

        create_calls = mock_quartz.CGEventCreateKeyboardEvent.call_args_list
        # First call: key_down=True, second: key_down=False
        assert create_calls[0][0][2] is True
        assert create_calls[1][0][2] is False

    def test_simulate_key_combo_calls_event_post(self) -> None:
        """_simulate_key_combo posts both events via CGEventPost."""
        mock_quartz = self._make_quartz_mock()

        with patch("promptune.daemon.clipboard.Quartz", mock_quartz):
            clipboard._simulate_key_combo(8, mock_quartz.kCGEventFlagMaskCommand)

        assert mock_quartz.CGEventPost.call_count == 2


# ---------------------------------------------------------------------------
# TestGetFrontmostApp
# ---------------------------------------------------------------------------


class TestGetFrontmostApp:
    def test_returns_bundle_id(self) -> None:
        """get_frontmost_app returns the bundle identifier string."""
        mock_app = MagicMock()
        mock_app.bundleIdentifier.return_value = "com.apple.finder"

        mock_workspace = MagicMock()
        shared = mock_workspace.sharedWorkspace.return_value
        shared.frontmostApplication.return_value = mock_app

        with patch("promptune.daemon.clipboard.NSWorkspace", mock_workspace):
            result = clipboard.get_frontmost_app()

        assert result == "com.apple.finder"

    def test_returns_empty_string_if_no_app(self) -> None:
        """get_frontmost_app returns '' when frontmostApplication is None."""
        mock_workspace = MagicMock()
        shared = mock_workspace.sharedWorkspace.return_value
        shared.frontmostApplication.return_value = None

        with patch("promptune.daemon.clipboard.NSWorkspace", mock_workspace):
            result = clipboard.get_frontmost_app()

        assert result == ""

    def test_returns_empty_string_if_bundle_id_none(self) -> None:
        """get_frontmost_app returns '' when bundleIdentifier() returns None."""
        mock_app = MagicMock()
        mock_app.bundleIdentifier.return_value = None

        mock_workspace = MagicMock()
        shared = mock_workspace.sharedWorkspace.return_value
        shared.frontmostApplication.return_value = mock_app

        with patch("promptune.daemon.clipboard.NSWorkspace", mock_workspace):
            result = clipboard.get_frontmost_app()

        assert result == ""


# ---------------------------------------------------------------------------
# TestCopySelection
# ---------------------------------------------------------------------------


class TestCopySelection:
    def test_calls_simulate_cmd_c_then_save_clipboard(self) -> None:
        """copy_selection simulates Cmd+C, sleeps, then reads clipboard."""
        mock_quartz = MagicMock()
        mock_quartz.kCGEventSourceStateHIDSystemState = 1
        mock_quartz.kCGEventFlagMaskCommand = 0x100000
        mock_quartz.kCGHIDEventTap = 0
        mock_quartz.CGEventSourceCreate.return_value = MagicMock()
        mock_quartz.CGEventCreateKeyboardEvent.return_value = MagicMock()

        mock_result = MagicMock()
        mock_result.stdout = "selected text"

        call_order: list[str] = []

        def fake_cmd_c() -> None:
            call_order.append("cmd_c")

        def fake_sleep(_: float) -> None:
            call_order.append("sleep")

        def fake_save() -> str:
            call_order.append("save_clipboard")
            return "selected text"

        with (
            patch("promptune.daemon.clipboard.simulate_cmd_c", fake_cmd_c),
            patch("promptune.daemon.clipboard.time.sleep", fake_sleep),
            patch("promptune.daemon.clipboard.save_clipboard", fake_save),
        ):
            result = clipboard.copy_selection()

        assert call_order == ["cmd_c", "sleep", "save_clipboard"]
        assert result == "selected text"

    def test_sleep_duration_matches_settle_ms(self) -> None:
        """copy_selection sleeps for CLIPBOARD_SETTLE_MS / 1000 seconds."""
        sleep_durations: list[float] = []

        with (
            patch("promptune.daemon.clipboard.simulate_cmd_c"),
            patch(
                "promptune.daemon.clipboard.time.sleep",
                side_effect=lambda d: sleep_durations.append(d),
            ),
            patch(
                "promptune.daemon.clipboard.save_clipboard",
                return_value="x",
            ),
        ):
            clipboard.copy_selection()

        assert sleep_durations == [clipboard.CLIPBOARD_SETTLE_MS / 1000.0]


# ---------------------------------------------------------------------------
# TestUndoBuffer
# ---------------------------------------------------------------------------


class TestUndoBuffer:
    def test_saves_json_with_clipboard_and_selection(
        self, tmp_path: Path
    ) -> None:
        """save_undo writes JSON containing original_clipboard and selected_text."""
        undo_file = tmp_path / "undo.txt"

        with patch("promptune.daemon.clipboard.UNDO_FILE", undo_file):
            clipboard.save_undo("prev clipboard", "my selection")

        payload = json.loads(undo_file.read_text())
        assert payload["original_clipboard"] == "prev clipboard"
        assert payload["selected_text"] == "my selection"

    def test_handles_none_clipboard(self, tmp_path: Path) -> None:
        """save_undo stores null for original_clipboard when it is None."""
        undo_file = tmp_path / "undo.txt"

        with patch("promptune.daemon.clipboard.UNDO_FILE", undo_file):
            clipboard.save_undo(None, "selected")

        payload = json.loads(undo_file.read_text())
        assert payload["original_clipboard"] is None
        assert payload["selected_text"] == "selected"

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        """save_undo creates missing parent directories."""
        undo_file = tmp_path / "nested" / "dir" / "undo.txt"

        with patch("promptune.daemon.clipboard.UNDO_FILE", undo_file):
            clipboard.save_undo("clip", "sel")

        assert undo_file.exists()
