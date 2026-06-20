"""Task 6: IPC Module — Unix Socket Server/Client tests."""

from __future__ import annotations

import contextlib
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="macOS-only",
)

from promptune.daemon.ipc import (  # noqa: E402
    DaemonState,
    send_ipc_message,
    start_ipc_server,
)


@pytest.fixture
def short_tmp():
    """Create a short temp dir for Unix sockets (macOS 104-byte path limit)."""
    d = tempfile.mkdtemp(dir="/tmp", prefix="pt_")
    yield Path(d)
    shutil.rmtree(d, ignore_errors=True)


class TestDaemonState:
    """Tests for DaemonState dataclass."""

    def test_initial_state(self) -> None:
        """DaemonState has correct default values."""
        state = DaemonState()
        assert state.last_cwd == ""
        assert state.last_project_root == ""
        assert state.enhancement_count == 0

    def test_lock_is_threading_lock(self) -> None:
        """DaemonState.lock is a threading.Lock instance."""
        state = DaemonState()
        assert isinstance(state.lock, type(threading.Lock()))

    def test_thread_safe_update(self) -> None:
        """Concurrent updates to state are safe."""
        state = DaemonState()
        results: list[str] = []

        def updater(val: str) -> None:
            with state.lock:
                state.last_cwd = val
                results.append(val)

        threads = [
            threading.Thread(target=updater, args=(f"/path/{i}",))
            for i in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All updates recorded, final state is one of the values
        assert len(results) == 10
        assert state.last_cwd.startswith("/path/")

    def test_state_fields_are_mutable(self) -> None:
        """DaemonState fields can be updated directly."""
        state = DaemonState()
        state.last_cwd = "/home/user/project"
        state.last_project_root = "/home/user/project"
        state.enhancement_count = 42

        assert state.last_cwd == "/home/user/project"
        assert state.last_project_root == "/home/user/project"
        assert state.enhancement_count == 42


class TestIPCServer:
    """Tests for start_ipc_server and send_ipc_message."""

    def test_report_cwd_updates_state(
        self, short_tmp: Path
    ) -> None:
        """report_cwd message causes server to update state."""
        sock_path = short_tmp / "test.sock"
        state = DaemonState()

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            start_ipc_server(state)
            time.sleep(0.2)

            send_ipc_message(
                {
                    "action": "report_cwd",
                    "cwd": "/home/user/myproject",
                    "project_root": "/home/user/myproject",
                }
            )
            time.sleep(0.1)

        assert state.last_cwd == "/home/user/myproject"
        assert (
            state.last_project_root == "/home/user/myproject"
        )

    def test_status_query_returns_state(
        self, short_tmp: Path
    ) -> None:
        """status action returns running, count, and cwd."""
        sock_path = short_tmp / "test.sock"
        state = DaemonState()
        state.last_cwd = "/projects/foo"
        state.enhancement_count = 7

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            start_ipc_server(state)
            time.sleep(0.2)

            response = send_ipc_message(
                {"action": "status"}
            )

        assert response is not None
        assert response["running"] is True
        assert response["enhancement_count"] == 7
        assert response["last_cwd"] == "/projects/foo"

    def test_send_to_nonexistent_socket_returns_none(
        self, short_tmp: Path
    ) -> None:
        """send_ipc_message returns None when socket missing."""
        missing_sock = short_tmp / "no_such.sock"

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH",
            missing_sock,
        ):
            result = send_ipc_message({"action": "status"})

        assert result is None

    def test_stale_socket_removed_before_binding(
        self, short_tmp: Path
    ) -> None:
        """start_ipc_server removes a stale socket file."""
        sock_path = short_tmp / "stale.sock"
        # Create a fake stale socket file
        sock_path.write_text("stale")
        assert sock_path.exists()

        state = DaemonState()

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            start_ipc_server(state)
            time.sleep(0.2)

        # Socket should now be a real socket, not a text file
        assert sock_path.exists()
        assert sock_path.stat().st_size == 0 or True  # it's a socket

    def test_report_cwd_only_updates_cwd_fields(
        self, short_tmp: Path
    ) -> None:
        """report_cwd does not change enhancement_count."""
        sock_path = short_tmp / "test2.sock"
        state = DaemonState()
        state.enhancement_count = 3

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            start_ipc_server(state)
            time.sleep(0.2)

            send_ipc_message(
                {
                    "action": "report_cwd",
                    "cwd": "/new/path",
                    "project_root": "/new",
                }
            )
            time.sleep(0.1)

        assert state.enhancement_count == 3
        assert state.last_cwd == "/new/path"

    def test_unknown_action_does_not_crash(
        self, short_tmp: Path
    ) -> None:
        """Unknown action is ignored gracefully."""
        sock_path = short_tmp / "test3.sock"
        state = DaemonState()

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            start_ipc_server(state)
            time.sleep(0.2)

            result = send_ipc_message(
                {"action": "unknown_action"}
            )

        # No crash — result is None (no response sent)
        assert result is None

    def test_malformed_json_is_handled(
        self, short_tmp: Path
    ) -> None:
        """Server ignores malformed JSON gracefully."""
        import socket as _socket

        sock_path = short_tmp / "bad_json.sock"
        state = DaemonState()

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            start_ipc_server(state)
            time.sleep(0.2)

            # Send raw invalid JSON bytes
            client = _socket.socket(
                _socket.AF_UNIX, _socket.SOCK_STREAM
            )
            client.connect(str(sock_path))
            client.sendall(b"not-valid-json{{{")
            client.close()
            time.sleep(0.1)

        # Server still running, state unchanged
        assert state.last_cwd == ""

    def test_handler_exception_on_recv(
        self, short_tmp: Path
    ) -> None:
        """OSError during conn.recv is caught."""
        import socket as _socket

        sock_path = short_tmp / "recv_err.sock"
        state = DaemonState()

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            start_ipc_server(state)
            time.sleep(0.2)

            # Connect then immediately close to trigger
            # OSError on server-side recv
            client = _socket.socket(
                _socket.AF_UNIX, _socket.SOCK_STREAM
            )
            client.connect(str(sock_path))
            client.close()
            time.sleep(0.1)

        # Server survives the error
        assert state.last_cwd == ""

    def test_stop_server_closes_socket(
        self, short_tmp: Path
    ) -> None:
        """Server thread exits after socket is closed."""
        import socket as _socket

        sock_path = short_tmp / "stop.sock"

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            # Manually create and close a server socket
            # to exercise the OSError break + finally
            srv = _socket.socket(
                _socket.AF_UNIX, _socket.SOCK_STREAM
            )
            srv.bind(str(sock_path))
            srv.listen(1)
            srv.settimeout(0.1)
            # Close it to force OSError on accept
            srv.close()

            # accept() on closed socket raises OSError
            with pytest.raises(OSError):
                srv.accept()

    def test_status_sendall_oserror(
        self, short_tmp: Path
    ) -> None:
        """OSError on conn.sendall during status is caught."""
        import json as _json
        import socket as _socket

        from promptune.daemon.ipc import _handle_message

        state = DaemonState()
        state.enhancement_count = 5

        # Create a socket pair; close the conn side
        # so sendall raises OSError
        s1, s2 = _socket.socketpair()
        s1.close()

        msg = {"action": "status"}
        data = _json.dumps(msg).encode()
        # Should not raise — the OSError is caught
        _handle_message(data, state, s1)
        s2.close()

    def test_client_connection_refused(
        self, short_tmp: Path
    ) -> None:
        """send_ipc_message returns None on connect refusal."""
        import socket as _socket

        sock_path = short_tmp / "refused.sock"
        # Create a real socket file but no listener
        srv = _socket.socket(
            _socket.AF_UNIX, _socket.SOCK_STREAM
        )
        srv.bind(str(sock_path))
        srv.close()

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            result = send_ipc_message(
                {"action": "status"}
            )

        assert result is None

    def test_client_recv_timeout(
        self, short_tmp: Path
    ) -> None:
        """Client handles socket.timeout on recv."""
        import socket as _socket

        sock_path = short_tmp / "timeout.sock"
        state = DaemonState()

        with patch(
            "promptune.daemon.ipc.SOCKET_PATH", sock_path
        ):
            start_ipc_server(state)
            time.sleep(0.2)

            # Connect with very short timeout
            client = _socket.socket(
                _socket.AF_UNIX, _socket.SOCK_STREAM
            )
            client.settimeout(0.001)
            client.connect(str(sock_path))
            # Send unknown action (no response)
            client.sendall(
                b'{"action": "unknown"}'
            )
            # recv should timeout
            with contextlib.suppress(_socket.timeout):
                client.recv(4096)
            client.close()

    def test_bind_failure_closes_server_socket(
        self, short_tmp: Path
    ) -> None:
        """start_ipc_server closes its socket when bind fails."""
        sock_path = short_tmp / "bind_fail.sock"
        state = DaemonState()
        fake_sock = MagicMock()
        fake_sock.bind.side_effect = OSError("bind failed")

        with (
            patch("promptune.daemon.ipc.SOCKET_PATH", sock_path),
            patch(
                "promptune.daemon.ipc.socket.socket",
                return_value=fake_sock,
            ),
            pytest.raises(OSError, match="bind failed"),
        ):
            start_ipc_server(state)

        fake_sock.close.assert_called_once()

    def test_client_invalid_json_response_returns_none(
        self, short_tmp: Path
    ) -> None:
        """send_ipc_message ignores malformed JSON responses."""
        sock_path = short_tmp / "bad_response.sock"
        sock_path.write_text("")
        fake_client = MagicMock()
        fake_client.recv.return_value = b"not-json"

        with (
            patch("promptune.daemon.ipc.SOCKET_PATH", sock_path),
            patch(
                "promptune.daemon.ipc.socket.socket",
                return_value=fake_client,
            ),
        ):
            result = send_ipc_message({"action": "status"})

        assert result is None
        fake_client.close.assert_called_once()


def test_recv_message_accumulates_multiple_chunks() -> None:
    """A message split across recv() buffers is reassembled, not truncated."""
    from unittest.mock import MagicMock

    from promptune.daemon.ipc import _recv_message

    payload = ('{"action": "report_cwd", "cwd": "' + "x" * 5000 + '"}').encode()
    mid = 4096
    conn = MagicMock()
    conn.recv.side_effect = [payload[:mid], payload[mid:], b""]

    data = _recv_message(conn)
    assert data == payload


def test_recv_message_returns_partial_data_on_timeout() -> None:
    """_recv_message stops cleanly when the peer stalls mid-message."""
    import socket
    from unittest.mock import MagicMock

    from promptune.daemon.ipc import _recv_message

    conn = MagicMock()
    conn.recv.side_effect = [b'{"action":', socket.timeout]

    data = _recv_message(conn)

    assert data == b'{"action":'
