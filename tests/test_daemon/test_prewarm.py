"""Tests for promptune.daemon.prewarm."""

from __future__ import annotations

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only"
)

from promptune.daemon.prewarm import (  # noqa: E402
    _RepeatingTimer,
    prewarm_ollama,
    start_prewarm_timer,
)

# ---------------------------------------------------------------------------
# TestPrewarmOllama
# ---------------------------------------------------------------------------


class TestPrewarmOllama:
    """Tests for the prewarm_ollama() function."""

    @patch("promptune.daemon.prewarm.httpx")
    def test_success_status_200(self, mock_httpx: MagicMock) -> None:
        """A 200 response is handled without raising."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_httpx.post.return_value = mock_response

        # Must not raise
        prewarm_ollama("http://localhost:11434", "qwen2.5:3b")

        mock_httpx.post.assert_called_once_with(
            "http://localhost:11434/api/generate",
            json={"model": "qwen2.5:3b", "prompt": "", "keep_alive": "30m"},
            timeout=10.0,
        )
        mock_response.raise_for_status.assert_called_once()

    @patch("promptune.daemon.prewarm.httpx")
    def test_http_error_status_500_does_not_raise(
        self, mock_httpx: MagicMock
    ) -> None:
        """An HTTP 500 error is logged but never re-raised."""
        import httpx as real_httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = (
            real_httpx.HTTPStatusError(
                "500 Server Error",
                request=MagicMock(),
                response=mock_response,
            )
        )
        mock_httpx.post.return_value = mock_response
        mock_httpx.HTTPStatusError = real_httpx.HTTPStatusError

        # Must not raise
        prewarm_ollama("http://localhost:11434", "qwen2.5:3b")

    @patch("promptune.daemon.prewarm.httpx")
    def test_connection_error_does_not_raise(
        self, mock_httpx: MagicMock
    ) -> None:
        """A network-level ConnectError is swallowed and never re-raised."""
        import httpx as real_httpx

        mock_httpx.post.side_effect = real_httpx.ConnectError(
            "Connection refused"
        )
        mock_httpx.HTTPStatusError = real_httpx.HTTPStatusError

        # Must not raise
        prewarm_ollama("http://localhost:11434", "qwen2.5:3b")

    @patch("promptune.daemon.prewarm.httpx")
    def test_custom_keepalive_forwarded(self, mock_httpx: MagicMock) -> None:
        """The keepalive parameter is forwarded in the JSON payload."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_httpx.post.return_value = mock_response

        prewarm_ollama("http://localhost:11434", "llama3", keepalive="10m")

        _, kwargs = mock_httpx.post.call_args
        assert kwargs["json"]["keep_alive"] == "10m"

    @patch("promptune.daemon.prewarm.httpx")
    def test_trailing_slash_stripped_from_host(
        self, mock_httpx: MagicMock
    ) -> None:
        """Trailing slashes on the host are stripped before building the URL."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_httpx.post.return_value = mock_response

        prewarm_ollama("http://localhost:11434/", "llama3")

        args, _ = mock_httpx.post.call_args
        assert args[0] == "http://localhost:11434/api/generate"


# ---------------------------------------------------------------------------
# TestStartPrewarmTimer
# ---------------------------------------------------------------------------


class TestStartPrewarmTimer:
    """Tests for start_prewarm_timer()."""

    @patch("promptune.daemon.prewarm.httpx")
    def test_prewarm_called_after_short_interval(
        self, mock_httpx: MagicMock
    ) -> None:
        """prewarm_ollama fires within a short interval when interval_minutes=0."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_httpx.post.return_value = mock_response

        timer = start_prewarm_timer(
            "http://localhost:11434", "qwen2.5:3b", interval_minutes=0
        )
        try:
            # 0.01s floor interval — wait generously for at least one fire
            time.sleep(0.15)
            assert mock_httpx.post.call_count >= 1
        finally:
            timer.cancel()

    def test_timer_is_daemon_thread(self) -> None:
        """The returned timer must be a daemon thread."""
        with patch("promptune.daemon.prewarm.httpx"):
            timer = start_prewarm_timer(
                "http://localhost:11434", "qwen2.5:3b", interval_minutes=60
            )
            try:
                assert timer.daemon is True
            finally:
                timer.cancel()

    def test_returns_repeating_timer_instance(self) -> None:
        """start_prewarm_timer returns a _RepeatingTimer."""
        with patch("promptune.daemon.prewarm.httpx"):
            timer = start_prewarm_timer(
                "http://localhost:11434", "qwen2.5:3b", interval_minutes=60
            )
            try:
                assert isinstance(timer, _RepeatingTimer)
            finally:
                timer.cancel()

    @patch("promptune.daemon.prewarm.httpx")
    def test_cancel_stops_repeating_chain(
        self, mock_httpx: MagicMock
    ) -> None:
        """Cancelling the timer stops subsequent fires via shared stop event."""
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_httpx.post.return_value = mock_response

        timer = start_prewarm_timer(
            "http://localhost:11434", "qwen2.5:3b", interval_minutes=0
        )
        # Let it fire a couple of times
        time.sleep(0.1)
        timer.cancel()
        # Allow in-flight timers to settle
        time.sleep(0.05)
        count_at_cancel = mock_httpx.post.call_count

        # Wait and confirm no more fires
        time.sleep(0.15)
        assert mock_httpx.post.call_count == count_at_cancel
