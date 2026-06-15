"""Linux Wayland platform backend.

Hotkey: xdg-desktop-portal GlobalShortcuts (dbus-next) with evdev fallback.
Clipboard: wl-paste / wl-copy.
Key simulation: ydotool.
Active window: GNOME Shell DBus / KDE KWin / sway IPC.
Notifications: notify-send.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import subprocess
import threading
import time
from typing import Any, Callable

from promptune.daemon.platform.base import (
    ActiveWindowBackend,
    ClipboardBackend,
    HotkeyBackend,
    NotifyBackend,
)

_log = logging.getLogger(__name__)


def _portal_variant(signature: str, value: object) -> object:
    """Wrap *value* in a ``dbus_next.Variant`` for an ``a{sv}`` portal option.

    Imported lazily so the module stays importable where ``dbus_next`` is not
    installed (e.g. macOS development / CI).
    """
    from dbus_next import Variant  # type: ignore[import]

    return Variant(signature, value)


class WaylandHotkey(HotkeyBackend):
    """Wayland hotkey via portal GlobalShortcuts, with evdev fallback."""

    def __init__(self, portal_timeout: float = 5.0) -> None:
        self._stop_event = threading.Event()
        self._callback: Callable[[], None] | None = None
        self._combo = ""
        self._portal_timeout = portal_timeout

    def register(self, combo: str, callback: Callable[[], None]) -> None:
        self._callback = callback
        self._combo = combo

    def check_conflict(self, combo: str) -> bool:
        return False

    def listen(self) -> None:
        try:
            self._listen_portal()
        except Exception:
            _log.info(
                "Portal GlobalShortcuts unavailable or handshake failed, "
                "falling back to evdev",
                exc_info=True,
            )
            try:
                self._listen_evdev()
            except Exception:
                _log.error("Both portal and evdev hotkey failed", exc_info=True)

    def _portal_sender_id(self, bus: object) -> str:
        unique_name = getattr(bus, "unique_name", "")
        if callable(unique_name):
            unique_name = unique_name()
        if not unique_name:
            raise RuntimeError("D-Bus unique name unavailable")
        return str(unique_name).lstrip(":").replace(".", "_")

    def _portal_request_path(self, bus: object, token: str) -> str:
        sender = self._portal_sender_id(bus)
        return f"/org/freedesktop/portal/desktop/request/{sender}/{token}"

    def _portal_session_handle(self, bus: object, token: str) -> str:
        sender = self._portal_sender_id(bus)
        return f"/org/freedesktop/portal/desktop/session/{sender}/{token}"

    def _listen_portal(self) -> None:
        # TODO(linux-ci): Integration test requires a running xdg-desktop-portal
        # with GlobalShortcuts support (GNOME ≥ 42, KDE Plasma ≥ 5.27, or niri).
        # On a real Wayland machine:
        #   1. Ensure DBUS_SESSION_BUS_ADDRESS is set
        #   2. Mock portal signals or use a test portal stub
        #   3. Send a synthetic D-Bus Activated signal and assert callback fires
        # See tests/test_daemon/test_platform/test_linux_wayland_integration.py
        #
        # PORTAL FLOW (org.freedesktop.portal.GlobalShortcuts):
        #   CreateSession(a{sv}) and BindShortcuts(...) do NOT return their
        #   results directly — they return an org.freedesktop.portal.Request
        #   object path, and the actual result (response code 0 == success
        #   plus a{sv} of results) arrives asynchronously via that Request's
        #   ``Response`` signal.  The real *session handle* is derived from the
        #   ``session_handle_token`` we pass in the CreateSession options; the
        #   portal echoes it back in the Response results, which we await here.
        #
        #   The previous implementation treated the CreateSession return value
        #   (a Request handle) as the session handle, which is incorrect and
        #   meant BindShortcuts was always called with the wrong object path.
        #   This is fixed below.  This code path cannot be exercised without a
        #   live portal (no Wayland hardware on macOS CI); it is covered by
        #   mocked unit tests and a real-portal integration test marked
        #   @pytest.mark.linux.
        from dbus_next.aio import MessageBus  # type: ignore[import]

        async def _portal_loop() -> None:
            bus = await MessageBus().connect()
            introspection = await bus.introspect(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
            )
            proxy = bus.get_proxy_object(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                introspection,
            )
            shortcuts = proxy.get_interface(
                "org.freedesktop.portal.GlobalShortcuts"
            )

            # Stable session token: GlobalShortcuts portals persist bindings by
            # session handle, so reusing one token across restarts lets a
            # previously-bound shortcut be reused instead of re-prompting each
            # launch. Per-request handle tokens stay unique (pid-based).
            session_token = "promptune_session"
            create_token = f"promptune_create_{os.getpid()}"
            create_request_path = self._portal_request_path(bus, create_token)
            create_response = self._watch_portal_response(
                bus, create_request_path
            )
            await self._add_portal_match(bus, create_request_path)

            # CreateSession returns a Request handle, not the session handle.
            # The session only becomes valid once the portal confirms it; we
            # subscribe to the Request response before issuing the call so a
            # fast portal response cannot be missed.
            await shortcuts.call_create_session(
                {
                    "handle_token": _portal_variant("s", create_token),
                    "session_handle_token": _portal_variant("s", session_token),
                }
            )
            create_results = await self._await_portal_response(
                create_response, create_request_path
            )
            if create_results is None:
                raise RuntimeError("Portal CreateSession was denied or timed out")
            session_handle = self._portal_response_value(
                create_results.get("session_handle")
            )
            if not isinstance(session_handle, str) or not session_handle:
                session_handle = self._portal_session_handle(bus, session_token)

            bind_token = f"promptune_bind_{os.getpid()}"
            bind_request_path = self._portal_request_path(bus, bind_token)
            bind_response = self._watch_portal_response(bus, bind_request_path)
            await self._add_portal_match(bus, bind_request_path)
            await shortcuts.call_bind_shortcuts(
                session_handle,
                [
                    (
                        "promptune-enhance",
                        {
                            "description": _portal_variant("s", "Enhance prompt"),
                        },
                    )
                ],
                "",
                {"handle_token": _portal_variant("s", bind_token)},
            )
            bind_results = await self._await_portal_response(
                bind_response, bind_request_path
            )
            if bind_results is None:
                raise RuntimeError("Portal BindShortcuts was denied or timed out")
            if not self._portal_shortcut_bound(bind_results):
                raise RuntimeError("Portal promptune-enhance was not bound")

            def on_activated(
                session: str, shortcut_id: str, timestamp: int, options: dict
            ) -> None:
                if self._callback:
                    self._callback()

            shortcuts.on_activated(on_activated)

            while not self._stop_event.is_set():
                await asyncio.sleep(0.1)

            bus.disconnect()

        asyncio.run(_portal_loop())

    def _portal_response_value(self, value: object) -> object:
        return getattr(value, "value", value)

    def _portal_shortcut_bound(self, results: dict[str, Any]) -> bool:
        shortcuts = self._portal_response_value(results.get("shortcuts"))
        if not isinstance(shortcuts, list):
            return False
        for shortcut in shortcuts:
            item = self._portal_response_value(shortcut)
            if not isinstance(item, (tuple, list)) or not item:
                continue
            shortcut_id = self._portal_response_value(item[0])
            if shortcut_id == "promptune-enhance":
                return True
        return False

    async def _add_portal_match(self, bus: object, request_path: str) -> None:
        from dbus_next import Message  # type: ignore[import]
        from dbus_next.constants import MessageType  # type: ignore[import]

        rule = (
            "type='signal',"
            "sender='org.freedesktop.portal.Desktop',"
            "interface='org.freedesktop.portal.Request',"
            "member='Response',"
            f"path='{request_path}'"
        )
        reply = await bus.call(  # type: ignore[attr-defined]
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                member="AddMatch",
                signature="s",
                body=[rule],
            )
        )
        if getattr(reply, "message_type", None) != MessageType.METHOD_RETURN:
            raise RuntimeError("Failed to add portal response match rule")

    def _watch_portal_response(
        self, bus: object, request_path: str
    ) -> asyncio.Future[dict[str, Any] | None]:
        from dbus_next.constants import MessageType  # type: ignore[import]

        loop = asyncio.get_event_loop()
        done: asyncio.Future[dict[str, Any] | None] = loop.create_future()

        def on_message(message: object) -> None:
            if done.done():
                return
            if getattr(message, "message_type", None) != MessageType.SIGNAL:
                return
            if getattr(message, "path", None) != request_path:
                return
            if (
                getattr(message, "interface", None)
                != "org.freedesktop.portal.Request"
            ):
                return
            if getattr(message, "member", None) != "Response":
                return
            body = getattr(message, "body", [])
            if len(body) < 2:
                done.set_result(None)
                return
            response, results = body[0], body[1]
            done.set_result(results if response == 0 else None)

        bus.add_message_handler(on_message)  # type: ignore[attr-defined]

        def cleanup(_future: asyncio.Future[dict[str, Any] | None]) -> None:
            with contextlib.suppress(Exception):
                bus.remove_message_handler(on_message)  # type: ignore[attr-defined]

        done.add_done_callback(cleanup)
        return done

    async def _await_portal_response(
        self,
        response: asyncio.Future[dict[str, Any] | None],
        request_path: str,
    ) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(response, timeout=self._portal_timeout)
        except asyncio.TimeoutError:
            _log.warning("Portal request %s timed out", request_path)
            return None

    def _listen_evdev(self) -> None:
        # TODO(linux-ci): Integration test requires the 'input' group membership
        # and physical keyboard devices under /dev/input/. On a real Linux machine:
        #   1. Add CI user to 'input' group: sudo usermod -aG input $USER
        #   2. Use uinput to create a virtual keyboard (requires uinput module)
        #   3. Inject a key event and assert the callback fires
        # Note: evdev is the fallback when portal GlobalShortcuts is unavailable
        # (e.g., on sway/i3 without a portal implementation).
        # See tests/test_daemon/test_platform/test_linux_wayland_integration.py
        from evdev import (  # type: ignore[import]
            InputDevice,
            categorize,
            ecodes,
            list_devices,
        )

        _log.warning("Using evdev hotkey listener — requires 'input' group membership")
        devices = [InputDevice(path) for path in list_devices()]
        keyboards = [d for d in devices if ecodes.EV_KEY in d.capabilities()]

        if not keyboards:
            raise RuntimeError("No keyboard input devices found")

        main_key, mod_groups = self._parse_evdev_combo(ecodes)

        pressed: set[int] = set()
        import select

        while not self._stop_event.is_set():
            readable, _, _ = select.select(keyboards, [], [], 0.1)
            for dev in readable:
                for event in dev.read():
                    if event.type != ecodes.EV_KEY:
                        continue
                    key_event = categorize(event)
                    if key_event.keystate == key_event.key_down:
                        pressed.add(key_event.scancode)
                    elif key_event.keystate == key_event.key_up:
                        pressed.discard(key_event.scancode)
                    if (
                        main_key in pressed
                        and all(
                            group & pressed for group in mod_groups
                        )
                        and self._callback
                    ):
                        self._callback()
                        pressed.clear()

    def _parse_evdev_combo(
        self, ecodes: object
    ) -> tuple[int, list[set[int]]]:
        """Parse ``self._combo`` into (main_key, list-of-modifier-groups).

        Each modifier maps to a *group* of acceptable scancodes (left and
        right variants) so e.g. right-ctrl satisfies a ``ctrl`` requirement.
        Raises ValueError if the non-modifier key cannot be mapped.
        """
        modifier_groups = {
            "ctrl": ("KEY_LEFTCTRL", "KEY_RIGHTCTRL"),
            "shift": ("KEY_LEFTSHIFT", "KEY_RIGHTSHIFT"),
            "alt": ("KEY_LEFTALT", "KEY_RIGHTALT"),
            "super": ("KEY_LEFTMETA", "KEY_RIGHTMETA"),
        }
        mod_groups: list[set[int]] = []
        main_key: int | None = None
        for part in (p.strip().lower() for p in self._combo.split("+")):
            if not part:
                continue
            if part in modifier_groups:
                group = {
                    getattr(ecodes, attr)
                    for attr in modifier_groups[part]
                    if getattr(ecodes, attr, None) is not None
                }
                mod_groups.append(group)
            else:
                main_key = getattr(ecodes, f"KEY_{part.upper()}", None)

        if main_key is None:
            raise ValueError(f"Cannot map key from combo: {self._combo}")
        return main_key, mod_groups

    def stop(self) -> None:
        self._stop_event.set()


class WaylandClipboard(ClipboardBackend):
    """Wayland clipboard via wl-paste / wl-copy + ydotool.

    Linux input-event-codes used for ``ydotool key`` (``<keycode>:<state>``):
      29 = KEY_LEFTCTRL, 46 = KEY_C, 47 = KEY_V
    (state 1 == press, 0 == release).
    """

    # Linux input-event-codes (linux/input-event-codes.h)
    _KEY_LEFTCTRL = 29
    _KEY_C = 46
    _KEY_V = 47

    def __init__(self, settle_ms: int = 100) -> None:
        self._settle_ms = settle_ms

    def read(self) -> str | None:
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.replace("\x00", "")
        except Exception:
            return None

    def write(self, text: str) -> None:
        try:
            subprocess.run(
                ["wl-copy"],
                input=text,
                text=True,
                check=True,
            )
        except FileNotFoundError as exc:
            _log.error("wl-copy not found — install wl-clipboard")
            raise RuntimeError(
                "wl-copy not found; install the 'wl-clipboard' package"
            ) from exc
        except subprocess.CalledProcessError as exc:
            _log.error("wl-copy failed (exit %s)", exc.returncode)
            raise RuntimeError("wl-copy failed to write clipboard") from exc

    def copy_selection(self) -> str | None:
        try:
            subprocess.run(
                [
                    "ydotool", "key",
                    f"{self._KEY_LEFTCTRL}:1",
                    f"{self._KEY_C}:1",
                    f"{self._KEY_C}:0",
                    f"{self._KEY_LEFTCTRL}:0",
                ],
                check=True,
            )
        except FileNotFoundError as exc:
            _log.error(
                "ydotool not found — cannot simulate copy; "
                "install ydotool and run ydotoold"
            )
            raise RuntimeError(
                "ydotool not found; install ydotool and run ydotoold "
                "to read the selection"
            ) from exc
        except subprocess.CalledProcessError as exc:
            _log.error("ydotool copy failed (exit %s)", exc.returncode)
            raise RuntimeError(
                f"ydotool copy failed (exit {exc.returncode}); "
                "is ydotoold running?"
            ) from exc
        time.sleep(self._settle_ms / 1000.0)
        return self.read()

    def paste_result(self, text: str) -> bool:
        # write() raises with a clear message if wl-copy is missing/fails, so
        # the enhanced text is never silently dropped.
        self.write(text)
        time.sleep(self._settle_ms / 1000.0)
        try:
            subprocess.run(
                [
                    "ydotool", "key",
                    f"{self._KEY_LEFTCTRL}:1",
                    f"{self._KEY_V}:1",
                    f"{self._KEY_V}:0",
                    f"{self._KEY_LEFTCTRL}:0",
                ],
                check=True,
            )
        except FileNotFoundError:
            # Text is already on the clipboard (write() succeeded); the user
            # can paste manually, so degrade rather than raise/lose data.
            _log.warning(
                "ydotool not found — enhanced text left on clipboard; "
                "paste manually"
            )
            return False
        except subprocess.CalledProcessError as exc:
            _log.warning(
                "ydotool paste failed (exit %s) — text left on clipboard",
                exc.returncode,
            )
            return False
        return True


class WaylandNotify(NotifyBackend):
    """Linux notifications via notify-send."""

    def send(self, title: str, body: str, sound: bool = True) -> None:
        if len(body) > 100:
            body = body[:100] + "..."
        try:
            subprocess.run(
                ["notify-send", title, body],
                check=False,
                timeout=5,
            )
        except FileNotFoundError:
            _log.debug("notify-send not found, skipping notification")
        except Exception:
            _log.debug("notify-send failed", exc_info=True)


class WaylandActiveWindow(ActiveWindowBackend):
    """Wayland active window via DE-specific methods."""

    def __init__(self, desktop: str = "") -> None:
        self._desktop = desktop or os.environ.get("XDG_CURRENT_DESKTOP", "")

    def get_frontmost_app(self) -> str:
        try:
            lower = self._desktop.lower()
            if "gnome" in lower or "pop" in lower or "ubuntu" in lower:
                return self._gnome_active_window()
            elif "kde" in lower or "plasma" in lower:
                return self._kde_active_window()
            elif "sway" in lower:
                return self._sway_active_window()
            return ""
        except Exception:
            return ""

    def _gnome_active_window(self) -> str:
        # NOTE: GNOME 41+ disables Shell.Eval unless "unsafe mode" is enabled
        # via Looking Glass, so on modern GNOME this gdbus call returns
        # (false, '') (or errors). Both cases degrade cleanly to "" below and
        # via get_frontmost_app()'s try/except — active-window detection is
        # simply unavailable on locked-down GNOME, which is acceptable (it is
        # only an optional same-app paste check).
        result = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", "org.gnome.Shell",
                "--object-path", "/org/gnome/Shell",
                "--method", "org.gnome.Shell.Eval",
                "global.display.focus_window"
                " ? global.display.focus_window.get_wm_class()"
                " : ''",
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        # Try plain JSON first (test format: {"success": true, "value": "firefox"})
        try:
            data = json.loads(result.stdout)
            if isinstance(data, dict):
                val = data.get("value", "")
                return str(val).strip('"') if val else ""
        except (json.JSONDecodeError, ValueError):
            pass
        # Fall back to gdbus tuple format: (true, 'value')
        try:
            normalized = (
                result.stdout
                .replace("(", "[")
                .replace(")", "]")
                .replace("'", '"')
            )
            data = json.loads(normalized)
            if data[0] and data[1]:
                return str(data[1]).strip('"')
        except (json.JSONDecodeError, IndexError, TypeError):
            pass
        return ""

    def _kde_active_window(self) -> str:
        result = subprocess.run(
            ["qdbus", "org.kde.KWin", "/KWin", "org.kde.KWin.activeWindow"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        return result.stdout.strip()

    def _sway_active_window(self) -> str:
        result = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True,
            text=True,
            check=True,
            timeout=2,
        )
        tree = json.loads(result.stdout)
        return self._find_focused(tree)

    def _find_focused(self, node: dict) -> str:
        if node.get("focused"):
            return str(node.get("app_id", "") or node.get("name", ""))
        children = (node.get("nodes") or []) + (node.get("floating_nodes") or [])
        for child in children:
            result = self._find_focused(child)
            if result:
                return result
        return ""
