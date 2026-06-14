"""Auto-enhance gate: score -> enhance if needed -> clipboard -> exit code.

Used as a hook command by AI tools (Claude Code, etc.).
Reads a JSON payload from stdin: {"prompt": "..."}.
Exits 0 to allow, 1 to block (showing enhanced version).
"""

from __future__ import annotations

import subprocess
import sys
from typing import Any

from promptune.engine import EnhanceResult, enhance
from promptune.scorer import ScoreResult, score_prompt


def copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard using platform-appropriate tool."""
    if sys.platform == "darwin":
        subprocess.run(
            ["pbcopy"], input=text, text=True, check=True
        )
    else:
        try:
            subprocess.run(
                ["wl-copy"], input=text, text=True, check=True
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            try:
                subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    input=text,
                    text=True,
                    check=True,
                )
            except (FileNotFoundError, subprocess.CalledProcessError):
                print(
                    "Warning: No clipboard tool found"
                    " (install xclip or wl-copy).",
                    file=sys.stderr,
                )


def _print_gate_block(
    original: str,
    result: EnhanceResult,
    score_before: ScoreResult,
) -> None:
    """Print the auto-enhance block to stderr."""
    width = 48
    border = "\u2500" * width
    print(
        f"\n\u250c\u2500 Auto-enhance {border[:width - 16]}\u2510",
        file=sys.stderr,
    )
    print("\u2502", file=sys.stderr)
    print(
        f"\u2502  Your prompt scored {score_before.total}/100.",
        file=sys.stderr,
    )
    print(
        "\u2502  Enhanced version (copied to clipboard):",
        file=sys.stderr,
    )
    print("\u2502", file=sys.stderr)
    for line in result.enhanced.splitlines():
        chunk = line[: width - 4]
        print(f"\u2502  {chunk}", file=sys.stderr)
    print("\u2502", file=sys.stderr)
    print(
        f"\u2502  Score: {score_before.total}"
        f" \u2192 {result.score_after.total}",
        file=sys.stderr,
    )
    print("\u2502", file=sys.stderr)
    print(
        "\u2502  [Paste] to use \u00b7 [Retype] to use original",
        file=sys.stderr,
    )
    bottom_border = "\u2500" * (width + 2)
    print(
        f"\u2514{bottom_border}\u2518\n",
        file=sys.stderr,
    )


def run_gate(prompt: str, config: dict[str, Any]) -> int:
    """Score prompt and enhance if below threshold.

    Returns 0 (allow) or 1 (block with enhanced copy on clipboard).
    """
    auto_cfg = config.get("auto_enhance", {})

    if not auto_cfg.get("enabled", True):
        return 0

    bypass = auto_cfg.get("bypass_prefix", "!")
    if bypass and prompt.startswith(bypass):
        return 0

    words = prompt.split()
    if len(words) < auto_cfg.get("min_words", 5):
        return 0

    threshold = auto_cfg.get("threshold", 60)
    score_before = score_prompt(prompt)

    if score_before.total >= threshold:
        return 0

    result = enhance(prompt, config)
    copy_to_clipboard(result.enhanced)
    _print_gate_block(prompt, result, score_before)
    return 1
