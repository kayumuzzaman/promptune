"""Tests for Linux Wayland platform backend.

All tests in this file run on macOS via mocked subprocess / dbus-next / evdev
calls. The real portal, evdev, ydotool and wl-clipboard code paths cannot run
without Wayland hardware, so they are exercised here with mocks injected via
``sys.modules`` and ``unittest.mock``.

TODO(linux-ci): On a real Linux Wayland machine, add an integration test module
  tests/test_daemon/test_platform/test_linux_wayland_integration.py that:
  - Requires: dbus-next, evdev, wl-clipboard, ydotool, notify-send installed
  - Mark each test with @pytest.mark.linux
  - Run with:
    pytest -m linux tests/test_daemon/test_platform/test_linux_wayland_integration.py
  See docs/MANUAL_TESTING.md §28.3 for the full manual checklist.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import types
from collections.abc import Callable
from unittest.mock import MagicMock, call, patch

import pytest

from promptune.daemon.platform.base import (
    ActiveWindowBackend,
    ClipboardBackend,
    HotkeyBackend,
    NotifyBackend,
)
from promptune.daemon.platform.linux_wayland import (
    WaylandActiveWindow,
    WaylandClipboard,
    WaylandHotkey,
    WaylandNotify,
)

# ---------------------------------------------------------------------------
# Fake module helpers (dbus_next / evdev are not installed on macOS)
# ---------------------------------------------------------------------------


class _FakeVariant:
    """Stand-in for dbus_next.Variant so option construction works in tests."""

    def __init__(self, signature: str, value: object) -> None:
        self.signature = signature
        self.value = value

    def __eq__(self, other: object) -> bool:  # pragma: no cover - convenience
        return (
            isinstance(other, _FakeVariant)
            and self.signature == other.signature
            and self.value == other.value
        )


class _FakeMessageType:
    SIGNAL = "signal"
    METHOD_RETURN = "method_return"


class _FakeMessage:
    def __init__(self, **kwargs: object) -> None:
        self.__dict__.update(kwargs)


def _install_fake_dbus(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject minimal fake ``dbus_next`` + ``dbus_next.aio`` modules."""
    dbus_mod = types.ModuleType("dbus_next")
    dbus_mod.Message = _FakeMessage  # type: ignore[attr-defined]
    dbus_mod.Variant = _FakeVariant  # type: ignore[attr-defined]
    aio_mod = types.ModuleType("dbus_next.aio")
    aio_mod.MessageBus = MagicMock(name="MessageBus")  # type: ignore[attr-defined]
    constants_mod = types.ModuleType("dbus_next.constants")
    constants_mod.MessageType = _FakeMessageType  # type: ignore[attr-defined]
    dbus_mod.aio = aio_mod  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "dbus_next", dbus_mod)
    monkeypatch.setitem(sys.modules, "dbus_next.aio", aio_mod)
    monkeypatch.setitem(sys.modules, "dbus_next.constants", constants_mod)
    return aio_mod


async def _method_return_response() -> object:
    return types.SimpleNamespace(message_type=_FakeMessageType.METHOD_RETURN)


# ---------------------------------------------------------------------------
# WaylandHotkey
# ---------------------------------------------------------------------------


