"""macOS notification helper — sends system notifications via osascript."""

from __future__ import annotations

import subprocess


def _escape(text: str) -> str:
    """Escape backslashes and double-quotes for AppleScript strings."""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def notify(title: str, message: str, sound: bool = True) -> None:
    """Show a macOS notification via osascript.

    Args:
        title:   Notification title.
        message: Notification body text.
        sound:   When True, play the 'Tink' system sound.
    """
    safe_title = _escape(title)
    safe_message = _escape(message)

    script = f'display notification "{safe_message}" with title "{safe_title}"'
    if sound:
        script += ' sound name "Tink"'

    subprocess.run(
        ["osascript", "-e", script],
        timeout=5,
        check=False,
    )


def notify_enhanced(score_before: int, score_after: int) -> None:
    """Notify the user that a prompt was enhanced.

    Shows the PQS delta and a reminder that Cmd+Z reverts the change.

    Args:
        score_before: PQS before enhancement.
        score_after:  PQS after enhancement.
    """
    delta = score_after - score_before
    sign = "+" if delta >= 0 else ""
    message = f"Prompt enhanced ({sign}{delta} PQS). Cmd+Z to undo."
    notify("Promptune", message, sound=True)


def notify_error(message: str) -> None:
    """Notify the user that an error occurred (no sound).

    Args:
        message: Human-readable error description.
    """
    notify("Promptune", message, sound=False)
