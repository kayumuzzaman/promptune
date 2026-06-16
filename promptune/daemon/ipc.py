"""Unix socket IPC — server/client for daemon state sharing."""

from __future__ import annotations

import contextlib
import json
import logging
import socket
import threading
from dataclasses import dataclass, field
from pathlib import Path

SOCKET_PATH = Path(
    "~/.local/share/promptune/promptune.sock"
).expanduser()

_BUFFER_SIZE = 4096
_log = logging.getLogger(__name__)


@dataclass
class DaemonState:
    """Shared mutable daemon state."""

    last_cwd: str = ""
    last_project_root: str = ""
    enhancement_count: int = 0
    lock: threading.Lock = field(
        default_factory=threading.Lock
    )


def _handle_message(
    data: bytes,
    state: DaemonState,
    conn: socket.socket,
) -> None:
    """Parse incoming JSON message and dispatch action."""
    try:
        msg: dict = json.loads(data.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        _log.warning("IPC: received invalid JSON")
        return

    action = msg.get("action", "")

    if action == "report_cwd":
        cwd = msg.get("cwd", "")
        project_root = msg.get("project_root", "")
        with state.lock:
            state.last_cwd = cwd
            state.last_project_root = project_root
        # Ack so the client doesn't block on its recv timeout waiting for a
        # reply that depends on connection-close timing.
        with contextlib.suppress(OSError):
            conn.sendall(json.dumps({"ok": True}).encode())

    elif action == "status":
        with state.lock:
            response = {
                "running": True,
                "enhancement_count": state.enhancement_count,
                "last_cwd": state.last_cwd,
            }
        try:
            conn.sendall(
                json.dumps(response).encode()
            )
        except OSError as exc:
            _log.warning(
                "IPC: failed to send response: %s", exc
            )

    else:
        _log.warning("IPC: unknown action %r", action)


def start_ipc_server(state: DaemonState) -> threading.Thread:
    """Start Unix domain socket listener in a daemon thread.

    Removes a stale socket file before binding. Returns the
    thread so callers can join or inspect it.
    """
    # Remove stale socket if it exists
    if SOCKET_PATH.exists():
        SOCKET_PATH.unlink()

    SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

    server_sock = socket.socket(
        socket.AF_UNIX, socket.SOCK_STREAM
    )
    try:
        server_sock.bind(str(SOCKET_PATH))
        SOCKET_PATH.chmod(0o700)
        server_sock.listen(5)
        server_sock.settimeout(1.0)
    except OSError:
        server_sock.close()
        raise

    def _serve() -> None:
        try:
            while True:
                try:
                    conn, _ = server_sock.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break

                try:
                    data = conn.recv(_BUFFER_SIZE)
                    if data:
                        _handle_message(data, state, conn)
                except OSError as exc:
                    _log.warning(
                        "IPC: connection error: %s", exc
                    )
                finally:
                    with contextlib.suppress(OSError):
                        conn.close()
        finally:
            with contextlib.suppress(OSError):
                server_sock.close()
            with contextlib.suppress(OSError):
                SOCKET_PATH.unlink()

    thread = threading.Thread(
        target=_serve, daemon=True, name="ipc-server"
    )
    thread.start()
    return thread


def send_ipc_message(msg: dict) -> dict | None:
    """Client: connect to the IPC socket, send *msg* as JSON.

    Returns the parsed response dict if the server replies,
    otherwise ``None``.
    """
    if not SOCKET_PATH.exists():
        return None

    try:
        client = socket.socket(
            socket.AF_UNIX, socket.SOCK_STREAM
        )
        client.settimeout(2.0)
        client.connect(str(SOCKET_PATH))
        client.sendall(json.dumps(msg).encode())

        # Try to receive a response (may be empty for fire-and-forget)
        try:
            data = client.recv(_BUFFER_SIZE)
            if data:
                return dict(json.loads(data.decode()))
        except (socket.timeout, json.JSONDecodeError):
            pass

        return None
    except OSError as exc:
        _log.debug("IPC: send failed: %s", exc)
        return None
    finally:
        with contextlib.suppress(OSError, UnboundLocalError):
            client.close()
