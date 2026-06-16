"""Linux service management and dependency checking.

Primary: systemd user service.
Fallback: direct PID-file process management.
"""

from __future__ import annotations

import contextlib
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

from promptune.daemon.platform.base import (
    DependencyChecker,
    DependencyStatus,
    ServiceBackend,
)

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_DEFAULT_SERVICE_PATH = Path(
    "~/.config/systemd/user/promptune.service"
).expanduser()

_DEFAULT_DATA_DIR = Path(
    "~/.local/share/promptune"
).expanduser()

# ---------------------------------------------------------------------------
# Service template
# ---------------------------------------------------------------------------

SERVICE_TEMPLATE = """\
[Unit]
Description=Promptune Prompt Enhancement Daemon
After=graphical-session.target
StartLimitIntervalSec=60
StartLimitBurst=3

[Service]
Type=simple
ExecStart={exec_start}
Restart=on-failure
RestartSec=5
MemoryMax=256M
EnvironmentFile=-{env_file}

[Install]
WantedBy=default.target
"""


# ---------------------------------------------------------------------------
# Package manager detection
# ---------------------------------------------------------------------------


def _detect_package_manager() -> str:
    """Detect the system package manager."""
    for pm in ("apt", "dnf", "pacman", "zypper"):
        if shutil.which(pm):
            return pm
    return ""


# ---------------------------------------------------------------------------
# Service backend
# ---------------------------------------------------------------------------


class LinuxService(ServiceBackend):
    """Linux systemd user service management."""

    def __init__(
        self,
        service_path: Path | None = None,
        data_dir: Path | None = None,
    ) -> None:
        self._service_path = service_path or _DEFAULT_SERVICE_PATH
        self._data_dir = data_dir or _DEFAULT_DATA_DIR

    def install(self) -> None:
        """Write systemd service file, daemon-reload, and enable."""
        self._service_path.parent.mkdir(parents=True, exist_ok=True)

        exec_start = f"{sys.executable} -m promptune daemon start --foreground"
        env_file = Path("~/.config/promptune/daemon.env").expanduser()

        content = SERVICE_TEMPLATE.format(
            exec_start=exec_start,
            env_file=str(env_file),
        )
        self._service_path.write_text(content, encoding="utf-8")

        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=True,
        )
        subprocess.run(
            ["systemctl", "--user", "enable", "promptune"],
            check=True,
        )

    def uninstall(self) -> None:
        """Disable service and remove service file."""
        if not self._service_path.exists():
            return

        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "promptune"],
            check=False,
        )
        self._service_path.unlink(missing_ok=True)
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=False,
        )

    def purge(self) -> None:
        """Remove all daemon files — service, socket, PID, undo, logs."""
        self.uninstall()

        files_to_remove = [
            self._data_dir / "promptune.sock",
            self._data_dir / "daemon.pid",
            self._data_dir / "undo.txt",
            self._data_dir / "daemon.log",
        ]
        for f in files_to_remove:
            with contextlib.suppress(FileNotFoundError):
                f.unlink()

    def is_installed(self) -> bool:
        """Return True if the service file exists."""
        return self._service_path.exists()


# ---------------------------------------------------------------------------
# Dependency checker
# ---------------------------------------------------------------------------


class LinuxDependencyChecker(DependencyChecker):
    """Check for required system tools based on display server type."""

    def __init__(self, session_type: str = "") -> None:
        self._session_type = session_type or os.environ.get(
            "XDG_SESSION_TYPE", "x11"
        )

    def check(self) -> list[DependencyStatus]:
        """Check all required system dependencies."""
        deps: list[DependencyStatus] = []

        if self._session_type == "x11":
            deps.append(self._check_tool("xclip", required=True))
            deps.append(self._check_tool("xdotool", required=True))
        else:
            deps.append(self._check_tool("wl-paste", required=True))
            deps.append(self._check_tool("wl-copy", required=True))
            deps.append(self._check_tool("ydotool", required=True))

        deps.append(self._check_tool("notify-send", required=False))
        return deps

    def _check_tool(self, name: str, required: bool) -> DependencyStatus:
        """Check if a single tool is available on PATH."""
        return DependencyStatus(
            name=name,
            installed=shutil.which(name) is not None,
            required=required,
        )

    def get_install_command(self, missing: list[str]) -> str:
        """Return the install command for the detected package manager."""
        pm = _detect_package_manager()
        pkg_list = " ".join(missing)

        pm_commands = {
            "apt": f"sudo apt install {pkg_list}",
            "dnf": f"sudo dnf install {pkg_list}",
            "pacman": f"sudo pacman -S {pkg_list}",
            "zypper": f"sudo zypper install {pkg_list}",
        }
        return pm_commands.get(pm, f"Install manually: {pkg_list}")
