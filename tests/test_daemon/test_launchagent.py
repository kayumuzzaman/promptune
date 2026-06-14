"""Tests for promptune.daemon.launchagent."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="macOS-only"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _import_module():
    from promptune.daemon import launchagent
    return launchagent


# ---------------------------------------------------------------------------
# TestGeneratePlist
# ---------------------------------------------------------------------------

class TestGeneratePlist:
    def test_contains_label(self):
        la = _import_module()
        plist = la.generate_plist()
        assert "dev.promptune.daemon" in plist

    def test_contains_promptune_command(self):
        la = _import_module()
        plist = la.generate_plist()
        assert "promptune" in plist
        assert "daemon" in plist
        assert "start" in plist
        assert "--foreground" in plist

    def test_has_run_at_load(self):
        la = _import_module()
        plist = la.generate_plist()
        assert "RunAtLoad" in plist
        assert "<true/>" in plist

    def test_has_keep_alive(self):
        la = _import_module()
        plist = la.generate_plist()
        assert "KeepAlive" in plist

    def test_is_valid_xml(self):
        la = _import_module()
        plist = la.generate_plist()
        # Should not raise
        root = ET.fromstring(plist)
        assert root.tag == "plist"

    def test_contains_log_path(self):
        la = _import_module()
        plist = la.generate_plist()
        assert "StandardOutPath" in plist
        assert "StandardErrorPath" in plist

    def test_contains_process_type_background(self):
        la = _import_module()
        plist = la.generate_plist()
        assert "ProcessType" in plist
        assert "Background" in plist


# ---------------------------------------------------------------------------
# TestInstallUninstall
# ---------------------------------------------------------------------------

class TestInstallUninstall:
    def test_install_writes_plist_file(self, tmp_path):
        la = _import_module()
        plist_path = tmp_path / "dev.promptune.daemon.plist"

        with (
            patch.object(la, "PLIST_PATH", plist_path),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            la.install_login_item()

        assert plist_path.exists()
        content = plist_path.read_text(encoding="utf-8")
        assert "dev.promptune.daemon" in content

    def test_install_calls_launchctl_load(self, tmp_path):
        la = _import_module()
        plist_path = tmp_path / "dev.promptune.daemon.plist"

        with (
            patch.object(la, "PLIST_PATH", plist_path),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            la.install_login_item()

        mock_run.assert_called_once_with(
            ["launchctl", "load", str(plist_path)],
            check=True,
        )

    def test_uninstall_removes_plist_file(self, tmp_path):
        la = _import_module()
        plist_path = tmp_path / "dev.promptune.daemon.plist"
        plist_path.write_text("dummy", encoding="utf-8")

        with (
            patch.object(la, "PLIST_PATH", plist_path),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            la.uninstall_login_item()

        assert not plist_path.exists()

    def test_uninstall_calls_launchctl_unload(self, tmp_path):
        la = _import_module()
        plist_path = tmp_path / "dev.promptune.daemon.plist"
        plist_path.write_text("dummy", encoding="utf-8")

        with (
            patch.object(la, "PLIST_PATH", plist_path),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = MagicMock(returncode=0)
            la.uninstall_login_item()

        mock_run.assert_called_once_with(
            ["launchctl", "unload", str(plist_path)],
            check=False,
        )

    def test_uninstall_nonexistent_is_noop(self, tmp_path):
        la = _import_module()
        plist_path = tmp_path / "dev.promptune.daemon.plist"
        # File does not exist

        with (
            patch.object(la, "PLIST_PATH", plist_path),
            patch("subprocess.run") as mock_run,
        ):
            la.uninstall_login_item()  # Should not raise

        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# TestIsInstalled
# ---------------------------------------------------------------------------

class TestIsInstalled:
    def test_returns_true_when_file_exists(self, tmp_path):
        la = _import_module()
        plist_path = tmp_path / "dev.promptune.daemon.plist"
        plist_path.write_text("dummy", encoding="utf-8")

        with patch.object(la, "PLIST_PATH", plist_path):
            assert la.is_installed() is True

    def test_returns_false_when_file_absent(self, tmp_path):
        la = _import_module()
        plist_path = tmp_path / "dev.promptune.daemon.plist"
        # File does not exist

        with patch.object(la, "PLIST_PATH", plist_path):
            assert la.is_installed() is False
