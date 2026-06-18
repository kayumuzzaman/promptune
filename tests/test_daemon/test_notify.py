"""Tests for promptune.daemon.notify — macOS notification helper."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only"
)

from promptune.daemon.notify import (  # noqa: E402
    _escape,
    notify,
    notify_enhanced,
    notify_error,
)


class TestEscape:
    def test_escapes_backslash(self) -> None:
        assert _escape("back\\slash") == "back\\\\slash"

    def test_escapes_double_quote(self) -> None:
        assert _escape('say "hello"') == 'say \\"hello\\"'

    def test_escapes_both(self) -> None:
        assert _escape('path\\to\\"file"') == 'path\\\\to\\\\\\"file\\"'

    def test_plain_text_unchanged(self) -> None:
        assert _escape("hello world") == "hello world"


class TestNotify:
    @patch("promptune.daemon.notify.subprocess")
    def test_with_sound_includes_tink(self, mock_subprocess: MagicMock) -> None:
        notify("Title", "Message", sound=True)

        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]  # third element of the command list
        assert 'sound name "Tink"' in script

    @patch("promptune.daemon.notify.subprocess")
    def test_without_sound_omits_tink(self, mock_subprocess: MagicMock) -> None:
        notify("Title", "Message", sound=False)

        mock_subprocess.run.assert_called_once()
        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert 'sound name "Tink"' not in script

    @patch("promptune.daemon.notify.subprocess")
    def test_escapes_quotes_in_message(self, mock_subprocess: MagicMock) -> None:
        notify("Title", 'say "hello"', sound=False)

        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert '\\"hello\\"' in script

    def test_swallows_subprocess_timeout(self) -> None:
        """A hung osascript must not raise — callers run notify() inside the
        clipboard-delivery try/except, where a raise is misreported as a paste
        failure."""
        import subprocess

        with patch(
            "promptune.daemon.notify.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="osascript", timeout=5),
        ):
            notify("Title", "Message")  # must not raise

    def test_swallows_missing_binary(self) -> None:
        """A missing osascript binary (OSError) must not raise."""
        with patch(
            "promptune.daemon.notify.subprocess.run",
            side_effect=FileNotFoundError("osascript not found"),
        ):
            notify("Title", "Message")  # must not raise

    @patch("promptune.daemon.notify.subprocess")
    def test_escapes_quotes_in_title(self, mock_subprocess: MagicMock) -> None:
        notify('Ti"tle', "Message", sound=False)

        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert 'Ti\\"tle' in script

    @patch("promptune.daemon.notify.subprocess")
    def test_uses_osascript(self, mock_subprocess: MagicMock) -> None:
        notify("T", "M")

        call_args = mock_subprocess.run.call_args
        command = call_args[0][0]
        assert command[0] == "osascript"
        assert command[1] == "-e"

    @patch("promptune.daemon.notify.subprocess")
    def test_timeout_is_five_seconds(self, mock_subprocess: MagicMock) -> None:
        notify("T", "M")

        call_kwargs = mock_subprocess.run.call_args[1]
        assert call_kwargs["timeout"] == 5


class TestNotifyEnhanced:
    @patch("promptune.daemon.notify.subprocess")
    def test_positive_delta(self, mock_subprocess: MagicMock) -> None:
        notify_enhanced(score_before=40, score_after=52)

        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert "+12 PQS" in script
        assert "Cmd+Z to undo" in script

    @patch("promptune.daemon.notify.subprocess")
    def test_negative_delta(self, mock_subprocess: MagicMock) -> None:
        notify_enhanced(score_before=50, score_after=45)

        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert "-5 PQS" in script

    @patch("promptune.daemon.notify.subprocess")
    def test_zero_delta(self, mock_subprocess: MagicMock) -> None:
        notify_enhanced(score_before=60, score_after=60)

        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert "+0 PQS" in script

    @patch("promptune.daemon.notify.subprocess")
    def test_plays_sound(self, mock_subprocess: MagicMock) -> None:
        notify_enhanced(score_before=30, score_after=50)

        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert 'sound name "Tink"' in script


class TestNotifyError:
    @patch("promptune.daemon.notify.subprocess")
    def test_no_sound(self, mock_subprocess: MagicMock) -> None:
        notify_error("Something went wrong")

        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert 'sound name "Tink"' not in script

    @patch("promptune.daemon.notify.subprocess")
    def test_title_is_promptune(self, mock_subprocess: MagicMock) -> None:
        notify_error("Something went wrong")

        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert 'with title "Promptune"' in script

    @patch("promptune.daemon.notify.subprocess")
    def test_message_in_script(self, mock_subprocess: MagicMock) -> None:
        notify_error("API key missing")

        call_args = mock_subprocess.run.call_args
        script = call_args[0][0][2]
        assert "API key missing" in script
