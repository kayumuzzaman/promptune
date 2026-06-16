"""Tests for Linux service management backend.

All tests in this file use a tmp_path fixture for the service file and mock
subprocess.run for systemctl calls — safe to run on macOS.

TODO(linux-ci): On a real Linux machine with systemd, add integration tests in
  tests/test_daemon/test_platform/test_linux_service_integration.py that:
  - Requires: systemd user session (systemctl --user) running
  - Mark each test with @pytest.mark.linux
  - Verify: systemctl --user status promptune.service reflects real state
  - Run with:
    pytest -m linux tests/test_daemon/test_platform/test_linux_service_integration.py
  See docs/MANUAL_TESTING.md §28.4 for the full manual checklist.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from promptune.daemon.platform.base import (
    DependencyChecker,
    ServiceBackend,
)
from promptune.daemon.platform.linux_service import (
    SERVICE_TEMPLATE,
    LinuxDependencyChecker,
    LinuxService,
    _detect_package_manager,
)


class TestLinuxService:
    def test_implements_interface(self) -> None:
        assert issubclass(LinuxService, ServiceBackend)

    def test_install_writes_service_file(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "promptune.service"
        svc = LinuxService(service_path=svc_file)
        with patch("subprocess.run") as mock_run:
            svc.install()
            assert svc_file.exists()
            content = svc_file.read_text()
            assert "promptune" in content
            assert "ExecStart" in content
            assert mock_run.call_count == 2

    def test_uninstall_removes_service(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "promptune.service"
        svc_file.write_text("dummy")
        svc = LinuxService(service_path=svc_file)
        with patch("subprocess.run"):
            svc.uninstall()
            assert not svc_file.exists()

    def test_uninstall_no_op_when_missing(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "nonexistent.service"
        svc = LinuxService(service_path=svc_file)
        with patch("subprocess.run"):
            svc.uninstall()

    def test_is_installed_true(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "promptune.service"
        svc_file.write_text("dummy")
        svc = LinuxService(service_path=svc_file)
        assert svc.is_installed() is True

    def test_is_installed_false(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "nonexistent.service"
        svc = LinuxService(service_path=svc_file)
        assert svc.is_installed() is False

    def test_purge_removes_all_files(self, tmp_path: Path) -> None:
        svc_file = tmp_path / "promptune.service"
        socket_file = tmp_path / "promptune.sock"
        pid_file = tmp_path / "daemon.pid"
        undo_file = tmp_path / "undo.txt"
        log_file = tmp_path / "daemon.log"
        svc_file.write_text("svc")
        socket_file.write_text("sock")
        pid_file.write_text("123")
        undo_file.write_text("{}")
        log_file.write_text("log")

        svc = LinuxService(
            service_path=svc_file,
            data_dir=tmp_path,
        )
        with patch("subprocess.run"):
            svc.purge()

        assert not svc_file.exists()
        assert not socket_file.exists()
        assert not pid_file.exists()
        assert not undo_file.exists()
        assert not log_file.exists()

    def test_service_template_valid(self) -> None:
        assert "[Unit]" in SERVICE_TEMPLATE
        assert "[Service]" in SERVICE_TEMPLATE
        assert "[Install]" in SERVICE_TEMPLATE
        assert "promptune" in SERVICE_TEMPLATE.lower()

    def test_start_limit_directives_in_unit_section(self) -> None:
        unit, _, rest = SERVICE_TEMPLATE.partition("[Service]")
        assert "StartLimitBurst" in unit
        assert "StartLimitIntervalSec" in unit
        assert "StartLimit" not in rest


class TestDetectPackageManager:
    def test_apt(self) -> None:
        def _which(cmd: str) -> str | None:
            return "/usr/bin/apt" if cmd == "apt" else None

        with patch("shutil.which", side_effect=_which):
            assert _detect_package_manager() == "apt"

    def test_dnf(self) -> None:
        def which(cmd: str) -> str | None:
            return "/usr/bin/dnf" if cmd == "dnf" else None
        with patch("shutil.which", side_effect=which):
            assert _detect_package_manager() == "dnf"

    def test_pacman(self) -> None:
        def which(cmd: str) -> str | None:
            return "/usr/bin/pacman" if cmd == "pacman" else None
        with patch("shutil.which", side_effect=which):
            assert _detect_package_manager() == "pacman"

    def test_unknown(self) -> None:
        with patch("shutil.which", return_value=None):
            assert _detect_package_manager() == ""


class TestLinuxDependencyChecker:
    def test_implements_interface(self) -> None:
        assert issubclass(LinuxDependencyChecker, DependencyChecker)

    def test_x11_checks_xclip_xdotool(self) -> None:
        checker = LinuxDependencyChecker(session_type="x11")
        with patch("shutil.which") as mock_which:
            mock_which.side_effect = (
                lambda cmd: f"/usr/bin/{cmd}"
                if cmd in ("xclip", "xdotool")
                else None
            )
            results = checker.check()
            names = [r.name for r in results]
            assert "xclip" in names
            assert "xdotool" in names
            xclip = next(r for r in results if r.name == "xclip")
            assert xclip.installed is True
            assert xclip.required is True

    def test_wayland_checks_wl_tools(self) -> None:
        checker = LinuxDependencyChecker(session_type="wayland")
        with patch("shutil.which") as mock_which:
            mock_which.return_value = None
            results = checker.check()
            names = [r.name for r in results]
            assert "wl-paste" in names
            assert "ydotool" in names
            wl = next(r for r in results if r.name == "wl-paste")
            assert wl.installed is False
            assert wl.required is True

    def test_get_install_command_apt(self) -> None:
        checker = LinuxDependencyChecker(session_type="x11")
        with patch(
            "promptune.daemon.platform.linux_service._detect_package_manager",
            return_value="apt",
        ):
            cmd = checker.get_install_command(["xclip", "xdotool"])
            assert cmd == "sudo apt install xclip xdotool"

    def test_get_install_command_pacman(self) -> None:
        checker = LinuxDependencyChecker(session_type="x11")
        with patch(
            "promptune.daemon.platform.linux_service._detect_package_manager",
            return_value="pacman",
        ):
            cmd = checker.get_install_command(["xclip"])
            assert cmd == "sudo pacman -S xclip"

    def test_get_install_command_unknown(self) -> None:
        checker = LinuxDependencyChecker(session_type="x11")
        with patch(
            "promptune.daemon.platform.linux_service._detect_package_manager",
            return_value="",
        ):
            cmd = checker.get_install_command(["xclip"])
            assert "xclip" in cmd
