"""macOS LaunchAgent management for the Promptune daemon.

Installs/uninstalls a Login Item plist so the daemon runs automatically
at login via launchd.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLIST_PATH: Path = (
    Path.home() / "Library" / "LaunchAgents" / "dev.promptune.daemon.plist"
)
LOG_FILE: Path = Path.home() / ".local" / "share" / "promptune" / "daemon.log"
LABEL: str = "dev.promptune.daemon"


# ---------------------------------------------------------------------------
# Plist generation
# ---------------------------------------------------------------------------

def generate_plist() -> str:
    """Return an XML plist string for the Promptune LaunchAgent.

    The generated plist configures launchd to:
    - Run the promptune daemon at login (RunAtLoad)
    - Keep it alive if it exits (KeepAlive)
    - Redirect stdout/stderr to LOG_FILE
    - Classify the process as Background
    """
    # XML-escape interpolated paths so a path containing &, <, or > can't
    # produce a malformed plist that launchctl refuses to load.
    log = escape(str(LOG_FILE))
    executable = escape(sys.executable)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{executable}</string>
        <string>-m</string>
        <string>promptune</string>
        <string>daemon</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
    <key>ProcessType</key>
    <string>Background</string>
</dict>
</plist>
"""


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------

def install_login_item() -> None:
    """Write the LaunchAgent plist and load it with launchctl.

    Creates the LaunchAgents directory if it does not exist.
    """
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(generate_plist(), encoding="utf-8")
    subprocess.run(
        ["launchctl", "load", str(PLIST_PATH)],
        check=True,
    )


def uninstall_login_item() -> None:
    """Unload the LaunchAgent and remove the plist file.

    A no-op if the plist file does not exist.
    """
    if not PLIST_PATH.exists():
        return
    subprocess.run(
        ["launchctl", "unload", str(PLIST_PATH)],
        check=False,
    )
    PLIST_PATH.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def is_installed() -> bool:
    """Return True if the LaunchAgent plist file exists."""
    return PLIST_PATH.exists()