class TestWaylandHotkey:
    def test_implements_interface(self) -> None:
        assert issubclass(WaylandHotkey, HotkeyBackend)

    def test_stop_sets_event(self) -> None:
        hk = WaylandHotkey()
        hk.stop()
        assert hk._stop_event.is_set()

    def test_check_conflict_returns_false(self) -> None:
        hk = WaylandHotkey()
        assert hk.check_conflict("ctrl+shift+e") is False

    def test_register_stores_combo_and_callback(self) -> None:
        hk = WaylandHotkey()
        cb = MagicMock()
        hk.register("ctrl+shift+e", cb)
        assert hk._combo == "ctrl+shift+e"
        assert hk._callback is cb

    def test_portal_session_handle_path(self) -> None:
        hk = WaylandHotkey()
        bus = types.SimpleNamespace(unique_name=":1.42")
        path = hk._portal_session_handle(bus, "promptune_123")
        assert path == (
            "/org/freedesktop/portal/desktop/session/1_42/promptune_123"
        )

    def test_portal_variant_wraps_value(self, monkeypatch) -> None:
        _install_fake_dbus(monkeypatch)
        from promptune.daemon.platform import linux_wayland

        v = linux_wayland._portal_variant("s", "hello")
        assert isinstance(v, _FakeVariant)
        assert v.signature == "s"
        assert v.value == "hello"

    # -- listen() fallback ordering --------------------------------------

    def test_listen_uses_portal_first(self) -> None:
        hk = WaylandHotkey()
        with (
            patch.object(hk, "_listen_portal") as portal,
            patch.object(hk, "_listen_evdev") as evdev,
        ):
            hk.listen()
            portal.assert_called_once()
            evdev.assert_not_called()

    def test_listen_falls_back_to_evdev_on_portal_failure(self) -> None:
        hk = WaylandHotkey()
        with (
            patch.object(hk, "_listen_portal", side_effect=RuntimeError("no portal")),
            patch.object(hk, "_listen_evdev") as evdev,
        ):
            hk.listen()
            evdev.assert_called_once()

    def test_listen_logs_when_both_backends_fail(self, caplog) -> None:
        hk = WaylandHotkey()
        with (
            patch.object(hk, "_listen_portal", side_effect=RuntimeError("p")),
            patch.object(hk, "_listen_evdev", side_effect=RuntimeError("e")),
            caplog.at_level("ERROR"),
        ):
            hk.listen()  # must not raise
        assert any("Both portal and evdev" in r.message for r in caplog.records)

    # -- portal loop (mocked dbus_next) ----------------------------------

    def test_listen_portal_success_path(self, monkeypatch) -> None:
        aio_mod = _install_fake_dbus(monkeypatch)

        shortcuts = MagicMock(name="shortcuts")
        events: list[str] = []
        expected_session_handle = ""

        async def _create_session(options):
            events.append("create")
            assert "session_handle_token" in options
            assert "handle_token" in options
            # Session token must be stable across restarts (no pid) so a
            # previously bound portal shortcut can be reused.
            assert options["session_handle_token"].value == "promptune_session"
            nonlocal expected_session_handle
            expected_session_handle = hk._portal_session_handle(
                bus, options["session_handle_token"].value
            )
            return "/req/create"

        async def _bind(session_handle, shortcuts_arg, parent, options):
            events.append("bind")
            assert session_handle == expected_session_handle
            return "/req/bind"

        shortcuts.call_create_session = _create_session
        shortcuts.call_bind_shortcuts = _bind

        proxy = MagicMock(name="proxy")
        proxy.get_interface.return_value = shortcuts

        bus = MagicMock(name="bus")
        bus.unique_name = ":1.42"

        async def _connect():
            return bus

        async def _introspect(*args, **kwargs):
            return MagicMock(name="introspection")

        bus.connect = MagicMock(side_effect=lambda: _connect())
        bus.introspect = MagicMock(side_effect=_introspect)
        bus.get_proxy_object.return_value = proxy
        bus.call = MagicMock(
            side_effect=lambda message: _method_return_response()
        )

        # MessageBus() -> object whose connect() is awaitable
        msgbus_instance = MagicMock()
        msgbus_instance.connect = MagicMock(side_effect=lambda: _connect())
        aio_mod.MessageBus.return_value = msgbus_instance

        user_cb = MagicMock()
        hk = WaylandHotkey()
        hk.register("ctrl+shift+e", user_cb)
        # Pre-set stop so the while-loop exits immediately after setup.
        hk.stop()

        async def _ok(*args, **kwargs):
            request_path = str(args[-1])
            events.append(f"await:{request_path}")
            if "/promptune_create_" in request_path:
                return {"session_handle": expected_session_handle}
            return {"shortcuts": [("promptune-enhance", {})]}

        original_watch = hk._watch_portal_response

        def _watch(bus_arg, request_path):
            events.append(f"watch:{request_path}")
            return original_watch(bus_arg, request_path)

        with (
            patch.object(hk, "_watch_portal_response", side_effect=_watch),
            patch.object(hk, "_await_portal_response", side_effect=_ok),
        ):
            hk._listen_portal()

        create_wait = next(
            e
            for e in events
            if e.startswith(
                "watch:/org/freedesktop/portal/desktop/request/1_42/"
                "promptune_create_"
            )
        )
        bind_wait = next(
            e
            for e in events
            if e.startswith(
                "watch:/org/freedesktop/portal/desktop/request/1_42/"
                "promptune_bind_"
            )
        )
        assert events.index(create_wait) < events.index("create")
        assert events.index(bind_wait) < events.index("bind")

        # Activated handler was registered and bus disconnected cleanly.
        shortcuts.on_activated.assert_called_once()
        bus.disconnect.assert_called_once()

        # Drive the registered Activated handler -> user callback fires.
        on_activated = shortcuts.on_activated.call_args[0][0]
        on_activated("/session", "promptune-enhance", 123, {})
        user_cb.assert_called_once()

    def test_listen_portal_raises_when_create_session_denied(
        self, monkeypatch
    ) -> None:
        aio_mod = _install_fake_dbus(monkeypatch)

        shortcuts = MagicMock(name="shortcuts")

        async def _create_session(options):
            return "/req/create"

        shortcuts.call_create_session = _create_session

        proxy = MagicMock(name="proxy")
        proxy.get_interface.return_value = shortcuts

        bus = MagicMock(name="bus")

        async def _connect():
            return bus

        async def _introspect(*args, **kwargs):
            return MagicMock()

        bus.introspect = MagicMock(side_effect=_introspect)
        bus.get_proxy_object.return_value = proxy
        bus.unique_name = ":1.42"
        bus.call = MagicMock(
            side_effect=lambda message: _method_return_response()
        )

        msgbus_instance = MagicMock()
        msgbus_instance.connect = MagicMock(side_effect=lambda: _connect())
        aio_mod.MessageBus.return_value = msgbus_instance

        hk = WaylandHotkey()
        hk.register("ctrl+shift+e", MagicMock())

        async def _denied(*args, **kwargs):
            return None

        with (
            patch.object(hk, "_await_portal_response", side_effect=_denied),
            pytest.raises(RuntimeError, match="denied or timed out"),
        ):
            hk._listen_portal()

    def test_listen_portal_raises_when_bind_denied(
        self, monkeypatch
    ) -> None:
        aio_mod = _install_fake_dbus(monkeypatch)

        shortcuts = MagicMock(name="shortcuts")
        session_handle = (
            "/org/freedesktop/portal/desktop/session/1_42/promptune_session"
        )

        async def _create_session(options):
            return "/req/create"

        async def _bind(session_handle_arg, shortcuts_arg, parent, options):
            assert session_handle_arg == session_handle
            return "/req/bind"

        shortcuts.call_create_session = _create_session
        shortcuts.call_bind_shortcuts = _bind

        proxy = MagicMock(name="proxy")
        proxy.get_interface.return_value = shortcuts

        bus = MagicMock(name="bus")
        bus.unique_name = ":1.42"

        async def _connect():
            return bus

        async def _introspect(*args, **kwargs):
            return MagicMock()

        bus.introspect = MagicMock(side_effect=_introspect)
        bus.get_proxy_object.return_value = proxy
        bus.call = MagicMock(
            side_effect=lambda message: _method_return_response()
        )

        msgbus_instance = MagicMock()
        msgbus_instance.connect = MagicMock(side_effect=lambda: _connect())
        aio_mod.MessageBus.return_value = msgbus_instance

        hk = WaylandHotkey()
        hk.register("ctrl+shift+e", MagicMock())
        hk.stop()

        async def _response(*args, **kwargs):
            request_path = str(args[-1])
            if "/promptune_create_" in request_path:
                return {"session_handle": session_handle}
            return None

        with (
            patch.object(hk, "_await_portal_response", side_effect=_response),
            pytest.raises(RuntimeError, match="BindShortcuts was denied"),
        ):
            hk._listen_portal()

    @pytest.mark.parametrize(
        "bound_shortcuts",
        [[], [("other-shortcut", {})]],
    )
    def test_listen_portal_raises_when_promptune_shortcut_unbound(
        self, monkeypatch, bound_shortcuts
    ) -> None:
        aio_mod = _install_fake_dbus(monkeypatch)

        shortcuts = MagicMock(name="shortcuts")
        session_handle = (
            "/org/freedesktop/portal/desktop/session/1_42/promptune_session"
        )

        async def _create_session(options):
            return "/req/create"

        async def _bind(session_handle_arg, shortcuts_arg, parent, options):
            assert session_handle_arg == session_handle
            return "/req/bind"

        shortcuts.call_create_session = _create_session
        shortcuts.call_bind_shortcuts = _bind

        proxy = MagicMock(name="proxy")
        proxy.get_interface.return_value = shortcuts

        bus = MagicMock(name="bus")
        bus.unique_name = ":1.42"

        async def _connect():
            return bus

        async def _introspect(*args, **kwargs):
            return MagicMock()

        bus.introspect = MagicMock(side_effect=_introspect)
        bus.get_proxy_object.return_value = proxy
        bus.call = MagicMock(
            side_effect=lambda message: _method_return_response()
        )

        msgbus_instance = MagicMock()
        msgbus_instance.connect = MagicMock(side_effect=lambda: _connect())
        aio_mod.MessageBus.return_value = msgbus_instance

        hk = WaylandHotkey()
        hk.register("ctrl+shift+e", MagicMock())
        hk.stop()

        async def _response(*args, **kwargs):
            request_path = str(args[-1])
            if "/promptune_create_" in request_path:
                return {"session_handle": session_handle}
            return {"shortcuts": bound_shortcuts}

        with (
            patch.object(hk, "_await_portal_response", side_effect=_response),
            pytest.raises(RuntimeError, match="promptune-enhance was not bound"),
        ):
            hk._listen_portal()

    def test_add_portal_match_subscribes_request_response(
        self, monkeypatch
    ) -> None:
        _install_fake_dbus(monkeypatch)
        hk = WaylandHotkey()
        bus = MagicMock()

        async def _call(message):
            return types.SimpleNamespace(
                message_type=_FakeMessageType.METHOD_RETURN
            )

        bus.call = MagicMock(side_effect=_call)

        asyncio.run(hk._add_portal_match(bus, "/req/x"))

        message = bus.call.call_args.args[0]
        assert message.destination == "org.freedesktop.DBus"
        assert message.path == "/org/freedesktop/DBus"
        assert message.member == "AddMatch"
        assert message.signature == "s"
        rule = message.body[0]
        assert "type='signal'" in rule
        assert "interface='org.freedesktop.portal.Request'" in rule
        assert "member='Response'" in rule
        assert "path='/req/x'" in rule

    def test_await_portal_response_fires_on_success(self, monkeypatch) -> None:
        _install_fake_dbus(monkeypatch)
        hk = WaylandHotkey()
        bus = MagicMock()
        handlers: list[Callable[[object], None]] = []
        bus.add_message_handler = lambda handler: handlers.append(handler)

        async def _run() -> dict[str, object] | None:
            response = hk._watch_portal_response(bus, "/req/x")
            handlers[0](
                types.SimpleNamespace(
                    message_type=_FakeMessageType.SIGNAL,
                    path="/req/x",
                    interface="org.freedesktop.portal.Request",
                    member="Response",
                    body=[0, {"session_handle": "/session/x"}],
                )
            )
            return await hk._await_portal_response(response, "/req/x")

        assert asyncio.run(_run()) == {"session_handle": "/session/x"}

    def test_await_portal_response_timeout_returns_false(self, monkeypatch) -> None:
        _install_fake_dbus(monkeypatch)
        hk = WaylandHotkey(portal_timeout=0.01)
        bus = MagicMock()
        bus.add_message_handler = MagicMock()

        async def _run() -> dict[str, object] | None:
            response = hk._watch_portal_response(bus, "/req/x")
            return await hk._await_portal_response(response, "/req/x")

        assert asyncio.run(_run()) is None

    def test_await_portal_response_nonzero_code_returns_false(
        self, monkeypatch
    ) -> None:
        _install_fake_dbus(monkeypatch)
        hk = WaylandHotkey()
        bus = MagicMock()
        handlers: list[Callable[[object], None]] = []
        bus.add_message_handler = lambda handler: handlers.append(handler)

        async def _run() -> dict[str, object] | None:
            response = hk._watch_portal_response(bus, "/req/x")
            handlers[0](
                types.SimpleNamespace(
                    message_type=_FakeMessageType.SIGNAL,
                    path="/req/x",
                    interface="org.freedesktop.portal.Request",
                    member="Response",
                    body=[1, {}],
                )
            )
            return await hk._await_portal_response(response, "/req/x")

        assert asyncio.run(_run()) is None

    # -- evdev combo parsing ---------------------------------------------

    def _fake_ecodes(self) -> object:
        ec = types.SimpleNamespace()
        ec.EV_KEY = 1
        ec.KEY_LEFTCTRL = 29
        ec.KEY_RIGHTCTRL = 97
        ec.KEY_LEFTSHIFT = 42
        ec.KEY_RIGHTSHIFT = 54
        ec.KEY_LEFTALT = 56
        ec.KEY_RIGHTALT = 100
        ec.KEY_LEFTMETA = 125
        ec.KEY_RIGHTMETA = 126
        ec.KEY_E = 18
        return ec

    def test_parse_evdev_combo_basic(self) -> None:
        hk = WaylandHotkey()
        hk.register("ctrl+shift+e", MagicMock())
        main_key, mod_groups = hk._parse_evdev_combo(self._fake_ecodes())
        assert main_key == 18  # KEY_E
        # ctrl group contains both left and right variants
        assert {29, 97} in mod_groups
        assert {42, 54} in mod_groups

    def test_parse_evdev_combo_super_and_alt(self) -> None:
        hk = WaylandHotkey()
        hk.register("super+alt+e", MagicMock())
        main_key, mod_groups = hk._parse_evdev_combo(self._fake_ecodes())
        assert main_key == 18
        assert {125, 126} in mod_groups
        assert {56, 100} in mod_groups

    def test_parse_evdev_combo_no_modifiers(self) -> None:
        hk = WaylandHotkey()
        hk.register("e", MagicMock())
        main_key, mod_groups = hk._parse_evdev_combo(self._fake_ecodes())
        assert main_key == 18
        assert mod_groups == []

    def test_parse_evdev_combo_unmappable_key_raises(self) -> None:
        hk = WaylandHotkey()
        hk.register("ctrl+shift+nonsense", MagicMock())
        with pytest.raises(ValueError, match="Cannot map key"):
            hk._parse_evdev_combo(self._fake_ecodes())

    def test_parse_evdev_combo_ignores_empty_parts(self) -> None:
        hk = WaylandHotkey()
        hk.register("ctrl++e", MagicMock())
        main_key, mod_groups = hk._parse_evdev_combo(self._fake_ecodes())
        assert main_key == 18
        assert {29, 97} in mod_groups

    # -- evdev listen loop (mocked evdev module) -------------------------

    def _install_fake_evdev(
        self, monkeypatch: pytest.MonkeyPatch, *, keyboards
    ) -> None:
        ec = self._fake_ecodes()

        def _categorize(event):
            return event

        evdev_mod = types.ModuleType("evdev")
        evdev_mod.InputDevice = lambda path: path  # type: ignore[attr-defined]
        evdev_mod.categorize = _categorize  # type: ignore[attr-defined]
        evdev_mod.ecodes = ec  # type: ignore[attr-defined]
        evdev_mod.list_devices = lambda: keyboards  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "evdev", evdev_mod)

    def test_listen_evdev_no_keyboards_raises(self, monkeypatch) -> None:
        self._install_fake_evdev(monkeypatch, keyboards=[])
        hk = WaylandHotkey()
        hk.register("ctrl+shift+e", MagicMock())
        with pytest.raises(RuntimeError, match="No keyboard"):
            hk._listen_evdev()

    def test_listen_evdev_fires_callback_on_combo(self, monkeypatch) -> None:
        ec = self._fake_ecodes()

        class _Ev:
            key_down = 1
            key_up = 0

            def __init__(self, scancode, keystate, etype=ec.EV_KEY) -> None:
                self.scancode = scancode
                self.keystate = keystate
                self.type = etype

        class _Dev:
            def __init__(self, events) -> None:
                self._events = events

            def capabilities(self):
                return {ec.EV_KEY: []}

            def read(self):
                return list(self._events)

        cb = MagicMock()
        hk = WaylandHotkey()
        hk.register("ctrl+e", cb)

        # press ctrl down, then e down -> should fire once
        events = [
            _Ev(ec.KEY_LEFTCTRL, _Ev.key_down),
            _Ev(ec.KEY_E, _Ev.key_down),
            # an unrelated event after fire (pressed was cleared)
            _Ev(ec.KEY_E, _Ev.key_up),
        ]
        dev = _Dev(events)

        keyboard_objs = [dev]

        ec_mod = types.SimpleNamespace(**vars(ec))
        evdev_mod = types.ModuleType("evdev")
        evdev_mod.InputDevice = lambda path: path  # type: ignore[attr-defined]
        evdev_mod.categorize = lambda e: e  # type: ignore[attr-defined]
        evdev_mod.ecodes = ec_mod  # type: ignore[attr-defined]
        evdev_mod.list_devices = lambda: keyboard_objs  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "evdev", evdev_mod)

        # select.select returns our device as readable on first poll, then we
        # stop the loop so it exits.
        call_count = {"n": 0}

        def _fake_select(rlist, wlist, xlist, timeout):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return (rlist, [], [])
            hk.stop()
            return ([], [], [])

        fake_select_mod = types.ModuleType("select")
        fake_select_mod.select = _fake_select  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "select", fake_select_mod)

        hk._listen_evdev()
        cb.assert_called_once()

    def test_listen_evdev_ignores_non_key_events(self, monkeypatch) -> None:
        ec = self._fake_ecodes()

        class _Ev:
            key_down = 1
            key_up = 0

            def __init__(self, scancode, keystate, etype) -> None:
                self.scancode = scancode
                self.keystate = keystate
                self.type = etype

        class _Dev:
            def capabilities(self):
                return {ec.EV_KEY: []}

            def read(self):
                # type 2 == EV_REL (not EV_KEY) -> ignored
                return [_Ev(ec.KEY_E, _Ev.key_down, 2)]

        cb = MagicMock()
        hk = WaylandHotkey()
        hk.register("e", cb)

        evdev_mod = types.ModuleType("evdev")
        evdev_mod.InputDevice = lambda path: path  # type: ignore[attr-defined]
        evdev_mod.categorize = lambda e: e  # type: ignore[attr-defined]
        evdev_mod.ecodes = types.SimpleNamespace(**vars(ec))  # type: ignore[attr-defined]
        evdev_mod.list_devices = lambda: [_Dev()]  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "evdev", evdev_mod)

        n = {"x": 0}

        def _fake_select(rlist, wlist, xlist, timeout):
            n["x"] += 1
            if n["x"] == 1:
                return (rlist, [], [])
            hk.stop()
            return ([], [], [])

        fake_select_mod = types.ModuleType("select")
        fake_select_mod.select = _fake_select  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "select", fake_select_mod)

        hk._listen_evdev()
        cb.assert_not_called()


