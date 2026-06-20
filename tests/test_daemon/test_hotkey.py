"""Tests for promptune.daemon.hotkey — macOS global hotkey module."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

if sys.platform != "darwin":
    pytest.skip("macOS-only", allow_module_level=True)

from promptune.daemon.hotkey import (  # noqa: E402
    DEFAULT_HOTKEY_KEYCODE,
    KEYCODE_MAP,
    parse_hotkey,
)

# ---------------------------------------------------------------------------
# TestParseHotkey — pure logic, no pyobjc mocking needed
# ---------------------------------------------------------------------------


class TestParseHotkey:
    def test_ctrl_shift_e(self):
        keycode, mask = parse_hotkey("ctrl+shift+e")
        assert keycode == KEYCODE_MAP["e"]

    def test_single_modifier(self):
        keycode, mask = parse_hotkey("cmd+a")
        assert keycode == KEYCODE_MAP["a"]

    def test_unknown_key_raises(self):
        with pytest.raises(ValueError, match="Unknown key"):
            parse_hotkey("ctrl+shift+9")

    def test_unknown_modifier_raises(self):
        with pytest.raises(ValueError, match="Unknown"):
            parse_hotkey("win+e")

    def test_case_insensitive(self):
        kc1, m1 = parse_hotkey("ctrl+e")
        kc2, m2 = parse_hotkey("CTRL+E")
        assert kc1 == kc2
        assert m1 == m2

    def test_all_letter_keys_exist(self):
        for letter in "abcdefghijklmnopqrstuvwxyz":
            kc, _ = parse_hotkey(f"ctrl+{letter}")
            assert kc == KEYCODE_MAP[letter]

    def test_space_key(self):
        keycode, _ = parse_hotkey("ctrl+space")
        assert keycode == KEYCODE_MAP["space"]

    def test_default_hotkey_keycode(self):
        assert KEYCODE_MAP["e"] == DEFAULT_HOTKEY_KEYCODE


# ---------------------------------------------------------------------------
# TestAccessibility — mock ApplicationServices at attribute level
# ---------------------------------------------------------------------------


class TestAccessibility:
    @patch("promptune.daemon.hotkey.ApplicationServices")
    def test_check_granted(self, mock_as):
        from promptune.daemon.hotkey import check_accessibility

        mock_as.AXIsProcessTrustedWithOptions.return_value = True
        assert check_accessibility() is True

    @patch("promptune.daemon.hotkey.ApplicationServices")
    def test_check_denied(self, mock_as):
        from promptune.daemon.hotkey import check_accessibility

        mock_as.AXIsProcessTrustedWithOptions.return_value = False
        assert check_accessibility() is False

    @patch("promptune.daemon.hotkey.ApplicationServices")
    def test_request_prompts(self, mock_as):
        from promptune.daemon.hotkey import request_accessibility

        mock_as.kAXTrustedCheckOptionPrompt = "AXTrustedCheckOptionPrompt"
        mock_as.AXIsProcessTrustedWithOptions.return_value = False
        result = request_accessibility()
        assert result is False
        call_args = mock_as.AXIsProcessTrustedWithOptions.call_args[0][0]
        assert call_args["AXTrustedCheckOptionPrompt"] is True

    @patch("promptune.daemon.hotkey.ApplicationServices")
    def test_request_returns_true_when_trusted(self, mock_as):
        from promptune.daemon.hotkey import request_accessibility

        mock_as.kAXTrustedCheckOptionPrompt = "AXTrustedCheckOptionPrompt"
        mock_as.AXIsProcessTrustedWithOptions.return_value = True
        assert request_accessibility() is True


# ---------------------------------------------------------------------------
# TestSecureInput — mock Quartz at attribute level
# ---------------------------------------------------------------------------


class TestSecureInput:
    @patch("promptune.daemon.hotkey.Quartz")
    def test_active(self, mock_q):
        from promptune.daemon.hotkey import is_secure_input_active

        mock_q.CGSIsSecureEventInputSet.return_value = True
        assert is_secure_input_active() is True

    @patch("promptune.daemon.hotkey.Quartz")
    def test_inactive(self, mock_q):
        from promptune.daemon.hotkey import is_secure_input_active

        mock_q.CGSIsSecureEventInputSet.return_value = False
        assert is_secure_input_active() is False


# ---------------------------------------------------------------------------
# TestRegisterHotkey — mock Quartz at attribute level
# ---------------------------------------------------------------------------


class TestRegisterHotkey:
    @patch("promptune.daemon.hotkey.Quartz")
    def test_raises_on_none_tap(self, mock_q):
        from promptune.daemon.hotkey import register_hotkey

        mock_q.CGEventTapCreate.return_value = None
        with pytest.raises(PermissionError, match="CGEventTap"):
            register_hotkey(lambda: None, 14, 0x0001)

    @patch("promptune.daemon.hotkey.Quartz")
    def test_success_returns_tap(self, mock_q):
        from promptune.daemon.hotkey import register_hotkey

        fake_tap = MagicMock(name="fake_tap")
        mock_q.CGEventTapCreate.return_value = fake_tap
        tap = register_hotkey(lambda: None, 14, 0x0001)
        assert tap is fake_tap


# -----------------------------------------------------------
# TestImportGuard — line 13
# -----------------------------------------------------------


class TestImportGuard:
    def test_non_darwin_raises_import_error(self):
        """Importing hotkey on non-darwin raises."""
        import importlib

        import promptune.daemon.hotkey as mod

        with (
            patch.object(sys, "platform", "linux"),
            pytest.raises(ImportError, match="macOS"),
        ):
            importlib.reload(mod)
        # Reload again so module is usable for later tests
        importlib.reload(mod)


# -----------------------------------------------------------
# TestParseHotkeyNoKey — line 86
# -----------------------------------------------------------


class TestParseHotkeyNoKey:
    def test_only_modifiers_raises(self):
        """Hotkey with no key part raises ValueError."""
        with pytest.raises(
            ValueError, match="No valid key found"
        ):
            parse_hotkey("ctrl+shift")

    def test_single_modifier_no_key(self):
        with pytest.raises(
            ValueError, match="No valid key found"
        ):
            parse_hotkey("alt")


# -----------------------------------------------------------
# TestEventCallback — lines 148-162
# -----------------------------------------------------------


class TestEventCallback:
    @patch("promptune.daemon.hotkey.Quartz")
    def test_matching_hotkey_fires_callback(self, mock_q):
        from promptune.daemon.hotkey import _event_callback

        mock_q.kCGEventKeyDown = 10
        mock_q.kCGEventFlagMaskControl = 0x40000
        mock_q.kCGEventFlagMaskShift = 0x20000
        mock_q.kCGEventFlagMaskAlternate = 0x80000
        mock_q.kCGEventFlagMaskCommand = 0x100000
        mock_q.kCGKeyboardEventKeycode = 9
        mock_q.kCGKeyboardEventAutorepeat = 8

        keycode = 14
        modifier_mask = 0x40000 | 0x20000  # ctrl+shift

        def _field(_ev, field):
            return 0 if field == 8 else keycode

        mock_q.CGEventGetIntegerValueField.side_effect = _field
        mock_q.CGEventGetFlags.return_value = modifier_mask

        fired = []
        handler = _event_callback(
            lambda: fired.append(True),
            keycode,
            modifier_mask,
        )
        event = MagicMock()
        result = handler(None, 10, event, None)
        assert fired == [True]
        assert result is event

    @patch("promptune.daemon.hotkey.Quartz")
    def test_non_matching_key_skips(self, mock_q):
        from promptune.daemon.hotkey import _event_callback

        mock_q.kCGEventKeyDown = 10
        mock_q.kCGEventFlagMaskControl = 0x40000
        mock_q.kCGEventFlagMaskShift = 0x20000
        mock_q.kCGEventFlagMaskAlternate = 0x80000
        mock_q.kCGEventFlagMaskCommand = 0x100000
        mock_q.kCGKeyboardEventKeycode = 9
        mock_q.kCGKeyboardEventAutorepeat = 8

        def _field(_ev, field):
            return 0 if field == 8 else 99

        mock_q.CGEventGetIntegerValueField.side_effect = _field
        mock_q.CGEventGetFlags.return_value = 0x40000

        fired = []
        handler = _event_callback(
            lambda: fired.append(True), 14, 0x40000
        )
        event = MagicMock()
        result = handler(None, 10, event, None)
        assert fired == []
        assert result is event

    @patch("promptune.daemon.hotkey.Quartz")
    def test_autorepeat_event_skips(self, mock_q):
        """OS key-repeat events must not fire the callback."""
        from promptune.daemon.hotkey import _event_callback

        mock_q.kCGEventKeyDown = 10
        mock_q.kCGEventFlagMaskControl = 0x40000
        mock_q.kCGEventFlagMaskShift = 0x20000
        mock_q.kCGEventFlagMaskAlternate = 0x80000
        mock_q.kCGEventFlagMaskCommand = 0x100000
        mock_q.kCGKeyboardEventKeycode = 9
        mock_q.kCGKeyboardEventAutorepeat = 8

        keycode = 14
        modifier_mask = 0x40000 | 0x20000

        def _field(_ev, field):
            # Autorepeat field is set (held key); keycode would otherwise match.
            return 1 if field == 8 else keycode

        mock_q.CGEventGetIntegerValueField.side_effect = _field
        mock_q.CGEventGetFlags.return_value = modifier_mask

        fired = []
        handler = _event_callback(
            lambda: fired.append(True), keycode, modifier_mask
        )
        event = MagicMock()
        result = handler(None, 10, event, None)
        assert fired == []
        assert result is event

    @patch("promptune.daemon.hotkey.Quartz")
    def test_wrong_event_type_skips(self, mock_q):
        from promptune.daemon.hotkey import _event_callback

        mock_q.kCGEventKeyDown = 10

        fired = []
        handler = _event_callback(
            lambda: fired.append(True), 14, 0x40000
        )
        event = MagicMock()
        result = handler(None, 99, event, None)
        assert fired == []
        assert result is event

    @patch("promptune.daemon.hotkey.Quartz")
    def test_disabled_event_tap_is_reenabled(self, mock_q):
        import promptune.daemon.hotkey as mod

        mock_q.kCGEventKeyDown = 10
        mock_q.kCGEventTapDisabledByTimeout = 99
        mock_q.kCGEventTapDisabledByUserInput = 100
        fake_tap = MagicMock(name="tap")
        old = mod._event_tap_ref
        try:
            mod._event_tap_ref = fake_tap
            handler = mod._event_callback(lambda: None, 14, 0x40000)
            event = MagicMock()

            result = handler(None, 99, event, None)

            assert result is event
            mock_q.CGEventTapEnable.assert_called_once_with(
                fake_tap, True
            )
        finally:
            mod._event_tap_ref = old


# -----------------------------------------------------------
# TestStartRunLoop — lines 221-234
# -----------------------------------------------------------


class TestStartRunLoop:
    @patch("promptune.daemon.hotkey.Quartz")
    def test_no_tap_raises(self, mock_q):
        import promptune.daemon.hotkey as mod

        old = mod._event_tap_ref
        try:
            mod._event_tap_ref = None
            with pytest.raises(
                RuntimeError, match="No event tap"
            ):
                mod.start_run_loop()
        finally:
            mod._event_tap_ref = old

    @patch("promptune.daemon.hotkey.Quartz")
    def test_starts_run_loop(self, mock_q):
        import promptune.daemon.hotkey as mod

        fake_tap = MagicMock(name="tap")
        fake_src = MagicMock(name="src")
        fake_loop = MagicMock(name="loop")

        mock_q.CFMachPortCreateRunLoopSource.return_value = (
            fake_src
        )
        mock_q.CFRunLoopGetCurrent.return_value = fake_loop
        mock_q.CFRunLoopRun.return_value = None

        old = mod._event_tap_ref
        try:
            mod._event_tap_ref = fake_tap
            mod.start_run_loop()

            mock_q.CFMachPortCreateRunLoopSource.assert_called_once_with(
                None, fake_tap, 0
            )
            mock_q.CFRunLoopAddSource.assert_called_once_with(
                fake_loop,
                fake_src,
                mock_q.kCFRunLoopCommonModes,
            )
            mock_q.CGEventTapEnable.assert_called_once_with(
                fake_tap, True
            )
            mock_q.CFRunLoopRun.assert_called_once()
            assert mod._run_loop_ref is fake_loop
        finally:
            mod._event_tap_ref = old
            mod._run_loop_ref = None


# -----------------------------------------------------------
# TestStopRunLoop — lines 241-243
# -----------------------------------------------------------


class TestStopRunLoop:
    @patch("promptune.daemon.hotkey.Quartz")
    def test_stops_when_ref_set(self, mock_q):
        import promptune.daemon.hotkey as mod

        fake_loop = MagicMock(name="loop")
        old = mod._run_loop_ref
        try:
            mod._run_loop_ref = fake_loop
            mod.stop_run_loop()

            mock_q.CFRunLoopStop.assert_called_once_with(
                fake_loop
            )
            assert mod._run_loop_ref is None
        finally:
            mod._run_loop_ref = old

    @patch("promptune.daemon.hotkey.Quartz")
    def test_noop_when_ref_none(self, mock_q):
        import promptune.daemon.hotkey as mod

        old = mod._run_loop_ref
        try:
            mod._run_loop_ref = None
            mod.stop_run_loop()
            mock_q.CFRunLoopStop.assert_not_called()
        finally:
            mod._run_loop_ref = old


# -----------------------------------------------------------
# TestCheckAccessibility — lines 241-243 alias coverage
# -----------------------------------------------------------


class TestCheckAccessibilityReturn:
    @patch("promptune.daemon.hotkey.ApplicationServices")
    def test_returns_bool_true(self, mock_as):
        from promptune.daemon.hotkey import check_accessibility

        mock_as.AXIsProcessTrustedWithOptions.return_value = 1
        assert check_accessibility() is True

    @patch("promptune.daemon.hotkey.ApplicationServices")
    def test_returns_bool_false(self, mock_as):
        from promptune.daemon.hotkey import check_accessibility

        mock_as.AXIsProcessTrustedWithOptions.return_value = 0
        assert check_accessibility() is False