# ---------------------------------------------------------------------------
# WaylandClipboard
# ---------------------------------------------------------------------------


class TestWaylandClipboard:
    def test_implements_interface(self) -> None:
        assert issubclass(WaylandClipboard, ClipboardBackend)

    def test_read_calls_wl_paste(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="clipboard text", returncode=0
            )
            result = cb.read()
            assert result == "clipboard text"
            mock_run.assert_called_once_with(
                ["wl-paste", "--no-newline"],
                capture_output=True,
                text=True,
                check=True,
            )

    def test_read_returns_none_on_error(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "wl-paste")
        with patch("subprocess.run", side_effect=err):
            result = cb.read()
            assert result is None

    def test_read_returns_none_when_binary_missing(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert cb.read() is None

    def test_write_pipes_to_wl_copy(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            cb.write("hello")
            mock_run.assert_called_once_with(
                ["wl-copy"],
                input="hello",
                text=True,
                check=True,
            )

    def test_write_raises_clear_error_when_binary_missing(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch("subprocess.run", side_effect=FileNotFoundError),
            pytest.raises(RuntimeError, match="wl-clipboard"),
        ):
            cb.write("hello")

    def test_write_raises_clear_error_on_called_process_error(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "wl-copy")
        with (
            patch("subprocess.run", side_effect=err),
            pytest.raises(RuntimeError, match="wl-copy failed"),
        ):
            cb.write("hello")

    def test_copy_selection_uses_ydotool(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch("subprocess.run") as mock_run,
            patch.object(cb, "_read", side_effect=["prev", "selected"]),
            patch.object(cb, "write"),
        ):
            result = cb.copy_selection()
            assert any(
                c.args[0] == ["ydotool", "key", "29:1", "46:1", "46:0", "29:0"]
                for c in mock_run.call_args_list
            )
            assert result == "selected"

    def test_copy_selection_clears_clipboard_before_copy(self) -> None:
        """The clipboard is cleared first so 'nothing copied' is detectable."""
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch("subprocess.run"),
            patch.object(cb, "_read", side_effect=["prev", "selected"]),
            patch.object(cb, "write") as mock_write,
        ):
            cb.copy_selection()
            mock_write.assert_any_call("")

    def test_copy_selection_accepts_selection_equal_to_clipboard(self) -> None:
        """A real selection identical to the prior clipboard is still valid."""
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch("subprocess.run"),
            patch.object(cb, "_read", side_effect=["foo", "foo"]),
            patch.object(cb, "write"),
        ):
            assert cb.copy_selection() == "foo"

    def test_copy_selection_empty_returns_none_and_restores(self) -> None:
        """Clipboard unchanged after copy -> None, and previous is restored."""
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch("subprocess.run"),
            patch.object(cb, "_read", side_effect=["prev", ""]),
            patch.object(cb, "write") as mock_write,
        ):
            assert cb.copy_selection() is None
            mock_write.assert_any_call("")  # cleared
            mock_write.assert_any_call("prev")  # restored

    def test_copy_selection_swallows_clear_and_restore_failures(self) -> None:
        """A failing wl-copy during clear/restore must not crash the hotkey."""
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch("subprocess.run"),
            patch.object(cb, "_read", side_effect=["prev", ""]),
            patch.object(cb, "write", side_effect=RuntimeError("wl-copy gone")),
        ):
            # No selection -> None; clear AND restore both raise, both swallowed.
            assert cb.copy_selection() is None

    def test_copy_selection_raises_when_wl_paste_missing(self) -> None:
        """ydotool copies but wl-paste read tool is missing -> raise."""
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch("subprocess.run"),
            patch.object(cb, "_read", side_effect=FileNotFoundError),
            patch.object(cb, "write"),
            pytest.raises(RuntimeError, match="wl-paste"),
        ):
            cb.copy_selection()

    def test_copy_selection_raises_when_wl_paste_errors(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "wl-paste")
        with (
            patch("subprocess.run"),
            patch.object(cb, "_read", side_effect=err),
            patch.object(cb, "write"),
            pytest.raises(RuntimeError, match="wl-paste"),
        ):
            cb.copy_selection()

    def test_copy_selection_raises_when_ydotool_missing(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch("subprocess.run", side_effect=FileNotFoundError),
            patch.object(cb, "_read", return_value="prev"),
            patch.object(cb, "write"),
            pytest.raises(RuntimeError),
        ):
            cb.copy_selection()

    def test_copy_selection_raises_on_ydotool_error(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "ydotool")
        with (
            patch("subprocess.run", side_effect=err),
            patch.object(cb, "_read", return_value="prev"),
            patch.object(cb, "write"),
            pytest.raises(RuntimeError),
        ):
            cb.copy_selection()

    def test_paste_result_uses_ydotool(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch.object(cb, "write") as mock_write,
            patch("subprocess.run") as mock_run,
        ):
            cb.paste_result("enhanced")
            mock_write.assert_called_once_with("enhanced")
            assert mock_run.call_args_list[0] == call(
                ["ydotool", "key", "29:1", "47:1", "47:0", "29:0"],
                check=True,
            )

    def test_paste_result_propagates_write_failure(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch.object(
                cb, "write", side_effect=RuntimeError("wl-copy not found")
            ),
            pytest.raises(RuntimeError),
        ):
            cb.paste_result("enhanced")

    def test_paste_result_degrades_when_ydotool_missing(self) -> None:
        """Text stays on the clipboard (write succeeded) -> no raise."""
        cb = WaylandClipboard(settle_ms=0)
        with (
            patch.object(cb, "write") as mock_write,
            patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            cb.paste_result("enhanced")  # must not raise
            mock_write.assert_called_once_with("enhanced")

    def test_paste_result_degrades_on_ydotool_error(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        err = subprocess.CalledProcessError(1, "ydotool")
        with (
            patch.object(cb, "write"),
            patch("subprocess.run", side_effect=err),
        ):
            cb.paste_result("enhanced")  # must not raise

    def test_read_strips_null_bytes(self) -> None:
        cb = WaylandClipboard(settle_ms=0)
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="hello\x00world", returncode=0
            )
            result = cb.read()
            assert result == "helloworld"


# ---------------------------------------------------------------------------
# WaylandNotify
# ---------------------------------------------------------------------------


class TestWaylandNotify:
    def test_implements_interface(self) -> None:
        assert issubclass(WaylandNotify, NotifyBackend)

    def test_send_calls_notify_send(self) -> None:
        n = WaylandNotify()
        with patch("subprocess.run") as mock_run:
            n.send("Title", "Body")
            mock_run.assert_called_once_with(
                ["notify-send", "Title", "Body"],
                check=False,
                timeout=5,
            )

    def test_send_truncates_long_body(self) -> None:
        n = WaylandNotify()
        long_body = "x" * 200
        with patch("subprocess.run") as mock_run:
            n.send("T", long_body)
            sent_body = mock_run.call_args[0][0][2]
            assert len(sent_body) <= 103
            assert sent_body.endswith("...")

    def test_send_degrades_when_binary_missing(self) -> None:
        n = WaylandNotify()
        with patch("subprocess.run", side_effect=FileNotFoundError):
            n.send("T", "B")  # must not raise

    def test_send_degrades_on_other_error(self) -> None:
        n = WaylandNotify()
        with patch("subprocess.run", side_effect=OSError("boom")):
            n.send("T", "B")  # must not raise


# ---------------------------------------------------------------------------
# WaylandActiveWindow
# ---------------------------------------------------------------------------


class TestWaylandActiveWindow:
    def test_implements_interface(self) -> None:
        assert issubclass(WaylandActiveWindow, ActiveWindowBackend)

    def test_defaults_desktop_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", "GNOME")
        aw = WaylandActiveWindow()
        assert aw._desktop == "GNOME"

    # -- GNOME ------------------------------------------------------------

    def test_gnome_detection_plain_json(self) -> None:
        aw = WaylandActiveWindow(desktop="GNOME")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout='{"success": true, "value": "firefox"}',
                returncode=0,
            )
            assert aw.get_frontmost_app() == "firefox"

    def test_gnome_detection_gdbus_tuple_format(self) -> None:
        aw = WaylandActiveWindow(desktop="GNOME")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="(true, 'firefox')",
                returncode=0,
            )
            assert aw.get_frontmost_app() == "firefox"

    def test_gnome_eval_disabled_returns_empty(self) -> None:
        """GNOME 41+ returns (false, '') when Shell.Eval is locked down."""
        aw = WaylandActiveWindow(desktop="GNOME")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="(false, '')", returncode=0)
            assert aw.get_frontmost_app() == ""

    def test_gnome_unparseable_output_returns_empty(self) -> None:
        aw = WaylandActiveWindow(desktop="GNOME")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="garbage!!", returncode=0)
            assert aw.get_frontmost_app() == ""

    def test_gnome_pop_and_ubuntu_route_to_gnome(self) -> None:
        for desktop in ("pop:GNOME", "ubuntu:GNOME"):
            aw = WaylandActiveWindow(desktop=desktop)
            with patch.object(
                aw, "_gnome_active_window", return_value="x"
            ) as g:
                aw.get_frontmost_app()
                g.assert_called_once()

    # -- KDE --------------------------------------------------------------

    def test_kde_detection(self) -> None:
        aw = WaylandActiveWindow(desktop="KDE")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout="  konsole \n", returncode=0
            )
            result = aw.get_frontmost_app()
            assert result == "konsole"
            assert mock_run.call_args[0][0][0] == "qdbus"

    def test_plasma_routes_to_kde(self) -> None:
        aw = WaylandActiveWindow(desktop="plasma")
        with patch.object(aw, "_kde_active_window", return_value="k") as k:
            aw.get_frontmost_app()
            k.assert_called_once()

    # -- sway -------------------------------------------------------------

    def test_sway_detection_top_level_focused(self) -> None:
        aw = WaylandActiveWindow(desktop="sway")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout='{"nodes":[{"focused":true,"app_id":"kitty"}]}',
                returncode=0,
            )
            assert aw.get_frontmost_app() == "kitty"

    def test_sway_detection_nested_focused_node(self) -> None:
        aw = WaylandActiveWindow(desktop="sway")
        tree = (
            '{"focused":false,"nodes":['
            '{"focused":false,"nodes":['
            '{"focused":true,"app_id":"firefox"}]}]}'
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=tree, returncode=0)
            assert aw.get_frontmost_app() == "firefox"

    def test_sway_focused_in_floating_node(self) -> None:
        aw = WaylandActiveWindow(desktop="sway")
        tree = (
            '{"focused":false,"nodes":[],"floating_nodes":['
            '{"focused":true,"app_id":"mpv"}]}'
        )
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=tree, returncode=0)
            assert aw.get_frontmost_app() == "mpv"

    def test_sway_falls_back_to_name_when_no_app_id(self) -> None:
        aw = WaylandActiveWindow(desktop="sway")
        tree = '{"focused":true,"name":"X-term"}'
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=tree, returncode=0)
            assert aw.get_frontmost_app() == "X-term"

    def test_sway_none_node_lists_do_not_crash(self) -> None:
        aw = WaylandActiveWindow(desktop="sway")
        # nodes/floating_nodes explicitly null
        tree = '{"focused":false,"nodes":null,"floating_nodes":null}'
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout=tree, returncode=0)
            assert aw.get_frontmost_app() == ""

    def test_sway_no_focused_node_returns_empty(self) -> None:
        aw = WaylandActiveWindow(desktop="sway")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                stdout='{"nodes":[{"focused":false,"app_id":"x"}]}',
                returncode=0,
            )
            assert aw.get_frontmost_app() == ""

    # -- misc -------------------------------------------------------------

    def test_unknown_desktop_returns_empty(self) -> None:
        aw = WaylandActiveWindow(desktop="i3")
        assert aw.get_frontmost_app() == ""

    def test_returns_empty_on_error(self) -> None:
        aw = WaylandActiveWindow(desktop="unknown")
        assert aw.get_frontmost_app() == ""

    def test_returns_empty_when_subprocess_fails(self) -> None:
        aw = WaylandActiveWindow(desktop="GNOME")
        with patch("subprocess.run", side_effect=Exception("dbus error")):
            assert aw.get_frontmost_app() == ""
